"""Ejecuta el pipeline en un subproceso con la configuración que envía la interfaz web.

Uso (lo lanza `servidor.py`; no hace falta correrlo a mano):
    python interfaz/ejecutor.py <config.json>

El JSON puede tener:
    etapas       {"captura": true, ...}        sobrescribe pipeline.ETAPAS
    categorias   ["plano", "objeto"]
    captura      {"categoria", "poses", "ciclos", "esperar_enter"}
    rehacer, fase, calibracion
    calib_poses  "ultima_sesion", "todas" o ["pose_08", ...]  (poses del patrón que calibran)
    simular      ruta de una captura existente para usar la cámara simulada (o null)

La vista en vivo de la cámara se escribe en `<resultados>/.vivo/frame.jpg` como máximo ~6 veces por
segundo, desde un hilo aparte para no retrasar la adquisición. Las líneas que empiezan con `@@` son
mensajes para el servidor (estado de la captura en vivo), no para el usuario.
"""

from __future__ import annotations

import builtins
import json
import os
import signal
from collections import deque
import sys
import threading
import time
from functools import partial
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import matplotlib  # noqa: E402

matplotlib.use("Agg")  # la interfaz web reemplaza a las ventanas de matplotlib

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import configuracion as cfg  # noqa: E402
import pipeline  # noqa: E402

DIR_VIVO = cfg.DIR_RESULTADOS / ".vivo"


