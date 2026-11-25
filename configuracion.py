"""Parámetros compartidos por todas las etapas del sistema de proyección de franjas.

Edita los valores de esta sección; `pipeline.py` y los scripts individuales los leen de aquí.
Los argumentos de línea de comandos de cada script tienen prioridad sobre estos valores.
"""

from __future__ import annotations

import os
from pathlib import Path

# ==============================================================================
# --- DIRECTORIOS ---
# ==============================================================================
RAIZ = Path(__file__).resolve().parent
# Carpeta base de los datos. Por defecto la del proyecto; la variable de entorno TESIS_DIR_DATOS
# permite trabajar con otra copia (p. ej. para probar sin tocar las capturas reales).
DATOS = Path(os.environ.get("TESIS_DIR_DATOS", RAIZ)).expanduser().resolve()
DIR_PATRONES = RAIZ / "patterns" / "secuencia_completa_bmp"   # .bmp que se cargan al LightCrafter
DIR_CAPTURAS = DATOS / "capturas"                 # capturas crudas (cualquier nombre / formato)
DIR_ORDENADAS = DATOS / "capturas_ordenadas"      # <categoria>/pose_XX/{H,V}/P18_FYY.tiff
DIR_RESULTADOS = DATOS / "resultados"             # fases, reconstrucción y diagnósticos
# Calibración vigente del montaje (archivos pequeños, VERSIONADOS en git para que viajen con el
# código). Cada recalibración guarda además una copia en calibraciones/historial/<fecha>/.
# TESIS_DIR_CALIBRACION permite usar otra carpeta (p. ej. para pruebas).
DIR_CALIBRACION = Path(os.environ.get("TESIS_DIR_CALIBRACION", RAIZ / "calibraciones")).expanduser().resolve()

# Categorías de captura: patrón de círculos, plano de referencia y objeto
CATEGORIAS = ("patron", "plano", "objeto")

# ==============================================================================
# --- PROYECTOR (TI DLP LightCrafter 4500) Y SECUENCIA DE PATRONES ---
# ==============================================================================
PROYECTOR_ANCHO = 912
PROYECTOR_ALTO = 1140
PERIODO = 18            # período de franja en píxeles del proyector
N_PASOS = PERIODO       # corrimientos de 1 px hasta completar un período
N_BITS_GRAY = 6         # 2^6 * 18 = 1152 px >= 1140: cubre todo el proyector
# Orden en que la cámara recibe los bits Gray: "msb", "lsb" o "auto" (detección sobre los datos).
# Con la secuencia cargada actualmente en el LightCrafter llegan en orden "lsb".
ORDEN_BITS_GRAY = "auto"

# Secuencia por ciclo: [H: N_PASOS + N_BITS_GRAY] [V: N_PASOS + N_BITS_GRAY] negro blanco
IMAGENES_POR_ORIENTACION = N_PASOS + N_BITS_GRAY
IMAGENES_POR_CICLO = 2 * IMAGENES_POR_ORIENTACION + 2
PREFIJO_ORDENADAS = f"P{PERIODO}_F"

# Tiempos del LightCrafter para el trigger externo de 20 Hz del Arduino (50 000 us)
LCR_EXPOSICION_US = 49700
LCR_PERIODO_US = 50000

# ==============================================================================
# --- CÁMARA (FLIR Blackfly S con trigger externo en Line0) ---
# ==============================================================================
CAM_EXPOSICION_US = 12000.0
CAM_DEBOUNCE_US = 500.0
CAM_TRIGGER_DELAY_US = None  # None = no modificar el valor de la cámara
CAM_TIMEOUT_MS = 2000
CICLOS_POR_CAPTURA = 1   # >1 captura varios ciclos seguidos; el organizador los promedia
# Además de los .tiff, un .avi FFV1 con los mismos frames. Duplica ~47 MB por pose y el organizador
# lo descarta cuando están los .tiff, así que está desactivado (AUDITORIA.md §4.1)
GUARDAR_VIDEO = False

# ==============================================================================
# --- RECUPERACIÓN DE FASE ---
# ==============================================================================
GAMMA_TH = 0.15            # umbral de modulación gm = B / A de las franjas verticales (fase X)
# Umbral para las franjas horizontales (fase Y). Es más bajo porque el DMD en diamante del
# LightCrafter 4500 da poco contraste en H (gm ~0.08-0.25) y Fy es la fase que mejor mide la
# profundidad en este montaje. Medido con las capturas del 2026-10-30 (con SUAVIZADO_FASE_PX = 1.5):
#   0.03 -> planitud 0.41 mm, objeto con ~740k puntos (casi toda la superficie)
#   0.05 -> planitud 0.39 mm, objeto con ~560k puntos
#   0.08 -> planitud 0.36 mm, pero el objeto se queda casi sin puntos
GAMMA_TH_Y = 0.03
# Filtro gaussiano (sigma en px de cámara) sobre S y C antes de calcular la fase. Elimina el
# moteado de la rejilla del DMD y reduce el ruido: con 1.5 el error de planitud baja de ~0.71 a
# ~0.39 mm. Suaviza bordes de discontinuidades en ~2 px. 0 = sin filtro (como el MATLAB).
SUAVIZADO_FASE_PX = 1.5
UMBRAL_INTENSIDAD = 25     # nivel mínimo en la imagen blanca para considerar un píxel válido
MED_FILT = 5               # tamaño del filtro de mediana para corregir errores de orden de franja
BORDE_MASCARA = 15         # píxeles recortados en los bordes de la imagen

