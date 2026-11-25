import numpy as np
import cv2

def generar_patrones_binarios(
    width,
    height,
    periodo=18,
    num_pasos=3,
    orientacion='vertical'
):
    """
    Genera patrones de franjas binarias (onda cuadrada 50% duty cycle)
    desplazados uniformemente para fringe shifting.

    Parámetros:
    - width, height: Resolución del proyector en píxeles.
    - periodo: Ancho total de una franja blanco+negro en píxeles (P = 18).
    - num_pasos: Cantidad de capturas de corrimiento (típicamente 3 o 4).
    - orientacion: 'vertical' (franjas en columnas) o 'horizontal' (en filas).
    """
    patrones = []
    
    # Desplazamiento por cada paso
    desplazamiento_por_paso = periodo / num_pasos

    for i in range(num_pasos):
        shift = i * desplazamiento_por_paso

        if orientacion == 'vertical':
            # Coordenadas X repetidas verticalmente
            x = np.arange(width)
            # Función cuadrada periódica binaria (0 o 255)
            # Ciclo de trabajo (duty cycle) al 50%: periodo/2
            fila = ((x + shift) % periodo < (periodo / 2.0)).astype(np.uint8) * 255
            patron = np.tile(fila, (height, 1))

        elif orientacion == 'horizontal':
            # Coordenadas Y repetidas horizontalmente
            y = np.arange(height)
            columna = ((y + shift) % periodo < (periodo / 2.0)).astype(np.uint8) * 255
            patron = np.tile(columna[:, np.newaxis], (1, width))

        else:
            raise ValueError("Orientación debe ser 'vertical' o 'horizontal'")

        patrones.append(patron)

    return patrones

# --- Generación y guardado ---
if __name__ == "__main__":
    from pathlib import Path

    PERIODO = 18        # Paso de 18 píxeles
    NUM_PASOS = 6       # 6-step phase shifting (desplazamiento de 3 px por paso)
    ANCHO = 912         # Resolución del LightCrafter 4500 (ancho x alto = 912 x 1140)
    ALTO = 1140
    destino = Path(__file__).resolve().parent.parent / "recursos" / "patterns"  # ejemplo de prueba
    destino.mkdir(parents=True, exist_ok=True)

    imagenes = generar_patrones_binarios(
        width=ANCHO, 
        height=ALTO, 
        periodo=PERIODO, 
        num_pasos=NUM_PASOS, 
        orientacion='vertical'
    )

    for idx, img in enumerate(imagenes):
        nombre_archivo = str(destino / f"patron_binario_paso_{idx+1}_de_{NUM_PASOS}.png")
        cv2.imwrite(nombre_archivo, img)
        print(f"Guardado: {nombre_archivo} (shift = {idx * (PERIODO / NUM_PASOS):.1f} px)")