class VistaEnVivo:
    """Escribe como JPEG lo que ve la cámara, desde un hilo y a cadencia limitada.

    Dos modos:
    - captura (`__call__(indice, frame)`): el último frame de la secuencia de 50 patrones, con su
      número de frame (mensaje `@@vivo i n`).
    - vista previa (`previa(frame)`): mientras se encuadra el objeto. Como el proyector sigue
      ciclando patrones, cada frame tiene franjas distintas; se muestra un promedio móvil, que da
      una imagen estable y uniformemente iluminada. También se mide la fracción de píxeles
      saturados (mensaje `@@previa saturacion`), útil para ajustar la exposición.
    """

    def __init__(self, total: int, intervalo_s: float = 0.15, alfa: float = 0.08) -> None:
        self.nitidez: deque[float] = deque(maxlen=cfg.IMAGENES_POR_CICLO)
        # Detección del tablero en la vista previa (solo si se va a capturar el patrón): ~1 vez/s
        self.buscar_tablero = False
        self.tablero_t = 0.0
        self.tablero: int | None = None
        self.n_previa = 0  # frames acumulados en el promedio de la vista previa
        try:  # un control.json viejo (de otra sesión) no se aplica
            self.control_m: float | None = (DIR_VIVO / "control.json").stat().st_mtime
        except OSError:
            self.control_m = None
        # alfa = 0.08: promedio de ~25 frames (~1.7 s a 15 fps), suficiente para que las franjas
        # del proyector se borren; el objeto tarda ese tiempo en "asentarse" al moverlo.
        self.total = total
        self.intervalo_s = intervalo_s
        self.alfa = alfa
        self.ultimo: tuple[str, int, object] | None = None
        self.version = 0
        self.escrita = -1
        self.media: np.ndarray | None = None
        # Fracción saturada de los últimos frames: el máximo cubre un ciclo completo de 50
        # patrones, que es cuando aparece el blanco (el que más satura)
        self.saturados: deque[float] = deque(maxlen=cfg.IMAGENES_POR_CICLO)
        DIR_VIVO.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=self._bucle, daemon=True).start()

    def __call__(self, indice: int, frame) -> None:
        self.media = None
        self.n_previa = 0
        self.ultimo = ("captura", indice, frame)  # solo asignaciones: no frena la captura
        self.version += 1

    def previa(self, frame) -> None:
        f8 = frame if frame.dtype == np.uint8 else (frame >> 8).astype(np.uint8)
        f = f8.astype(np.float32)
        self.n_previa += 1
        if self.media is None or self.media.shape != f.shape:
            self.media = f
            self.n_previa = 1
        else:
            cv2.accumulateWeighted(f, self.media, self.alfa)  # media ← (1-α)·media + α·frame
        muestra = f8[::4, ::4]
        self.saturados.append(float(np.count_nonzero(muestra >= 250)) / muestra.size)
        # Nitidez: varianza del laplaciano en el centro del frame crudo (con franjas). Se toma el
        # máximo de un ciclo, cuando se proyectan las franjas más finas: sube al enfocar
        alto, ancho = f8.shape[:2]
        centro = f8[alto // 4: 3 * alto // 4: 2, ancho // 4: 3 * ancho // 4: 2]
        self.nitidez.append(float(cv2.Laplacian(centro, cv2.CV_32F).var()))
        self.ultimo = ("previa", 0, self.media)
        self.version += 1

    @staticmethod
    def _detectar_tablero(img_mitad: np.ndarray) -> int:
        """Círculos del tablero detectados en la vista previa (0 si no se encuentra la grilla).

        Se busca sobre la imagen promediada (iluminación uniforme) llevada a resolución completa,
        porque el detector está ajustado al tamaño real de los círculos."""
        from calibracion_estereo import detectar_puntos_tablero

        completa = cv2.resize(img_mitad, (0, 0), fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
        try:
            puntos = detectar_puntos_tablero(completa, (cfg.PATRON_COLUMNAS, cfg.PATRON_FILAS),
                                             cfg.PATRON_TIPO, cfg.PATRON_COLOR_CIRCULOS)
            return len(puntos)
        except RuntimeError:
            return 0

    def _aplicar_control(self) -> None:
        """La interfaz deja en `.vivo/control.json` la exposición pedida; se aplica a la cámara abierta."""
        ruta = DIR_VIVO / "control.json"
        try:
            m = ruta.stat().st_mtime
        except OSError:
            return
        if m == self.control_m:
            return
        self.control_m = m
        import capturar_patrones as cp

        try:
            pedido = json.loads(ruta.read_text(encoding="utf-8"))
            if cp.camara_activa is not None and pedido.get("exposicion_us"):
                aplicada = cp.camara_activa.fijar_exposicion(float(pedido["exposicion_us"]))
                cfg.CAM_EXPOSICION_US = aplicada  # también para las poses que siguen
                sys.stdout.write(f"\n@@exposicion {aplicada:.0f}\n")
                sys.stdout.flush()
        except Exception as exc:  # noqa: BLE001
            sys.stdout.write(f"\n[AVISO] No se pudo cambiar la exposición: {exc}\n")
            sys.stdout.flush()

    def _bucle(self) -> None:
        while True:
            time.sleep(self.intervalo_s)
            self._aplicar_control()
            dato, version = self.ultimo, self.version
            if dato is None or version == self.escrita:
                continue
            modo, indice, frame = dato
            img = np.clip(frame, 0, 255).astype(np.uint8) if frame.dtype != np.uint8 else frame
            img = cv2.resize(img, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
            tmp = DIR_VIVO / "frame_tmp.jpg"
            cv2.imwrite(str(tmp), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            os.replace(tmp, DIR_VIVO / "frame.jpg")  # reemplazo atómico: el navegador nunca lee a medias
            self.escrita = version
            # Una sola escritura con salto de línea incluido: print() escribe el texto y el "\n"
            # por separado, y otro hilo podría intercalarse y pegar el mensaje a su línea
            if modo == "captura":
                mensaje = f"@@vivo {indice + 1} {self.total}\n"
            else:
                # Solo con el promedio ya estable (~30 frames): un frame suelto tiene franjas encima
                if self.buscar_tablero and self.n_previa >= 30 and time.time() - self.tablero_t > 1.0:
                    self.tablero_t = time.time()
                    self.tablero = self._detectar_tablero(img)
                tablero = "" if self.tablero is None else f" {self.tablero}"
                mensaje = (f"@@previa {max(self.saturados, default=0.0):.4f} "
                           f"{max(self.nitidez, default=0.0):.1f}{tablero}\n")
            sys.stdout.write("\n" + mensaje)
            sys.stdout.flush()


# Los ajustes de la interfaz se aplican con el módulo compartido `ajustes` (también lo usa pipeline.py)
def aplicar_ajustes(efectivos: dict) -> list[str]:
    import ajustes

    return ajustes.aplicar(efectivos)


def configurar(conf: dict) -> None:
    p = pipeline
    cambios = aplicar_ajustes(conf.get("ajustes") or {})
    p.AJUSTES_APLICADOS = True  # pipeline.main() no vuelve a leer ajustes.json
    if cambios:
        print(f"[AJUSTES] Distintos de configuracion.py: {', '.join(cambios)}", flush=True)
    for etapa, activa in conf.get("etapas", {}).items():
        if etapa in p.ETAPAS:
            p.ETAPAS[etapa] = bool(activa)
    p.ETAPAS["visualizacion"] = False  # la visualización la hace la web
    if conf.get("categorias"):
        p.CATEGORIAS = list(conf["categorias"])
    cap = conf.get("captura", {})
    p.CAPTURA_CATEGORIA = cap.get("categoria", p.CAPTURA_CATEGORIA)
    p.CAPTURA_POSES = int(cap.get("poses", p.CAPTURA_POSES))
    p.CAPTURA_CICLOS = int(cap.get("ciclos", p.CAPTURA_CICLOS))
    p.CAPTURA_ESPERAR_ENTER = bool(cap.get("esperar_enter", p.CAPTURA_ESPERAR_ENTER))
    p.CAPTURA_NOMBRE = str(cap.get("nombre") or "").strip()[:80] or None
    if cap.get("plan"):  # varias categorías en una sesión: {"patron": 12, "plano": 3, "objeto": 1}
        p.CAPTURA_PLAN = {c: int(n) for c, n in cap["plan"].items()}
    p.REHACER = bool(conf.get("rehacer", p.REHACER))
    p.FASE_TRIANGULACION = conf.get("fase", p.FASE_TRIANGULACION)
    p.CALIBRACION_USADA = conf.get("calibracion", p.CALIBRACION_USADA)
    p.CALIBRACION_POSES = conf.get("calib_poses", p.CALIBRACION_POSES)
    if conf.get("seleccion"):
        # Selección manual de poses (pestaña Calibración): pasa a ser la configuración en uso, así las
        # etapas procesan exactamente esas poses y la calibración usa esas del patrón
        import sesiones

        sesiones.fijar_seleccion(conf["seleccion"])
        patron = conf["seleccion"].get("patron") or []
        if patron:
            p.CALIBRACION_POSES = list(patron)
        print("[PIPELINE] Selección manual: " + ", ".join(
            f"{c} {len(v)}" for c, v in conf["seleccion"].items() if v), flush=True)

    # Captura: vista en vivo y, opcionalmente, cámara simulada
    import capturar_patrones as cp

    vista = VistaEnVivo(cfg.IMAGENES_POR_CICLO * max(p.CAPTURA_CICLOS, 1))
    vista.buscar_tablero = "patron" in (p.CAPTURA_PLAN or {p.CAPTURA_CATEGORIA: p.CAPTURA_POSES})
    extra: dict = {"al_frame": vista, "al_previa": vista.previa}
    simular = conf.get("simular")
    if simular and p.ETAPAS.get("captura"):
        extra["camara"] = cp.CamaraSimulada(cfg.DIR_CAPTURAS / simular)
        extra["sufijo"] = "_simulada"
    cp.capturar_poses = partial(cp.capturar_poses, **extra)


def solo_vista_previa(conf: dict) -> None:
    """Abre la cámara y transmite la vista previa hasta que el usuario la cierra (Enter)."""
    import capturar_patrones as cp

    print("# ETAPA: previa", flush=True)
    vista = VistaEnVivo(cfg.IMAGENES_POR_CICLO)
    simular = conf.get("simular")
    try:
        camara = cp.CamaraSimulada(cfg.DIR_CAPTURAS / simular) if simular else cp.CamaraFLIR()
        with camara:
            camara.iniciar_vista_previa(vista.previa)
            try:
                input("Vista previa de la cámara activa: pulsa Enter para cerrar: ")
            finally:
                camara.detener_vista_previa()
    except KeyboardInterrupt:
        pass  # «Detener» desde la interfaz: la cámara ya se cerró al salir del `with`
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] No se pudo abrir la vista previa: {exc}\n"
              f"        Posibles causas y soluciones: MANUAL.md §16.3 (o ejecuta .env/bin/python verificar.py)",
              flush=True)
        raise SystemExit(1) from None
    print("[OK] Vista previa cerrada.", flush=True)


def _input_marcado(prompt: str = "") -> str:
    """Reemplaza a `input()`: anuncia la pregunta al servidor con una línea `@@pregunta …`.

    Así la interfaz sabe que el proceso espera una respuesta sin tener que reconocer frases
    concretas del texto (que podrían cambiar)."""
    sys.stdout.write(f"\n@@pregunta {prompt.strip()}\n")
    sys.stdout.flush()
    linea = sys.stdin.readline()
    if not linea:
        raise EOFError
    return linea.rstrip("\n")


def _al_detener(_senal, _marco) -> None:
    """«Detener» de la interfaz envía SIGTERM. Por defecto Python moriría sin ejecutar los
    `finally`/`with` y la cámara quedaría abierta (sin DeInit). Se convierte en una interrupción
    normal para que todo se cierre bien."""
    raise KeyboardInterrupt


def importar_y_elegir(opciones: dict) -> None:
    """Importa una carpeta de capturas como proceso nuevo y lo deja como configuración en uso, para
    que las etapas siguientes procesen exactamente esas capturas (pestaña Archivos → Importar)."""
    import importar
    import sesiones

    print("# ETAPA: importar", flush=True)
    print(f"[INFO] Importando {opciones['ruta']}", flush=True)
    try:
        res = importar.importar(opciones["ruta"], opciones.get("nombre") or None, bool(opciones.get("mover")))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"[ERROR] No se pudo importar: {exc}") from None
    # Solo este proceso: sus capturas pueden ser de fechas en medio de otros procesos
    sesiones.fijar_solo_proceso(res["proceso"])
    print(f"[PIPELINE] Configuración en uso: solo el proceso importado {res['proceso']}", flush=True)


def main() -> None:
    signal.signal(signal.SIGTERM, _al_detener)
    builtins.input = _input_marcado
    os.environ["TESIS_MARCAS_AVANCE"] = "1"  # avance.py: marcas @@avance para la barra de progreso
    os.environ["TESIS_INTERACTIVO"] = "1"  # organizar puede preguntar (la interfaz muestra botones)
    conf = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if conf.get("solo_previa"):
        solo_vista_previa(conf)
        return
    try:
        if conf.get("importar"):
            importar_y_elegir(conf["importar"])
        configurar(conf)
        pipeline.main()
    except SystemExit as exc:
        if isinstance(exc.code, str):  # pipeline.main() sale con un mensaje de texto
            print(exc.code, flush=True)
        sys.stdout.flush()
        raise SystemExit(exc.code if isinstance(exc.code, int) else 1) from None


if __name__ == "__main__":
    main()
