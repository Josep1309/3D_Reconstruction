"""Captura 50 frames de una Blackfly S usando el trigger externo.

La cámara debe estar conectada al mismo pulso que el proyector. Al iniciar
este programa no se intenta alinear el primer patrón: se captura el siguiente
pulso disponible y se conservan los 50 siguientes. Por eso esta estrategia
funciona aunque el proyector ya esté ejecutando la secuencia en loop.

Ejemplo:
    python capturar_patrones.py --salida capturas

La numeración de ``frame_00`` corresponde al primer pulso recibido por la
cámara, no necesariamente a ``f_00.bmp`` del proyector. Para conocer la fase
del loop hace falta una señal de sincronización adicional o una marca conocida.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import PySpin


NUM_FRAMES = 50
TRIGGER_LINE = PySpin.TriggerSource_Line0
TRIGGER_TIMEOUT_MS = 2_000
EXPOSURE_TIME_US = 12000


def configurar_trigger(camera: PySpin.Camera) -> None:
    """Configura trigger externo con filtro antirrebotes y sin solapamiento."""
    if camera.TriggerMode.GetAccessMode() != PySpin.RW:
        raise RuntimeError("TriggerMode no es escribible")
    camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

    if camera.ExposureAuto.GetAccessMode() == PySpin.RW:
        camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
    if camera.ExposureTime.GetAccessMode() != PySpin.RW:
        raise RuntimeError("ExposureTime no es escribible")

    exposure_time = min(
        max(EXPOSURE_TIME_US, camera.ExposureTime.GetMin()),
        camera.ExposureTime.GetMax(),
    )
    camera.ExposureTime.SetValue(exposure_time)

    # Configurar filtro de Debounce en Line0 (ej. 500 us) para evitar disparos múltiples por ruido
    if camera.LineSelector.GetAccessMode() == PySpin.RW:
        camera.LineSelector.SetValue(PySpin.LineSelector_Line0)
        if camera.LineInputFilterSelector.GetAccessMode() == PySpin.RW:
            camera.LineInputFilterSelector.SetValue(PySpin.LineInputFilterSelector_Debounce)
        if camera.LineFilterWidth.GetAccessMode() == PySpin.RW:
            camera.LineFilterWidth.SetValue(500.0)

    if camera.TriggerSelector.GetAccessMode() != PySpin.RW:
        raise RuntimeError("TriggerSelector no es escribible")
    camera.TriggerSelector.SetValue(PySpin.TriggerSelector_FrameStart)

    if camera.TriggerSource.GetAccessMode() != PySpin.RW:
        raise RuntimeError("TriggerSource no es escribible")
    camera.TriggerSource.SetValue(TRIGGER_LINE)

    if camera.TriggerActivation.GetAccessMode() == PySpin.RW:
        camera.TriggerActivation.SetValue(PySpin.TriggerActivation_RisingEdge)

    # Evitar que se encolen triggers espurios durante la exposición
    if camera.TriggerOverlap.GetAccessMode() == PySpin.RW:
        camera.TriggerOverlap.SetValue(PySpin.TriggerOverlap_Off)

    if camera.TriggerMode.GetAccessMode() != PySpin.RW:
        raise RuntimeError("TriggerMode no es escribible")
    camera.TriggerMode.SetValue(PySpin.TriggerMode_On)
    print(f"Exposición configurada: {exposure_time:.0f} us")


def desactivar_trigger(camera: PySpin.Camera) -> None:
    """Desactiva el trigger antes de liberar la cámara."""
    if camera.TriggerMode.GetAccessMode() == PySpin.RW:
        camera.TriggerMode.SetValue(PySpin.TriggerMode_Off) 


def escribir_video(frames: list[np.ndarray], ruta: Path, fps: float) -> None:
    """Escribe un AVI sin pérdida si el códec FFV1 está disponible."""
    if not frames:
        raise ValueError("No hay frames para escribir")

    alto, ancho = frames[0].shape[:2]
    writer = cv2.VideoWriter(
        str(ruta),
        cv2.VideoWriter.fourcc("F", "F", "V", "1"),
        fps,
        (ancho, alto),
        isColor=False,
    )
    if not writer.isOpened():
        raise RuntimeError(
            "No se pudo abrir el códec FFV1. Guarde los TIFF y use un códec "
            "sin pérdida instalado en el sistema."
        )

    try:
        for frame in frames:
            writer.write(frame)
    finally:
        writer.release()


def capturar(salida: Path, cantidad: int = NUM_FRAMES) -> Path:
    """Captura ``cantidad`` frames a partir de los siguientes triggers."""
    if cantidad < 1:
        raise ValueError("cantidad debe ser mayor que cero")

    salida.mkdir(parents=True, exist_ok=True)
    carpeta = salida / "objeto" / datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta.mkdir()

    system = PySpin.System.GetInstance()
    cameras = system.GetCameras()
    camera = None

    if cameras.GetSize() == 0:
        cameras.Clear()
        system.ReleaseInstance()
        raise RuntimeError("No se encontró ninguna cámara FLIR")

    try:
        camera = cameras.GetByIndex(0)
        camera.Init()
        configurar_trigger(camera)

        if camera.AcquisitionMode.GetAccessMode() != PySpin.RW:
            raise RuntimeError("AcquisitionMode no es escribible")
        camera.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
        camera.BeginAcquisition()

        frames: list[np.ndarray] = []
        try:
            print(
                f"Esperando {cantidad} pulsos externos en "
                f"{TRIGGER_LINE}..."
            )
            for indice in range(cantidad):
                image = camera.GetNextImage(TRIGGER_TIMEOUT_MS)
                try:
                    if image.IsIncomplete():
                        raise RuntimeError(
                            f"Frame {indice} incompleto: "
                            f"{image.GetImageStatus()}"
                        )

                    frame = np.array(image.GetNDArray(), copy=True)
                    frames.append(frame)
                    ruta_frame = carpeta / f"objeto_frame_{indice:02d}.tiff"
                    if not cv2.imwrite(str(ruta_frame), frame):
                        raise OSError(f"No se pudo guardar {ruta_frame}")
                    print(f"Capturado {indice + 1}/{cantidad}: {ruta_frame}")
                finally:
                    image.Release()
                    del image
        finally:
            camera.EndAcquisition()
            desactivar_trigger(camera)

        fps = 20.0
        escribir_video(frames, carpeta / "captura_50_frames.avi", fps)
        return carpeta
    finally:
        if camera is not None:
            camera.DeInit()
            del camera
        cameras.Clear()
        system.ReleaseInstance()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--salida",
        type=Path,
        default=Path("capturas"),
        help="Directorio donde se crea una carpeta por adquisición",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=NUM_FRAMES,
        help=f"Cantidad de frames a capturar (por defecto: {NUM_FRAMES})",
    )
    args = parser.parse_args()
    carpeta = capturar(args.salida, args.frames)
    print(f"Adquisición terminada: {carpeta}")


if __name__ == "__main__":
    main()
