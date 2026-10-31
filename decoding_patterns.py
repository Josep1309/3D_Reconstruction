import cv2
import numpy as np
import matplotlib
matplotlib.use('TkAgg')  # Configura el backend interactivo
import matplotlib.pyplot as plt

def decodificar_patron_gray(imagenes_gray):
    num_bits, alto, ancho = imagenes_gray.shape
    mapa_binario = np.copy(imagenes_gray[0]).astype(np.uint32)
    valores_decodificados = np.copy(mapa_binario)
    
    for i in range(1, num_bits):
        mapa_binario = np.bitwise_xor(mapa_binario, imagenes_gray[i])
        valores_decodificados = (valores_decodificados << 1) | mapa_binario
        
    return valores_decodificados

# 1. Definir los archivos en orden desde el MSB (menor frecuencia) hasta el LSB (mayor frecuencia)
archivos = [
    'f_18.bmp', 'f_19.bmp', 'f_20.bmp', 
    'f_21.bmp', 'f_22.bmp', 'f_23.bmp'
]

imagenes_binarizadas = []


for archivo in archivos:
    # 2. Leer la imagen en escala de grises
    img = cv2.imread("patterns/secuencia_completa_bmp/" + archivo, cv2.IMREAD_GRAYSCALE)
    
    if img is None:
        print(f"Error al cargar {archivo}. Verifica que estén en el mismo directorio del script.")
        continue
        
    # 3. Binarizar la imagen
    # cv2.THRESH_BINARY con valor máximo 1 convierte los píxeles > 127 en 1, y el resto en 0.
    _, img_bin = cv2.threshold(img, 127, 1, cv2.THRESH_BINARY)
    
    imagenes_binarizadas.append(img_bin)

# Convertir la lista a un array 3D de numpy (6, Alto, Ancho)
imagenes_gray = np.array(imagenes_binarizadas)

# 4. Ejecutar la decodificación
if len(imagenes_gray) == len(archivos):
    mapa_decodificado = decodificar_patron_gray(imagenes_gray)
    
    # 5. Visualizar el resultado (Mapa de Fase Desenrollado / Coordenadas)
    plt.figure(figsize=(8, 6))
    # Usamos un mapa de colores para visualizar la rampa de valores decimales (0 a 63)
    plt.imshow(mapa_decodificado, cmap='jet')
    plt.colorbar(label='Valor decimal (0 - 63)')
    plt.title('Mapa de Coordenadas Decodificado (6 bits)')
    plt.xlabel('Píxeles X')
    plt.ylabel('Píxeles Y')
    plt.show()