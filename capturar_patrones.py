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
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import configuracion as cfg


class CamaraFLIR:
    """Blackfly S configurada con trigger externo en Line0 (se usa con `with`)."""

    def __init__(
        self,
        exposicion_us: float = cfg.CAM_EXPOSICION_US,
        debounce_us: float = cfg.CAM_DEBOUNCE_US,
        trigger_delay_us: float | None = cfg.CAM_TRIGGER_DELAY_US,
        timeout_ms: int = cfg.CAM_TIMEOUT_MS,
        indice: int = 0,
    ) -> None:
        import PySpin  # solo se necesita al capturar

        self.ps = PySpin
        self.exposicion_us = exposicion_us
        self.debounce_us = debounce_us
        self.trigger_delay_us = trigger_delay_us
        self.timeout_ms = timeout_ms
        self.indice = indice
        self.system = None
        self.cameras = None
        self.camera = None

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
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
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

    def capturar(self, cantidad: int) -> list[np.ndarray]:
        """Captura `cantidad` frames consecutivos a partir del siguiente pulso de trigger."""
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
                finally:
                    image.Release()
        finally:
            cam.EndAcquisition()

        if len(tiempos) > 2:
            dt = np.diff(tiempos) * 1000.0
            print(f"    Δt entre frames: mediana {np.median(dt):.1f} ms, máx {dt.max():.1f} ms")
            if dt.max() > 1.5 * np.median(dt):
                print("    [AVISO] posible pulso perdido; el organizador lo detectará y separará los ciclos.")
        return frames


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


def guardar_captura(frames: list[np.ndarray], salida: Path, categoria: str, video: bool = cfg.GUARDAR_VIDEO) -> Path:
    """Guarda los frames en `<salida>/<categoria>/<fecha>/` y devuelve la carpeta."""
    carpeta = salida / categoria / datetime.now().strftime("%Y%m%d_%H%M%S")
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


def capturar_poses(
    categoria: str,
    poses: int = 1,
    ciclos: int = cfg.CICLOS_POR_CAPTURA,
    salida: Path = cfg.DIR_CAPTURAS,
    esperar_enter: bool = True,
) -> list[Path]:
    """Captura `poses` secuencias de la categoría indicada, pidiendo confirmación entre poses."""
    cantidad = cfg.IMAGENES_POR_CICLO * max(ciclos, 1)
    carpetas: list[Path] = []
    with CamaraFLIR() as camara:
        for pose in range(poses):
            if esperar_enter:
                resp = input(
                    f"\n[{categoria}] Prepara la pose {pose + 1}/{poses} y presiona Enter (q = terminar): "
                ).strip().lower()
                if resp == "q":
                    break
            print(f"    Capturando {cantidad} frames...")
            frames = camara.capturar(cantidad)
            carpeta = guardar_captura(frames, salida, categoria)
            carpetas.append(carpeta)
            print(f"    [OK] {len(frames)} frames en '{carpeta}'")
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
    carpetas = capturar_poses(args.categoria, args.poses, args.ciclos, args.salida, not args.sin_pausa)
    print(f"\nAdquisición terminada: {len(carpetas)} poses guardadas.")


if __name__ == "__main__":
    main()
