import numpy as np
import cv2
from matplotlib import pyplot as plt
import PySpin
import os

def generate_sinusoidal_pattern(width, height, frequency, phase_shift=0.0, orientation='vertical'):
    """
    Genera un patrón sinusoidal
    width, height: dimensiones de la imagen
    frequency: frecuencia espacial del patrón
    phase_shift: desplazamiento de fase en radianes
    orientation: 'vertical' u 'horizontal'
    """
    x = np.linspace(0, 2*np.pi*frequency, width)
    y = np.linspace(0, 2*np.pi*frequency, height)
    
    if orientation == 'vertical':
        xx, _ = np.meshgrid(x, y)
        pattern = 0.5 * (1 + np.sin(xx + phase_shift))
    else:  # horizontal
        _, yy = np.meshgrid(x, y)
        pattern = 0.5 * (1 + np.sin(yy + phase_shift))
    
    # Convertir a uint8 para visualización
    pattern = (pattern * 255).astype(np.uint8)
    return pattern

def capture_and_save_patterns():
    # Inicializar sistema FLIR
    system = PySpin.System.GetInstance()
    cam_list = system.GetCameras()
    
    if cam_list.GetSize() == 0:
        print("No se encontró ninguna cámara FLIR")
        return
        
    camera = cam_list.GetByIndex(0)
    camera.Init()
    
    # Crear directorio para guardar las imágenes
    output_dir = "captured_patterns"
    os.makedirs(output_dir, exist_ok=True)
    
    # Configuración de patrones
    width = 1280  # Ajusta según tu proyector
    height = 640  # Ajusta según tu proyector
    frequency = 10
    num_patterns = 6
    
    # Generar patrones
    patterns = []
    for i in range(num_patterns):
        phase = i * 2 * np.pi / num_patterns
        pattern = generate_sinusoidal_pattern(width, height, frequency, phase)
        patterns.append(pattern)
    
    # Configurar ventana de proyección
    window_name = 'Sinusoidal Pattern'
    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    # Iniciar captura
    camera.BeginAcquisition()
    
    try:
        # Proyectar y capturar cada patrón
        for i, pattern in enumerate(patterns):
            # Proyectar patrón
            cv2.imshow(window_name, pattern)
            cv2.waitKey(500)  # Esperar 500ms para estabilización
            
            # Capturar imagen
            image_result = camera.GetNextImage()
            if not image_result.IsIncomplete():
                # Convertir y guardar imagen
                image_data = image_result.GetNDArray()
                cv2.imwrite(os.path.join(output_dir, f'pattern_{i}.png'), image_data)
                
            image_result.Release()
            
    finally:
        # Limpieza
        camera.EndAcquisition()
        camera.DeInit()
        cv2.destroyAllWindows()
        
    # Liberar sistema
    del camera
    cam_list.Clear()
    system.ReleaseInstance()

if __name__ == "__main__":
    capture_and_save_patterns()