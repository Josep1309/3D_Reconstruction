import time
from pathlib import Path
import cv2
import numpy as np
import PySpin

# --- PARÁMETROS DE CONFIGURACIÓN ---
NUM_FRAMES = 50            # 50 capturas correspondientes a los 50 patrones
EXPOSURE_US = 10000.0      # 10 ms de exposición
DEBOUNCE_US = 1000.0       # 1 ms de filtro antirrebotes para ignorar ruido eléctrico
TRIGGER_DELAY_US = 2000.0  # 2 ms de retardo tras el flanco para que el DMD del LightCrafter estabilice
TIMEOUT_MS = 5000          # Espera máxima por cada pulso (5 segundos)
CARPETA_SALIDA = Path("prueba_trigger")


def configurar_camara(cam: PySpin.CameraPtr) -> None:
    """Configura la exposición fija y el trigger por hardware en Line0."""
    # 1. Apagar el trigger antes de modificar parámetros
    if cam.TriggerMode.GetAccessMode() == PySpin.RW:
        cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)

    # 2. Configurar exposición manual fija
    if cam.ExposureAuto.GetAccessMode() == PySpin.RW:
        cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
    if cam.ExposureTime.GetAccessMode() == PySpin.RW:
        exp_min = cam.ExposureTime.GetMin()
        exp_max = cam.ExposureTime.GetMax()
        cam.ExposureTime.SetValue(min(max(EXPOSURE_US, exp_min), exp_max))

    # 3. Configurar filtro antirrebotes (Debounce) en Line0
    # En Blackfly S el nodo se configura con LineInputFilterSelector + LineFilterWidth
    if cam.LineSelector.GetAccessMode() == PySpin.RW:
        cam.LineSelector.SetValue(PySpin.LineSelector_Line0)
    if cam.LineMode.GetAccessMode() == PySpin.RW:
        cam.LineMode.SetValue(PySpin.LineMode_Input)
    if cam.LineInputFilterSelector.GetAccessMode() == PySpin.RW:
        cam.LineInputFilterSelector.SetValue(PySpin.LineInputFilterSelector_Debounce)
    if cam.LineFilterWidth.GetAccessMode() == PySpin.RW:
        deb_min = cam.LineFilterWidth.GetMin()
        deb_max = cam.LineFilterWidth.GetMax()
        cam.LineFilterWidth.SetValue(min(max(DEBOUNCE_US, deb_min), deb_max))

    # 4. Configurar el Trigger en flanco de subida (Rising Edge) y retardo de estabilización
    if cam.TriggerSelector.GetAccessMode() == PySpin.RW:
        cam.TriggerSelector.SetValue(PySpin.TriggerSelector_FrameStart)
    if cam.TriggerSource.GetAccessMode() == PySpin.RW:
        cam.TriggerSource.SetValue(PySpin.TriggerSource_Line0)
    if cam.TriggerActivation.GetAccessMode() == PySpin.RW:
        cam.TriggerActivation.SetValue(PySpin.TriggerActivation_RisingEdge)
    if cam.TriggerDelay.GetAccessMode() == PySpin.RW:
        delay_min = cam.TriggerDelay.GetMin()
        delay_max = cam.TriggerDelay.GetMax()
        cam.TriggerDelay.SetValue(min(max(TRIGGER_DELAY_US, delay_min), delay_max))

    # 5. Ignorar pulsos que lleguen mientras la cámara sigue leyendo el sensor
    if cam.TriggerOverlap.GetAccessMode() == PySpin.RW:
        cam.TriggerOverlap.SetValue(PySpin.TriggerOverlap_Off)

    # 6. Vaciar buffers viejos y entregar siempre el frame en orden de llegada
    s_node_map = cam.GetTLStreamNodeMap()
    handling_mode = PySpin.CEnumerationPtr(s_node_map.GetNode("StreamBufferHandlingMode"))
    if PySpin.IsAvailable(handling_mode) and PySpin.IsWritable(handling_mode):
        entry = handling_mode.GetEntryByName("OldestFirst")
        handling_mode.SetIntValue(entry.GetValue())

    # 7. Activar el trigger y modo continuo
    cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
    cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)

    debounce_actual = (
        cam.LineFilterWidth.GetValue()
        if cam.LineFilterWidth.GetAccessMode() in (PySpin.RO, PySpin.RW)
        else DEBOUNCE_US
    )
    delay_actual = (
        cam.TriggerDelay.GetValue()
        if cam.TriggerDelay.GetAccessMode() in (PySpin.RO, PySpin.RW)
        else TRIGGER_DELAY_US
    )
    print(
        f"[OK] Exposición: {cam.ExposureTime.GetValue():.0f} us | "
        f"Debounce: {debounce_actual:.0f} us | "
        f"TriggerDelay: {delay_actual:.0f} us"
    )


def main() -> None:
    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

    system = PySpin.System.GetInstance()
    cam_list = system.GetCameras()

    if cam_list.GetSize() == 0:
        cam_list.Clear()
        system.ReleaseInstance()
        print("[ERROR] No se detectó ninguna cámara Blackfly S.")
        return

    cam = cam_list.GetByIndex(0)

    try:
        cam.Init()
        configurar_camara(cam)

        frames_capturados = []
        tiempos_captura = []

        cam.BeginAcquisition()
        print(f"\nEsperando {NUM_FRAMES} pulsos en Line0...")

        try:
            while len(frames_capturados) < NUM_FRAMES:
                # Se bloquea aquí hasta que entra un pulso por el cable en Line0
                image_result = cam.GetNextImage(TIMEOUT_MS)

                try:
                    if image_result.IsIncomplete():
                        print(
                            f"[WARN] Frame incompleto descartado "
                            f"(Estado: {image_result.GetImageStatus()})"
                        )
                        continue

                    t_actual = time.perf_counter()
                    # Copiar imagen a memoria RAM
                    frame = np.array(image_result.GetNDArray(), copy=True)
                    frames_capturados.append(frame)
                    tiempos_captura.append(t_actual)
                    num_actual = len(frames_capturados)

                    # Calcular el tiempo transcurrido desde el pulso anterior (diagnóstico)
                    if num_actual > 1:
                        dt_ms = (tiempos_captura[-1] - tiempos_captura[-2]) * 1000.0
                        print(f" -> Pulso #{num_actual:02d}/{NUM_FRAMES} recibido | Δt = {dt_ms:.2f} ms")
                    else:
                        print(f" -> Pulso #{num_actual:02d}/{NUM_FRAMES} recibido (Primer frame)")

                finally:
                    # Siempre liberar el buffer interno de PySpin inmediatamente
                    image_result.Release()
                    del image_result

        except PySpin.SpinnakerException as ex:
            print(f"\n[ERROR] Timeout o fallo durante la espera del trigger: {ex}")

        finally:
            if cam.IsStreaming():
                cam.EndAcquisition()
            if cam.TriggerMode.GetAccessMode() == PySpin.RW:
                cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)

        # Guardar los frames en disco fuera del bucle crítico de tiempo real
        print("\nGuardando imágenes en disco...")
        for idx, frame in enumerate(frames_capturados):
            ruta = CARPETA_SALIDA / f"frame_{idx:02d}.tiff"
            cv2.imwrite(str(ruta), frame)
        print(f"[OK] {len(frames_capturados)} imágenes guardadas en '{CARPETA_SALIDA.resolve()}'")

    finally:
        if cam.IsInitialized():
            cam.DeInit()
        del cam
        cam_list.Clear()
        system.ReleaseInstance()


if __name__ == "__main__":
    main()