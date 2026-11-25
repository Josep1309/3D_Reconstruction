"""Verifica que este computador tenga todo lo necesario para el sistema de reconstrucción 3D.

Uso:
    .env/bin/python verificar.py                 # todo, incluido el hardware conectado
    .env/bin/python verificar.py --sin-hardware  # solo software, patrones, calibración y datos

Cada problema indica qué hacer y en qué sección de MANUAL.md hay más detalle.
Código de salida: 0 si no hay errores (✖), 1 si los hay. Las advertencias (⚠) no impiden usar el
sistema: por ejemplo, sin PySpin no se puede capturar, pero sí procesar y ver resultados.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

USA_COLOR = sys.stdout.isatty()
SIMBOLOS = {"ok": ("✔", "32"), "aviso": ("⚠", "33"), "error": ("✖", "31"), "info": ("·", "0")}
resumen = {"ok": 0, "aviso": 0, "error": 0}
resultados: list[dict] = []   # para --json (la pestaña Sistema de la interfaz)
_grupo = ""


def informar(nivel: str, texto: str, solucion: str = "", seccion: str = "") -> None:
    simbolo, color = SIMBOLOS[nivel]
    if nivel in resumen:
        resumen[nivel] += 1
    resultados.append({"grupo": _grupo, "nivel": nivel, "texto": texto, "solucion": solucion, "seccion": seccion})
    marca = f"\033[{color}m{simbolo}\033[0m" if USA_COLOR else simbolo
    print(f"  {marca} {texto}")
    if solucion:
        print(f"      → {solucion}")
    if seccion:
        print(f"      → Ver MANUAL.md {seccion}")


def titulo(texto: str) -> None:
    global _grupo
    _grupo = texto
    print(f"\n{texto}")


# ==============================================================================
# Comprobaciones
# ==============================================================================


def verificar_python() -> None:
    titulo("Python")
    v = sys.version_info
    texto = f"Python {v.major}.{v.minor}.{v.micro} en {sys.executable}"
    if (v.major, v.minor) == (3, 10):
        informar("ok", texto)
    elif v >= (3, 9):
        informar("aviso", texto + " (el wheel de PySpin instalado en el equipo original es para 3.10)",
                 "Para capturar, descarga el wheel de PySpin que corresponda a esta versión de Python.", "§20.3")
    else:
        informar("error", texto, "Se necesita Python 3.9 o superior (recomendado 3.10).", "§20.1")
    if sys.prefix == sys.base_prefix:
        informar("aviso", "No se está usando un entorno virtual",
                 "Ejecuta con .env/bin/python (lo crea ./instalar.sh).", "§20.2")


def _versiones_requeridas() -> dict[str, str]:
    requeridas = {}
    ruta = RAIZ / "requirements.txt"
    if ruta.exists():
        for linea in ruta.read_text().splitlines():
            linea = linea.split("#")[0].strip()
            if "==" in linea:
                nombre, version = linea.split("==")
                requeridas[nombre.strip().lower()] = version.strip()
    return requeridas


def verificar_paquetes() -> bool:
    titulo("Paquetes de Python (requirements.txt)")
    requeridas = _versiones_requeridas()
    todo_bien = True
    for modulo, paquete in (("numpy", "numpy"), ("cv2", "opencv-python"), ("matplotlib", "matplotlib")):
        try:
            mod = importlib.import_module(modulo)
        except Exception as exc:  # noqa: BLE001
            informar("error", f"{paquete}: no se puede importar ({exc})",
                     "Ejecuta ./instalar.sh  (o .env/bin/pip install -r requirements.txt)", "§20.2")
            todo_bien = False
            continue
        version = getattr(mod, "__version__", "?")
        esperada = requeridas.get(paquete)
        if esperada and not version.startswith(esperada.rsplit(".", 1)[0] if paquete == "opencv-python" else esperada):
            informar("aviso", f"{paquete} {version} (probado con {esperada})",
                     "Suele funcionar igual; si algo falla, instala la versión probada.", "§20.2")
        else:
            informar("ok", f"{paquete} {version}")
    return todo_bien


def verificar_camara(con_hardware: bool) -> tuple[int, int] | None:
    titulo("Cámara FLIR (PySpin / Spinnaker)")
    try:
        import PySpin  # noqa: N813
    except Exception as exc:  # noqa: BLE001
        informar("aviso", f"PySpin no está instalado ({type(exc).__name__}). Solo hace falta para capturar.",
                 "Instala el Spinnaker SDK y el wheel de PySpin: ./instalar.sh --pyspin <archivo.whl>", "§20.3")
        return None
    informar("ok", "PySpin importado")
    if not con_hardware:
        informar("info", "Detección de la cámara omitida (--sin-hardware)")
        return None
    sistema = camaras = None
    try:
        sistema = PySpin.System.GetInstance()
        camaras = sistema.GetCameras()
        n = camaras.GetSize()
        if n == 0:
            informar("aviso", "PySpin funciona pero no detecta ninguna cámara",
                     "Revisa el cable USB3 (puerto azul), la alimentación y que SpinView la vea.", "§16.3")
            return None
        cam = camaras.GetByIndex(0)
        mapa = cam.GetTLDeviceNodeMap()
        modelo = PySpin.CStringPtr(mapa.GetNode("DeviceModelName"))
        serie = PySpin.CStringPtr(mapa.GetNode("DeviceSerialNumber"))
        texto_modelo = modelo.GetValue() if PySpin.IsReadable(modelo) else "?"
        texto_serie = serie.GetValue() if PySpin.IsReadable(serie) else "?"
        cam.Init()
        tamano = (int(cam.WidthMax.GetValue()), int(cam.HeightMax.GetValue()))
        cam.DeInit()
        del cam
        informar("ok", f"{n} cámara(s): {texto_modelo} (serie {texto_serie}), sensor {tamano[0]}x{tamano[1]}")
        return tamano
    except Exception as exc:  # noqa: BLE001
        informar("error", f"Error al abrir la cámara: {exc}",
                 "¿Otro programa (SpinView, la interfaz web) la está usando? Ciérralo y repite.", "§16.3")
        return None
    finally:
        if camaras is not None:
            camaras.Clear()
        if sistema is not None:
            sistema.ReleaseInstance()


def verificar_lightcrafter(con_hardware: bool) -> None:
    titulo("Proyector LightCrafter 4500 (USB)")
    if Path("/etc/udev/rules.d/99-lightcrafter.rules").exists():
        informar("ok", "Regla udev instalada (/etc/udev/rules.d/99-lightcrafter.rules)")
    else:
        informar("aviso", "Regla udev no instalada: hará falta sudo para configurar el proyector",
                 "./instalar.sh --udev", "§20.4")
    if not con_hardware:
        informar("info", "Detección del proyector omitida (--sin-hardware)")
        return
    import configurar_lightcrafter as lcr

    try:
        ruta = lcr.LightCrafter4500._buscar_hidraw()
    except FileNotFoundError:
        informar("aviso", "No se detecta el LightCrafter por USB (solo hace falta para la etapa 'lightcrafter')",
                 "Conecta el cable mini-USB del proyector y enciéndelo.", "§16.2")
        return
    if not os.access(ruta, os.R_OK | os.W_OK):
        informar("error", f"LightCrafter en {ruta}, pero sin permisos de lectura/escritura",
                 "./instalar.sh --udev y desconecta/conecta el USB (temporal: sudo chmod a+rw " + ruta + ")", "§20.4")
        return
    try:
        with lcr.LightCrafter4500(ruta) as dispositivo:
            exp, per = dispositivo.leer_exposicion_y_periodo()
        informar("ok", f"LightCrafter en {ruta}: exposición {exp} µs, período {per} µs")
    except Exception as exc:  # noqa: BLE001
        informar("aviso", f"LightCrafter en {ruta}, pero no respondió: {exc}",
                 "Apágalo y enciéndelo; cierra el software de TI si está abierto.", "§16.2")


def verificar_patrones() -> None:
    titulo("Patrones del proyector")
    import cv2

    import configuracion as cfg

    bmps = sorted(cfg.DIR_PATRONES.glob("f_*.bmp"))
    if len(bmps) != cfg.IMAGENES_POR_CICLO:
        informar("aviso", f"{len(bmps)} de {cfg.IMAGENES_POR_CICLO} patrones en {cfg.DIR_PATRONES}",
                 "Genera los patrones: .env/bin/python secuencia_patrones.py (deben coincidir con los "
                 "cargados en el LightCrafter)", "§6")
        return
    img = cv2.imread(str(bmps[0]), cv2.IMREAD_GRAYSCALE)
    if img is None or img.shape != (cfg.PROYECTOR_ALTO, cfg.PROYECTOR_ANCHO):
        informar("error", f"{bmps[0].name} no tiene {cfg.PROYECTOR_ANCHO}x{cfg.PROYECTOR_ALTO} px",
                 "Regenera los patrones con secuencia_patrones.py.", "§6")
        return
    informar("ok", f"{len(bmps)} patrones de {cfg.PROYECTOR_ANCHO}x{cfg.PROYECTOR_ALTO} (período {cfg.PERIODO} px)")


def verificar_calibracion(tamano_camara: tuple[int, int] | None) -> None:
    titulo("Calibración del montaje")
    import numpy as np

    import configuracion as cfg

    ruta = cfg.DIR_CALIBRACION / "Estereo_TSC_0_2.npz"
    if not ruta.exists():
        informar("error", f"No hay calibración en {cfg.DIR_CALIBRACION}",
                 "Sin ella no se puede reconstruir. Copia la carpeta calibraciones/ del otro equipo, o "
                 "captura 10–15 poses del patrón y ejecuta la etapa 'calibracion'.", "§20.5")
        return
    try:
        datos = dict(np.load(ruta))
    except Exception as exc:  # noqa: BLE001
        informar("error", f"{ruta.name} no se puede leer: {exc}", "Restaura una copia de calibraciones/historial/.", "§20.5")
        return
    resumen_json = ruta.with_suffix(".json")
    info = json.loads(resumen_json.read_text(encoding="utf-8")) if resumen_json.exists() else {}
    informar("ok", f"Calibración del {info.get('fecha', '?')}: {len(info.get('poses', []))} poses, "
                   f"RMS estéreo {float(datos.get('rms_stereo', np.nan)):.3f} px, "
                   f"línea base {np.linalg.norm(datos['T']):.1f} mm")
    if int(datos.get("fringe_pitch", cfg.PERIODO)) != cfg.PERIODO:
        informar("error", f"La calibración se hizo con período {int(datos['fringe_pitch'])} px y configuracion.py "
                          f"dice {cfg.PERIODO}", "Recalibra con los patrones actuales.", "§12")
    if tamano_camara and "cam_size_wh" in datos and tuple(int(v) for v in datos["cam_size_wh"]) != tamano_camara:
        informar("error", f"La calibración es para una cámara de {tuple(datos['cam_size_wh'])} px y la conectada "
                          f"mide {tamano_camara}", "¿Es otra cámara o cambió la resolución? Recalibra.", "§20.5")
    try:  # el mismo control de calidad que decide si una calibración nueva se pone en uso
        import calibracion_estereo as ce

        resumen_json = json.loads((cfg.DIR_CALIBRACION / "Estereo_TSC_0_2.json").read_text(encoding="utf-8"))
        motivos = ce.control_calidad(resumen_json)
    except (OSError, ValueError):
        motivos = []
    if motivos:
        informar("aviso", "La calibración en uso no pasa el control de calidad: " + "; ".join(motivos),
                 "Revisa la pestaña Calibración de la interfaz (errores por pose y mapa de cobertura).", "§12.4")
    else:
        informar("ok", "La calibración en uso pasa el control de calidad (cobertura: ver el mapa en la pestaña Calibración)")
    historial = sorted((cfg.DIR_CALIBRACION / "historial").glob("*"))
    informar("info", f"{len(historial)} calibración(es) en el historial")
    try:
        cambios = subprocess.run(["git", "status", "--porcelain", "--", str(cfg.DIR_CALIBRACION)],
                                 cwd=RAIZ, capture_output=True, text=True, timeout=5).stdout.strip()
        if cambios:
            informar("aviso", "Hay cambios en calibraciones/ sin commit: no viajarán con el código",
                     "git add calibraciones && git commit -m 'Nueva calibración'", "§20.5")
    except (OSError, subprocess.SubprocessError):
        pass


def verificar_datos() -> None:
    titulo("Datos")
    import configuracion as cfg

    informar("info", f"Carpeta de datos: {cfg.DATOS}"
                     + ("  (TESIS_DIR_DATOS)" if os.environ.get("TESIS_DIR_DATOS") else ""))
    try:
        cfg.DATOS.mkdir(parents=True, exist_ok=True)
        prueba = cfg.DATOS / ".prueba_escritura"
        prueba.write_text("ok")
        prueba.unlink()
    except OSError as exc:
        informar("error", f"No se puede escribir en {cfg.DATOS}: {exc}", "Revisa permisos o TESIS_DIR_DATOS.", "§20.6")
        return
    libre = shutil.disk_usage(cfg.DATOS).free / 1e9
    if libre < 5:
        informar("aviso", f"Solo {libre:.1f} GB libres (cada pose ocupa ~150 MB entre capturas y resultados)",
                 "Libera espacio o usa un disco externo con TESIS_DIR_DATOS.", "§20.6")
    else:
        informar("ok", f"{libre:.0f} GB libres")
    n = sum(1 for _ in cfg.DIR_CAPTURAS.glob("*/*")) if cfg.DIR_CAPTURAS.exists() else 0
    informar("info", f"{n} capturas crudas en {cfg.DIR_CAPTURAS}")


def verificar_interfaz(puerto: int = 8000) -> None:
    titulo("Interfaz web")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", puerto)) == 0:
            informar("aviso", f"El puerto {puerto} ya está en uso (¿la interfaz ya está abierta?)",
                     f"Usa otro: .env/bin/python interfaz/servidor.py --puerto {puerto + 1}", "§16.8")
        else:
            informar("ok", f"Puerto {puerto} libre: .env/bin/python interfaz/servidor.py")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sin-hardware", action="store_true", help="No intenta detectar la cámara ni el proyector")
    parser.add_argument("--json", action="store_true", help="Solo imprime el resultado en JSON (para la interfaz)")
    args = parser.parse_args()
    con_hw = not args.sin_hardware
    if args.json:
        import contextlib
        import io
        import json

        with contextlib.redirect_stdout(io.StringIO()):
            try:
                _comprobar(con_hw)
            except SystemExit:
                pass
        print(json.dumps({"resumen": resumen, "resultados": resultados}, ensure_ascii=False))
        return

    print(f"Verificación del sistema de reconstrucción 3D por franjas — {RAIZ}")
    _comprobar(con_hw)
    print(f"\nResumen: {resumen['ok']} correctos, {resumen['aviso']} advertencias, {resumen['error']} errores.")
    if resumen["error"]:
        print("Corrige los errores (✖) antes de usar el sistema. Detalles en MANUAL.md §20 y §16.")
    elif resumen["aviso"]:
        print("Se puede usar; revisa las advertencias (⚠) si necesitas capturar o configurar el proyector.")
    else:
        print("Todo listo.")
    raise SystemExit(1 if resumen["error"] else 0)


def _comprobar(con_hw: bool) -> None:
    verificar_python()
    if not verificar_paquetes():
        print("\nFaltan paquetes básicos: corrige eso primero (./instalar.sh) y vuelve a verificar.")
        raise SystemExit(1)
    tamano = verificar_camara(con_hw)
    verificar_lightcrafter(con_hw)
    verificar_patrones()
    verificar_calibracion(tamano)
    verificar_datos()
    verificar_interfaz()


if __name__ == "__main__":
    main()
