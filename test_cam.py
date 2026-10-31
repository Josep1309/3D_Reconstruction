import sys
import PySpin
import numpy as np

def test_spinnaker():
    # 1. Obtener la instancia del sistema
    system = PySpin.System.GetInstance()
    version = system.GetLibraryVersion()
    print(f"[OK] Spinnaker SDK inicializado con éxito.")
    print(f"     Versión del SDK: {version.major}.{version.minor}.{version.type}.{version.build}")

    # 2. Obtener lista de cámaras
    cam_list = system.GetCameras()
    num_cameras = cam_list.GetSize()
    print(f"\n[INFO] Cámaras detectadas: {num_cameras}")

    if num_cameras == 0:
        print("[AVISO] No se detectó ninguna cámara.")
        cam_list.Clear()
        system.ReleaseInstance()
        return

    # 3. Inicializar la cámara
    cam = cam_list.GetByIndex(0)
    image_result = None

    try:
        cam.Init()

        nodemap_tldevice = cam.GetTLDeviceNodeMap()
        node_device_model = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceModelName'))
        node_device_serial = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))
        
        model_name = node_device_model.GetValue() if PySpin.IsReadable(node_device_model) else "Desconocido"
        serial_number = node_device_serial.GetValue() if PySpin.IsReadable(node_device_serial) else "Desconocido"
        print(f"[OK] Conectado a: {model_name} (S/N: {serial_number})")

        # 4. Configurar adquisición SingleFrame
        nodemap = cam.GetNodeMap()
        node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
        if PySpin.IsWritable(node_acquisition_mode):
            node_acquisition_mode_single = node_acquisition_mode.GetEntryByName('SingleFrame')
            node_acquisition_mode.SetIntValue(node_acquisition_mode_single.GetValue())

        # Iniciar adquisición
        cam.BeginAcquisition()
        print("[INFO] Capturando imagen de prueba...")

        # Adquirir fotograma
        image_result = cam.GetNextImage(2000)

        if image_result.IsIncomplete():
            print(f"[ERROR] Imagen incompleta: {image_result.GetImageStatus()}")
        else:
            width = image_result.GetWidth()
            height = image_result.GetHeight()
            print(f"[OK] Fotograma recibido: {width} x {height} px")

            # Obtener el array de NumPy nativo
            image_data = image_result.GetNDArray()
            print(f"     Forma del arreglo NumPy: {image_data.shape}, Tipo de dato: {image_data.dtype}")

            # Método oficial Spinnaker 4.x: usar ImageProcessor
            processor = PySpin.ImageProcessor()
            processor.SetColorProcessing(PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR)
            
            # Convertir a Mono8 (o PixelFormat_BGR8 si la cámara es color)
            converted_image = processor.Convert(image_result, PySpin.PixelFormat_Mono8)
            
            output_filename = "test_spinnaker_output.jpg"
            converted_image.Save(output_filename)
            print(f"[OK] Imagen guardada en disco exitosamente como: {output_filename}")

    except PySpin.SpinnakerException as ex:
        print(f"[ERROR PySpin] Excepción: {ex}")
    finally:
        # Asegurar la liberación de búferes y referencias en el orden estricto de Spinnaker
        if image_result is not None:
            try:
                image_result.Release()
            except Exception:
                pass
            del image_result

        try:
            if cam.IsStreaming():
                cam.EndAcquisition()
        except Exception:
            pass

        try:
            cam.DeInit()
        except Exception:
            pass

        del cam
        cam_list.Clear()
        system.ReleaseInstance()
        print("\n[INFO] Recursos liberados limpiamente.")

if __name__ == "__main__":
    test_spinnaker()