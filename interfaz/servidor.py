"""Interfaz web local para controlar y visualizar el sistema de proyección de franjas.

Ejecuta:
    .env/bin/python interfaz/servidor.py            # abre http://127.0.0.1:8000 en el navegador
    .env/bin/python interfaz/servidor.py --puerto 8080 --sin-navegador
    .env/bin/python interfaz/servidor.py --host 0.0.0.0   # accesible desde otra PC de la red (¡sin clave!)

Solo usa la librería estándar de Python más NumPy/OpenCV del proyecto. El pipeline corre en un
subproceso (`ejecutor.py`) para poder detenerlo y para responder a las pausas de la captura desde
la web. El navegador recibe en tiempo real (Server-Sent Events) el registro, la etapa en curso, la
vista en vivo de la cámara y cada resultado nuevo (pose organizada, fase relativa, fase absoluta,
reconstrucción), que se detectan vigilando las carpetas de resultados.

API (todas las respuestas JSON salvo imágenes y nube):
    GET  /api/config                       valores por defecto de pipeline.py / configuracion.py
    GET  /api/estado                       ejecución, calibración y poses disponibles
    POST /api/ejecutar   {config}          lanza el pipeline
    POST /api/detener                      termina el subproceso
    POST /api/entrada    {"texto": "..."}  responde a una pausa (Enter, q)
    GET  /api/eventos                      flujo SSE
    GET  /api/imagen?cat=&pose=&tipo=&ancho=   PNG de un paso (cabecera X-Rango con la escala)
    GET  /api/nube?cat=&pose=&max=         nube binaria: uint32 N | float32 xyz*N | uint8 gris*N
    GET  /api/vivo.jpg                     último frame de la cámara durante la captura
"""

from __future__ import annotations

import argparse
import codecs
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import zipfile
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import configuracion as cfg  # noqa: E402

DIR_ESTATICO = Path(__file__).resolve().parent / "estatico"
DIR_FASES = cfg.DIR_RESULTADOS / "fases"
DIR_RECONSTRUCCION = cfg.DIR_RESULTADOS / "reconstruccion"
DIR_CALIBRACION = cfg.DIR_CALIBRACION
ARCHIVO_VIVO = cfg.DIR_RESULTADOS / ".vivo" / "frame.jpg"
RE_POSE = re.compile(r"^pose_\d+$")
RE_ORDENADA = re.compile(r"^img_([HV])_(\d{1,2})$")
RE_MARCA = re.compile(r"@@(vivo) (\d+) (\d+)|@@(previa) ([\d.]+)(?: ([\d.]+))?(?: (\d+))?|@@exposicion [\d.]+")
RE_PREGUNTA = re.compile(r"^@@pregunta (.*)$")  # el ejecutor anuncia así cada input() (ejecutor._input_marcado)
RE_META = re.compile(r"^@@meta (\{.*\})$")        # datos de la próxima pregunta (capturar_patrones.preguntar)
RE_CALIDAD = re.compile(r"^@@calidad (\{.*\})$")  # control de una pose recién capturada
# Progreso: «=== Fase relativa: 'plano' (3 poses) ===», «=== RECONSTRUCCIÓN 3D: 'PLANO' (3 poses) ===»,
# «=== Calibración Estéreo Tradicional (8 poses, …» y una línea «  [pose_XX] …» por pose terminada
RE_TOTAL = re.compile(r"^=+ *[^:(]+?(?:: '(\w+)')? \((\d+) poses")
RE_POSE_HECHA = re.compile(r"^\s+\[pose_\d+\]")


# ==============================================================================
# Difusión de eventos (SSE)
# ==============================================================================


class Difusor:
    def __init__(self) -> None:
        self.clientes: list[queue.Queue] = []
        self.lock = threading.Lock()
        self.historial: list[str] = []  # registro reciente para quien se conecta tarde

    def suscribir(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=2000)
        with self.lock:
            self.clientes.append(q)
            for texto in self.historial[-400:]:
                q.put(("log", {"texto": texto}))
        return q

    def desuscribir(self, q: queue.Queue) -> None:
        with self.lock:
            if q in self.clientes:
                self.clientes.remove(q)

    def emitir(self, evento: str, datos: dict) -> None:
        if evento == "log":
            self.historial.append(datos["texto"])
            del self.historial[:-2000]
        with self.lock:
            for q in list(self.clientes):
                try:
                    q.put_nowait((evento, datos))
                except queue.Full:
                    pass


difusor = Difusor()


# ==============================================================================
# Ejecución del pipeline en un subproceso
# ==============================================================================


