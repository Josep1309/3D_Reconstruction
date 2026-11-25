"""Captura secuencias completas de patrones con una Blackfly S usando el trigger externo.

La cámara debe estar conectada al mismo pulso del Arduino que el proyector. No hace falta alinear
el primer patrón: se capturan los siguientes `IMAGENES_POR_CICLO` pulsos (o varios ciclos) y
`organizar_capturas.py` detecta el par negro -> blanco para reordenar la secuencia.

Cada pose se guarda en `capturas/<categoria>/<AAAAMMDD_HHMMSS>/` como `<categoria>_frame_XX.tiff`
(y opcionalmente un `.avi` FFV1 sin pérdida).

Ejemplos:
    python capturar_patrones.py --categoria patron --poses 10   # pide Enter antes de cada pose
    python capturar_patrones.py --categoria objeto --ciclos 2
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

import configuracion as cfg

AlFrame = Callable[[int, np.ndarray], None]
AlPrevia = Callable[[np.ndarray], None]

# Cámara abierta en este momento (la usa la interfaz para cambiar la exposición en vivo)
camara_activa: "CamaraFLIR | CamaraSimulada | None" = None


class CamaraFLIR:
    """Blackfly S configurada con trigger externo en Line0 (se usa con `with`)."""

    def __init__(
        self,
        exposicion_us: float | None = None,
        debounce_us: float = cfg.CAM_DEBOUNCE_US,
        trigger_delay_us: float | None = cfg.CAM_TRIGGER_DELAY_US,
        timeout_ms: int = cfg.CAM_TIMEOUT_MS,
        indice: int = 0,
    ) -> None:
        import PySpin  # solo se necesita al capturar

        self.ps = PySpin
        # None = la de configuracion.py en el momento de abrir (la interfaz puede haberla cambiado)
        self.exposicion_us = cfg.CAM_EXPOSICION_US if exposicion_us is None else exposicion_us
        self.debounce_us = debounce_us
        self.trigger_delay_us = trigger_delay_us
        self.timeout_ms = timeout_ms
        self.indice = indice
        self.system = None
        self.cameras = None
        self.camera = None
        self._hilo_previa: threading.Thread | None = None
        self._previa_activa = False

    def __enter__(self) -> CamaraFLIR:
        ps = self.ps
        self.system = ps.System.GetInstance()
        self.cameras = self.system.GetCameras()
        if self.cameras.GetSize() <= self.indice:
            self.__exit__(None, None, None)
            raise RuntimeError("No se encontró ninguna cámara FLIR")
        self.camera = self.cameras.GetByIndex(self.indice)
        self.camera.Init()
        self._configurar_trigger()
        global camara_activa
        camara_activa = self
        return self

    def fijar_exposicion(self, exposicion_us: float) -> float:
        """Cambia la exposición (también durante la vista previa). Devuelve el valor aplicado."""
        cam = self.camera
        valor = min(max(float(exposicion_us), cam.ExposureTime.GetMin()), cam.ExposureTime.GetMax())
        cam.ExposureTime.SetValue(valor)
        self.exposicion_us = valor
        return cam.ExposureTime.GetValue()

    def __exit__(self, exc_type, exc, tb) -> None:
        global camara_activa
        camara_activa = None
        self.detener_vista_previa()
        if self.camera is not None:
            try:
                if self.camera.IsStreaming():
                    self.camera.EndAcquisition()
                if self.camera.TriggerMode.GetAccessMode() == self.ps.RW:
                    self.camera.TriggerMode.SetValue(self.ps.TriggerMode_Off)
                self.camera.DeInit()
            finally:
                del self.camera
                self.camera = None
        if self.cameras is not None:
            self.cameras.Clear()
            self.cameras = None
        if self.system is not None:
            self.system.ReleaseInstance()
            self.system = None

    def _configurar_trigger(self) -> None:
        """Exposición fija, filtro antirrebotes y trigger por flanco de subida sin solapamiento."""
        ps, cam = self.ps, self.camera
        if cam.TriggerMode.GetAccessMode() != ps.RW:
            raise RuntimeError("TriggerMode no es escribible")
        cam.TriggerMode.SetValue(ps.TriggerMode_Off)

        if cam.ExposureAuto.GetAccessMode() == ps.RW:
            cam.ExposureAuto.SetValue(ps.ExposureAuto_Off)
        if cam.ExposureTime.GetAccessMode() != ps.RW:
            raise RuntimeError("ExposureTime no es escribible")
        cam.ExposureTime.SetValue(
            min(max(self.exposicion_us, cam.ExposureTime.GetMin()), cam.ExposureTime.GetMax())
        )

        # Filtro de Debounce en Line0 para evitar disparos múltiples por ruido
        if cam.LineSelector.GetAccessMode() == ps.RW:
            cam.LineSelector.SetValue(ps.LineSelector_Line0)
            if cam.LineInputFilterSelector.GetAccessMode() == ps.RW:
                cam.LineInputFilterSelector.SetValue(ps.LineInputFilterSelector_Debounce)
            if cam.LineFilterWidth.GetAccessMode() == ps.RW:
                cam.LineFilterWidth.SetValue(
                    min(max(self.debounce_us, cam.LineFilterWidth.GetMin()), cam.LineFilterWidth.GetMax())
                )

        cam.TriggerSelector.SetValue(ps.TriggerSelector_FrameStart)
        cam.TriggerSource.SetValue(ps.TriggerSource_Line0)
        if cam.TriggerActivation.GetAccessMode() == ps.RW:
            cam.TriggerActivation.SetValue(ps.TriggerActivation_RisingEdge)
        if self.trigger_delay_us is not None and cam.TriggerDelay.GetAccessMode() == ps.RW:
            cam.TriggerDelay.SetValue(
                min(max(self.trigger_delay_us, cam.TriggerDelay.GetMin()), cam.TriggerDelay.GetMax())
            )
        # Evitar que se encolen triggers espurios durante la exposición
        if cam.TriggerOverlap.GetAccessMode() == ps.RW:
            cam.TriggerOverlap.SetValue(ps.TriggerOverlap_Off)

        # Entregar los frames en orden de llegada
        handling = ps.CEnumerationPtr(cam.GetTLStreamNodeMap().GetNode("StreamBufferHandlingMode"))
        if ps.IsAvailable(handling) and ps.IsWritable(handling):
            handling.SetIntValue(handling.GetEntryByName("OldestFirst").GetValue())

        cam.AcquisitionMode.SetValue(ps.AcquisitionMode_Continuous)
        cam.TriggerMode.SetValue(ps.TriggerMode_On)
        print(f"[OK] Cámara lista | exposición {cam.ExposureTime.GetValue():.0f} us | trigger Line0")

    def capturar(self, cantidad: int, al_frame: AlFrame | None = None) -> list[np.ndarray]:
        """Captura `cantidad` frames consecutivos a partir del siguiente pulso de trigger.

        `al_frame(indice, frame)` se llama con cada frame recibido (p. ej. para la vista en vivo de
        la interfaz web). Debe ser instantáneo: si tarda, se pierden triggers.
        """
        cam = self.camera
        frames: list[np.ndarray] = []
        tiempos: list[float] = []
        cam.BeginAcquisition()
        try:
            for indice in range(cantidad):
                try:
                    image = cam.GetNextImage(self.timeout_ms)
                except self.ps.SpinnakerException as exc:
                    raise RuntimeError(
                        f"Sin trigger tras {self.timeout_ms} ms en el frame {indice}: "
                        f"¿está encendido el Arduino y conectado Line0? ({exc})"
                    ) from exc
                try:
                    if image.IsIncomplete():
                        raise RuntimeError(f"Frame {indice} incompleto: {image.GetImageStatus()}")
                    frames.append(np.array(image.GetNDArray(), copy=True))
                    tiempos.append(time.perf_counter())
                    if al_frame is not None:
                        al_frame(indice, frames[-1])
                finally:
                    image.Release()
        finally:
            cam.EndAcquisition()

        _reportar_tiempos(tiempos)
        return frames

    # ------------------------------------------------------------------ vista previa
    def iniciar_vista_previa(self, al_frame: AlPrevia, fps: float = 15.0) -> None:
        """Adquisición continua SIN trigger mientras se encuadra el objeto (no depende del Arduino).

        Cada frame se entrega a `al_frame(frame)` desde un hilo. `detener_vista_previa()` vuelve a
        dejar la cámara con el trigger externo, lista para `capturar()`.
        """
        if self._hilo_previa is not None:
            return
        ps, cam = self.ps, self.camera
        cam.TriggerMode.SetValue(ps.TriggerMode_Off)
        try:  # limitar la cadencia: no hace falta más para encuadrar
            if cam.AcquisitionFrameRateEnable.GetAccessMode() == ps.RW:
                cam.AcquisitionFrameRateEnable.SetValue(True)
                cam.AcquisitionFrameRate.SetValue(
                    min(max(fps, cam.AcquisitionFrameRate.GetMin()), cam.AcquisitionFrameRate.GetMax())
                )
        except ps.SpinnakerException:
            pass
        cam.BeginAcquisition()
        self._previa_activa = True

        def bucle() -> None:
            while self._previa_activa:
                try:
                    imagen = cam.GetNextImage(300)
                except ps.SpinnakerException:
                    continue
                try:
                    if not imagen.IsIncomplete():
                        al_frame(np.array(imagen.GetNDArray(), copy=True))
                finally:
                    imagen.Release()

        self._hilo_previa = threading.Thread(target=bucle, daemon=True)
        self._hilo_previa.start()

    def detener_vista_previa(self) -> None:
        """Detiene la vista previa y restaura el trigger externo (y la cadencia libre)."""
        if self._hilo_previa is None:
            return
        ps, cam = self.ps, self.camera
        self._previa_activa = False
        self._hilo_previa.join(timeout=2.0)
        self._hilo_previa = None
        try:
            if cam.IsStreaming():
                cam.EndAcquisition()
            # Con la cadencia limitada a 15 fps se perderían triggers del Arduino (20 Hz)
            if cam.AcquisitionFrameRateEnable.GetAccessMode() == ps.RW:
                cam.AcquisitionFrameRateEnable.SetValue(False)
        except ps.SpinnakerException:
            pass
        cam.TriggerMode.SetValue(ps.TriggerMode_On)


def _reportar_tiempos(tiempos: list[float]) -> None:
    if len(tiempos) > 2:
        dt = np.diff(tiempos) * 1000.0
        print(f"    Δt entre frames: mediana {np.median(dt):.1f} ms, máx {dt.max():.1f} ms")
        if dt.max() > 1.5 * np.median(dt):
            print("    [AVISO] posible pulso perdido; el organizador lo detectará y separará los ciclos.")


class CamaraSimulada:
    """Sustituto de `CamaraFLIR` para probar sin hardware (modo demo de la interfaz web).

    Reproduce en bucle los frames de una captura existente (una carpeta de `capturas/`), a la
    cadencia del Arduino y empezando en un patrón al azar, igual que la cámara real.
    """

    def __init__(self, carpeta: Path, periodo_s: float = 0.05) -> None:
        import organizar_capturas as oc

        fuentes = oc.descubrir_fuentes([Path(carpeta)])
        if not fuentes:
            raise FileNotFoundError(f"No hay imágenes ni videos para simular en '{carpeta}'")
        self.frames = oc.cargar_frames(fuentes[0])
        self.periodo_s = periodo_s
        self.inicio = int(np.random.default_rng().integers(len(self.frames)))
        self.ganancia = 1.0  # simula la exposición: frames × (exposición / exposición original)
        print(f"[OK] Cámara SIMULADA con {len(self.frames)} frames de '{carpeta}'")

    def __enter__(self) -> CamaraSimulada:
        global camara_activa
        camara_activa = self
        self.fijar_exposicion(cfg.CAM_EXPOSICION_US)  # la elegida en Ajustes
        return self

    def __exit__(self, *_exc) -> None:
        global camara_activa
        camara_activa = None

    def fijar_exposicion(self, exposicion_us: float) -> float:
        self.ganancia = float(exposicion_us) / cfg.VALORES_ORIGINALES["CAM_EXPOSICION_US"]
        return float(exposicion_us)

    def _frame(self, i: int) -> np.ndarray:
        f = self.frames[i % len(self.frames)]
        if self.ganancia == 1.0:
            return f.copy()
        return np.clip(f.astype(np.float32) * self.ganancia, 0, 255 if f.dtype == np.uint8 else 65535).astype(f.dtype)

    def capturar(self, cantidad: int, al_frame: AlFrame | None = None) -> list[np.ndarray]:
        frames, tiempos = [], []
        for indice in range(cantidad):
            time.sleep(self.periodo_s)
            frames.append(self._frame(self.inicio + indice))
            tiempos.append(time.perf_counter())
            if al_frame is not None:
                al_frame(indice, frames[-1])
        self.inicio = (self.inicio + cantidad) % len(self.frames)
        _reportar_tiempos(tiempos)
        return frames

    def iniciar_vista_previa(self, al_frame: AlPrevia, fps: float = 15.0) -> None:
        self._previa_activa = True

        def bucle() -> None:
            i = self.inicio
            while self._previa_activa:
                time.sleep(1.0 / fps)
                al_frame(self._frame(i))
                i += 1

        self._hilo_previa = threading.Thread(target=bucle, daemon=True)
        self._hilo_previa.start()

    def detener_vista_previa(self) -> None:
        if getattr(self, "_hilo_previa", None) is not None:
            self._previa_activa = False
            self._hilo_previa.join(timeout=2.0)
            self._hilo_previa = None


def escribir_video(frames: list[np.ndarray], ruta: Path, fps: float = 20.0) -> bool:
    """Escribe un AVI sin pérdida (FFV1). Devuelve False si el códec no está disponible."""
    alto, ancho = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(ruta), cv2.VideoWriter.fourcc(*"FFV1"), fps, (ancho, alto), isColor=False)
    if not writer.isOpened():
        return False
    try:
        for frame in frames:
            writer.write(frame if frame.dtype == np.uint8 else (frame >> 8).astype(np.uint8))
    finally:
        writer.release()
    return True


def guardar_captura(
    frames: list[np.ndarray], salida: Path, categoria: str, video: bool = cfg.GUARDAR_VIDEO, sufijo: str = ""
) -> Path:
    """Guarda los frames en `<salida>/<categoria>/<fecha><sufijo>/` y devuelve la carpeta."""
    carpeta = salida / categoria / (datetime.now().strftime("%Y%m%d_%H%M%S") + sufijo)
    while carpeta.exists():  # dos capturas en el mismo segundo
        carpeta = carpeta.with_name(carpeta.name + "_b")
    carpeta.mkdir(parents=True)
    for indice, frame in enumerate(frames):
        ruta = carpeta / f"{categoria}_frame_{indice:03d}.tiff"
        if not cv2.imwrite(str(ruta), frame):
            raise OSError(f"No se pudo guardar {ruta}")
    if video and not escribir_video(frames, carpeta / f"captura_{len(frames)}_frames.avi"):
        print("    [AVISO] códec FFV1 no disponible: solo se guardaron los .tiff")
    return carpeta


def preguntar(texto: str, **meta) -> str:
    """`input()` con datos para la interfaz web: antes de la pregunta imprime `@@meta {json}`, que
    el servidor usa para mostrar los botones adecuados (en la terminal es solo una línea más)."""
    if meta:
        print("@@meta " + json.dumps(meta, ensure_ascii=False), flush=True)
    return input(texto).strip().lower()


def _a_papelera(carpeta: Path) -> None:
    """Una pose descartada no se borra: va a <DATOS>/papelera/ (recuperable)."""
    import shutil

    lote = cfg.DATOS / "papelera" / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_repetida")
    try:  # misma ruta relativa que en los datos (capturas/<proceso>/<cat>/…), para poder restaurarla
        destino = lote / carpeta.resolve().relative_to(cfg.DATOS.resolve())
    except ValueError:
        destino = lote / "capturas" / carpeta.parent.name / carpeta.name
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(carpeta), str(destino))
    print(f"    [OK] Pose descartada: {carpeta.name} movida a la papelera")


def nuevo_proceso(plan: list[tuple[str, int]], salida: Path = cfg.DIR_CAPTURAS) -> Path:
    """Crea la carpeta de un proceso de captura (`capturas/AAAA-MM-DD_HHMM/`) con su `proceso.json`.

    Todas las poses del proceso (patrón, plano, objeto) se guardan dentro, en una subcarpeta por
    categoría: así se encuentran juntas al buscar a mano. Ver rutas.py."""
    import rutas

    nombre = rutas.nombre_proceso(datetime.now())
    carpeta = salida / nombre
    carpeta.mkdir(parents=True, exist_ok=False)
    datos = {"proceso": nombre, "inicio": datetime.now().isoformat(timespec="seconds"),
             "plan": {c: n for c, n in plan}, "capturas": {}, "poses": {}}
    (carpeta / "proceso.json").write_text(json.dumps(datos, indent=1, ensure_ascii=False), encoding="utf-8")
    return carpeta


def cerrar_proceso(carpeta: Path, capturas: list[Path]) -> None:
    """Completa el `proceso.json` al terminar: hora de fin y capturas guardadas por categoría
    (las poses organizadas las agrega `organizar`)."""
    import sesiones

    ruta = carpeta / "proceso.json"
    with sesiones.ESCRITURA:
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            datos = {"proceso": carpeta.name}
        datos["fin"] = datetime.now().isoformat(timespec="seconds")
        por_cat: dict[str, list[str]] = {}
        for c in capturas:
            if c.exists():
                por_cat.setdefault(c.parent.name, []).append(c.name)
        datos["capturas"] = por_cat
        sesiones.escribir_json(ruta, datos)
    if not capturas and not any(p for p in carpeta.iterdir() if p.name != "proceso.json"):
        shutil_rmtree_seguro(carpeta)  # proceso sin ninguna captura: no deja carpetas vacías


def shutil_rmtree_seguro(carpeta: Path) -> None:
    import shutil

    if carpeta.is_dir() and carpeta.resolve().parent == cfg.DIR_CAPTURAS.resolve():
        shutil.rmtree(carpeta)


def capturar_poses(
    categoria: str,
    poses: int = 1,
    ciclos: int = cfg.CICLOS_POR_CAPTURA,
    salida: Path = cfg.DIR_CAPTURAS,
    esperar_enter: bool = True,
    camara: object | None = None,
    al_frame: AlFrame | None = None,
    sufijo: str = "",
    al_previa: AlPrevia | None = None,
    validar: bool = True,
) -> list[Path]:
    """Captura `poses` secuencias de la categoría indicada, pidiendo confirmación entre poses.

    - `camara`: objeto con `__enter__` y `capturar` (por defecto `CamaraFLIR()`; `CamaraSimulada`
      para el modo demo). `sufijo` se añade al nombre de la carpeta (p. ej. "_simulada").
    - `al_previa(frame)`: si se da, durante cada pausa la cámara transmite una vista previa continua
      (sin trigger) para encuadrar; se detiene al confirmar la pose.
    - `validar`: tras cada pose se comprueba la secuencia (`organizar_capturas.evaluar_captura`). Si
      no sirve (p. ej. el proyector no proyectaba) se ofrece repetirla.
    - En la pausa, «r» repite la pose anterior (la descartada va a la papelera).
    """
    import organizar_capturas as oc

    cantidad = cfg.IMAGENES_POR_CICLO * max(ciclos, 1)
    carpetas: list[Path] = []
    pose = 0
    with (camara if camara is not None else CamaraFLIR()) as camara:
        while pose < poses:
            if esperar_enter:
                previa = al_previa is not None and hasattr(camara, "iniciar_vista_previa")
                if previa:
                    camara.iniciar_vista_previa(al_previa)
                try:
                    extra = ", r = repetir la anterior" if carpetas else ""
                    resp = preguntar(
                        f"\n[{categoria}] Prepara la pose {pose + 1}/{poses} y presiona Enter (q = terminar{extra}): ",
                        tipo="pose", cat=categoria, i=pose + 1, n=poses, puede_repetir=bool(carpetas),
                    )
                finally:
                    if previa:
                        camara.detener_vista_previa()
                if resp == "q":
                    break
                if resp == "r" and carpetas:
                    _a_papelera(carpetas.pop())
                    pose -= 1
                    continue
            print(f"    Capturando {cantidad} frames...", flush=True)
            try:
                frames = camara.capturar(cantidad, al_frame)
            except RuntimeError as exc:  # p. ej. sin trigger: Arduino apagado o desconectado
                print(f"    [ERROR] {exc}", flush=True)
                if not esperar_enter:
                    raise
                resp = preguntar(
                    f"[{categoria}] La pose {pose + 1} no se pudo capturar. Enter = reintentar, q = terminar: ",
                    tipo="reintentar", cat=categoria, i=pose + 1, n=poses, error=str(exc),
                )
                if resp == "q":
                    break
                continue
            carpeta = guardar_captura(frames, salida, categoria, sufijo=sufijo)
            print(f"    [OK] {len(frames)} frames en '{carpeta}'")
            if validar:
                ev = oc.evaluar_captura(frames)
                print("@@calidad " + json.dumps({"cat": categoria, "i": pose + 1, "n": poses, **ev}, ensure_ascii=False),
                      flush=True)
                for aviso in ev["avisos"]:
                    print(f"    [AVISO] {aviso}")
                if not ev["ok"]:
                    for motivo in ev["motivos"]:
                        print(f"    [ERROR] Pose {pose + 1} inválida: {motivo}")
                    if esperar_enter:
                        resp = preguntar(
                            f"[{categoria}] La pose {pose + 1}/{poses} no sirve. Enter/r = repetirla, "
                            f"s = guardarla igual, q = terminar: ",
                            tipo="invalida", cat=categoria, i=pose + 1, n=poses, motivos=ev["motivos"],
                        )
                        if resp in ("", "r"):
                            _a_papelera(carpeta)
                            continue
                        if resp == "q":
                            carpetas.append(carpeta)
                            break
                else:
                    print(f"    [OK] Pose válida | modulación H={ev['modulacion_H']:.2f} V={ev['modulacion_V']:.2f} | "
                          f"saturado {100 * ev['saturado']:.1f} %")
            carpetas.append(carpeta)
            pose += 1
    return carpetas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--categoria", choices=cfg.CATEGORIAS, required=True)
    parser.add_argument("--poses", type=int, default=1, help="Cantidad de poses a capturar")
    parser.add_argument("--ciclos", type=int, default=cfg.CICLOS_POR_CAPTURA,
                        help="Ciclos completos de la secuencia por pose (se promedian al organizar)")
    parser.add_argument("--salida", type=Path, default=cfg.DIR_CAPTURAS)
    parser.add_argument("--sin-pausa", action="store_true", help="No esperar Enter entre poses")
    args = parser.parse_args()
    proceso = nuevo_proceso([(args.categoria, args.poses)], args.salida)
    carpetas = []
    try:
        carpetas = capturar_poses(args.categoria, args.poses, args.ciclos, proceso, not args.sin_pausa)
    finally:
        cerrar_proceso(proceso, carpetas)
    print(f"[OK] Proceso de captura: {proceso}")
    print(f"\nAdquisición terminada: {len(carpetas)} poses guardadas.")


if __name__ == "__main__":
    main()