# ==============================================================================
# --- PATRÓN DE CALIBRACIÓN (grilla simétrica de círculos blancos) ---
# ==============================================================================
PATRON_COLUMNAS = 9
PATRON_FILAS = 12
# Distancia entre centros de círculos (mm). Puede ser un número o un par (entre columnas,
# entre filas) si la impresión del tablero quedó escalada distinto en cada eje. Los MATLAB tienen
# comentada la corrección medida (15.0588, 14.9090); con ella la cámara sale con fx = fy, lo que
# indica que el tablero real probablemente no es 15 x 15. Mídelo con un calibrador antes de usarla.
PATRON_DISTANCIA_MM = 15.0
PATRON_TIPO = "symmetric"
PATRON_COLOR_CIRCULOS = "white"
# Qué poses del patrón entran a la calibración. Todas deben ser del MISMO montaje: si la cámara o
# el proyector se movieron entre sesiones, mezclarlas da un error estéreo enorme y planos curvos.
#   "ultima_sesion" -> solo el último proceso de captura que incluyó el patrón (sesiones.py)
#   "todas"         -> todas las poses de capturas_ordenadas/patron
#   ["pose_08", ...] -> una lista explícita
CALIBRACION_POSES: str | list[str] = "ultima_sesion"
# Control de calidad: una calibración nueva solo se pone en uso si lo cumple; si no, queda en el
# historial marcada como rechazada y sigue la anterior (se puede forzar)
CALIB_RMS_ESTEREO_MAX_PX = 1.5    # RMS estéreo máximo
CALIB_RAZON_ESTEREO_MAX = 3.0     # RMS estéreo / máx(RMS cámara, RMS proyector): poses incoherentes
CALIB_POSES_MIN = 6               # poses del patrón mínimas
CALIB_COBERTURA_MIN = 0.4         # fracción mínima del ancho y del alto del proyector cubierta
HORAS_ENTRE_SESIONES = 2.0
# True: las etapas de proceso y la interfaz solo usan y muestran las poses de la configuración
# vigente: desde el último proceso de captura que incluyó el patrón hasta hoy (ver sesiones.py).
# Lo anterior queda en disco pero se ignora. False: se usa todo.
SOLO_CONFIGURACION_ACTUAL = True
# Capturas antiguas sin registro de proceso: una pausa mayor que esto separa dos procesos, salvo
# que siga capturándose el patrón tras una pausa menor que MINUTOS_CONTINUACION_PATRON (p. ej. al
# reacomodar el tablero: el 30-oct hubo 5 min entre dos poses del mismo proceso)
MINUTOS_ENTRE_PROCESOS = 3.0
MINUTOS_CONTINUACION_PATRON = 10.0

# ==============================================================================
# --- RECONSTRUCCIÓN 3D ---
# ==============================================================================
# Fase usada para triangular:
#   "auto"  -> la coordenada del proyector alineada con la línea base (mayor |T|): aquí Fy
#   "Fx"    -> solo franjas verticales (u_p)      "Fy" -> solo franjas horizontales (v_p)
#   "ambas" -> mínimos cuadrados con las dos. Solo conviene si la calibración cubre bien todo el
#              rango de u_p y v_p; con la calibración actual Fx tiene sesgos de hasta 20 mm en el
#              borde izquierdo (zona de u_p no cubierta por las poses del tablero).
FASE_TRIANGULACION = "auto"
CALIBRACION = "independiente"  # "independiente" (Estereo_TSC_0_2) o "conjunta" (_J)
Z_MIN_MM = 100.0
Z_MAX_MM = 1500.0
SALTO_MAX_MM = 5.0             # salto local máximo en Z (filtro de puntos atípicos)
FILTRO_VECINOS_SIGMA = 0.0     # quita puntos aislados en 3D (mascara.filtrar_vecinos); 0 = desactivado
PLANO_UMBRAL_MM = 3.0          # distancia máxima al plano (RANSAC) para medir la planitud de `plano`

# Valores tal como están en este archivo, antes de que la interfaz aplique sus ajustes (los usa
# fase.py para saber con qué parámetros se calcularon los resultados anteriores a la «firma»)
VALORES_ORIGINALES = {k: v for k, v in dict(globals()).items() if k.isupper()}