class Ejecucion:
    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.etapa: str | None = None
        self.esperando = False
        self.pregunta = ""
        self.inicio: float | None = None
        self.ultimo_codigo: int | None = None
        self.meta: dict | None = None       # datos de la pregunta en curso (tipo, pose, motivos…)
        self.progreso: dict | None = None   # {"cat", "i", "n", "t0"} de la etapa en curso
        self.calidades: list[dict] = []      # control de cada pose capturada en esta ejecución
        self.ultimo_error = ""               # última línea [ERROR] (se muestra si el proceso falla)
        self.lock = threading.Lock()

    @property
    def activa(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def estado(self) -> dict:
        return {
            "ejecutando": self.activa, "etapa": self.etapa, "esperando": self.esperando,
            "pregunta": self.pregunta if self.esperando else "",
            "meta": self.meta if self.esperando else None,
            "progreso": self._progreso(),
            "calidades": self.calidades[-60:],
            "error": self.ultimo_error if self.ultimo_codigo not in (None, 0) else "",
            "codigo": self.ultimo_codigo,
            "segundos": round(time.time() - self.inicio, 1) if self.inicio and self.activa else None,
        }

    def _progreso(self) -> dict | None:
        p = self.progreso
        if not p or not self.activa:
            return None
        transcurrido = time.time() - p["t0"]
        restante = transcurrido / p["i"] * (p["n"] - p["i"]) if p["i"] else None
        return {"cat": p["cat"], "i": p["i"], "n": p["n"], "restante_s": round(restante) if restante is not None else None}

    def _emitir_estado(self) -> None:
        difusor.emitir("estado", self.estado())

    def lanzar(self, conf: dict) -> None:
        with self.lock:
            if self.activa:
                raise RuntimeError("Ya hay un proceso en ejecución.")
            ruta = Path(tempfile.mkstemp(prefix="pipeline_", suffix=".json")[1])
            ruta.write_text(json.dumps(conf), encoding="utf-8")
            env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
            self.proc = subprocess.Popen(
                [sys.executable, "-u", str(Path(__file__).with_name("ejecutor.py")), str(ruta)],
                cwd=RAIZ, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            self.etapa, self.esperando, self.inicio, self.ultimo_codigo = None, False, time.time(), None
            self.meta, self.progreso, self.calidades, self.ultimo_error = None, None, [], ""
        difusor.emitir("log", {"texto": f"\n▶ Ejecución iniciada {time.strftime('%H:%M:%S')}"})
        self._emitir_estado()
        threading.Thread(target=self._leer_salida, args=(self.proc, ruta), daemon=True).start()

    def _linea(self, linea: str) -> None:
        # Mensajes internos de la vista en vivo: se extraen aunque otro hilo los haya pegado a
        # una línea del registro
        for m in RE_MARCA.finditer(linea):
            if m.group(1):
                difusor.emitir("vivo", {"i": int(m.group(2)), "n": int(m.group(3))})
            elif m.group(4):
                difusor.emitir("vivo", {"previa": True, "saturacion": float(m.group(5)),
                                        "nitidez": float(m.group(6) or 0),
                                        "tablero": None if m.group(7) is None else int(m.group(7))})
        linea = RE_MARCA.sub("", linea)
        if not linea.strip():
            return
        m = RE_META.match(linea.strip())
        if m:
            try:
                self.meta = json.loads(m.group(1))
            except json.JSONDecodeError:
                self.meta = None
            return
        m = RE_CALIDAD.match(linea.strip())
        if m:
            try:
                calidad = json.loads(m.group(1))
            except json.JSONDecodeError:
                return
            self.calidades.append(calidad)
            difusor.emitir("calidad", calidad)
            return
        m = RE_TOTAL.match(linea.strip())
        if m:
            self.progreso = {"cat": (m.group(1) or "patron").lower(), "i": 0, "n": int(m.group(2)), "t0": time.time()}
            self._emitir_estado()
        elif self.progreso and RE_POSE_HECHA.match(linea):
            self.progreso["i"] = min(self.progreso["i"] + 1, self.progreso["n"])
            self._emitir_estado()
        if "[ERROR]" in linea:
            self.ultimo_error = linea.strip()
        m = RE_PREGUNTA.match(linea.strip())
        if m:  # el proceso espera una respuesta
            self.pregunta = m.group(1)
            self.esperando = True
            difusor.emitir("log", {"texto": self.pregunta})
            self._emitir_estado()
            return
        m = re.match(r"# ETAPA: (\w+)", linea)
        if m:
            self.etapa = m.group(1)
            self.progreso = None
            self._emitir_estado()
        if set(linea.strip()) == {"#"}:
            return  # separadores decorativos
        difusor.emitir("log", {"texto": linea})

    def _leer_salida(self, proc: subprocess.Popen, ruta_conf: Path) -> None:
        decodificador = codecs.getincrementaldecoder("utf-8")(errors="replace")
        pendiente = ""
        fd = proc.stdout.fileno()
        while True:
            bloque = os.read(fd, 4096)
            if not bloque:
                break
            pendiente += decodificador.decode(bloque)
            *lineas, pendiente = pendiente.split("\n")
            for linea in lineas:
                self._linea(linea.rstrip("\r"))
        if pendiente:
            self._linea(pendiente)
        codigo = proc.wait()
        ruta_conf.unlink(missing_ok=True)
        self.ultimo_codigo, self.esperando, self.etapa = codigo, False, None
        texto = "✔ Proceso terminado correctamente" if codigo == 0 else f"✖ Proceso terminado con código {codigo}"
        difusor.emitir("log", {"texto": f"{texto} ({time.time() - (self.inicio or time.time()):.1f} s)"})
        self._emitir_estado()

    def entrada(self, texto: str) -> None:
        if not self.activa or self.proc.stdin is None:
            raise RuntimeError("No hay un proceso esperando entrada.")
        self.proc.stdin.write((texto + "\n").encode())
        self.proc.stdin.flush()
        self.esperando = False
        self.meta = None
        difusor.emitir("log", {"texto": f"  ⏎ {texto or '(Enter)'}"})
        self._emitir_estado()

    def detener(self) -> None:
        if self.activa:
            self.proc.terminate()  # el ejecutor lo convierte en KeyboardInterrupt y cierra la cámara
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            difusor.emitir("log", {"texto": "■ Proceso detenido por el usuario"})


ejecucion = Ejecucion()


# ==============================================================================
# Inventario de poses y vigilancia de cambios
# ==============================================================================


def _mtime(ruta: Path) -> float | None:
    try:
        return ruta.stat().st_mtime
    except OSError:
        return None


def _archivos_pose(cat: str, pose: str) -> dict[str, Path]:
    return {
        "organizada": cfg.DIR_ORDENADAS / cat / pose / "H" / f"{cfg.PREFIJO_ORDENADAS}{cfg.IMAGENES_POR_ORIENTACION + 1:02d}.tiff",
        "relativa": DIR_FASES / cat / f"{pose}_relativa.npz",
        "absoluta": DIR_FASES / cat / f"{pose}.npz",
        "reconstruida": DIR_RECONSTRUCCION / cat / f"{cat}_{pose}.npz",
    }


def listar_poses(cat: str) -> list[str]:
    """Poses de la categoría en la configuración vigente del montaje (sesiones.py)."""
    import sesiones

    vigentes = sesiones.poses_vigentes(cat)
    nombres = set()
    for carpeta in (cfg.DIR_ORDENADAS / cat, DIR_FASES / cat):
        if carpeta.is_dir():
            for p in carpeta.iterdir():
                nombre = p.name.split("_relativa")[0].removesuffix(".npz").removesuffix(".png")
                if RE_POSE.match(nombre) and (vigentes is None or nombre in vigentes):
                    nombres.add(nombre)
    return sorted(nombres, key=lambda n: int(n[5:]))


def _firma_pose(ruta: Path, tipo: str) -> str | None:
    """Parámetros con los que se calculó la fase de una pose (los anteriores a la firma: los de
    configuracion.py). None si la pose aún no tiene esa fase."""
    import fase

    if _mtime(ruta) is None:
        return None
    try:
        npz = cargar_npz(ruta)
        return str(npz["firma"]) if "firma" in npz else fase._firma_original(tipo)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return None


def inventario() -> dict:
    import ajustes

    esperada_rel, esperada_abs = ajustes.firmas_esperadas()
    import archivos

    notas = archivos.leer_notas()
    datos = {}
    for cat in cfg.CATEGORIAS:
        resumen_ruta = DIR_RECONSTRUCCION / cat / f"{cat}_resumen.json"
        resumen = {}
        if resumen_ruta.exists():
            try:
                resumen = json.loads(resumen_ruta.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        poses = []
        for pose in listar_poses(cat):
            archivos = _archivos_pose(cat, pose)
            estado = {k: _mtime(r) is not None for k, r in archivos.items()}
            info = resumen.get(pose, {})
            # Procedencia: ¿se calculó con los ajustes actuales? (si no, hay que volver a procesar)
            f_rel, f_abs = _firma_pose(archivos["relativa"], "rel"), _firma_pose(archivos["absoluta"], "abs")
            distintos = [f for f, esperada in ((f_rel, esperada_rel), (f_abs, esperada_abs)) if f and f != esperada]
            poses.append({"pose": pose, **estado, "puntos": info.get("puntos"), "erms_mm": info.get("erms_mm"),
                          "nota": notas.get(f"pose:{cat}/{pose}"),
                          "z": [info.get("z_p1_mm"), info.get("z_p99_mm")],
                          "ajustes_ok": not distintos,
                          "calculada_con": " · ".join(ajustes.describir_firma(f) for f in (f_rel, f_abs) if f)})
        datos[cat] = poses
    return datos


def resumen_calibracion() -> dict | None:
    ruta = DIR_CALIBRACION / "Estereo_TSC_0_2.json"
    if not ruta.exists():
        return None
    try:
        info = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    claves = ("fecha", "poses", "rms_cam_px", "rms_proj_px", "rms_stereo_indep_px", "linea_base_mm",
              "T_mm", "cobertura_up_px", "cobertura_vp_px", "center_distance_mm")
    return {k: info.get(k) for k in claves}


def listado_archivos() -> dict:
    """Todas las capturas agrupadas por proceso, con sus poses y lo calculado de cada una."""
    import archivos
    import calibracion_estereo as ce
    import sesiones

    lista = sesiones.procesos()
    conf = sesiones.configuracion_vigente()
    rangos = sesiones.configuraciones(lista)
    notas = archivos.leer_notas()
    calibs = ce.listar_calibraciones(DIR_CALIBRACION)
    proceso_calib = {}
    for c in calibs:
        proceso_calib.setdefault(sesiones.proceso_de_poses("patron", c["poses"]), []).append(
            {"id": c["id"], "activa": c["activa"], "rms_stereo_px": c["rms_stereo_px"]})
    salida = []
    for i, p in enumerate(lista):
        config = next((lista[a]["id"] for a, b in rangos if a <= i < b), None)
        items = []
        for it in p["items"]:
            poses = []
            for pose in it["poses"]:
                estado = {k: _mtime(r) is not None for k, r in _archivos_pose(it["cat"], pose).items()}
                poses.append({"pose": pose, **estado})
            # Espacio: captura cruda + poses organizadas (lo que se libera al borrarla, sin contar resultados)
            bytes_item = archivos.tamano(cfg.DIR_CAPTURAS / it["carpeta"]) + sum(
                archivos.tamano(cfg.DIR_ORDENADAS / it["cat"] / p["pose"]) for p in poses)
            items.append({"cat": it["cat"], "carpeta": it["carpeta"], "hora": it["hora"].isoformat(timespec="seconds"),
                          "existe": it["existe"], "poses": poses, "rechazo": it.get("rechazo"),
                          "pureza": it.get("pureza"), "bytes": bytes_item,
                          "nota": notas.get(f"pose:{it['cat']}/{it['poses'][0]}") if it["poses"] else None})
        salida.append({
            "id": p["id"], "fin": p["fin"].isoformat(timespec="seconds"), "registrado": p["registrado"],
            "nota": notas.get(f"proceso:{p['id']}"), "bytes": sum(i["bytes"] for i in items),
            "patron": p["patron"], "configuracion": config, "vigente": bool(conf) and config == conf["proceso"],
            "inicia_configuracion": config == p["id"], "calibraciones": proceso_calib.get(p["id"], []),
            "items": items,
        })
    return {"procesos": salida, "vigente": sesiones.info_vigente(), "papelera": archivos.info_papelera(),
            "lotes": archivos.listar_papelera()}


def _tamano(ruta: Path) -> int:
    total = 0
    pila = [ruta]
    while pila:
        try:
            with os.scandir(pila.pop()) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        pila.append(e.path)
                    elif e.is_file(follow_symlinks=False):
                        total += e.stat(follow_symlinks=False).st_size
        except OSError:
            pass
    return total


_cache_sistema: dict = {}


def estado_sistema(con_hardware: bool, forzar: bool = False) -> dict:
    """Comprobación del sistema (verificar.py --json) más el espacio en disco. Se cachea 60 s.

    Con un proceso en curso no se busca el hardware: la cámara está ocupada por el pipeline."""
    con_hardware = con_hardware and not ejecucion.estado()["ejecutando"]
    clave = con_hardware
    if not forzar and clave in _cache_sistema and time.time() - _cache_sistema[clave]["t"] < 60:
        return _cache_sistema[clave]["datos"]
    comando = [sys.executable, str(RAIZ / "verificar.py"), "--json"] + ([] if con_hardware else ["--sin-hardware"])
    try:
        r = subprocess.run(comando, capture_output=True, text=True, timeout=90, cwd=RAIZ, env={**os.environ})
        verif = json.loads(r.stdout.strip().splitlines()[-1])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, IndexError) as exc:
        verif = {"resumen": {"ok": 0, "aviso": 0, "error": 1},
                 "resultados": [{"grupo": "verificar.py", "nivel": "error", "texto": f"No se pudo ejecutar: {exc}",
                                 "solucion": "", "seccion": "§20"}]}
    import shutil

    disco = shutil.disk_usage(cfg.DATOS)
    import archivos

    datos = {
        **verif, "con_hardware": con_hardware, "hora": time.strftime("%H:%M:%S"),
        "disco": {"libre": disco.free, "total": disco.total,
                  "carpetas": {nombre: _tamano(ruta) for nombre, ruta in (
                      ("capturas", cfg.DIR_CAPTURAS), ("capturas_ordenadas", cfg.DIR_ORDENADAS),
                      ("resultados", cfg.DIR_RESULTADOS), ("papelera", archivos.PAPELERA))}},
    }
    _cache_sistema[clave] = {"t": time.time(), "datos": datos}
    return datos


_cache_errores: dict = {}
_lock_errores = threading.Lock()


def _puntos_calibracion(info: dict) -> dict:
    """Correspondencias de la calibración en uso: las que guardó al calibrar
    (`Estereo_TSC_0_2_puntos.npz`) o, si es anterior a ese archivo, las recalculadas una vez desde
    las fases de sus poses (se guardan en resultados/calibracion/puntos_<fecha>.npz)."""
    import calibracion_estereo as ce

    ruta = DIR_CALIBRACION / ce.ARCHIVO_PUNTOS
    nuevo = ruta.exists()
    if not nuevo:
        ruta = cfg.DIR_RESULTADOS / "calibracion" / f"puntos_{re.sub(r'[^0-9T]', '', info.get('fecha') or 'sin_fecha')}.npz"
        if not ruta.exists():
            calc = ce.puntos_desde_fases(info)
            if not calc["poses"]:
                raise FileNotFoundError("no quedan fases de las poses de esta calibración (¿se borraron?)")
            ruta.parent.mkdir(parents=True, exist_ok=True)
            np.savez(ruta, poses=np.array(calc["poses"]), usadas=np.array(calc["usadas"]),
                     cam=np.stack(calc["cam"]).astype(np.float32), proj=np.stack(calc["proj"]).astype(np.float32),
                     worldPoints=calc["worldPoints"], faltan=np.array(calc["faltan"], dtype=str))
    with np.load(ruta) as d:
        return {"poses": [str(x) for x in d["poses"]], "usadas": {str(x) for x in d["usadas"]},
                "cam": d["cam"], "proj": d["proj"], "mundo": d["worldPoints"],
                "faltan": [str(x) for x in d["faltan"]] if "faltan" in d.files else [], "completo": nuevo}


def errores_calibracion(variante: str = "independiente") -> dict:
    """Errores de reproyección por pose con la calibración en uso, evaluada con SUS poses del
    patrón (las usadas y, en las calibraciones nuevas, también las detectadas que no entraron).
    Se recalcula solo cuando cambia la calibración en uso."""
    import calibracion_estereo as ce

    nombre = "Estereo_TSC_0_2_J.npz" if variante == "conjunta" else "Estereo_TSC_0_2.npz"
    ruta_cal = DIR_CALIBRACION / nombre
    ruta_json = DIR_CALIBRACION / "Estereo_TSC_0_2.json"
    if _mtime(ruta_cal) is None:
        raise FileNotFoundError("no hay calibración guardada")
    clave = (variante, *(_mtime(r) for r in (ruta_cal, ruta_json, DIR_CALIBRACION / ce.ARCHIVO_PUNTOS)))
    with _lock_errores:
        if clave in _cache_errores:
            return _cache_errores[clave]
        with np.load(ruta_cal) as d:
            calib = {k: d[k] for k in d.files}
        try:
            info = json.loads(ruta_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            info = {}
        pts = _puntos_calibracion(info)
        poses = pts["poses"]
        detalle = info.get("errores_por_pose", {})
        sesiones = ce.sesiones_patron()
        errores = ce.errores_reproyeccion(calib, list(pts["cam"]), list(pts["proj"]), pts["mundo"], residuos=True)
        datos = {
            "variante": variante,
            "fecha": info.get("fecha"),
            "criterio": info.get("poses_criterio", "todas"),
            "rms": {"cam": info.get("rms_cam_px"), "proj": info.get("rms_proj_px"),
                    "estereo": float(calib["rms_stereo"]) if "rms_stereo" in calib else info.get("rms_stereo_indep_px")},
            "cam_wh": [int(v) for v in calib.get("cam_size_wh", (1280, 1024))],
            "proj_wh": [int(v) for v in calib.get("proj_size_wh", (cfg.PROYECTOR_ANCHO, cfg.PROYECTOR_ALTO))],
            "completo": pts["completo"],
            "faltan": pts["faltan"],
            "poses": [{"pose": n, "usada": n in pts["usadas"], **sesiones.get(n, {}),
                       **{k: detalle[n][k] for k in ("hora", "sesion") if k in detalle.get(n, {})}, **e}
                      for n, e in zip(poses, errores)],
        }
        _cache_errores.clear()
        _cache_errores[clave] = datos
        return datos


def fuentes_demo() -> list[str]:
    """Capturas existentes que puede reproducir la cámara simulada (solo del montaje vigente)."""
    import sesiones

    salida = []
    for cat in cfg.CATEGORIAS:
        carpeta = cfg.DIR_CAPTURAS / cat
        if carpeta.is_dir():
            salida += [str(p.relative_to(cfg.DIR_CAPTURAS)) for p in sorted(carpeta.iterdir())
                       if p.is_dir() and not p.name.endswith("_simulada") and sesiones.captura_vigente(p)]
    return salida


def vigilar() -> None:
    """Emite 'cambio' cuando aparece o se actualiza un resultado de una pose.

    Solo avisa cuando la fecha de modificación se mantiene en dos sondeos seguidos, para no
    anunciar un archivo que aún se está escribiendo."""
    visto: dict[tuple, float] = {}
    candidato: dict[tuple, float] = {}
    primera = True
    while True:
        actual = {}
        for cat in cfg.CATEGORIAS:
            for pose in listar_poses(cat):
                for tipo, ruta in _archivos_pose(cat, pose).items():
                    m = _mtime(ruta)
                    if m is not None:
                        actual[(cat, pose, tipo)] = m
        ahora = time.time()
        for clave, m in actual.items():
            # Un archivo viejo que «aparece» no es un resultado nuevo: es una pose que pasó a ser
            # visible al cambiar de configuración. Se registra sin avisar (si no, «Seguir la
            # última» movería la vista a ella)
            if primera or (clave not in visto and m < ahora - 30):
                visto[clave] = m
            elif visto.get(clave) != m:
                if candidato.get(clave) == m:
                    visto[clave] = m
                    candidato.pop(clave)
                    difusor.emitir("cambio", {"cat": clave[0], "pose": clave[1], "tipo": clave[2]})
                else:
                    candidato[clave] = m
        primera = False
        time.sleep(0.7)


# ==============================================================================
# Imágenes de cada paso y nube de puntos
# ==============================================================================


class _CacheMapas:
    """Caché de mapas de los .npz con un límite de memoria.

    Se guarda cada mapa por separado, (ruta, fecha, clave): una imagen necesita 1–3 de los 10–15
    mapas de una pose (~5 MB cada uno). Antes se cacheaban .npz completos, 24 de hasta 52 MB:
    ~1.2 GB de RAM.
    """

    def __init__(self, max_bytes: int = 400_000_000) -> None:
        self.max_bytes = max_bytes
        self.datos: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
        self.claves_npz: dict[tuple, list[str]] = {}
        self.bytes = 0
        self.lock = threading.Lock()

    def claves(self, ruta: str, m: float) -> list[str]:
        with self.lock:
            if (ruta, m) not in self.claves_npz:
                with np.load(ruta) as d:
                    self.claves_npz[(ruta, m)] = list(d.files)
            return self.claves_npz[(ruta, m)]

    def mapa(self, ruta: str, m: float, clave: str) -> np.ndarray:
        k = (ruta, m, clave)
        with self.lock:
            if k in self.datos:
                self.datos.move_to_end(k)
                return self.datos[k]
            with np.load(ruta) as d:
                valor = d[clave]
            self.datos[k] = valor
            self.bytes += valor.nbytes
            while self.bytes > self.max_bytes and len(self.datos) > 1:
                _, viejo = self.datos.popitem(last=False)
                self.bytes -= viejo.nbytes
            return valor

    def limpiar(self) -> None:
        with self.lock:
            self.datos.clear()
            self.claves_npz.clear()
            self.bytes = 0


_cache_mapas = _CacheMapas()
_lock_npz = threading.Lock()  # se toma al mover archivos a la papelera


class _Npz:
    """Vista perezosa de un .npz: cada mapa se lee (y cachea) solo cuando se pide."""

    def __init__(self, ruta: Path, m: float) -> None:
        self.ruta, self.m = str(ruta), m

    def __getitem__(self, clave: str) -> np.ndarray:
        if clave not in self:
            raise KeyError(clave)
        return _cache_mapas.mapa(self.ruta, self.m, clave)

    def __contains__(self, clave: str) -> bool:
        return clave in _cache_mapas.claves(self.ruta, self.m)


def cargar_npz(ruta: Path) -> _Npz:
    m = _mtime(ruta)
    if m is None:
        raise FileNotFoundError(str(ruta))
    return _Npz(ruta, m)


def _leer_ordenada(cat: str, pose: str, orient: str, indice: int) -> np.ndarray:
    import fase

    return fase.leer_gris(fase.buscar_imagen_patron(cfg.DIR_ORDENADAS / cat / pose / orient / cfg.PREFIJO_ORDENADAS, indice))


FONDO = np.array([38, 34, 32], dtype=np.uint8)  # BGR de los píxeles sin dato


def _color(mapa: np.ndarray, mascara: np.ndarray | None, colormap: int,
           rango: tuple[float, float] | None = None, percentiles=(1, 99)) -> tuple[np.ndarray, tuple[float, float]]:
    mapa = mapa.astype(np.float64)
    valido = np.isfinite(mapa) if mascara is None else (mascara.astype(bool) & np.isfinite(mapa))
    if not np.any(valido):
        return np.broadcast_to(FONDO, (*mapa.shape, 3)).copy(), (0.0, 0.0)
    if rango is None:
        lo, hi = np.percentile(mapa[valido], percentiles)
    else:
        lo, hi = rango
    norm = np.clip((np.where(valido, mapa, lo) - lo) / max(hi - lo, 1e-12) * 255, 0, 255).astype(np.uint8)
    img = cv2.applyColorMap(norm, colormap)
    img[~valido] = FONDO
    return img, (float(lo), float(hi))


def generar_imagen(cat: str, pose: str, tipo: str) -> tuple[np.ndarray, str]:
    """Devuelve (imagen BGR o gris, texto de escala) para un paso del proceso."""
    archivos = _archivos_pose(cat, pose)
    n, b = cfg.N_PASOS, cfg.N_BITS_GRAY
    if tipo.startswith("dif:"):  # diferencia de Z contra una referencia (comparar)
        dif, _ = diferencia_z(cat, pose, tipo[4:])
        validos = np.isfinite(dif)
        lim = float(np.percentile(np.abs(dif[validos]), 98)) if np.any(validos) else 1.0
        img, r = _color(dif, None, cv2.COLORMAP_TURBO, (-max(lim, 1e-3), max(lim, 1e-3)))
        return img, f"ΔZ ±{lim:.2f} mm"
    m = RE_ORDENADA.match(tipo)
    if m:  # cualquier imagen organizada: img_V_03 = franja vertical, paso 3
        indice = int(m.group(2))
        if not 0 <= indice < cfg.IMAGENES_POR_ORIENTACION + 2:
            raise ValueError("índice de imagen fuera de rango")
        return _leer_ordenada(cat, pose, m.group(1), indice), "intensidad"
    if tipo in ("franja_V", "franja_H"):
        return _leer_ordenada(cat, pose, tipo[-1], 0), "intensidad"
    if tipo == "gray_V":
        return _leer_ordenada(cat, pose, "V", n), "bit Gray"
    if tipo == "textura":
        if archivos["absoluta"].exists():
            return cargar_npz(archivos["absoluta"])["Itex"], "intensidad"
        return _leer_ordenada(cat, pose, "H", n + b + 1), "intensidad"
    if tipo in ("phiX", "phiY", "qX", "qY"):
        rel = cargar_npz(archivos["relativa"])
        if tipo.startswith("phi"):
            img, r = _color(rel[tipo], None, cv2.COLORMAP_TWILIGHT_SHIFTED, (-np.pi, np.pi))
            return img, "−π … π rad"
        img, r = _color(rel[tipo], None, cv2.COLORMAP_VIRIDIS, (0.0, 1.0))
        return img, "γ 0 … 1"
    if tipo in ("Fx", "Fy", "kX", "kY", "mascara"):
        absl = cargar_npz(archivos["absoluta"])
        if tipo == "mascara":
            nivel = absl["MaskX"].astype(np.uint8) + 2 * absl["MaskY"].astype(np.uint8)
            paleta = np.array([FONDO, [70, 130, 230], [80, 200, 120], [240, 240, 240]], dtype=np.uint8)
            return paleta[nivel], "gris: nada · azul: solo X · verde: solo Y · blanco: ambas"
        mascara = absl["MaskX"] if tipo in ("Fx", "kX") else absl["MaskY"]
        if tipo.startswith("k"):
            img, r = _color(absl[tipo], mascara, cv2.COLORMAP_JET, percentiles=(0, 100))
            return img, f"orden {r[0]:.0f} … {r[1]:.0f}"
        img, r = _color(absl[tipo], mascara, cv2.COLORMAP_TURBO, percentiles=(0.5, 99.5))
        return img, f"{r[0]:.0f} … {r[1]:.0f} rad"
    if tipo in ("Z", "error"):
        xyz = cargar_npz(archivos["reconstruida"])
        if tipo == "Z":
            img, r = _color(xyz["Z"], xyz["Mask"], cv2.COLORMAP_VIRIDIS)
            return img, f"Z {r[0]:.1f} … {r[1]:.1f} mm"
        if "E" not in xyz:
            raise FileNotFoundError("sin mapa de error (solo categoría plano)")
        e = xyz["E"]
        lim = float(np.nanpercentile(np.abs(e), 98)) if np.any(np.isfinite(e)) else 1.0
        img, r = _color(e, None, cv2.COLORMAP_TURBO, (-lim, lim))
        return img, f"error ±{lim:.2f} mm"
    raise ValueError(f"tipo de imagen desconocido: {tipo}")


# ------------------------------------------------------------------ medición sobre la reconstrucción
def _xyz(cat: str, pose: str) -> _Npz:
    return cargar_npz(_archivos_pose(cat, pose)["reconstruida"])


def punto_3d(cat: str, pose: str, fx: float, fy: float, radio: int = 6) -> dict:
    """X, Y, Z del píxel válido más cercano a (fx, fy) ∈ [0, 1]² de la imagen (radio en px)."""
    xyz = _xyz(cat, pose)
    m = xyz["Mask"].astype(bool) & np.isfinite(xyz["Z"])
    alto, ancho = m.shape
    c, f = int(round(fx * (ancho - 1))), int(round(fy * (alto - 1)))
    f0, f1, c0, c1 = max(f - radio, 0), min(f + radio + 1, alto), max(c - radio, 0), min(c + radio + 1, ancho)
    ys, xs = np.nonzero(m[f0:f1, c0:c1])
    if not len(ys):
        raise ValueError("sin punto 3D válido cerca de ahí")
    k = int(np.argmin((ys + f0 - f) ** 2 + (xs + c0 - c) ** 2))
    fi, ci = int(ys[k] + f0), int(xs[k] + c0)
    return {"fila": fi, "col": ci, "fx": ci / (ancho - 1), "fy": fi / (alto - 1),
            **{k2: float(xyz[k2][fi, ci]) for k2 in ("X", "Y", "Z")}}


def perfil_3d(cat: str, pose: str, a: tuple[float, float], b: tuple[float, float], n: int = 400) -> dict:
    """Z (y la distancia recorrida en mm) a lo largo del segmento a→b de la imagen."""
    xyz = _xyz(cat, pose)
    m = xyz["Mask"].astype(bool) & np.isfinite(xyz["Z"])
    alto, ancho = m.shape
    t = np.linspace(0, 1, n)
    cols = np.clip(np.round((a[0] + (b[0] - a[0]) * t) * (ancho - 1)).astype(int), 0, ancho - 1)
    filas = np.clip(np.round((a[1] + (b[1] - a[1]) * t) * (alto - 1)).astype(int), 0, alto - 1)
    # Cada muestra: mediana de los píxeles válidos en una ventana 5×5 (el mapa tiene píxeles sueltos
    # sin dato por la rejilla del DMD; leer solo el píxel exacto deja la curva entrecortada)
    mapas = {k: np.where(m, xyz[k], np.nan) for k in ("X", "Y", "Z")}
    X, Y, Z = (np.full(n, np.nan) for _ in range(3))
    for i, (f, c) in enumerate(zip(filas, cols)):
        ventana = (slice(max(f - 2, 0), f + 3), slice(max(c - 2, 0), c + 3))
        if np.any(m[ventana]):
            X[i], Y[i], Z[i] = (float(np.nanmedian(mapas[k][ventana])) for k in ("X", "Y", "Z"))
    # Distancia recorrida en el plano X-Y (mm), interpolando sobre los huecos
    pasos = np.hypot(np.diff(X), np.diff(Y))
    pasos = np.where(np.isfinite(pasos), pasos, np.nanmedian(pasos) if np.any(np.isfinite(pasos)) else 0)
    s = np.concatenate([[0], np.cumsum(pasos)])
    return {"s_mm": np.round(s, 3).tolist(), "z_mm": [None if not np.isfinite(z) else round(float(z), 3) for z in Z]}


def histograma_plano(cat: str, pose: str, bins: int = 60) -> dict:
    """Histograma del error respecto al plano ajustado (solo plano) y sus estadísticas."""
    xyz = _xyz(cat, pose)
    if "E" not in xyz:
        raise FileNotFoundError("sin mapa de error (solo categoría plano)")
    e = xyz["E"][np.isfinite(xyz["E"])].astype(np.float64)
    lim = float(np.percentile(np.abs(e), 99.5)) or 1.0
    cuentas, bordes = np.histogram(np.clip(e, -lim, lim), bins=bins, range=(-lim, lim))
    return {"cuentas": cuentas.tolist(), "bordes": np.round(bordes, 4).tolist(), "n": int(e.size),
            "rms": float(np.sqrt(np.mean((e - e.mean()) ** 2))), "p95": float(np.percentile(np.abs(e), 95)),
            "max": float(np.max(np.abs(e)))}


# ------------------------------------------------------------------ comparar resultados
DIR_COMPARACIONES = cfg.DIR_RESULTADOS / "comparaciones"
RE_REF = re.compile(r"^(copia:\d{8}_\d{6}_\w+|pose:pose_\d+)$")


def guardar_comparacion(cat: str, pose: str) -> dict:
    """Copia el resultado actual de una pose (X, Y, Z, Mask, E) para compararlo después, p. ej. tras
    cambiar un ajuste (el reprocesado sobrescribe el resultado)."""
    import archivos

    origen = _archivos_pose(cat, pose)["reconstruida"]
    if not origen.exists():
        raise FileNotFoundError("esta pose aún no tiene reconstrucción")
    inv = next((p for p in inventario().get(cat, []) if p["pose"] == pose), {})
    ident = f"{time.strftime('%Y%m%d_%H%M%S')}_{cat}_{pose}"
    DIR_COMPARACIONES.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copyfile(origen, DIR_COMPARACIONES / f"{ident}.npz")
    meta = {"id": ident, "cat": cat, "pose": pose, "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "calculada_con": inv.get("calculada_con"), "puntos": inv.get("puntos"), "erms_mm": inv.get("erms_mm"),
            "nota": archivos.leer_notas().get(f"pose:{cat}/{pose}")}
    (DIR_COMPARACIONES / f"{ident}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def listar_comparaciones(cat: str) -> list[dict]:
    if not DIR_COMPARACIONES.is_dir():
        return []
    salida = []
    for ruta in sorted(DIR_COMPARACIONES.glob(f"*_{cat}_pose_*.json"), reverse=True):
        try:
            salida.append(json.loads(ruta.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return salida


def _ruta_referencia(cat: str, ref: str) -> Path:
    if not RE_REF.match(ref):
        raise ValueError("referencia inválida")
    tipo, valor = ref.split(":", 1)
    ruta = DIR_COMPARACIONES / f"{valor}.npz" if tipo == "copia" else _archivos_pose(cat, valor)["reconstruida"]
    if not ruta.exists():
        raise FileNotFoundError("la referencia no existe")
    return ruta


def diferencia_z(cat: str, pose: str, ref: str) -> tuple[np.ndarray, dict]:
    """Z(actual) − Z(referencia) en los píxeles válidos en ambos, y estadísticas de la comparación."""
    a, b = _xyz(cat, pose), cargar_npz(_ruta_referencia(cat, ref))
    ma = a["Mask"].astype(bool) & np.isfinite(a["Z"])
    mb = b["Mask"].astype(bool) & np.isfinite(b["Z"])
    comun = ma & mb
    dif = np.where(comun, a["Z"].astype(np.float64) - b["Z"].astype(np.float64), np.nan)
    d = dif[comun]
    stats = {"puntos_actual": int(ma.sum()), "puntos_ref": int(mb.sum()), "comunes": int(comun.sum()),
             "solo_actual": int((ma & ~mb).sum()), "solo_ref": int((mb & ~ma).sum())}
    if d.size:
        stats.update(media=float(d.mean()), rms=float(np.sqrt(np.mean(d ** 2))), p95=float(np.percentile(np.abs(d), 95)),
                     max=float(np.max(np.abs(d))))
    return dif, stats


def generar_nube(cat: str, pose: str, maximo: int) -> bytes:
    archivos = _archivos_pose(cat, pose)
    xyz = cargar_npz(archivos["reconstruida"])
    m = xyz["Mask"].astype(bool) & np.isfinite(xyz["Z"])
    idx = np.flatnonzero(m)
    if len(idx) > maximo:
        idx = np.sort(np.random.default_rng(0).choice(idx, maximo, replace=False))
    pts = np.column_stack([xyz[k].ravel()[idx] for k in ("X", "Y", "Z")]).astype("<f4")
    if archivos["absoluta"].exists():
        gris = cargar_npz(archivos["absoluta"])["Itex"].ravel()[idx].astype(np.uint8)
    else:
        gris = np.full(len(idx), 200, np.uint8)
    return np.uint32(len(idx)).tobytes() + pts.tobytes() + gris.tobytes()


# ==============================================================================
# Servidor HTTP
# ==============================================================================


def _distancia_tablero() -> tuple[float, float]:
    d = cfg.VALORES_ORIGINALES["PATRON_DISTANCIA_MM"]
    return (float(d), float(d)) if not isinstance(d, (tuple, list)) else (float(d[0]), float(d[1]))


def configuracion_por_defecto() -> dict:
    import pipeline as p

    return {
        "etapas": {**p.ETAPAS, "visualizacion": False},
        "categorias": p.CATEGORIAS,
        "captura": {"categoria": p.CAPTURA_CATEGORIA, "poses": p.CAPTURA_POSES,
                    "ciclos": p.CAPTURA_CICLOS, "esperar_enter": p.CAPTURA_ESPERAR_ENTER},
        "rehacer": p.REHACER, "fase": p.FASE_TRIANGULACION, "calibracion": p.CALIBRACION_USADA,
        "calib_poses": p.CALIBRACION_POSES,
        "parametros": {k: getattr(cfg, k) for k in (
            "PERIODO", "N_BITS_GRAY", "GAMMA_TH", "GAMMA_TH_Y", "SUAVIZADO_FASE_PX", "UMBRAL_INTENSIDAD",
            "MED_FILT", "BORDE_MASCARA", "ORDEN_BITS_GRAY", "SALTO_MAX_MM", "PLANO_UMBRAL_MM",
            "CAM_EXPOSICION_US", "PATRON_COLUMNAS", "PATRON_FILAS", "PATRON_DISTANCIA_MM", "Z_MIN_MM", "Z_MAX_MM")},
        "fuentes_demo": fuentes_demo(),
        "tablero_mm": list(_distancia_tablero()),
        "datos": str(cfg.DATOS),
    }


TIPOS_MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
              ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}


class Manejador(BaseHTTPRequestHandler):
    server_version = "TesisFranjas/1.0"

    def log_message(self, formato, *args):  # silencio: el registro útil va a la web
        pass

    # --- utilidades ---
    def _enviar(self, codigo: int, cuerpo: bytes, tipo: str, extra: dict | None = None) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, datos, codigo: int = 200) -> None:
        self._enviar(codigo, json.dumps(datos, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _error(self, codigo: int, mensaje: str) -> None:
        self._json({"error": mensaje}, codigo)

    def _cuerpo(self) -> dict:
        largo = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(largo) or b"{}")

    # --- rutas ---
    # --- seguridad: solo peticiones de la propia interfaz ---
    def _host_valido(self) -> bool:
        """Rechaza nombres de host ajenos (DNS rebinding): solo 127.0.0.1/localhost, salvo --host 0.0.0.0."""
        if getattr(self.server, "red_abierta", False):
            return True
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in ("127.0.0.1", "localhost", "::1")

    def _post_valido(self) -> bool:
        """Contra CSRF: una página ajena puede enviar un formulario a 127.0.0.1, pero no con
        Content-Type JSON sin permiso CORS (que este servidor nunca da), ni con un Origin ajeno."""
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return False
        origen = self.headers.get("Origin")
        return origen is None or urlparse(origen).netloc == self.headers.get("Host")

    def do_GET(self) -> None:
        if not self._host_valido():
            return self._error(403, "host no permitido")
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path in ("/", "/index.html"):
                return self._estatico("index.html")
            if url.path.startswith("/estatico/"):
                return self._estatico(url.path.removeprefix("/estatico/"))
            if url.path == "/api/config":
                return self._json(configuracion_por_defecto())
            if url.path == "/api/estado":
                import sesiones

                return self._json({"ejecucion": ejecucion.estado(), "calibracion": resumen_calibracion(),
                                   "poses": inventario(), "vigente": sesiones.info_vigente()})
            if url.path == "/api/eventos":
                return self._eventos()
            if url.path == "/api/vivo.jpg":
                if not ARCHIVO_VIVO.exists():
                    return self._error(404, "sin vista en vivo")
                return self._enviar(200, ARCHIVO_VIVO.read_bytes(), "image/jpeg")
            if url.path == "/api/imagen":
                return self._imagen(q)
            if url.path == "/api/punto":
                cat, pose = self._cat_pose(q)
                return self._json(punto_3d(cat, pose, float(q["fx"]), float(q["fy"])))
            if url.path == "/api/perfil":
                cat, pose = self._cat_pose(q)
                return self._json(perfil_3d(cat, pose, (float(q["ax"]), float(q["ay"])), (float(q["bx"]), float(q["by"]))))
            if url.path == "/api/comparaciones":
                cat = q.get("cat", "")
                if cat not in cfg.CATEGORIAS:
                    raise ValueError("categoría inválida")
                return self._json(listar_comparaciones(cat))
            if url.path == "/api/comparar":
                cat, pose = self._cat_pose(q)
                return self._json(diferencia_z(cat, pose, q.get("ref", ""))[1])
            if url.path == "/api/histograma":
                cat, pose = self._cat_pose(q)
                return self._json(histograma_plano(cat, pose))
            if url.path == "/api/descargar":
                return self._descargar(q)
            if url.path == "/api/ajustes":
                import ajustes

                return self._json(ajustes.leer())
            if url.path == "/api/sistema":
                return self._json(estado_sistema(q.get("hw", "1") == "1", q.get("forzar") == "1"))
            if url.path == "/api/manual":  # MANUAL.md, que la interfaz muestra con su índice
                return self._enviar(200, (RAIZ / "MANUAL.md").read_bytes(), "text/markdown; charset=utf-8")
            if url.path == "/api/calibraciones":
                import calibracion_estereo as ce
                import sesiones

                lista = ce.listar_calibraciones(DIR_CALIBRACION)
                for c in lista:
                    c["proceso"] = sesiones.proceso_de_poses("patron", c["poses"])
                return self._json(lista)
            if url.path == "/api/archivos":
                return self._json(listado_archivos())
            if url.path == "/api/captura/lista":
                import archivos

                return self._json([p.name for p in archivos.frames_captura(q.get("carpeta", ""))])
            if url.path == "/api/captura/imagen":
                import archivos

                return self._imagen(q, archivos.leer_frame(q.get("carpeta", ""), int(q.get("i", 0))), "intensidad")
            if url.path == "/api/calibracion":
                return self._json(errores_calibracion(q.get("variante", "independiente")))
            if url.path == "/api/nube":
                cat, pose = self._cat_pose(q)
                datos = generar_nube(cat, pose, int(q.get("max", 400_000)))
                return self._enviar(200, datos, "application/octet-stream")
            return self._error(404, "ruta desconocida")
        except FileNotFoundError as exc:
            return self._error(404, f"no disponible todavía: {exc}")
        except (ValueError, KeyError) as exc:
            return self._error(400, str(exc))
        except (OSError, EOFError, zipfile.BadZipFile) as exc:  # p. ej. .npz a medio escribir (versión vieja)
            return self._error(503, f"reintentar: {exc}")

    def do_POST(self) -> None:
        if not (self._host_valido() and self._post_valido()):
            return self._error(403, "petición rechazada: solo se aceptan peticiones JSON de la propia interfaz")
        url = urlparse(self.path)
        try:
            if url.path == "/api/ejecutar":
                ejecucion.lanzar(self._cuerpo())
                return self._json({"ok": True})
            if url.path == "/api/detener":
                ejecucion.detener()
                return self._json({"ok": True})
            if url.path == "/api/ajustes":  # los guarda la interfaz al cambiar cualquier ajuste
                import ajustes

                cuerpo = self._cuerpo()
                if not isinstance(cuerpo.get("efectivos"), dict):
                    raise ValueError("faltan los ajustes efectivos")
                ajustes.guardar({k: cuerpo.get(k) for k in ("efectivos", "valores", "selects")})
                return self._json({"ok": True})
            if url.path == "/api/camara":  # exposición en vivo: la aplica el ejecutor (VistaEnVivo)
                us = float(self._cuerpo().get("exposicion_us", 0))
                if not 50 <= us <= 1_000_000:
                    raise ValueError("exposición fuera de rango")
                dir_vivo = cfg.DIR_RESULTADOS / ".vivo"
                dir_vivo.mkdir(parents=True, exist_ok=True)
                tmp = dir_vivo / "control.tmp"
                tmp.write_text(json.dumps({"exposicion_us": us}), encoding="utf-8")
                tmp.replace(dir_vivo / "control.json")
                return self._json({"ok": True, "activa": ejecucion.estado()["ejecutando"]})
            if url.path == "/api/comparacion/guardar":
                cuerpo = self._cuerpo()
                cat, pose = self._cat_pose({k: str(v) for k, v in cuerpo.items()})
                return self._json(guardar_comparacion(cat, pose))
            if url.path == "/api/notas":
                import archivos

                cuerpo = self._cuerpo()
                archivos.guardar_nota(str(cuerpo.get("clave", "")), str(cuerpo.get("texto", "")))
                return self._json({"ok": True})
            if url.path in ("/api/archivos/borrar", "/api/archivos/vaciar_papelera", "/api/configuracion/elegir",
                            "/api/archivos/restaurar"):
                if ejecucion.estado()["ejecutando"]:
                    raise RuntimeError("hay un proceso en curso: espera a que termine")
                return self._json(self._post_archivos(url.path, self._cuerpo()))
            if url.path == "/api/calibraciones/activar":
                import calibracion_estereo as ce
                if ejecucion.estado()["ejecutando"]:
                    raise RuntimeError("hay un proceso en curso: espera a que termine para cambiar de calibración")
                ident = str(self._cuerpo().get("id", ""))
                try:
                    with _lock_errores:
                        elegida = ce.activar_calibracion(ident, DIR_CALIBRACION)
                except FileNotFoundError as exc:
                    return self._error(404, str(exc))
                # Se ven y procesan las poses de la configuración de la que salió esa calibración
                import sesiones

                proceso = sesiones.proceso_de_poses("patron", elegida["poses"])
                sesiones.fijar_configuracion(proceso)
                difusor.emitir("log", {"texto": f"[OK] Calibración en uso: {ident}. Configuración vigente: la "
                                                f"del proceso {proceso or '(última)'}. Las poses se "
                                                f"reconstruirán con ella en la próxima ejecución."})
                return self._json(elegida)
            if url.path == "/api/entrada":
                ejecucion.entrada(str(self._cuerpo().get("texto", "")))
                return self._json({"ok": True})
            return self._error(404, "ruta desconocida")
        except RuntimeError as exc:
            return self._error(409, str(exc))
        except FileNotFoundError as exc:
            return self._error(404, str(exc))
        except (ValueError, KeyError, OSError) as exc:
            return self._error(400, str(exc))

    def _descargar(self, q: dict) -> None:
        """Archivos para llevarse: la nube .ply, los puntos en .csv o el informe de la calibración."""
        tipo = q.get("tipo", "")
        if tipo == "calibracion":
            ruta = DIR_CALIBRACION / "Estereo_TSC_0_2.json"
            if not ruta.exists():
                raise FileNotFoundError("no hay calibración")
            return self._enviar(200, ruta.read_bytes(), "application/json; charset=utf-8",
                                {"Content-Disposition": f'attachment; filename="calibracion_{ruta.stat().st_mtime:.0f}.json"'})
        cat, pose = self._cat_pose(q)
        if tipo == "ply":
            ruta = DIR_RECONSTRUCCION / cat / f"{cat}_{pose}.ply"
            if not ruta.exists():
                raise FileNotFoundError("esta pose aún no tiene reconstrucción")
            return self._enviar(200, ruta.read_bytes(), "application/octet-stream",
                                {"Content-Disposition": f'attachment; filename="{ruta.name}"'})
        if tipo == "csv":
            xyz = _xyz(cat, pose)
            m = xyz["Mask"].astype(bool) & np.isfinite(xyz["Z"])
            filas, cols = np.nonzero(m)
            datos = np.column_stack([cols, filas, xyz["X"][m], xyz["Y"][m], xyz["Z"][m]])
            import io

            buf = io.StringIO()
            buf.write("columna,fila,X_mm,Y_mm,Z_mm\n")
            np.savetxt(buf, datos, fmt=["%d", "%d", "%.3f", "%.3f", "%.3f"], delimiter=",")
            return self._enviar(200, buf.getvalue().encode(), "text/csv; charset=utf-8",
                                {"Content-Disposition": f'attachment; filename="{cat}_{pose}_xyz.csv"'})
        raise ValueError("tipo de descarga desconocido")

    def _post_archivos(self, ruta: str, cuerpo: dict) -> dict:
        import archivos
        import calibracion_estereo as ce
        import sesiones

        if ruta == "/api/archivos/borrar":
            carpetas = [str(c) for c in cuerpo.get("carpetas", [])]
            if not carpetas:
                raise ValueError("no se indicó qué borrar")
            with _lock_npz, _lock_errores:
                res = archivos.mover_a_papelera(carpetas)
                _cache_mapas.limpiar()
                _cache_errores.clear()
            difusor.emitir("log", {"texto": f"[OK] {len(carpetas)} captura(s) movidas a la papelera "
                                            f"({res['elementos']} elementos): {res['papelera']}"})
            return res
        if ruta == "/api/archivos/restaurar":
            with _lock_npz, _lock_errores:
                res = archivos.restaurar(str(cuerpo.get("lote", "")))
                _cache_mapas.limpiar()
                _cache_errores.clear()
            texto = f"[OK] Restaurado de la papelera: {res['devueltos']} elementos"
            if res["conflictos"]:
                texto += f" · [AVISO] {len(res['conflictos'])} ya existían y quedaron en la papelera"
            difusor.emitir("log", {"texto": texto})
            return res
        if ruta == "/api/archivos/vaciar_papelera":
            res = archivos.vaciar_papelera()
            difusor.emitir("log", {"texto": f"[OK] Papelera vaciada ({res['bytes'] / 1e6:.0f} MB liberados)."})
            return res
        # Elegir configuración: None = la última. Si hay una calibración hecha con sus poses, se pone en uso
        proceso = cuerpo.get("proceso") or None
        sesiones.fijar_configuracion(proceso)
        conf = sesiones.configuracion_vigente()
        objetivo = conf["proceso"] if conf else None  # también al volver a la última
        calib = None
        if objetivo:
            for c in ce.listar_calibraciones(DIR_CALIBRACION):  # de la más reciente a la más antigua
                if sesiones.proceso_de_poses("patron", c["poses"]) == objetivo:
                    calib = c["id"]
                    if not c["activa"]:
                        with _lock_errores:
                            ce.activar_calibracion(calib, DIR_CALIBRACION)
                    break
        texto = f"[OK] Configuración vigente: {'la última' if not proceso else 'desde ' + proceso}"
        if calib:
            texto += f" · calibración en uso: {calib}"
        elif objetivo:
            texto += " · [AVISO] ninguna calibración del historial salió de este proceso: calibra con él"
        difusor.emitir("log", {"texto": texto})
        return {"proceso": conf and conf["proceso"], "calibracion": calib}

    def _cat_pose(self, q: dict) -> tuple[str, str]:
        cat, pose = q.get("cat", ""), q.get("pose", "")
        if cat not in cfg.CATEGORIAS or not RE_POSE.match(pose):
            raise ValueError("categoría o pose inválida")
        return cat, pose

    def _estatico(self, nombre: str) -> None:
        ruta = (DIR_ESTATICO / nombre).resolve()
        if DIR_ESTATICO not in ruta.parents or not ruta.is_file():
            return self._error(404, "no encontrado")
        self._enviar(200, ruta.read_bytes(), TIPOS_MIME.get(ruta.suffix, "application/octet-stream"))

    def _imagen(self, q: dict, img: np.ndarray | None = None, escala: str = "") -> None:
        if img is None:
            cat, pose = self._cat_pose(q)
            img, escala = generar_imagen(cat, pose, q.get("tipo", ""))
        ancho = max(64, min(int(q.get("ancho", 900)), 2000))
        if img.shape[1] > ancho:
            f = ancho / img.shape[1]
            img = cv2.resize(img, (0, 0), fx=f, fy=f, interpolation=cv2.INTER_AREA)
        if img.dtype != np.uint8:
            img = np.clip(img, 0, 255).astype(np.uint8)
        # JPEG para mapas continuos y ruidosos (≈10x más liviano que PNG); PNG para la máscara (colores planos)
        tipo = q.get("tipo", "")
        ext, mime, params = (".png", "image/png", []) if tipo == "mascara" else (
            ".jpg", "image/jpeg", [cv2.IMWRITE_JPEG_QUALITY, 90])
        ok, datos = cv2.imencode(ext, img, params)
        if not ok:
            raise OSError("no se pudo codificar la imagen")
        self._enviar(200, datos.tobytes(), mime,
                     {"X-Escala": quote(escala),
                      "Access-Control-Expose-Headers": "X-Escala"})

    def _eventos(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = difusor.suscribir()
        try:
            self._sse("estado", ejecucion.estado())
            while True:
                try:
                    evento, datos = q.get(timeout=15)
                    self._sse(evento, datos)
                except queue.Empty:
                    self.wfile.write(b": latido\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            difusor.desuscribir(q)

    def _sse(self, evento: str, datos: dict) -> None:
        self.wfile.write(f"event: {evento}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n".encode())
        self.wfile.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="Interfaz web del sistema de proyección de franjas.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="127.0.0.1 = solo este equipo (por defecto); 0.0.0.0 = toda la red, sin autenticación")
    parser.add_argument("--puerto", type=int, default=8000)
    parser.add_argument("--sin-navegador", action="store_true", help="No abrir el navegador automáticamente")
    args = parser.parse_args()

    threading.Thread(target=vigilar, daemon=True).start()
    servidor = ThreadingHTTPServer((args.host, args.puerto), Manejador)
    servidor.daemon_threads = True
    servidor.red_abierta = args.host not in ("127.0.0.1", "localhost", "::1")
    url = f"http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{args.puerto}"
    print(f"[OK] Interfaz en {url}  (datos: {cfg.DATOS})  — Ctrl+C para salir")
    if args.host == "0.0.0.0":
        print("[AVISO] Accesible desde la red sin contraseña: cualquiera en la red puede lanzar capturas.")
    if not args.sin_navegador:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando…")
    finally:
        ejecucion.detener()
        servidor.server_close()


if __name__ == "__main__":
    main()
