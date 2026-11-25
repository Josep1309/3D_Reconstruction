# Manual del sistema de reconstrucción 3D por proyección de franjas

**Phase shifting + código Gray · Calibración estéreo cámara–proyector · Triangulación**

Este manual explica, de principio a fin y con detalle, cómo funciona el sistema, cómo se usa y
qué hace cada función importante del código. Está pensado para que alguien que llega nuevo al
proyecto pueda operar el montaje, entender los resultados y modificar el código con criterio.

---

## Índice

1. [Qué hace el sistema](#1-qué-hace-el-sistema)
2. [Uso rápido](#2-uso-rápido)
3. [Hardware y sincronización](#3-hardware-y-sincronización)
4. [Estructura del proyecto](#4-estructura-del-proyecto)
5. [Configuración: `configuracion.py` y `pipeline.py`](#5-configuración)
6. [Etapa `patrones`: la secuencia proyectada](#6-etapa-patrones-la-secuencia-proyectada)
7. [Etapa `lightcrafter`: tiempos del proyector](#7-etapa-lightcrafter-tiempos-del-proyector)
8. [Etapa `captura`: adquisición con la cámara](#8-etapa-captura-adquisición-con-la-cámara)
9. [Etapa `organizar`: de capturas crudas a poses](#9-etapa-organizar-de-capturas-crudas-a-poses)
10. [Etapa `fase_relativa`: phase shifting](#10-etapa-fase_relativa-phase-shifting)
11. [Etapa `fase_absoluta`: código Gray y coordenadas del proyector](#11-etapa-fase_absoluta-código-gray-y-coordenadas-del-proyector)
12. [Etapa `calibracion` (opcional): calibración estéreo](#12-etapa-calibracion-opcional-calibración-estéreo)
13. [Etapa `reconstruccion`: triangulación 3D](#13-etapa-reconstruccion-triangulación-3d)
14. [Etapa `visualizacion`](#14-etapa-visualizacion)
15. [Resultados de referencia y precisión](#15-resultados-de-referencia-y-precisión)
16. [Solución de problemas por etapa](#16-solución-de-problemas-por-etapa)
17. [Correspondencia con el código MATLAB y diferencias](#17-correspondencia-con-el-código-matlab-y-diferencias)
18. [Referencia de archivos de salida](#18-referencia-de-archivos-de-salida)
19. [Interfaz web](#19-interfaz-web)
20. [Instalación en otro computador](#20-instalación-en-otro-computador)

---

## 1. Qué hace el sistema

Un proyector **TI DLP LightCrafter 4500** (912 × 1140 px) proyecta sobre el objeto una secuencia
de 50 imágenes: franjas desplazadas y código Gray, en horizontal y en vertical, más una imagen
negra y una blanca. Una cámara **FLIR Blackfly S** (1280 × 1024 px), disparada por el mismo pulso
de un **Arduino**, captura una imagen por cada patrón.

Para cada píxel de la cámara, las franjas codifican **qué columna y qué fila del proyector lo
ilumina**. Con esa correspondencia cámara↔proyector y un modelo calibrado de ambos dispositivos,
el sistema se comporta como un par estéreo y se puede **triangular** la posición 3D de cada
píxel.

El proceso completo:

```
 captura ─► organizar ─► fase relativa ─► fase absoluta ─► [calibración] ─► reconstrucción ─► visualización
 (cámara)   (ordena los   (N-step phase    (código Gray →    (solo cuando     (X, Y, Z en mm,
            50 frames)    shifting)        u_p, v_p)         se recalibra)    nubes .ply)
```

La **calibración es opcional**: se hace una vez (o cuando se mueve la cámara o el proyector) y
después se pueden medir tantos objetos como se quiera reutilizando la calibración guardada.

---

## 2. Uso rápido

Hay dos formas de usar el sistema:

- **Interfaz web** (recomendada para operar el montaje):
  `.env/bin/python interfaz/servidor.py`. Ver §19.
- **Script**: `pipeline.py`, descrito a continuación.

Todo se controla desde `pipeline.py`, que **no recibe argumentos**: se editan las variables de
la sección `CONFIGURACIÓN DEL PIPELINE` y se ejecuta:

```bash
cd ~/Documents/Tesis
.env/bin/python pipeline.py
```

### 2.1 Medir objetos con el sistema ya calibrado (caso habitual)

```python
ETAPAS = {
    "patrones": False,
    "lightcrafter": False,     # True si hay que reconfigurar tiempos del proyector
    "captura": True,
    "organizar": True,
    "fase_relativa": True,
    "fase_absoluta": True,
    "calibracion": False,      # ← NO se recalibra
    "reconstruccion": True,
    "visualizacion": True,
}
CATEGORIAS = ["plano", "objeto"]
CAPTURA_CATEGORIA = "objeto"
CAPTURA_POSES = 3              # pide Enter antes de cada objeto/pose
```

- Antes de capturar, el pipeline **comprueba que exista una calibración** y muestra cuál usará
  (número de poses, error RMS y fecha). Si no existe, se detiene antes de encender la cámara.
- Las fases del patrón **no** se calculan (no hacen falta sin calibración).
- Las poses ya procesadas **se reutilizan** (fases y reconstrucción): solo se calculan las
  nuevas. Medir un objeto más cuesta ~5 s de proceso, más la visualización.
- La visualización muestra por defecto **la última pose** capturada (`VIS_POSE = "ultima"`).

### 2.2 Recalibrar el sistema

1. Captura 10–15 poses del tablero de círculos (`CAPTURA_CATEGORIA = "patron"`,
   `CAPTURA_POSES = 12`). Cubre **todo el campo** del proyector: tablero en el centro, en las
   cuatro esquinas, en los bordes izquierdo y derecho, y con inclinaciones de ±20–30°.
2. Pon `"calibracion": True`. El pipeline organiza, calcula las fases del patrón y calibra.
3. Revisa en la salida: error RMS por pose, la línea `Cobertura del proyector` y los avisos.
4. Vuelve a `"calibracion": False` para medir objetos.

> Cada recalibración guarda una copia en `calibraciones/historial/<fecha>/`, así que la anterior
> no se pierde. Después de recalibrar, haz commit de `calibraciones/` para que viaje con el código
> (§20.5).

### 2.3 Otros flujos

| Quiero… | Etapas en `True` |
|---|---|
| Procesar capturas que copié a mano a `capturas/` | `organizar` → `reconstruccion` (+ `visualizacion`) |
| Solo ver resultados ya calculados | `visualizacion` |
| Recalcular todo tras cambiar umbrales | Las de fase y `reconstruccion`, con `REHACER = True` |
| Cambié período o bits de los patrones | `patrones`, recargar los `.bmp` en el LightCrafter y recapturar todo (incluida la calibración) |

### 2.4 Scripts sueltos

Algunos módulos se pueden correr solos con argumentos (`--help` los lista):

```bash
.env/bin/python organizar_capturas.py --simular                # qué haría, sin escribir
.env/bin/python organizar_capturas.py --entrada ~/sesion3 --categoria objeto
.env/bin/python calibracion_estereo.py --distancia 15.0588 14.909
.env/bin/python reconstruccion_3d.py --categorias objeto --fase Fy
.env/bin/python capturar_patrones.py --categoria patron --poses 12
.env/bin/python visualizacion.py                               # usa su cabecera
```

`configurar_lightcrafter.py` se configura en su cabecera. `fase.py` se usa desde el pipeline.

---

## 3. Hardware y sincronización

```
Arduino (20 Hz) ──pin 9──► Cámara Line0 (trigger, flanco de subida)
                └─pin 10─► LightCrafter (trigger de entrada)
```

- **Arduino** (`arduino_pulses/arduino_pulses.ino`): conmuta los pines 9 y 10 **a la vez**
  escribiendo directamente en `PORTB`, cada 25 ms. Resulta una onda cuadrada de 20 Hz (50 ms por
  ciclo). El tiempo se acumula sumando `semiPeriodo` a `tiempoPrevio`, en lugar de leer `micros()`
  de nuevo, para que no haya deriva acumulada.
- **LightCrafter**: tiene cargada la secuencia `f_00 … f_49` y avanza **un patrón por pulso**, en
  bucle. La exposición y el período del patrón (49.7 ms / 50 ms) se fijan por USB con
  `configurar_lightcrafter.py`.
- **Cámara**: un frame por flanco de subida con 12 ms de exposición (`CAM_EXPOSICION_US`), que
  debe ser menor que el período de 50 ms.
- **No hace falta que la captura empiece en `f_00`**: el organizador encuentra el inicio de la
  secuencia buscando el par negro → blanco (§9).

Una secuencia completa tarda 50 × 50 ms = **2.5 s**. La escena no debe moverse durante ese
tiempo.

**Permisos USB del LightCrafter.** Si la etapa `lightcrafter` falla por permisos:

```bash
sudo chmod a+rw /dev/hidrawX       # el script dice cuál es X
```

---

## 4. Estructura del proyecto

```
Tesis/
├── pipeline.py               ← CONTROL: qué etapas correr y con qué opciones
├── configuracion.py          ← PARÁMETROS físicos y umbrales (compartidos)
│
├── patterns.py               ← generador de franjas binarias desplazadas
├── secuencia_patrones.py     ← etapa 'patrones': 50 .bmp para el LightCrafter
├── configurar_lightcrafter.py← etapa 'lightcrafter': USB-HID con el DLPC350
├── capturar_patrones.py      ← etapa 'captura': cámara FLIR con trigger externo
├── organizar_capturas.py     ← etapa 'organizar': segmenta y ordena capturas crudas
├── fase.py                   ← etapas 'fase_relativa' y 'fase_absoluta'
├── calibracion_estereo.py    ← etapa 'calibracion'
├── reconstruccion_3d.py      ← etapa 'reconstruccion'
├── visualizacion.py          ← etapa 'visualizacion'
│
├── arduino_pulses/           ← firmware del generador de pulsos
├── calibraciones/            ← calibración vigente + historial/ (VERSIONADA, §20.5)
├── instalar.sh, verificar.py, requirements.txt, instalacion/  ← instalación (§20)
├── interfaz/                 ← interfaz web (§19)
├── patterns/secuencia_completa_bmp/   f_00.bmp … f_49.bmp
│   (las tres carpetas de datos se ordenan igual: una carpeta por PROCESO de captura, §4.1)
├── capturas/                 ← CRUDAS: el código no las modifica; solo tú desde «Archivos» (a la papelera)
│   └── <AAAA-MM-DD_HHMM>/                 ← un proceso de captura
│       ├── proceso.json                   ← plan, hora, capturas y poses que salieron de él
│       └── <categoria>/<AAAAMMDD_HHMMSS>/ *_frame_XXX.tiff
├── capturas_ordenadas/       ← DERIVADAS (se pueden borrar y regenerar)
│   ├── manifiesto.json
│   └── <AAAA-MM-DD_HHMM>/<categoria>/pose_XX/{H,V}/P18_F00 … P18_F25.tiff + origen.json
├── resultados/               ← DERIVADOS
│   ├── <AAAA-MM-DD_HHMM>/fases/<categoria>/pose_XX_relativa.npz|.png, pose_XX.npz|.png
│   ├── <AAAA-MM-DD_HHMM>/reconstruccion/<categoria>/<cat>_pose_XX.ply|.npz, figura
│   ├── reconstruccion/<categoria>/<cat>_resumen.json   ← resumen de todas las poses
│   ├── calibracion/ comparaciones/ visualizacion/     ← lo que no es de una pose
│   └── …
└── Matlab_Codes/             ← código original de referencia (no se ejecuta)
```

### 4.1 Una carpeta por proceso de captura

Cada vez que capturas (un **proceso**: por ejemplo patrón × 8, plano × 3 y objeto × 1), todo va a
una carpeta con su fecha y hora de inicio, `AAAA-MM-DD_HHMM`. Esa misma carpeta existe en
`capturas/`, `capturas_ordenadas/` y `resultados/`. Para encontrar las poses de un día, se abre esa
carpeta en cualquiera de las tres.

- `capturas/<proceso>/proceso.json`: inicio y fin, plan, capturas por categoría y las poses
  organizadas que salieron de ellas.
- `capturas_ordenadas/<proceso>/<cat>/pose_XX/origen.json`: de qué captura y proceso salió cada pose.
- Los **nombres de pose** (`pose_23`) siguen siendo únicos dentro de su categoría en todo el
  sistema: las calibraciones, notas y selecciones los usan.
- La carpeta del proceso es solo dónde están: el módulo `rutas.py` la lee del manifiesto. Todo el
  sistema la usa, también la interfaz.
- Lo que no es de una pose queda fuera de las carpetas de proceso: calibraciones, comparaciones,
  resumen por categoría.

**Datos con la estructura anterior** (`capturas/<cat>/…`, sin carpeta de proceso): siguen
funcionando. Para pasarlos a la nueva estructura, usa `migrar_por_proceso.py`:

```bash
.env/bin/python migrar_por_proceso.py              # modo de prueba: muestra qué movería
.env/bin/python migrar_por_proceso.py --aplicar    # lo hace
.env/bin/python migrar_por_proceso.py --deshacer respaldo_migracion_<fecha>
```

- Agrupa los procesos igual que la pestaña Archivos.
- Solo **mueve** carpetas (renombra, en el mismo disco): no modifica ninguna imagen y conserva las
  fechas, así que no hay que recalcular nada.
- Actualiza el manifiesto (rutas y firmas) y escribe `proceso.json` y `origen.json`.
- Deja en `<DATOS>/respaldo_migracion_<fecha>/` el manifiesto, el registro y la lista de
  movimientos, para poder deshacerlo.

### 4.2 Importar capturas tomadas antes o en otro equipo

Si tienes una carpeta con subcarpetas `patron/`, `plano/` y `objeto/` (no hace falta que estén las tres):

- **Interfaz:** pestaña Archivos → *Importar capturas de otra carpeta*.
  1. Pulsa **📁 Elegir carpeta…** para buscarla en la ventana del sistema, o escribe la ruta y
     pulsa *Revisar*. La ventana se abre en el equipo donde corre el servidor y puede quedar detrás
     del navegador. Desde otro equipo de la red hay que escribir la ruta.
  2. Revisa lo que encontró (todavía no se copia nada) y pulsa *Importar*.
- **Terminal:**
  ```bash
  .env/bin/python importar.py /ruta/carpeta                       # muestra qué importaría
  .env/bin/python importar.py /ruta/carpeta --aplicar --procesar  # importa y procesa todo
  ```

Qué hace:

- **Copia** las capturas como un proceso nuevo, `capturas/<fecha>/…`, con su `proceso.json`. Tu
  carpeta no se toca, salvo con *Mover en vez de copiar* o `--mover`.
- Dentro de cada categoría, cada captura puede ser una subcarpeta con imágenes, un video o, si no
  hay subcarpetas, las imágenes sueltas (una sola captura).
- También reconoce nombres como `pattern`, `calib`, `plane` u `object`, e ignora las carpetas que
  no reconoce.
- La fecha del proceso sale del nombre de las capturas (`AAAAMMDD_HHMMSS`) o de la fecha de sus
  archivos.
- Omite las capturas que ya están en el sistema, así que importar dos veces no duplica nada.
- Deja como configuración en uso **solo ese proceso** y lo procesa: organizar, fases, calibración
  (si trae patrón) y reconstrucción.
- Si no trae patrón, reconstruye con la calibración en uso, que debe ser del mismo montaje.

**Categorías de captura:**

| Categoría | Qué es | Para qué se usa |
|---|---|---|
| `patron` | Tablero con grilla simétrica de **9 × 12 círculos blancos**, 15 mm entre centros | Calibración |
| `plano` | Superficie plana de referencia | Medir la exactitud (error de planitud) |
| `objeto` | Lo que se quiere medir | Reconstrucción 3D |

---

## 5. Configuración

### 5.1 `configuracion.py` — parámetros del sistema

| Grupo | Variable | Valor | Significado |
|---|---|---|---|
| Directorios | `DIR_PATRONES`, `DIR_CAPTURAS`, `DIR_ORDENADAS`, `DIR_RESULTADOS` | | Rutas, relativas a la raíz del proyecto |
| Proyector | `PROYECTOR_ANCHO/ALTO` | 912 / 1140 | Resolución nativa del LightCrafter 4500 |
| | `PERIODO` | 18 | Período de franja en px del proyector |
| | `N_PASOS` | = `PERIODO` | Corrimientos de 1 px hasta completar el período |
| | `N_BITS_GRAY` | 6 | 2⁶ · 18 = 1152 ≥ 1140 px |
| | `ORDEN_BITS_GRAY` | `"auto"` | `"msb"`, `"lsb"` o detección automática |
| | `LCR_EXPOSICION_US/PERIODO_US` | 49700 / 50000 | Tiempos del patrón |
| Cámara | `CAM_EXPOSICION_US` | 12000 | Exposición |
| | `CAM_DEBOUNCE_US` | 500 | Filtro antirrebote de Line0 |
| | `CICLOS_POR_CAPTURA` | 1 | > 1 captura varios ciclos que se promedian |
| Fase | `GAMMA_TH` | 0.15 | Modulación mínima γ de las franjas V (fase X) |
| | `GAMMA_TH_Y` | 0.03 | Modulación mínima γ de las franjas H (fase Y) |
| | `SUAVIZADO_FASE_PX` | 1.5 | σ del filtro gaussiano sobre S y C |
| | `UMBRAL_INTENSIDAD` | 25 | Nivel mínimo en la imagen blanca |
| | `MED_FILT` | 5 | Mediana para corregir errores de orden de franja |
| | `BORDE_MASCARA` | 15 | Píxeles descartados en el borde de la imagen |
| Patrón | `PATRON_COLUMNAS/FILAS` | 9 / 12 | Círculos por fila / columna |
| | `PATRON_DISTANCIA_MM` | 15.0 | Número o par `(dx, dy)` (§12.6) |
| | `PATRON_TIPO`, `PATRON_COLOR_CIRCULOS` | symmetric / white | |
| | `CALIBRACION_POSES` | `"ultima_sesion"` | Poses que calibran: `"ultima_sesion"`, `"todas"` o lista (§12.4) |
| | `HORAS_ENTRE_SESIONES` | 2 | Capturas separadas por más que esto son sesiones distintas |
| Datos | `SOLO_CONFIGURACION_ACTUAL` | `True` | Solo se procesan y muestran las poses del último proceso con patrón en adelante (§9.1) |
| | `MINUTOS_ENTRE_PROCESOS` | 3 | Capturas sin registro: una pausa mayor separa dos procesos |
| 3D | `FASE_TRIANGULACION` | `"auto"` | §13.3 |
| | `CALIBRACION` | `"independiente"` | o `"conjunta"` (archivo `_J`) |
| | `Z_MIN_MM`, `Z_MAX_MM` | 100 / 1500 | Rango físico válido de Z |
| | `SALTO_MAX_MM` | 5 | Salto local máximo (filtro de atípicos) |

### 5.2 `pipeline.py` — qué correr

- `ETAPAS`: diccionario de etapas en orden fijo. `True` = se ejecuta.
- `CATEGORIAS`: categorías a procesar en fase y reconstrucción. `patron` se agrega solo si
  `calibracion` está activa.
- `CAPTURA_*`: categoría, número de poses, ciclos por pose y si se espera Enter.
- `CAPTURA_PLAN`: varias categorías en una sola sesión, por ejemplo
  `{"patron": 12, "plano": 3, "objeto": 1}`. Reemplaza a `CAPTURA_CATEGORIA` y `CAPTURA_POSES`.
  Se captura todo el plan (patrón → plano → objeto) antes de las demás etapas; con `q` se pasa
  a la siguiente categoría.
- `ORGANIZAR_*`: carpetas de entrada, categoría forzada y reorganización total.
- `REHACER`: ignora la caché y recalcula las fases y la reconstrucción de todas las poses.
- `FASE_TRIANGULACION`, `CALIBRACION_USADA`: sobrescriben los de `configuracion.py`.
- `VIS_CATEGORIA`, `VIS_POSE` (`"ultima"` o `"pose_XX"`), `VIS_COLOR_3D`.

Funciones del pipeline:

- `main()`: valida `ETAPAS`. Avisa si se captura sin organizar. Si se reconstruye sin
  calibrar, llama a `_verificar_calibracion_existente()` **antes** de cualquier etapa. Luego
  ejecuta cada etapa midiendo su tiempo; un error detiene el proceso indicando la etapa.
- `_categorias_fase()`: categorías para las etapas de fase.
- `ruta_calibracion()`: `Estereo_TSC_0_2.npz` o `Estereo_TSC_0_2_J.npz`.
- `etapa_<nombre>()`: un envoltorio por etapa que llama al módulo correspondiente con los
  parámetros de la configuración.

**Añadir una etapa:** escribe `def etapa_x()`, agrégala a `FUNCIONES` y a `ETAPAS` en la posición
deseada.

---

## 6. Etapa `patrones`: la secuencia proyectada

`secuencia_patrones.py` genera **50 imágenes de 912 × 1140**:

| Índices | Contenido | Uso |
|---|---|---|
| `f_00`–`f_17` | 18 franjas **horizontales** binarias, P = 18 px, desplazadas 1 px | Fase Y |
| `f_18`–`f_23` | 6 bits de código Gray horizontal | Orden de franja Y |
| `f_24`–`f_41` | 18 franjas **verticales** binarias desplazadas 1 px | Fase X |
| `f_42`–`f_47` | 6 bits de código Gray vertical | Orden de franja X |
| `f_48` | Negro | Detección del inicio de la secuencia |
| `f_49` | Blanco | Textura, umbral, detección de círculos |

Funciones:

- `patterns.generar_patrones_binarios(width, height, periodo, num_pasos, orientacion)`: onda
  cuadrada del 50 %: blanco donde `(x + shift) mod P < P/2`, con `shift = i·P/num_pasos`.
- `crear_patrones_gray(ancho, alto, paso, orientacion, cantidad_bits)`: cada columna (o fila)
  tiene índice de período `j = x // P` y código Gray `g = j XOR (j >> 1)`. Se genera un plano por
  bit, del **más significativo al menos significativo** (MSB primero).
- `crear_patrones_uniformes`: negro y blanco.
- `crear_secuencia_completa()`: arma la lista en el orden de la tabla.
- `guardar_secuencia()`: escribe `f_XX.bmp` y `secuencia.json`.

**¿Por qué franjas binarias y N = P?** El DMD es binario: una franja binaria se proyecta con
precisión y sin necesidad de calibrar la respuesta (gamma) del proyector. Una onda cuadrada tiene
armónicos impares (3, 5, 7…), pero con N = P = 18 pasos de 1 px, un armónico k solo se confunde
con la fundamental si k ≡ ±1 (mod 18), es decir a partir de k = 17. Ese armónico tiene amplitud
1/17 y además el desenfoque lo atenúa casi por completo. Por eso la fase calculada es exacta: al
decodificar los propios `.bmp`, u_p coincide con la columna real con error **0.000 px**.

> **Orden de los bits Gray.** En los `.bmp` el primer bit es el MSB. Con la secuencia cargada
> actualmente en el LightCrafter, la cámara los recibe en orden **inverso** (LSB primero). El
> código lo detecta solo (`ORDEN_BITS_GRAY = "auto"`), así que funciona en ambos casos.

Tras regenerar los patrones hay que cargarlos en el LightCrafter con el software de TI
(*Pattern Sequence*, trigger externo, un patrón por trigger, en el orden `f_00 … f_49`).

---

## 7. Etapa `lightcrafter`: tiempos del proyector

`configurar_lightcrafter.py` habla con el controlador DLPC350 por **USB-HID** directamente sobre
`/dev/hidraw*`, sin el software de TI.

- `LightCrafter4500._buscar_hidraw()`: busca en `/sys/class/hidraw` el dispositivo con
  VID:PID `0451:6401` y elige la interfaz de control.
- `_enviar_comando(cmd, payload, lectura)`: arma el paquete HID de 64 bytes + Report ID:
  - byte de banderas (bit 7 = lectura, bit 6 = pedir respuesta);
  - número de secuencia;
  - longitud;
  - comando de 16 bits;
  - datos.

  Espera la respuesta 2 s y comprueba el bit de error (NACK).
- `configurar_exposicion_y_periodo(exp, per)`:
  1. Pasa a *Pattern Display Mode* (`0x1A1B`).
  2. Detiene la secuencia (`0x1A24 = 0`).
  3. Escribe exposición y período (`0x1A29`, dos `uint32` en µs).
  4. Valida (`0x1A1A`) y espera a que termine.
  5. Si la validación indica que la secuencia no tiene *Insert Black* (bits 0/3), iguala
     período = exposición y valida de nuevo.
  6. Interpreta las banderas de error y reinicia la secuencia (`0x1A24 = 2`).
- `main()`: lee los valores actuales, escribe los nuevos y los vuelve a leer para confirmar.

---

## 8. Etapa `captura`: adquisición con la cámara

`capturar_patrones.py`:

- **`CamaraFLIR`** (se usa con `with`): abre la cámara con PySpin **una sola vez** y la configura:
  - exposición manual fija;
  - filtro antirrebote en Line0;
  - trigger *FrameStart* por flanco de subida en Line0;
  - retardo de trigger opcional;
  - `TriggerOverlap = Off`, para que no se encolen disparos espurios;
  - buffer `OldestFirst`, para recibir los frames en orden.

  Al salir apaga el trigger y libera la cámara aunque haya errores.
- **`capturar(cantidad)`**: adquiere `cantidad` frames seguidos. Los guarda **en memoria**
  durante la adquisición; escribir a disco en medio haría perder triggers. Si pasan
  `CAM_TIMEOUT_MS` sin pulso, da un error que sugiere revisar el Arduino. Al final imprime el
  Δt entre frames y avisa si hay un salto (pulso perdido).
- **`guardar_captura(frames, salida, categoria)`**: crea `capturas/<categoria>/<fecha_hora>/`
  con un `.tiff` por frame y, opcionalmente, un `.avi` FFV1 sin pérdida.
- **`capturar_poses(categoria, poses, ciclos)`**: pide Enter antes de cada pose y captura
  `50 × ciclos` frames. En la pausa:
  - `q` termina;
  - `r` **repite la pose anterior**: la descartada va a la papelera.
- **Control de cada pose al capturarla** (`organizar_capturas.evaluar_captura`, ~0.1 s). Usa la
  misma segmentación que *Organizar* y revisa:
  - que esté el par negro/blanco y haya contraste. Sin proyección, el brillo medio varía < 8
    niveles; en una captura buena, ~80;
  - la pureza de las franjas H y V (< 0.5 = frame perdido o secuencia distinta);
  - la modulación V;
  - el % saturado en la imagen blanca y si la escena se movió (estos dos son avisos, no
    invalidan la pose).

  Si la pose **no sirve**, el proceso pregunta: Enter/`r` = repetirla (la mala va a la papelera),
  `s` = guardarla igual, `q` = terminar. En la interfaz son botones, y el resultado de cada pose
  aparece en la pestaña Cámara.
- **Sin trigger** (Arduino apagado o desconectado): en vez de abortar todo el plan, pregunta si
  reintentar esa pose.
- La exposición inicial es `CAM_EXPOSICION_US`, o la de **Ajustes → Cámara**. Durante la vista
  previa se puede cambiar en vivo (§19.3).

**Varios ciclos.** Con `CICLOS_POR_CAPTURA = 2` o más, el organizador promedia los ciclos de la
misma escena. El ruido baja ∝ 1/√ciclos, lo que ayuda sobre todo con las franjas H de bajo
contraste. Cada ciclo extra son 2.5 s más de captura.

---

## 9. Etapa `organizar`: de capturas crudas a poses

`organizar_capturas.py` convierte capturas **en cualquier forma** en poses ordenadas, sin
modificar los originales.

**Qué acepta:**
- Carpetas de imágenes (`.tiff/.tif/.png/.bmp/.jpg/.pgm`, TIFF multipágina) con cualquier nombre.
  Se ordenan de forma natural: `img_2` antes que `img_10`.
- Videos (`.avi/.mp4/.mov/.mkv…`). Si un video tiene tantos frames como imágenes hay en su misma
  carpeta, se considera duplicado y se ignora.
- Cualquier número de frames: 50 empezando en cualquier patrón, varios ciclos o grabaciones
  largas con varias poses.

**Algoritmo (`organizar()`):**

1. **`descubrir_fuentes(raices)`**: recorre las carpetas de entrada, excepto las de salida y
   resultados.
2. **`cargar_frames(fuente)`**: lee todos los frames en gris conservando la profundidad de bits.
3. **`segmentar_secuencias(frames, 50)`**:
   - Calcula la intensidad media de cada frame.
   - **`detectar_pares_negro_blanco`** busca frames muy brillantes precedidos de uno muy oscuro
     (umbrales al 20 % del rango). Ese par es `f_48 → f_49`, el final de un ciclo.
   - Con **exactamente 50 frames**, el ciclo se reordena circularmente (el `circshift` de MATLAB).
   - Con **más frames**, los blancos deben estar separados por múltiplos de 50. Si no, se perdió
     o sobró un frame: la grabación se parte en tramos continuos y los ciclos rotos se descartan.
   - **`_ciclo_estable`** compara la media de los corrimientos H con la de los V. Si su
     correlación es < 0.97, la escena se movió durante el ciclo y este se descarta.
   - **`_agrupar_ciclos`** promedia los ciclos consecutivos de la misma escena (correlación de la
     imagen blanca ≥ 0.98). Si la escena cambió, se crean poses distintas.
4. **`verificar_secuencia`** calcula, para H y V:
   - la **pureza**: fracción de la energía temporal (sin DC) en la frecuencia fundamental. Cerca
     de 1 si la secuencia está bien alineada, < 0.5 si se coló un frame Gray, negro o blanco;
   - la **modulación** mediana.

   También comprueba que el negro y el blanco sean los frames extremos.
5. **Categoría**:
   1. `categoria_por_nombre`: palabras clave en la ruta (`patron/pattern/calib/circle…`,
      `plano/plane/flat…`, `objeto/object/pieza…`). Basta con guardar en `capturas/patron/` etc.
   2. Si el nombre no lo indica, `categoria_por_contenido`: si se detecta la grilla de círculos es
      `patron`; si no, **se pregunta en la terminal** si es plano u objeto.
   3. `ORGANIZAR_CATEGORIA_FORZADA` asigna una categoría a todo lo nuevo.
6. **`guardar_pose`** escribe `H/` = `[f_00…f_23, negro, blanco]` y
   `V/` = `[f_24…f_47, negro, blanco]` como `P18_F00 … P18_F25.tiff`, igual que `savePatterns.m`.
7. Todo se registra en **`capturas_ordenadas/manifiesto.json`**:
   - fuente y su firma (nombres, tamaños y fechas de los archivos);
   - frames usados y ciclos promediados;
   - cómo se decidió la categoría;
   - métricas de calidad.

**Incremental:** las fuentes ya registradas se omiten y las nuevas reciben el siguiente número de
pose.
- **Capturas rechazadas:** si una captura no tiene ningún ciclo válido, se registra en
  `manifiesto["rechazadas"]` con el motivo y no se vuelve a leer en cada ejecución. Por ejemplo:
  «brillo casi constante (29–30): el proyector no estaba proyectando la secuencia o la cámara no
  está sincronizada». Aparece en la pestaña *Archivos* como **rechazada**.
- **`ORGANIZAR_REHACER = True`** (o `--rehacer`) rehace las categorías indicadas desde cero:
  - lo organizado antes va a la papelera;
  - **cada captura conserva su nombre de pose**, porque las calibraciones guardan esos nombres;
  - los números de las poses borradas no se reutilizan.
- Las rutas del manifiesto y la firma de cada captura son relativas a la carpeta de datos. Por eso
  siguen valiendo aunque los datos se muevan de carpeta o de disco (`TESIS_DIR_DATOS`).
- Para **excluir** una pose mala, muévela a la papelera desde la pestaña *Archivos*.

---

### 9.1 Configuración vigente: un solo montaje a la vez — `sesiones.py`

`capturas_ordenadas/` acumula todo lo capturado: poses de montajes anteriores, pruebas sueltas,
corridas repetidas. Con la calibración actual, las poses de otro montaje darían resultados falsos.
Por eso, con `SOLO_CONFIGURACION_ACTUAL = True` (por defecto), **las etapas de proceso y la
interfaz solo usan y muestran la configuración vigente**:

- Un **proceso** es una ejecución de la captura, por ejemplo patrón × 8 + plano × 3 + objeto × 1.
  `etapa_captura` lo registra en `procesos_captura.json`, en la carpeta de datos, junto con sus
  carpetas de `capturas/`. Las capturas anteriores a ese registro se agrupan por tiempo: una
  pausa de más de `MINUTOS_ENTRE_PROCESOS` (3 min) empieza otro proceso.
  Si el patrón sigue capturándose después de una pausa (menos de 2 h), es el mismo proceso.
- Una **configuración** empieza en un proceso que capturó el patrón e incluye los procesos
  siguientes hasta el próximo patrón. Así, un objeto medido mañana sin recalibrar sigue viéndose
  junto a su calibración.
- La **configuración vigente** es, por defecto, **la última**. Al capturar un patrón nuevo, lo
  anterior desaparece de la vista y del proceso.
- **Se puede elegir otra** en la pestaña **Archivos** (*Usar esta configuración*). Si en el
  historial hay una calibración hecha con sus poses, se pone en uso también. Lo mismo ocurre al
  revés: al elegir una calibración en la pestaña **Calibración**, la vigente pasa a ser la
  configuración de la que salió. La elección se guarda en `configuracion_elegida.json`, en la
  carpeta de datos. *Volver a la última* la borra, y capturar un patrón nuevo también.
- **Selección manual** (pestaña Calibración → *Recalibrar con capturas elegidas*): en vez de una
  configuración por procesos, eliges tú las poses exactas, de cualquier fecha (§19.2). Se guarda en
  `configuracion_elegida.json` como `{"seleccion": {cat: [poses]}}`, y las etapas y la interfaz
  usan solo esas poses. *Volver a la última* o capturar un patrón nuevo la quitan.
- Calibrar con la etapa *Calibración* usa solo las poses del patrón de la configuración vigente.
  Por eso, después de un proceso completo (patrón + plano + objeto), basta marcar *Calibración*
  para calibrar solo con ese proceso.
- Lo anterior **no se borra**: sigue en `capturas/`, `capturas_ordenadas/` y `resultados/`, y se
  ve en la pestaña *Archivos*, donde se puede mover a la papelera (§19.2). Para usar todo otra
  vez, pon `SOLO_CONFIGURACION_ACTUAL = False`.
- El pipeline la indica al empezar:
  `Configuración vigente desde 2026-11-24 13:02 (patron 8, plano 3, objeto 1; se ignoran 9 proceso(s) anteriores)`.
  La interfaz la muestra en la tarjeta *Poses*.

## 10. Etapa `fase_relativa`: phase shifting

### 10.1 Teoría

En cada píxel, la intensidad del paso n (n = 0…N−1) es aproximadamente

```
I_n = A + B·cos(φ + 2πn/N)
```

donde A es el fondo, B la amplitud de las franjas y φ la fase buscada. Proyectando sobre la
frecuencia fundamental:

```
S = Σ I_n · sin(2πn/N)        C = Σ I_n · cos(2πn/N)

φ = −atan2(S, C)               ∈ [−π, π]   (fase envuelta)
B = 2·√(S² + C²) / N
A = media(I_n)
γ = B / A                      (modulación o contraste, entre 0 y 1)
```

γ mide la calidad de cada píxel: cerca de 0 no hay franjas (sombra, fondo, desenfoque fuerte);
en estas capturas vale ≈ 0.55 en las franjas V y solo 0.08–0.25 en las H (§16).

### 10.2 Implementación: `fase.fase_relativa(imagenes, gamma_th, suavizado)`

1. Convierte la pila a `float32`. Las capturas son de 8 bits, así que no se pierde nada y se usa
   la mitad de memoria.
2. Calcula S y C como **un producto matriz-vector** (BLAS) del vector de senos/cosenos por la
   pila aplanada (N × píxeles). Es mucho más rápido que multiplicar y sumar imagen por imagen.
3. Calcula B **sin suavizar**, para que el umbral γ signifique siempre lo mismo.
4. Si `suavizado > 0` (por defecto 1.5 px), aplica un **filtro gaussiano a S y a C**. Promediar el
   numerador complejo, en lugar de la fase, no sesga la fase en superficies suaves. A cambio:
   - elimina el **moteado de la rejilla del DMD**, visible como una trama fina en los mapas;
   - reduce el ruido;
   - suaviza ~2 px los bordes de discontinuidades de profundidad.

   Con las capturas actuales baja el error de planitud de ~0.71 a ~0.39 mm.
5. Calcula `φ = −atan2(S, C)` y `γ = B / A`.

### 10.3 Sobre el filtro de `ComputeNStepPhase.m`

El MATLAB convoluciona la pila, en el eje temporal, con un coseno ventaneado (Hanning) antes de
calcular S y C. Pero S y C **solo miran la frecuencia fundamental**, y una convolución circular se
convierte en un producto en frecuencia. Por eso ese filtro equivale **exactamente** a multiplicar
el coeficiente de la fundamental por una constante H[1]. Se verificó numéricamente:

- la fase sale rotada −0.0052 rad (= −0.015 px);
- B queda multiplicado por una ganancia constante (el código Python anterior la compensaba).

El filtro no quitaba ningún armónico que importara, porque ya los rechaza N = P (§6). Costaba
3 FFT sobre toda la pila. En Python se eliminó: el resultado es el mismo sin el sesgo de 0.015 px
y la etapa es ~6 veces más rápida.

### 10.4 Etapa: `fase.etapa_fase_relativa(...)`

- Para cada categoría y pose calcula la fase de `V/` (X) y de `H/` (Y).
- **Caché:** si `pose_XX_relativa.npz` es más reciente que todas las imágenes de la pose, se
  reutiliza (`_actualizado`).
- **Paralelismo:** las poses pendientes se procesan en hasta 4 hilos (`_en_paralelo`). NumPy y
  OpenCV liberan el GIL en las operaciones pesadas, así que varios hilos trabajan de verdad en
  paralelo sin copiar datos entre procesos.
- **Salida:** `resultados/fases/<cat>/pose_XX_relativa.npz` con `phiX, phiY, AX, AY, BX, BY,
  qX, qY` (q = γ), más un `.png` con las fases envueltas y los mapas de modulación.

---

## 11. Etapa `fase_absoluta`: código Gray y coordenadas del proyector

La fase relativa se repite cada período (18 px del proyector). El **código Gray** dice en qué
período está cada píxel (el *orden de franja* k = 0…63).

### 11.1 Binarización — `bits_gray(imagenes_gray, umbral, med_filt_size)`

- `bit = I_gray > A`: el umbral es el fondo A de las franjas de la misma orientación, que está
  justo a mitad de camino entre blanco y negro en cada píxel. Se adapta solo a la reflectividad
  del objeto.
- Filtro de **mediana 5×5** en cada plano binario: elimina el moteado del DMD sin desplazar los
  bordes rectos del código.

### 11.2 Decodificación — `decodificar_gray(bits, orden_bits)`

Gray → binario por XOR acumulado desde el bit más significativo:
`b₀ = g₀`, `bᵢ = bᵢ₋₁ XOR gᵢ`, y `k = Σ bᵢ·2^(B−1−i)`.

`orden_bits = "msb"` usa el primer plano capturado como MSB; `"lsb"` invierte el orden.

### 11.3 Detección del orden — `detectar_orden_bits(...)`

Decodifica con los dos órdenes y se queda con el que da una fase absoluta **más continua**: la
menor fracción de vecinos con saltos > π (`_saltos_fase`). Con el orden equivocado, k salta
caóticamente, así que la diferencia es enorme. Por eso se evalúa sobre la imagen submuestreada a
la mitad en cada eje, lo que la hace 4 veces más barata.

### 11.4 Desenvolvimiento — `fase_absoluta(phi, k, P, med_filt_size)`

1. **Alinear el corte.** La fase envuelta salta de π a −π en un lugar que no coincide con los
   bordes del código Gray. Con la onda cuadrada de `patterns.py`, la franja blanca está centrada
   en c = (⌈P/2⌉ − 1)/2 = 4 px, y los bordes Gray caen en φ = −2π(c + 0.5)/P = −π/2
   (`desfase_corte`). Se rota la fase para que su corte coincida con esos bordes.
2. `Φ = φ_rotada + 2πk − rotación`.
3. **Corrección de errores de ±1 orden.** En los bordes de cada período, el bit Gray puede leerse
   del lado equivocado. Se compara Φ con su mediana local y se corrige el número entero de
   períodos de diferencia:

   ```
   Φ ← Φ − 2π·round((Φ − mediana(Φ)) / 2π)
   ```

   Es igual que `UnwrapPhaseGrayCode.m`.

### 11.5 Coordenada del proyector — `coordenada_proyector(Φ, P)`

```
u_p = Φx · P / (2π) + c        v_p = Φy · P / (2π) + c        (c = 4 px para P = 18)
```

u_p es la **columna** del proyector que ilumina el píxel y v_p la **fila**. Verificado con los
`.bmp`: error 0.000 px.

> En este montaje la cámara ve el proyector girado 180°: u_p y v_p **decrecen** al avanzar en la
> imagen. Es válido para el modelo pinhole y no requiere ningún cambio.

### 11.6 Máscaras — `mascara_valida(...)`

- `MaskX = (γx ≥ GAMMA_TH) & (blanco > UMBRAL_INTENSIDAD) & fuera del borde`.
- `MaskY` = lo mismo con `γy ≥ GAMMA_TH_Y`. El umbral es menor porque las franjas H tienen poco
  contraste en este proyector (§16) y aun así Fy es la fase más útil (§13.3).
- `MaskC = MaskX & MaskY`.

### 11.7 Etapa: `fase.etapa_fase_absoluta(...)` / `_fase_absoluta_pose(...)`

- Lee **solo las 8 imágenes que necesita**: los 6 bits Gray de cada orientación y la imagen
  blanca. La fase relativa ya está en el `.npz` anterior.
- Usa la misma caché y el mismo paralelismo que la fase relativa.
- **Salida:** `resultados/fases/<cat>/pose_XX.npz` con:
  - `Fx, Fy`: fase absoluta;
  - `up, vp`: coordenadas del proyector;
  - `kX, kY`: orden de franja;
  - `qFx, qFy`: modulación;
  - `BX, BY`: amplitud;
  - `Itex`: textura, la imagen blanca;
  - `MaskX, MaskY, MaskC`;
  - `orden_bits_V/H`.

  Más un `.png` con la textura, u_p y v_p.

---

## 12. Etapa `calibracion` (opcional): calibración estéreo

El proyector se modela como una **cámara inversa**: tiene intrínsecos, distorsión y una pose
respecto a la cámara. Para calibrarlo hacen falta, en varias poses de un tablero plano,
correspondencias entre:

- la posición conocida de cada círculo en el tablero (mm);
- su posición en la cámara (u_c, v_c), detectada en la imagen blanca;
- su posición en el proyector (u_p, v_p), leída de la fase.

**Cuándo recalibrar:** si se movió o se reenfocó la cámara o el proyector, o si cambió el zoom.
Si el montaje no cambió, no hace falta: la etapa queda desactivada y la reconstrucción usa la
calibración guardada.

**Todas las poses de una calibración deben ser del mismo montaje.** Si capturas poses nuevas del
tablero otro día, las anteriores siguen en `capturas_ordenadas/patron/`. Basta un movimiento de
1–2° de la cámara o el proyector para que las sesiones sean incompatibles. Mezclarlas da un error
estéreo enorme (12.8 px en vez de 0.6), aunque cada cámara por separado siga dando ~0.5 px, y los
planos salen **curvos** (1.5 mm de error de planitud en vez de 0.5). Por eso, por defecto, solo
calibra la **última sesión** (`CALIBRACION_POSES`, §12.4).

### 12.1 Detección del tablero — `detectar_puntos_tablero(...)`

- Suaviza la imagen blanca (gaussiana 5×5) y la **invierte**: `findCirclesGrid` busca blobs
  oscuros y los círculos son blancos.
- `crear_detector_circulos()` configura un `SimpleBlobDetector` tolerante al moteado del DMD:
  - área entre 80 y 15000 px;
  - circularidad ≥ 0.55;
  - convexidad ≥ 0.65;
  - inercia ≥ 0.45.
- Prueba primero la búsqueda normal y, si falla, con `CALIB_CB_CLUSTERING`.
- Si no encuentra los 9 × 12 círculos, la pose se descarta con un aviso.

### 12.2 Máscara del tablero — `create_mask_cb(...)`

Envolvente convexa de los círculos, expandida `offset` px (10) hacia afuera, como
`createMaskCB.m`. Se quitan los bordes de la imagen.

### 12.3 Limpieza de fase — `ajustar_polinomio_2d(...)` (CleanPhase)

Sobre un plano, u_p(u_c, v_c) y v_p(u_c, v_c) son funciones suaves. En lugar de leer la fase
ruidosa directamente en el centro de cada círculo, se ajusta un **polinomio 2D de grado 5**
(21 términos) sobre todo el tablero y se evalúa en los centros:

- Coordenadas normalizadas (media 0, desviación 1) para que el sistema esté bien condicionado.
- Submuestreo 2×2, que da suficientes puntos y es 4 veces más rápido.
- **Rechazo iterativo de atípicos:** hasta 3 iteraciones descartando residuos > 3σ, con σ robusta
  calculada por MAD.
- `_mascara_ajuste`: si la modulación H es tan baja que quedaría < 30 % del tablero, baja el
  umbral (×0.7 cada vez) hasta conservarlo. El ajuste con rechazo compensa el ruido extra.

El residuo del ajuste se reporta por pose (`residuo ajuste u=… v=… px`): con el suavizado de
fase es ~0.05 px en u y ~0.1–0.3 px en v.

### 12.4 Calibración con OpenCV — `ejecutar_calibracion_estereo(...)`

Igual que `Traditional_StereoCalib.m` (2 coeficientes radiales y tangencial, sin skew):

0. **Selección de poses** (`sesiones_patron`, `seleccionar_poses`). Agrupa las poses del patrón
   por **proceso de captura**, el mismo agrupamiento del resto del sistema (§9.1). Se detectan los círculos en
   todas las poses, pero solo calibran las que elige `CALIBRACION_POSES`:
   - `"ultima_sesion"` (por defecto): la sesión más reciente;
   - `"todas"`;
   - una lista, por ejemplo `["pose_08", "pose_09", ...]`.

   En la interfaz es la opción **Poses del patrón** de *Ajustes → Calibración*. Por línea de
   comandos: `calibracion_estereo.py --poses todas` o `--poses pose_08 pose_09 …`.
1. `calibrateCamera` de la cámara y del proyector **por separado** (`CALIB_FIX_K3` → k1, k2, p1,
   p2).
2. `stereoCalibrate` con los intrínsecos fijos → **`Estereo_TSC_0_2.npz`** (equivale a
   `estimateStereoBaseline`).
3. `stereoCalibrate` refinando todo junto → **`Estereo_TSC_0_2_J.npz`**.
4. **Errores de reproyección por pose** (`errores_reproyeccion`), para todas las poses detectadas,
   también las que no se usaron:
   - **cámara** y **proyector**: cada uno con su propia pose del tablero (`solvePnP`). Miden los
     intrínsecos y las correspondencias, pero **no** delatan un montaje que se movió;
   - **estéreo**: una sola pose del tablero vista por los dos a través de R, T. Es el mismo
     criterio que minimiza `stereoCalibrate` (Gauss-Newton por pose con `composeRT`) y es el que
     importa para reconstruir;
   - **ΔR** y **ΔT**: diferencia entre la R, T de la calibración y la que se deduce solo de esa
     pose.

   Se marcan con `<-- no coherente con la línea base` las poses cuyo error estéreo supera 3× la
   mediana (mínimo 2 px). Si el RMS estéreo supera 3× el de cámara y proyector, se avisa de que
   las poses vienen de montajes distintos. Todo queda en el `.json` (`errores_por_pose`) y en la
   pestaña **Calibración** de la interfaz (§19.2).
5. **Cobertura del proyector:** el rango de u_p y v_p que cubren los círculos de todas las poses.
   Fuera de ese rango el modelo, sobre todo la distorsión, **se extrapola**. Si cubre menos del
   70 % en algún eje, se avisa. El rango se guarda en el `.npz` y la reconstrucción avisa cuando
   usa puntos fuera de él.
6. **Control de calidad (`control_calidad`).** La calibración nueva se guarda siempre en
   `historial/<fecha>/`, pero **solo se pone en uso si pasa el control**:

   | Criterio | Variable | Límite |
   |---|---|---|
   | RMS estéreo | `CALIB_RMS_ESTEREO_MAX_PX` | ≤ 1.5 px |
   | RMS estéreo / máx(cámara, proyector) | `CALIB_RAZON_ESTEREO_MAX` | ≤ 3 |
   | Poses del patrón usadas | `CALIB_POSES_MIN` | ≥ 6 |
   | Fracción del ancho y del alto del proyector cubierta | `CALIB_COBERTURA_MIN` | ≥ 40 % |

   - Si no lo pasa, el registro lista los motivos, sigue en uso la anterior y **el pipeline se
     detiene antes de reconstruir**, porque usar la anterior con capturas de otro montaje daría
     resultados falsos.
   - Para usarla igual: `CALIBRACION_FORZAR = True` en `pipeline.py`, `--forzar`, o *Usar esta
     calibración* en la pestaña Calibración, que pide confirmación y muestra los motivos.
   - Si no había ninguna calibración, se pone en uso igual, con un aviso.
   - El resultado queda en el `.json` (`control_calidad`), y la interfaz marca las calibraciones
     rechazadas con ⚠.

### 12.5 Salidas

- `Estereo_TSC_0_2.npz` y `Estereo_TSC_0_2_J.npz`:
  - `Ac, Ap`: matrices intrínsecas de cámara y proyector;
  - `dist_cam, dist_proj`: `[k1, k2, p1, p2, k3]`;
  - `Kr1, Kt1, Kr2, Kt2`: los mismos coeficientes en el formato del MATLAB;
  - `R, T`: pose del proyector respecto a la cámara, `X_p = R·X_c + T`, en mm;
  - `E, F`;
  - errores RMS, `cobertura_up`, `cobertura_vp`.
- `Estereo_TSC_0_2.json`: resumen legible con fecha, poses, criterio de selección
  (`poses_criterio`), errores por pose (`errores_por_pose`, con sesión y hora de cada una),
  parámetros y cobertura.
- `patron_PhasesData.npz`: correspondencias `M` (ajustadas) y `M_raw` (sin ajustar) de las poses
  usadas, puntos del mundo e imágenes; equivale a `Estereo_PhasesData.mat`. Además,
  `poses_detectadas` y `M_detectadas` traen todas las poses con el tablero detectado, para evaluar
  también las no usadas. Los mapas de `RegWcordtoImage.m`
  (`Maps`) solo se guardan con `--mapas`, porque solo los usan las calibraciones híbridas de
  MATLAB y ocupan ~10 MB por pose.
- `diagnostico_calibracion_pose_00.png`: círculos detectados y residuos del ajuste polinomial.

### 12.6 Sobre el tamaño real del tablero

La cámara calibrada sale con fx/fy = 1.0098, algo raro en un sensor de píxeles cuadrados. Los
scripts de MATLAB tienen comentada la corrección `worldPoints = (worldPoints/15).*[15.0588
14.9090]`, cuyo cociente es 1.0100. Al calibrar con esa escala, la cámara queda con fx ≈ fy y
el mismo error RMS. Esto indica que **el tablero impreso no mide exactamente 15 × 15 mm**.

- **Mídelo con un calibrador** (por ejemplo, la distancia entre el primer y el último círculo de
  una fila y de una columna) y pon el resultado en `PATRON_DISTANCIA_MM = (dx, dy)`.
- Un error de escala del tablero se traslada directamente a la escala de toda la reconstrucción.

---

## 13. Etapa `reconstruccion`: triangulación 3D

### 13.1 Rayo de la cámara

Para el píxel (u_c, v_c): `r = Ac⁻¹·[u_c, v_c, 1]ᵀ`. Se le quita la distorsión con
**`comp_distortion_oulu`**, que invierte iterativamente (20 iteraciones) el modelo radial +
tangencial, como `comp_distortion_oulu.m`. El punto 3D está en `X = Z·r̃`, con `r̃ = (x, y, 1)`.

### 13.2 Ecuaciones en Z

Las coordenadas del proyector se normalizan con `Ap⁻¹` y se les quita la distorsión, dando
(x_p, y_p). Como el punto en el sistema del proyector es `R·X + T`, su proyección cumple
`x_p = (R₁·X + T₁)/(R₃·X + T₃)`. Sustituyendo `X = Z·r̃` queda **una ecuación lineal en Z** por
cada coordenada (Rᵢ = fila i de R):

```
con u_p:  (R₁·r̃ − x_p·R₃·r̃)·Z = x_p·T₃ − T₁
con v_p:  (R₂·r̃ − y_p·R₃·r̃)·Z = y_p·T₃ − T₂
```

Esto es lo que hace `StereoReconstruction.m`. Luego `X = Z·x`, `Y = Z·y`, en el sistema de la
cámara y en mm.

### 13.3 Qué fase usar — `elegir_fase(fd, stereo_params)`

| `FASE_TRIANGULACION` | Qué hace |
|---|---|
| `"auto"` (por defecto) | Usa la coordenada alineada con la **línea base**: Fx si \|T_x\| > \|T_y\|, Fy si no |
| `"Fx"` | Solo u_p (franjas verticales) |
| `"Fy"` | Solo v_p (franjas horizontales) — lo que usaba `R3D_ComplexShape.m` |
| `"ambas"` | Mínimos cuadrados con las dos ecuaciones, pesos (f_p·B)² |

**¿Por qué no "ambas"?** Un error de δ px en la coordenada del proyector produce un error en Z
inversamente proporcional a la componente de la línea base en esa dirección. Aquí
T ≈ (25, −88, −6) mm: **v_p es ~3.5 veces más sensible a la profundidad que u_p**.

Además, con la calibración actual u_p tiene un **sesgo sistemático**. Al comparar Z obtenida con
Fx y con Fy sobre los planos de referencia, difieren entre −10 y −20 mm en el borde izquierdo de
la imagen. Esa zona corresponde a u_p > 750, que ninguna pose del tablero cubrió: allí el modelo
del proyector se extrapola.

Mezclar ambas fases arrastraba ese sesgo. Resultados en los 8 planos de referencia:

| Modo | Error de planitud (RMS) |
|---|---|
| `"ambas"`, código anterior | 1.27 mm |
| `"Fy"` sin suavizado de fase | 0.76 mm |
| `"Fy"` con suavizado σ = 1.5 (actual) | **0.50 mm** |

Si en el futuro se calibra con poses que cubran todo el ancho del proyector, vale la pena
volver a comparar `"ambas"` con `"Fy"`.

### 13.4 `triangular(up, vp, mascara_x, mascara_y, stereo_params, fd, peso_x, peso_y)`

1. Resuelve `fd` con `elegir_fase`.
2. Arma la máscara de píxeles a usar según la fase.
3. Calcula los rayos y les quita la distorsión.
4. Normaliza u_p y v_p y les quita la distorsión del proyector. Esa corrección necesita las dos
   coordenadas a la vez.
5. Acumula `num = Σ w·a·b` y `den = Σ w·a²` con las ecuaciones activas y resuelve `Z = num/den`.

Devuelve X, Y, Z (NaN fuera de la máscara) y la máscara final. Todo está vectorizado: ~1.5 s por
pose de 1.3 Mpx.

### 13.5 Filtrado — `filtrar_outliers_3d(z, mask, salto_max, z_min, z_max)`

Descarta los puntos que se alejan más de `SALTO_MAX_MM` de la mediana local 5×5 y los que están
fuera de `[Z_MIN_MM, Z_MAX_MM]`. Equivale al `pcdenoise` de MATLAB.

Después se aplican, si existen:

- **La máscara de la pose** (`mascara.py`, pestaña *Máscara*).
- **El filtro de puntos aislados** (`FILTRO_VECINOS_SIGMA`, apagado por defecto). Para cada
  punto calcula la distancia media 3D a sus 8 vecinos de la imagen. Quita los que superan la
  mediana en más de σ desviaciones robustas (MAD) y los que no tienen vecinos. Con 3σ quita entre
  el 5 y el 8 % de los puntos de un objeto (bordes y puntos volando).

La caché de la reconstrucción incluye los dos: cambiar la máscara recalcula solo esa pose.

### 13.6 Ajuste de plano — `plane_fitting(x, y, z, mask)` (solo categoría `plano`)

1. **RANSAC**: 300 iteraciones sobre 20 000 puntos al azar. Elige el plano con más puntos a menos
   de 3 mm, para que la placa de soporte u otras superficies no sesguen el ajuste.
2. **Mínimos cuadrados** `Z = A·X + B·Y + C` sobre los inliers, como `Plane_fitting.m`.
3. Distancia perpendicular de cada punto al plano y **error RMS** respecto a su media.

Devuelve el mapa de error, el RMS y los coeficientes. Es la métrica de exactitud del sistema.

### 13.7 Cobertura — `fuera_de_cobertura(...)`

Fracción de puntos cuya coordenada del proyector cae fuera del rango calibrado. Si supera el 5 %,
la etapa lo avisa.

### 13.8 Salidas y caché — `procesar_reconstruccion(...)`

Por cada pose:

- `<cat>_pose_XX.ply`: nube **binaria** con textura en gris (`escribir_ply_binario`). Se abre en
  MeshLab o CloudCompare.
- `<cat>_pose_XX.npz`:
  - `X, Y, Z` en mm (float32, NaN fuera de la máscara);
  - `Mask`;
  - `fase` usada;
  - en los planos, `E`: el mapa de error al plano.

  Se lee con `cargar_reconstruccion_pose(ruta)`.
- `reconstruccion_<cat>_pose_XX.png`: textura | Z | error del plano (solo `plano`).

Por categoría, `<cat>_resumen.json` guarda por pose:

- número de puntos y rango de Z;
- fracción fuera de cobertura;
- en los planos, `erms_mm` y los coeficientes del plano;
- el identificador de caché.

**Caché.** Una pose no se vuelve a triangular si su `.npz` es más reciente que su fase absoluta y
se calculó con la misma calibración (ruta y fecha de modificación), el mismo modo de
triangulación y los mismos filtros (`_id_reconstruccion`). Recalibrar o cambiar
`FASE_TRIANGULACION` invalida la caché automáticamente; `REHACER = True` la ignora.

> Antes se guardaba un único `<cat>_R3D.npz` con todas las poses apiladas, como los `.mat` de
> MATLAB. Se reemplazó por un archivo por pose: con decenas de objetos, el apilado pesaba cientos
> de MB y había que reescribirlo entero cada vez.

---

## 14. Etapa `visualizacion`

`visualizacion.visualizar_pose(categoria, pose, …)`. Con `pose = "ultima"` toma la pose más
reciente. Abre dos ventanas:

1. **Cuadrícula 3×4 del proceso:**
   - franjas V y H del paso 0;
   - primer bit Gray;
   - textura;
   - fases relativas X e Y;
   - orden de franja k;
   - modulación γ;
   - fases absolutas Fx y Fy;
   - máscara (0 = ninguna fase, 1 = una, 3 = ambas);
   - profundidad Z.
2. **Nube 3D interactiva** (gira con el ratón):
   - hasta 80 000 puntos a escala real;
   - coloreada por profundidad o por textura;
   - vista desde la cámara.

Las figuras también se guardan en `resultados/visualizacion/`.

---

## 15. Resultados de referencia y precisión

Prueba completa con las capturas del 2026-10-30: 8 poses de patrón, 8 de plano y 1 objeto.

| Etapa | Antes | Ahora |
|---|---|---|
| fase relativa (17 poses) | 79 s | 13.5 s |
| fase absoluta (17 poses) | 88 s | 17 s |
| calibración (8 poses) | 56 s | 13 s |
| reconstrucción (9 poses) | 25 s | 21 s |
| **Total, recalculando todo** | **249 s** | **≈ 69 s** |
| Medir 1 objeto nuevo (sin calibrar) | ≈ 115 s (rehacía todo) | **≈ 5 s** (+ 4 s de visualización) |
| Error de planitud medio (8 planos) | 1.27 mm | **0.50 mm** |
| Puntos del objeto | 773k | 738k |

**Calibración actual:**

- RMS cámara 0.54 px, proyector 0.43 px, estéreo 0.51 px.
- Línea base de 91.6 mm, casi vertical.
- Cobertura del proyector: u_p 364–753 (**43 % del ancho**) y v_p 160–1107 (83 % del alto).

Los tiempos de proceso no incluyen la captura (2.5 s por ciclo de 50 patrones).

---

## 16. Solución de problemas por etapa

**Primer paso ante cualquier problema:** ejecuta `.env/bin/python verificar.py` (§20.7). Revisa
Python, paquetes, cámara, proyector, patrones, calibración y datos, y dice qué hacer en cada caso.
Si una etapa del pipeline falla, el mensaje de error indica la subsección de esta guía que le
corresponde. Cada subsección es una tabla de **síntoma → causa probable → solución**.

### 16.1 Instalación y arranque

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ModuleNotFoundError: numpy / cv2 / matplotlib` | Se ejecutó con el Python del sistema, o falta instalar | Usa `.env/bin/python …`; si persiste, `./instalar.sh` (§20.2) |
| `ResolutionImpossible` / conflicto de numpy al instalar | Versiones de OpenCV y numpy incompatibles con PySpin | Usa las de `requirements.txt` (numpy < 2, OpenCV 4.11); no actualices OpenCV a 4.12+ o 5.x mientras uses PySpin 4.x |
| `No se pudo crear el entorno` en `instalar.sh` | Falta el módulo venv | `sudo apt install python3.10-venv` |
| `ModuleNotFoundError: PySpin` | PySpin no instalado | Solo hace falta para capturar: §20.3 |
| `ImportError: libSpinnaker.so…` al importar PySpin | Falta el Spinnaker SDK o es de otra versión que el wheel | Instala el SDK de la **misma versión** que el wheel (§20.3) |
| `No hay calibración en …` | Falta `calibraciones/` | Cópiala del otro equipo o recalibra (§20.5) |

### 16.2 Patrones y LightCrafter (etapas `patrones` y `lightcrafter`)

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Sin permisos para abrir /dev/hidrawX` | Falta la regla udev | `./instalar.sh --udev` y reconectar el USB (§20.4) |
| `No se detectó el DLP LightCrafter 4500 por USB` | Cable mini-USB desconectado o proyector apagado | Conéctalo; `lsusb` debe mostrar `0451:6401` |
| `Timeout esperando respuesta…` | El proyector está ocupado o el software de TI lo tiene abierto | Cierra el software de TI y apaga y enciende el proyector |
| `Bandera de validación DLPC350 = 0x..` | Tiempos no válidos para la secuencia cargada | Lee el detalle impreso. Sin *Insert Black*, la exposición debe ser igual al período; con él, período ≥ exposición + 230 µs (§7) |
| La secuencia proyectada no coincide con `f_00…f_49` | Se cargó otra secuencia o en otro orden | Regenera (etapa `patrones`) y vuelve a cargarla en el software de TI en orden |

### 16.3 Captura (cámara FLIR y Arduino)

| Síntoma | Causa probable | Solución |
|---|---|---|
| `No se encontró ninguna cámara FLIR` | Cable, alimentación, o la cámara está abierta en otro programa | Cierra SpinView o la otra interfaz; prueba otro puerto **USB3** (azul); comprueba que SpinView la vea |
| `Sin trigger tras … ms en el frame N` | El Arduino no está enviando pulsos, o Line0 está desconectado | Revisa la alimentación del Arduino, el cable pin 9 → Line0 y la masa común |
| Frames incompletos o pérdidas con cámara USB3 | Buffer USB del kernel pequeño | Sube `usbfs_memory_mb` a 1000, como indica FLIR (§20.3) |
| `Δt … [AVISO] posible pulso perdido` | El equipo está cargado, o mala conexión del trigger | Cierra otros programas; el organizador descarta los ciclos rotos, pero conviene repetir la pose |
| Imágenes saturadas o muy oscuras | Exposición inadecuada | Ajusta `CAM_EXPOSICION_US` (debe ser menor de 50 ms) |
| Funciona en el equipo original pero no en otro | Versión de PySpin, SDK o Python distinta | §20.3 |

### 16.4 Organizar

| Síntoma | Causa probable | Solución |
|---|---|---|
| `no se encontró el par negro → blanco` | No hay un ciclo completo, o el blanco no se distingue del resto | Captura de nuevo; revisa la exposición (que el blanco no sature) |
| `pureza baja` / `corrimientos poco sinusoidales` | Frame perdido, o la secuencia del proyector no coincide | Repite la pose; verifica la secuencia cargada (§16.2) |
| `la escena se movió … se descarta` | El objeto o el soporte se movieron durante los 2.5 s | Fija bien el objeto y repite |
| `modulación H baja` | Franjas horizontales por debajo de `GAMMA_TH_Y` | Desenfoque o exposición. Mejora con `CICLOS_POR_CAPTURA` 2–4 o enfocando mejor |
| En *Archivos* una captura aparece como **dudosa · pureza 0.3** | Se organizó antes de los controles actuales, pero su secuencia no se parece a la proyectada | Muévela a la papelera; no la uses para calibrar |
| `brillo casi constante …: el proyector no estaba proyectando la secuencia` (captura **rechazada**) | Proyector apagado, en otro modo, sin la secuencia cargada, o el Arduino no dispara a los dos | Revisa el proyector y el Arduino y repite la pose. La captura queda en *Archivos* como rechazada; muévela a la papelera |
| Una pose quedó en la categoría equivocada | El nombre de la carpeta no tenía la palabra clave | Mueve la captura cruda a `capturas/<categoria>/`, borra `capturas_ordenadas/` y reorganiza (§9) |
| La interfaz no pregunta si es plano u objeto | Sin terminal interactiva se asigna `objeto` | Guarda las capturas en `capturas/plano/` u `objeto/` |

### 16.5 Fases (envuelta y desenvuelta)

| Síntoma | Causa probable | Solución |
|---|---|---|
| Fase con saltos o franjas de colores mezcladas | Orden de bits Gray equivocado o mala binarización | El orden se detecta solo; revisa el panel "Orden de franja k": debe crecer en escalones limpios |
| Muchos píxeles inválidos (máscara casi vacía) | Poco contraste, sombras o superficies muy oscuras o brillantes | Más ciclos, mejor enfoque o iluminación; ajusta `GAMMA_TH`, `GAMMA_TH_Y` o `UMBRAL_INTENSIDAD` |
| Trama fina en los mapas de fase | Rejilla de micro-espejos del DMD vista por la cámara | Ya se atenúa con `SUAVIZADO_FASE_PX`; desenfocar levemente el proyector también ayuda |
| Cambié un umbral y no cambia nada | Caché | `REHACER = True` (o "Recalcular todo" en la interfaz) |

### 16.6 Calibración

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Calibración RECHAZADA: sigue en uso la anterior` y el pipeline se detiene | No pasó el control de calidad (§12.4, punto 6) | Lee los motivos en el registro o en la pestaña Calibración. Repite las poses del patrón, o fuerza su uso si sabes lo que haces |
| `[AVISO] … se descarta la pose` | No se detectaron los 9 × 12 círculos | Tablero completo en la imagen, sin reflejos y bien iluminado; revisa la imagen blanca de esa pose |
| `Solo N poses válidas` | Menos de 3 poses con el tablero detectado | Captura más poses (10–15 recomendadas) |
| `Cobertura del proyector … [AVISO]` | Las poses no cubren todo el campo del proyector | Agrega poses con el tablero en los bordes y esquinas, inclinado ±20–30° |
| RMS estéreo muy superior al de cámara y proyector (p. ej. 12 px contra 0.5), `[AVISO] … las poses no son coherentes entre sí`, planos curvos | Poses de sesiones distintas y el montaje se movió entre ellas | Calibra solo con una sesión: `CALIBRACION_POSES = "ultima_sesion"` (por defecto), o **Poses del patrón: última sesión** en la interfaz. Revisa la pestaña **Calibración** (§19.2) |
| Una pose marcada `<-- no coherente con la línea base` | Esa pose es de otro montaje, o tiene malas correspondencias | Si no se usó (otra sesión), es lo esperado. Si se usó, quítala (§9, cómo excluir) y recalibra |
| Escala global incorrecta (objetos más grandes o más pequeños) | Tamaño real del tablero distinto de 15 mm | Mide el tablero y ajusta `PATRON_DISTANCIA_MM` (§12.6) |
| Quiero volver a la calibración anterior o usar otra | — | Pestaña **Calibración** → *Usar esta calibración*, o `calibracion_estereo.py --activar <fecha>` (§20.5) |

### 16.7 Reconstrucción y precisión

| Síntoma | Causa probable | Solución |
|---|---|---|
| `No existe la calibración …` | Falta `calibraciones/Estereo_TSC_0_2.npz` | §20.5 |
| `% de los puntos fuera del rango calibrado` | El objeto está en una zona del proyector que la calibración no cubrió | Recalibra con más cobertura (§16.6) |
| No aparecen poses que capturé antes | Son de otra configuración (§9.1) | Están en la pestaña *Archivos*; ahí se puede elegir esa configuración. Para ver todo a la vez: `SOLO_CONFIGURACION_ACTUAL = False` |
| Cambié un ajuste y no veo diferencia | La ejecución no incluyó las etapas afectadas | Las máscaras y el suavizado requieren *Fase envuelta*/*desenvuelta* y *Reconstrucción*; los filtros de Z, solo *Reconstrucción* |
| Borré algo por error | — | Muévelo de vuelta desde `papelera/<fecha>/` a la misma ruta (antes de vaciarla) y ejecuta *Organizar* si era una captura |
| Planos curvos en todas las poses (≈1.5 mm) justo después de recalibrar | La calibración mezcló poses de dos montajes | §16.6, primera fila |
| Los planos antiguos salen curvos con la calibración nueva | Se capturaron con el montaje anterior | Pon en uso la calibración de entonces (pestaña **Calibración**, §20.5), reconstruye y vuelve a la actual |
| Error de planitud en forma de cuenco (±1–2 mm en las esquinas) | Calibración con pocas poses, poca inclinación o poca cobertura | 10–15 poses con ±20–30°; confirma que la superficie sea realmente plana |
| Error sistemático cerca del borde izquierdo de la imagen | Zona del proyector (u_p alto) no cubierta por la calibración | Igual que el anterior: poses del tablero desplazadas a esa zona |
| Huecos o estrías horizontales en superficies oscuras | Poco contraste de las franjas H (DMD en diamante) | Más ciclos por captura; mejor iluminación; ver el último punto de §16.9 |
| Puntos sueltos muy lejos del objeto | Atípicos que pasan el filtro | Pestaña *Máscara* (región más grande, recortar el contorno, excluir zonas); activa *Quitar puntos aislados en 3D* en ⚙; o ajusta `Z_MIN_MM`, `Z_MAX_MM` y `SALTO_MAX_MM` |
| Resultados distintos tras cambiar `FASE_TRIANGULACION` | Esperable: Fx y Fy no tienen la misma sensibilidad | Usa `auto` (§13.3) |

### 16.8 Interfaz web

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Address already in use` | El puerto 8000 está ocupado (¿otra interfaz abierta?) | `interfaz/servidor.py --puerto 8001` |
| "Sin conexión con el servidor…" | Se cerró el servidor | Vuelve a ejecutar `interfaz/servidor.py` y recarga la página |
| El visor 3D no muestra nada | El navegador no tiene WebGL, o la pose no está reconstruida | Prueba con Chrome o Firefox actualizados; revisa que la pose tenga los 4 puntos verdes |
| No aparece la vista previa / la cámara "no carga" | El **servidor se inició antes de actualizar el código** (el servidor no recarga sus archivos solo) | Detén el servidor (Ctrl+C) y vuelve a lanzar `interfaz/servidor.py`; recarga la página |
| La vista previa no aparece durante la pausa | La pausa está desactivada, o la cámara no entrega imágenes en modo libre | Activa «Pausa antes de cada pose»; prueba «Ver cámara»; revisa el registro y `verificar.py` (§16.3) |
| La vista previa avisa de píxeles saturados | Exposición o brillos excesivos | Baja `CAM_EXPOSICION_US` o la luz, o cambia el ángulo (§19.3) |
| Las capturas del modo demo aparecen como poses reales | Se guardan en `capturas/` con sufijo `_simulada` | Borra esas carpetas y las poses que generaron (§19.1) |
| No se puede abrir desde otra PC | El servidor escucha solo en el equipo local | `--host 0.0.0.0` (sin contraseña: solo en redes de confianza) |

### 16.9 Limitaciones conocidas del montaje

- **Las franjas horizontales (H) tienen muy poco contraste** (γ ≈ 0.08–0.25 frente a ≈ 0.55 en
  las V).
  - *Causa:* la matriz de micro-espejos del LightCrafter 4500 está en **diamante**: las filas
    están intercaladas y 18 filas equivalen a ~9 px físicos. Por eso fy del proyector es ≈ 2·fx.
    El desenfoque borra casi por completo esas franjas finas.
  - *Mitigación en el código:* `GAMMA_TH_Y` bajo y suavizado de fase.
  - *Mitigación física:* capturar con `CICLOS_POR_CAPTURA = 2–4`, o usar un período mayor solo
    para las franjas H. Esto último requiere cambiar `secuencia_patrones.py`, recargar el
    proyector y recalibrar.
- **Cobertura de la calibración actual:** solo el 43 % del ancho del proyector (§16.6).
- **El control del LightCrafter solo funciona en Linux** (usa `/dev/hidraw`).

---

## 17. Correspondencia con el código MATLAB y diferencias

| MATLAB (`Matlab_Codes/Codes/`) | Python |
|---|---|
| `AcquisitionCodes/SaveImagesFromVidAvi.m`, `savePatterns.m` | `organizar_capturas.segmentar_secuencias`, `guardar_pose` |
| `AcquisitionCodes/ConfAndCapture_FLIRcam_*.m` | `capturar_patrones.CamaraFLIR` |
| `PhaseRecoveryCodes/ComputeNStepPhase.m` | `fase.fase_relativa` |
| `PhaseRecoveryCodes/UnwrapPhaseGrayCode.m`, `GenGrayCode.m`, `GenInverseGrayCodeLUT.m` | `fase.bits_gray`, `decodificar_gray`, `fase_absoluta` |
| `PhaseRecoveryCodes/RecoveryPhases_objects.m` | `fase.etapa_fase_relativa` + `etapa_fase_absoluta` |
| `PhaseRecoveryCodes/CleanPhase.m`, `Adj2D_5thPol.m`, `HybridCalibCodes/PhaseAdj5.m` | `calibracion_estereo.ajustar_polinomio_2d` |
| `StereoCalibCodes/createMaskCB.m`, `RegWcordtoImage.m` | `calibracion_estereo.create_mask_cb`, `reg_wcord_to_image` |
| `StereoCalibCodes/Traditional_StereoCalib.m` | `calibracion_estereo.ejecutar_calibracion_estereo` |
| `StereoCalibCodes/StereoReconstruction.m`, `comp_distortion_oulu.m` | `reconstruccion_3d.triangular`, `comp_distortion_oulu` |
| `3DReconstructionCodes/Plane_fitting.m`, `XYZtoPC.m`, `pcwrite` | `reconstruccion_3d.plane_fitting`, `escribir_ply_binario` |

**Diferencias deliberadas:**

1. **Bits Gray:** se decodifican los 6 bits reales. El MATLAB leía 7, y el 7.º era la imagen
   negra.
2. **Orden de bits:** se detecta automáticamente.
3. **Desfase de la onda cuadrada:** u_p se corrige +c = 4 px para que coincida con la columna
   real del proyector.
4. **Filtro temporal Hanning eliminado:** era una rotación de fase constante (§10.3).
5. **Suavizado espacial de S y C** (opcional, nuevo; §10.2).
6. **Umbral γ separado para las franjas H** (`GAMMA_TH_Y`).
7. **Selección automática de la fase de triangulación** por la línea base. Coincide con
   `Fd = 'Fy'` del MATLAB en este montaje.
8. **Ajuste polinomial con rechazo robusto de atípicos** y máscara de tablero automática. El
   MATLAB pedía dibujar el polígono a mano.
9. **Ajuste de plano con RANSAC.**
10. **Cobertura del proyector** registrada y verificada.
11. **Tablero con distancia por eje** opcional (la corrección comentada en el MATLAB).

No se portaron las calibraciones híbridas ni la recalibración (`HybridCalibCodes/`,
`Recalibracion/`), ni el registro SIFT de varias vistas (`Sift3DRegister.m`).

---

## 18. Referencia de archivos de salida

En esta tabla, `<P>` es la carpeta del proceso de captura (`AAAA-MM-DD_HHMM`, §4.1).

| Archivo | Contenido | Lo genera |
|---|---|---|
| `capturas/<P>/<cat>/<fecha>/*.tiff` | Frames crudos | `captura` |
| `capturas/<P>/proceso.json` | Plan, horas, capturas y poses del proceso | `captura`, `organizar` |
| `capturas_ordenadas/manifiesto.json` | Origen, carpeta y calidad de cada pose | `organizar` |
| `capturas_ordenadas/<P>/<cat>/pose_XX/{H,V}/P18_FYY.tiff` | 26 imágenes por orientación | `organizar` |
| `capturas_ordenadas/<P>/<cat>/pose_XX/origen.json` | De qué captura y proceso salió la pose | `organizar` |
| `resultados/<P>/fases/<cat>/pose_XX_relativa.npz` | `phiX/Y, AX/Y, BX/Y, qX/Y` | `fase_relativa` |
| `resultados/<P>/fases/<cat>/pose_XX.npz` | `Fx, Fy, up, vp, kX, kY, qFx, qFy, BX, BY, Itex, MaskX/Y/C` | `fase_absoluta` |
| `calibraciones/Estereo_TSC_0_2.npz` | Calibración (intrínsecos fijos) — versionada | `calibracion` |
| `calibraciones/Estereo_TSC_0_2_J.npz` | Calibración conjunta — versionada | `calibracion` |
| `calibraciones/Estereo_TSC_0_2.json` | Resumen legible — versionado | `calibracion` |
| `calibraciones/historial/<fecha>/` | Copia de cada calibración anterior | `calibracion` |
| `resultados/calibracion/patron_PhasesData.npz` | Correspondencias del tablero | `calibracion` |
| `resultados/<P>/fases/<cat>/pose_XX_mascara.png` / `.json` | Máscara de la pose y sus parámetros | pestaña Máscara |
| `mediciones.json` | Mediciones de distancia por pose | pestaña Medición |
| `resultados/<P>/reconstruccion/<cat>/<cat>_pose_XX.ply` | Nube de puntos | `reconstruccion` |
| `resultados/<P>/reconstruccion/<cat>/<cat>_pose_XX.npz` | `X, Y, Z, Mask` (y `E` en planos) | `reconstruccion` |
| `resultados/reconstruccion/<cat>/<cat>_resumen.json` | Estadísticas de todas las poses, `erms_mm` | `reconstruccion` |
| `resultados/visualizacion/*.png` | Figuras del proceso y 3D | `visualizacion` |

Para leer un `.npz` en Python:

```python
import numpy as np
d = np.load("resultados/2026-11-24_1302/reconstruccion/objeto/objeto_pose_06.npz")
# o, sin saber en qué proceso está:  import rutas; d = np.load(rutas.reconstruccion("objeto", "pose_06"))
Z = d["Z"]                   # mapa de profundidad (mm), NaN donde no hay medida
```

En MATLAB, los `.ply` se leen con `pcread`.

---

## 19. Interfaz web

Una aplicación web **local** para controlar todo el proceso y ver cada paso mientras ocurre.
Corre en el mismo computador que la cámara y el proyector, y se usa desde el navegador.

```bash
cd ~/Documents/Tesis
.env/bin/python interfaz/servidor.py          # abre http://127.0.0.1:8000
```

Opciones:

- `--puerto 8080`: otro puerto.
- `--sin-navegador`: no abre el navegador automáticamente.
- `--host 0.0.0.0`: accesible desde otro equipo de la red. **No tiene contraseña:** cualquiera en
  la red podría lanzar capturas. Úsalo solo en una red de confianza.

No necesita instalar nada: usa la librería estándar de Python más NumPy y OpenCV, y el visor 3D
está escrito en WebGL puro, así que funciona sin internet.

### 19.1 Panel de control (izquierda)

- **Medir.** Elige la categoría, el número de poses y los ciclos, y pulsa **Capturar y
  reconstruir**. Corre `captura → organizar → fase relativa → fase absoluta → reconstrucción`:
  - con *Objeto* o *Plano*, usa la calibración guardada y solo reconstruye esa categoría;
  - con *Patrón (calibrar)*, además recalibra y reconstruye de nuevo planos y objetos, porque
    cambió la calibración.
- **Pausa antes de cada pose.** Cuando la captura espera, aparece un aviso con **Continuar ⏎** y
  **Terminar (q)**. Equivalen al Enter y la `q` de la terminal; la tecla Enter también funciona.
- **Modo demo (cámara simulada).** Reproduce una captura existente en lugar de usar la cámara,
  para probar o enseñar la interfaz sin el montaje (clase `CamaraSimulada` de
  `capturar_patrones.py`). Las capturas simuladas se guardan en `capturas/<cat>/<fecha>_simulada`;
  **bórralas** al terminar, o se procesarán como poses reales.
- **Proceso por etapas.** El equivalente a `ETAPAS` de `pipeline.py`, en tres bloques:
  1. **Categorías y poses.** Casillas para activar *Patrón*, *Plano* y *Objeto* (cualquier
     combinación), con el número de poses de cada una, los ciclos y la pausa.
     - Con la etapa *Captura* marcada se capturan **todas** las poses de las categorías activas,
       siempre en el orden patrón → plano → objeto, y recién después se procesa.
     - Las categorías activas son también las que se procesan. El patrón se procesa cuando
       *Calibración* está marcada.
     - En una pausa, *Terminar (q)* salta a la siguiente categoría.
     - Debajo aparece un resumen ("Se capturará: patrón × 12 → plano × 3 → objeto × 1") y avisos,
       por ejemplo si capturas el patrón sin marcar *Calibración*.
  2. **Etapas.** Las 8 etapas **numeradas en su orden de ejecución**, cada una con una
     descripción breve y una etiqueta: *hardware* si necesita el montaje, *opcional* para la
     calibración, *ocasional* para la generación de patrones. Durante la ejecución se resalta la
     etapa en curso.
  3. **Opciones.** *Recalcular todo* (`REHACER`). Triangulación, calibración, máscaras y filtros
     están en **Ajustes** (⚙).

  Ejemplo de una sesión completa en un solo paso: activa las tres categorías (patrón × 12,
  plano × 3, objeto × 1) y marca todas las etapas de *Captura* a *Reconstrucción*.
- **Pausas.** En cada pausa, la tarjeta de pausa y la pestaña *Cámara* indican qué toca, por
  ejemplo "Patrón · pose 3 de 12".
- **Detener proceso.** Termina el subproceso del pipeline.
- **Poses.** Las poses de la configuración vigente (§9.1), es decir, del último proceso que
  capturó el patrón en adelante. Arriba se indica desde cuándo y cuántos procesos anteriores están
  ocultos. Los cuatro puntos indican, en orden:
  organizada · fase envuelta · fase desenvuelta · reconstruida. Un clic la abre.
- **Calibración.** Resumen de la calibración en uso: fecha, errores RMS, línea base y cobertura
  del proyector.

### 19.2 Visualización (derecha)

**Panel de avance:** mientras algo se ejecuta, arriba de la vista aparece un panel que se queda
fijo al bajar por la página, en cualquier pestaña. Esto incluye capturar, recalibrar con capturas
elegidas, importar y el proceso por etapas. El panel muestra:

- todas las etapas de esa ejecución: ✓ las terminadas, con su duración, y la actual resaltada;
- una barra con el avance total;
- qué se está haciendo ahora, por ejemplo «Calibrando la cámara y el proyector» o «Reconstrucción
  3D: 'plano'»;
- una barra de la etapa con poses o capturas «i/n» y el tiempo restante estimado. Si el paso no
  se puede contar, la barra queda en movimiento;
- el tiempo de la etapa y el total.

Al terminar, el panel indica si todo salió bien (se oculta a los 20 s) o en qué etapa se detuvo.
Se cierra con ×.

Ocho pestañas de pasos y tres aparte: **Sistema** (estado del equipo, lista de comprobación antes
de medir y espacio en disco), **Archivos** y **Calibración**. Arriba a la derecha están el
**manual** (📖, también con la tecla `?`) y los **Ajustes** (⚙). Las pestañas de resultados siguen solas al proceso en curso
cuando **Seguir la última** está activo:

1. **Cámara.** Todo lo de la cámara en un solo lugar. Se abre sola cuando la cámara se activa,
   aunque estés en otra pestaña.
   - **Vista previa para encuadrar** (marco verde): en cada pausa antes de una pose, con los
     botones *Continuar* y *Terminar* ahí mismo. Detalles en §19.3.
   - **Captura en vivo** (marco naranja, ~6 imágenes/s), con el avance de los 50 patrones.
   - **Sin actividad:** el botón **Ver cámara** abre la vista previa sin capturar nada, para
     encuadrar, enfocar o ajustar la exposición. Se cierra con *Cerrar vista previa*. En modo
     demo muestra la captura elegida.
2. **Imágenes.** Las 50 imágenes del ciclo de la pose, en carpetas:
   - franjas verticales (18 pasos, con su desfase);
   - franjas horizontales (18);
   - código Gray vertical (6 bits);
   - código Gray horizontal (6);
   - negro y blanco (2). Hay uno de cada uno por ciclo; `organizar` los copia en `H/` y en `V/`
     (`P18_F24` y `F25`) para que cada orientación quede completa como en `savePatterns.m`.

   Un clic en una carpeta muestra todas sus miniaturas. Un clic en una miniatura la abre a
   pantalla completa, donde se pasa de una a otra con ← →, y `Esc` cierra.
3. **Fase envuelta.** φ de X e Y en [−π, π] y la modulación γ de cada una.
4. **Fase desenvuelta.** Fx y Fy, el orden de franja k del código Gray y el mapa de píxeles
   válidos.
5. **Máscara.** Qué píxeles de la pose se reconstruyen, para quitar el fondo y los
   **puntos volando** que no son del objeto. Es opcional: sin máscara se usan solo los umbrales de ⚙.
   La guía paso a paso está en §19.5; aquí va el resumen de los controles.
   - Se arma sobre la **modulación γ** de la fase con la que se triangula (normalmente Fy). Se
     puede ver sobre la textura o sobre el mapa de γ. En **rojo**, lo que quita la máscara; en
     oscuro, lo que ya descartaba la fase.
   - **Modulación mínima:** sube el umbral de γ solo en esta pose. El histograma de γ ayuda a
     elegirlo.
   - **Limpieza:**
     - *Recortar el contorno* N px: los bordes del objeto mezclan fase de objeto y fondo. Solo
       recorta el contorno exterior; los agujeritos de dentro no crecen.
     - *Quitar regiones sueltas* menores de N px.
     - *Conservar solo la región más grande*: normalmente, el objeto.
   - **Zonas dibujadas:**
     - *Recortar a una zona*: conserva solo lo que está dentro.
     - *Excluir una zona*: la quita, por ejemplo un soporte o la mesa.

     Para dibujar, haz clic en cada vértice y cierra con doble clic, Enter o un clic en el
     primer punto. Esc cancela.
   - La vista previa es inmediata y dice cuántos píxeles conserva y cuántos puntos quedarían de
     la nube actual.
   - **Aplicar lo mismo a otras poses** de la categoría: mismos parámetros y mismas zonas. La
     cámara no se mueve, así que sirve si el objeto está en el mismo lugar.
   - *Guardar y reconstruir* reconstruye solo lo que cambió.
   - Se guarda en `resultados/<proceso>/fases/<cat>/pose_XX_mascara.png`, donde blanco =
     se conserva, y se puede editar fuera. Al lado queda un `.json` con los parámetros.
6. **Profundidad.** Mapa Z y, en los planos, el error respecto al plano ajustado. Debajo,
   **Medir sobre el mapa Z**:
   - *Punto y distancia*: un clic en el mapa Z lee X, Y, Z del píxel válido más cercano. Un
     segundo clic da la distancia 3D entre los dos puntos, ΔZ y la distancia en X-Y.
   - *Perfil*: dos clics grafican Z a lo largo de la línea. Cada muestra es la mediana de los
     píxeles válidos de una ventana 5 × 5. Incluye Z mínima, máxima y rango.
   - En los planos, el **histograma del error** respecto al plano, con RMS, P95 y máximo.
   - **Descargas:** la nube `.ply` (binaria, con color), los puntos `.csv` (columna, fila, X, Y, Z
     en mm) y el informe de la calibración en uso (`.json`).
   - *Ampliar* agranda el mapa sin dejar de medir.

   **Comparar**, debajo, muestra el mapa de **Z actual − Z de una referencia**, píxel a píxel,
   donde las dos tienen dato. Si no difieren, se ve en gris.
   - En **rojo**, los píxeles que solo tiene la referencia; en **azul**, los que solo tiene la
     actual. Por ejemplo, los puntos que quita un filtro.
   - También da cuántos puntos tiene cada una y la diferencia media, RMS, P95 y máxima.
   - Ejemplo real: con y sin el filtro de saltos en Z, la nube pasa de 568 794 a 528 929 puntos, sin
     cambiar los comunes, porque el filtro solo quita atípicos.

   La referencia puede ser:
   - **otra pose** de la misma categoría: repetibilidad entre dos capturas de la misma escena;
   - **una copia guardada** de esta pose. Reprocesar sobrescribe el resultado, así que para
     comparar ajustes:
     1. pulsa *Guardar el resultado actual para comparar*;
     2. cambia el ajuste en ⚙ y vuelve a procesar (fases y reconstrucción);
     3. elige la copia guardada.

   Las copias quedan en `resultados/comparaciones/`, con los ajustes con que se calcularon.
7. **Nube de puntos.** Visor 3D interactivo con hasta 400 000 puntos, coloreados por profundidad
   o por textura:
   - arrastrar = girar;
   - clic derecho o Shift + arrastrar = desplazar;
   - rueda = acercar;
   - doble clic = vista inicial.
8. **Medición.** Distancia 3D entre **dos puntos cualesquiera de la nube** de la pose. Guía
   paso a paso en §19.6.
   - **Nube 3D** (vista principal): la nube completa, sin submuestrear. Se gira, se desplaza y
     se acerca igual que en la pestaña *Nube de puntos*. Un **clic sin arrastrar** sobre un punto
     lo marca como A y otro clic marca B. Entre los puntos bajo el cursor se elige el que se ve
     delante. Si haces clic en el vacío, avisa.
   - **Textura / Profundidad Z**: lo mismo, marcando sobre la imagen de la cámara. Rueda =
     acercar (hasta 24×), arrastrar = desplazar. Cada clic se ajusta al punto 3D válido más
     cercano y avisa si se movió.
   - Da la **distancia 3D**, ΔX, ΔY, ΔZ y X, Y, Z de cada punto, con su **ruido**: el RMS de la
     superficie alrededor del punto respecto a un plano local (ventana de 9 × 9 px). La
     incertidumbre de la distancia es la combinación de los dos. En el plano da ~0.03 mm por
     punto.
   - **Mediciones guardadas** por pose, con nombre. Se exportan a `.csv` y quedan en
     `<DATOS>/mediciones.json`.
   - Si la pose se vuelve a reconstruir, por ejemplo con otra máscara, se marcan con ⚠.
     *Volver a medir con la nube actual* las recalcula en los mismos lugares de la imagen.

**Calibración** (pestaña aparte, a la derecha).

**Recalibrar con capturas elegidas** (tarjeta plegable, arriba). Sirve para recalibrar y reconstruir
con capturas tomadas antes, sin depender de cómo el sistema agrupa los procesos.
1. Lista **todas** las poses organizadas, agrupadas por la fecha de su proceso, cada una con la
   **miniatura** de su imagen blanca (tablero, plano u objeto) para reconocerla. Las **dudosas**
   (pureza < 0.5) se marcan con ⚠.
2. Marca poses sueltas o un proceso entero (su casilla): del **patrón** para calibrar y de
   **plano / objeto** para reconstruir.
3. **Procesar la selección**:
   - calcula las fases que falten;
   - calibra con esas poses del patrón (si elegiste alguna; si no, usa la calibración en uso);
   - reconstruye los planos y objetos elegidos.

La calibración pasa por el mismo control de calidad (§12.4) y **recuerda su selección**: al
activarla más adelante, vuelve a esas mismas poses. Ejemplo: con las 8 poses del patrón del 30-oct
y los 8 planos de ese día se obtiene 0.509 px y 0.498 mm de planitud media, como en la sesión
original.

Más abajo, **Calibración en uso** permite elegir
cualquier calibración del historial (fecha, poses y error estéreo; ⚠ = error estéreo muy alto) y
ponerla en uso con **Usar esta calibración** (§20.5). Al calibrar en *Proceso por etapas*, la
nueva queda en uso sola. Debajo, los errores de reproyección de cada pose del tablero con la
calibración en uso (*independiente* o *conjunta*, según la opción **Calibración**):
- resumen: fecha, poses usadas, criterio y RMS de cámara, proyector y estéreo;
- gráfico de barras por pose, con cámara, proyector y estéreo, separado por sesiones. Las poses
  no usadas salen atenuadas, y las que se salen de escala llevan su valor encima (▲);
- tabla con los mismos errores, más ΔR, ΔT y la distancia al tablero;
- al hacer clic en una pose, los **vectores de error** de cada círculo en la cámara y en el
  proyector, ampliados. En gris se ven los círculos de las demás poses, que muestran la
  cobertura;
- el **mapa de cobertura**: el proyector dividido en 4 × 5 zonas, a la izquierda.
  - Verde = con círculos.
  - Rojo = sin círculos y visible para la cámara: ahí el modelo se extrapola.
  - Gris = fuera del campo de la cámara: no se mide, así que no importa.

  A la derecha, en la imagen de la cámara, círculos naranjas numerados marcan
  **dónde poner el tablero** en la próxima calibración para cubrir las zonas rojas. La posición se calcula con un
  ajuste afín proyector → cámara de todas las correspondencias, así que es aproximada. Con la
  calibración del 24-nov se cubren 11 de 12 zonas visibles; falta el borde izquierdo de la
  imagen.

Si el error estéreo de la calibración es muy alto, el chip de calibración de la barra superior y
el ícono de la pestaña se ponen en rojo, y la pestaña explica qué hacer (§16.6). Para ver también
las poses no usadas, la calibración tiene que haberse hecho con esta versión.

**Archivos** (pestaña aparte). Navegador de todo lo capturado, agrupado por **configuración**
(desde cada patrón, §9.1) y por **proceso**. Cada captura muestra su categoría, hora, carpeta y
las poses que salieron de ella, con cuatro puntos: organizada · fase envuelta · fase desenvuelta
· reconstruida.
- **Ver** abre las imágenes crudas de la captura (las 50 o más que guardó la cámara), con el mismo
  visor.
- **Notas:**
  - cada proceso tiene una nota («calibración de la mañana, objeto rotado 30°…»);
  - cada captura, el **nombre de la pieza** («pieza A, cara superior»).

  El nombre se ve en la lista de *Poses*, en el selector de pose y en las métricas. Se guardan en
  `<DATOS>/notas.json`.
- Cada captura y cada proceso muestran el **espacio** que ocupan: captura cruda más poses
  organizadas, que es lo que se libera al borrarlos.
- Las capturas **rechazadas** (sin ciclos válidos) y las **dudosas** (organizadas antes de los
  controles actuales, con pureza < 0.5) se marcan con su motivo.
- **Usar esta configuración** la pone en uso, junto con su calibración si existe. 
  **Volver a la última** regresa a la más reciente.
- **Borrar:** marca capturas, un proceso o una configuración entera (*Seleccionar todo*) y pulsa
  **Mover a la papelera**. Se mueve la captura cruda y todo lo que depende de ella: poses
  organizadas, fases y reconstrucciones. También se quitan sus entradas del manifiesto, del
  resumen y del registro.
  - Antes de borrar se pide confirmación, con un aviso si hay poses del patrón usadas por la
    calibración en uso o capturas de la configuración vigente.
  - Lo borrado va a `papelera/<fecha>/` en la carpeta de datos, con las mismas rutas. Cada lote
    guarda en `papelera.json` las entradas que se quitaron del manifiesto y del registro.
  - Al final de la pestaña, **Papelera** lista los lotes.
    - **Restaurar** devuelve un lote a su lugar, con los **mismos nombres de pose**.
    - No pisa nada: lo que ya exista queda en la papelera y se avisa.
    - Los lotes de una pose repetida en la captura no tienen datos del manifiesto: se devuelven
      solo los archivos, y *Organizar* les da un número de pose nuevo.
  - **Vaciar papelera** lo elimina definitivamente.
  - Los números de pose borrados no se reutilizan (`ultimo_indice` en el manifiesto), así que
    una calibración nunca apunta a una pose distinta de la que usó.

**Ajustes** (botón ⚙ de la barra superior). Un punto naranja indica que hay valores distintos de
los de `configuracion.py`.
- Se guardan en `<DATOS>/ajustes.json` (módulo `ajustes.py`). Los usan la interfaz, cualquier
  navegador y **también `pipeline.py` por terminal**.
- El registro lo indica con `[AJUSTES] … distintos de configuracion.py: …`.
- **Procedencia:** cada pose sabe con qué parámetros se calculó. Si fue con otros ajustes, se
  marca con borde punteado en *Poses* y con la métrica «Ajustes: distintos de los actuales»; el
  detalle aparece al pasar el mouse. Se actualiza en la próxima ejecución.

| Ajuste | Variable | Por defecto | Desactivado = |
|---|---|---|---|
| Tema | — | automático | claro u oscuro fijo |
| Suavizado de la fase (σ) | `SUAVIZADO_FASE_PX` | 1.5 px | fase sin suavizar |
| Máscara de modulación X | `GAMMA_TH` | γ ≥ 0.15 | todos los píxeles |
| Máscara de modulación Y | `GAMMA_TH_Y` | γ ≥ 0.03 | todos los píxeles |
| Máscara de intensidad | `UMBRAL_INTENSIDAD` | > 25 | también los oscuros |
| Recorte del borde | `BORDE_MASCARA` | 15 px | sin recorte |
| Filtro de mediana del orden de franja | `MED_FILT` | 5 | sin filtro |
| Orden de los bits Gray | `ORDEN_BITS_GRAY` | automático | (LSB / MSB fijo) |
| Fase para triangular | `FASE_TRIANGULACION` | auto | (Fy / Fx / ambas) |
| Filtro de saltos en Z | `SALTO_MAX_MM` | 5 mm | sin filtro |
| Rango de Z válido | `Z_MIN_MM`, `Z_MAX_MM` | 100–1500 mm | sin límite |
| Quitar puntos aislados en 3D | `FILTRO_VECINOS_SIGMA` | apagado | (activo: 3 σ) |
| Tolerancia del plano (RANSAC) | `PLANO_UMBRAL_MM` | 3 mm | — |
| Calibración / poses del patrón | `CALIBRACION`, `CALIBRACION_POSES` | independiente / última sesión | — |
| Distancia entre círculos del tablero (columnas – filas) | `PATRON_DISTANCIA_MM` | 15 – 15 mm | — (mídela con un calibre y recalibra) |
| Exposición de la cámara | `CAM_EXPOSICION_US` | 12 ms | — (también en vivo, §19.3) |

Cada fase guarda con qué parámetros se calculó (`firma` en el `.npz`), y la reconstrucción guarda
los suyos en su id. Al cambiar un ajuste, la próxima ejecución recalcula solo lo afectado; al
volver al valor anterior, recalcula otra vez. Ejemplo con los planos 17–19: sin suavizado ni
máscara X, 0.78 mm de planitud; con los valores por defecto, 0.62 mm.

**Idioma.** El selector **ES | EN** de la barra superior cambia toda la interfaz entre español e
inglés al instante, sin perder lo que estás viendo. La elección se recuerda en el navegador; por
defecto está en español. El **registro del proceso** sigue en español porque es la salida directa
de los scripts de Python. Los textos de ambos idiomas están en `interfaz/estatico/i18n.js`: para
cambiar un texto o agregar otro idioma, se edita ese archivo.

**Ayudas.** Cada opción tiene un botón **?**. Muestra su descripción al pasar el mouse, al
enfocarlo con el teclado o al tocarlo en pantallas táctiles.

Un clic en cualquier imagen la amplía y `Esc` la cierra. Arriba se muestran el número de puntos,
el rango de Z y, en los planos, el error de planitud. Abajo está el **registro** completo del
proceso.

Enlace directo a una pose y un paso: `http://127.0.0.1:8000/#paso=desenvuelta&cat=plano&pose=pose_03`
(pasos: `camara`, `captura` (imágenes), `envuelta`, `desenvuelta`, `profundidad`, `nube`,
`archivos`, `calibracion`).

### 19.3 Vista previa para encuadrar el objeto

Con **Pausa antes de cada pose** activada (por defecto), en cada pausa la pestaña **Cámara**
muestra lo que ve la cámara **en tiempo real**, para acomodar el objeto antes de capturar. El botón
**Ver cámara** abre la misma vista en cualquier momento, sin capturar.

Se verificó con la cámara FLIR real: vista previa a ~15 imágenes/s, cierre limpio, y captura
posterior con el trigger del Arduino sin pérdidas (Δt 49.9 ms) y secuencia válida.


- **No depende del Arduino.** Durante la pausa la cámara pasa a adquisición libre (~15
  imágenes/s, sin trigger). Al pulsar *Continuar* vuelve al trigger externo y empieza la captura
  de los 50 patrones.
- **Imagen estable.** El proyector sigue ciclando patrones, así que cada imagen tiene franjas
  distintas. La vista previa muestra un **promedio móvil** de las últimas imágenes: el objeto
  aparece estable y uniformemente iluminado.
- **Retícula.** Cruz central y líneas de tercios para centrar el objeto. Se desactiva con la
  casilla *Retícula*.
- **Aviso de saturación.** Muestra el porcentaje de píxeles saturados (≥ 250) en el último ciclo
  completo de patrones. Por encima de 0.5 % aparece en naranja. Los píxeles saturados distorsionan
  la fase: baja `CAM_EXPOSICION_US`, la intensidad del proyector o la luz ambiente, o cambia el
  ángulo para evitar brillos. Con las capturas de referencia el objeto tenía ~4.5 % de píxeles
  saturados en alguna imagen de franjas (el brillo de la madera), y eso se ve como una mancha
  ruidosa en los mapas de fase.
- **Exposición en vivo.** Control deslizante de 0.1 a 49 ms, en escala logarítmica.
  - Se aplica a la cámara en ~0.2 s (el servidor deja la orden en `resultados/.vivo/control.json`
    y el ejecutor la pasa a `ExposureTime`).
  - Se guarda en Ajustes, así que se mantiene para las poses siguientes y las próximas capturas.
  - En el modo demo se simula escalando el brillo.
- **Tablero detectado.** Al capturar el **patrón**, el texto bajo la imagen indica cada segundo
  si se detecta el tablero completo («✔ tablero detectado (108 círculos)»). Si no se detecta
  («✖ tablero NO detectado», en rojo), esa pose no servirá para calibrar: debe verse entero, sin
  reflejos.
- **Nitidez.** Varianza del laplaciano en el centro de la imagen, el máximo de un ciclo de franjas.
  Para enfocar la cámara o el proyector, gira el anillo hasta que la barra llegue al máximo. La
  escala se reinicia al cambiar la exposición.
- **Botones de la pausa** según el caso:
  - antes de cada pose: *Continuar* y *Terminar*, más *Repetir la anterior* desde la segunda;
  - si la pose no sirve: *Repetir la pose*, *Guardarla igual* y *Terminar*, con el motivo;
  - sin trigger: *Reintentar* y *Terminar*;
  - al organizar una captura sin categoría: *Plano*, *Objeto* y *Omitir*.
- **Control de las poses capturadas.** Lista en la pestaña Cámara, con ✔ / ⚠ / ✖, la modulación
  H/V y el % saturado de cada pose.
- Con *Terminar (q)* se sale sin capturar, así que la vista previa también sirve solo para
  revisar el encuadre o el enfoque.

Funciona igual en el modo demo, que reproduce la captura elegida. Solo está disponible desde la
interfaz web: `pipeline.py` en la terminal sigue pidiendo Enter sin vista previa.

### 19.4 Cómo funciona

**Progreso y errores.**
- El estado de la barra superior muestra la etapa, la categoría, «N/M» poses y el tiempo
  restante estimado. La etapa en curso tiene su barra de progreso en *Proceso por etapas*.
- Si el proceso termina con error, aparece un **aviso destacado** sobre las pestañas con la causa
  y, si el pipeline la indica, la sección del manual.
- El **registro** se puede filtrar (todo, avisos y errores, solo errores), descargar como `.txt`
  y limpiar.

**Seguridad.**
- El servidor escucha solo en `127.0.0.1` y rechaza:
  - nombres de host ajenos (*DNS rebinding*);
  - POST que no sean JSON o que vengan de otro origen. Así una página web cualquiera abierta en el
    mismo navegador no puede lanzar capturas ni borrar datos (CSRF).
- *Detener* envía SIGTERM, y el ejecutor lo convierte en una interrupción normal para que la
  cámara se cierre bien.
- Las preguntas del proceso (`input()`) se anuncian con una línea `@@pregunta …`.

```
navegador ──HTTP/SSE──► interfaz/servidor.py ──subproceso──► interfaz/ejecutor.py ──► pipeline.main()
                              │  vigila resultados/ y avisa de cada pose nueva
                              └─ genera las imágenes de cada paso desde los .npz
```

- **`servidor.py`** (`ThreadingHTTPServer`):
  - sirve la página y la API;
  - lanza el pipeline en un **subproceso** (`Ejecucion`), para poder detenerlo y escribir en su
    entrada estándar las respuestas a las pausas;
  - lee su salida y la reenvía al navegador por **Server-Sent Events** (`/api/eventos`): registro,
    etapa en curso, avance de la captura;
  - con un hilo (`vigilar`) revisa cada 0.7 s qué poses tienen resultados nuevos y emite un evento
    `cambio`. Solo avisa cuando el archivo dejó de cambiar, para no leerlo a medio escribir;
  - genera las imágenes de cada paso al vuelo (`generar_imagen`) con mapas de color de OpenCV, y
    la nube en binario (`generar_nube`).
- **`ejecutor.py`**:
  - aplica la configuración recibida sobre las variables de `pipeline.py`;
  - desactiva la visualización de matplotlib;
  - conecta la vista en vivo (`VistaEnVivo`): la captura solo guarda una referencia al último
    frame, y un hilo aparte lo escribe como JPEG cada 0.15 s, así que la adquisición no se
    retrasa ni se pierden triggers;
  - durante las pausas recibe la **vista previa** (`VistaEnVivo.previa`): promedio móvil y
    saturación. La genera `CamaraFLIR.iniciar_vista_previa()` / `detener_vista_previa()` en
    `capturar_patrones.py`, que también restauran el trigger y la cadencia;
  - con el modo demo, sustituye la cámara por `CamaraSimulada`.
- **`estatico/`**: `index.html`, `estilo.css` (modo claro/oscuro automático), `i18n.js` (textos en
  español e inglés), `app.js` (lógica) y `nube.js` (visor WebGL).

API, por si se quiere automatizar algo:

| Ruta | Uso |
|---|---|
| `GET /api/config` | Valores por defecto de `pipeline.py` y `configuracion.py` |
| `GET /api/estado` | Ejecución, calibración y poses con sus resultados |
| `POST /api/ejecutar` | Lanza el pipeline. Cuerpo: `{etapas, categorias, captura, rehacer, fase, calibracion, simular}` |
| `POST /api/detener` | Detiene el proceso |
| `POST /api/entrada` | `{"texto": ""}` = Enter, `{"texto": "q"}` = terminar |
| `GET /api/eventos` | Flujo SSE: `log`, `estado`, `vivo`, `cambio` |
| `GET /api/imagen?cat=&pose=&tipo=` | Imagen de un paso. `tipo`: `img_V_03` (cualquier imagen organizada: orientación e índice 0–25), `franja_V`, `franja_H`, `gray_V`, `textura`, `phiX`, `phiY`, `qX`, `qY`, `Fx`, `Fy`, `kX`, `kY`, `mascara`, `Z`, `error` |
| `GET /api/nube?cat=&pose=&max=` | Nube binaria: `uint32 N`, `float32 xyz·N`, `uint8 gris·N` |
| `GET /api/vivo.jpg` | Último frame de la cámara |
| `GET /api/calibraciones` | Calibraciones del historial, cuál está en uso, sus poses de origen y su proceso |
| `GET /api/archivos` | Capturas por proceso y configuración, configuración vigente y papelera |
| `POST /api/archivos/borrar` | `{"carpetas": ["patron/2026…", …]}`: a la papelera, con todo lo derivado |
| `POST /api/archivos/vaciar_papelera` | Borra definitivamente la papelera |
| `POST /api/configuracion/elegir` | `{"proceso": "<id>" | null}`: configuración vigente (null = la última) y su calibración |
| `GET /api/punto?cat=&pose=&fx=&fy=` | X, Y, Z del píxel válido más cercano (coordenadas de la imagen en [0, 1]) |
| `GET /api/perfil?cat=&pose=&ax=&ay=&bx=&by=` | Z a lo largo de un segmento |
| `GET /api/histograma?cat=plano&pose=` | Histograma y estadísticas del error respecto al plano |
| `GET /api/descargar?tipo=ply\|csv\|calibracion&cat=&pose=` | Archivos para descargar |
| `GET /api/sistema?hw=0\|1` | Comprobaciones de `verificar.py --json` y espacio en disco |
| `GET /api/manual` | `MANUAL.md` (la interfaz lo muestra con su índice) |
| `POST /api/camara` | `{"exposicion_us": N}`: exposición en vivo durante la vista previa |
| `GET /api/captura/lista?carpeta=` · `GET /api/captura/imagen?carpeta=&i=&ancho=` | Imágenes crudas de una captura |
| `POST /api/calibraciones/activar` | `{"id": "<fecha>"}`: pone en uso esa calibración (no durante una ejecución) |
| `GET /api/calibracion?variante=` | Errores de reproyección por pose con la calibración en uso (`independiente` o `conjunta`), con los vectores de error |

**Probar con otra copia de los datos.** La variable de entorno `TESIS_DIR_DATOS` hace que todo
(pipeline e interfaz) use `capturas/`, `capturas_ordenadas/` y `resultados/` de otra carpeta. Es
útil para ensayar sin tocar las capturas reales:

```bash
TESIS_DIR_DATOS=~/pruebas_tesis .env/bin/python interfaz/servidor.py
```

---

### 19.5 Máscara paso a paso

**Qué es.** Cada píxel de la cámara da, como mucho, un punto 3D. La máscara es una imagen en
blanco y negro, del tamaño de la cámara, que dice qué píxeles se convierten en puntos: blanco =
se conserva, negro = se descarta. Se arma sobre la imagen de la cámara (2D), pero su efecto se ve
en la nube (3D).

**De dónde salen los puntos volando:**

- **El fondo** (mesa, pared) tiene franjas, así que da puntos que no son del objeto.
- **Los bordes del objeto** mezclan la luz del objeto y la del fondo. Esa fase mezclada da
  puntos que quedan «flotando» entre los dos, a la profundidad equivocada.
- **Las zonas oscuras o con brillo** tienen poca modulación γ (franjas con poco contraste) y su
  fase es ruidosa.

**Receta habitual** (pose de un objeto sobre una mesa):

1. Abre la pestaña **5 · Máscara** con la pose elegida. La vista previa muestra la textura:
   - normal = lo que se reconstruye;
   - **rojo** = lo que quitará tu máscara;
   - oscuro = lo que la fase ya descarta (umbrales de ⚙).
2. **Recorta a una zona:** pulsa *✂ Recortar a una zona* y haz clic alrededor del objeto, un
   vértice por clic. Cierra con doble clic o Enter. Todo lo de fuera se pone rojo. Es lo que más
   quita: el fondo entero.
3. **Recortar el contorno:** sube el deslizador a 3–6 px. Quita el anillo del borde del objeto,
   de donde salen la mayoría de los puntos volando. Los agujeritos de dentro no crecen.
4. **Conservar solo la región más grande:** quita los trozos sueltos que quedaron.
5. Si una zona del objeto sale mal (brillo, sombra), usa *⊘ Excluir una zona*. Si toda la pose
   tiene puntos ruidosos, marca *Subir el umbral de γ* y súbelo un poco. El histograma muestra la
   γ de los píxeles; los ruidosos están a la izquierda.
6. Mira la línea de abajo: cuántos píxeles conserva y
   **cuántos puntos quedarían de la nube actual**.
7. Pulsa **Guardar y reconstruir**. Luego revisa la pestaña *Nube de puntos*. Si quedan puntos
   volando sueltos, activa *Quitar puntos aislados en 3D* en ⚙ Ajustes y reconstruye otra vez.

**Otras cosas que conviene saber:**

- **Varias poses:** si el objeto está en el mismo lugar, marca las poses en
  *Aplicar lo mismo a otras poses* antes de guardar. Se copian los parámetros y las zonas. Como la cámara no se
  mueve, las zonas caen en el mismo lugar.
- **Quitar máscara** vuelve a reconstruir solo con los umbrales de ⚙.
- **Valores iniciales** deja los controles sin máscara, pero no borra nada hasta guardar.
- **La máscara no cambia la fase ni la calibración:** solo decide qué puntos entran en la nube.
  Las mediciones hechas antes de cambiarla quedan marcadas con ⚠ (§19.6).

### 19.6 Medición paso a paso

1. Abre la pestaña **8 · Medición** con la pose elegida. Carga la nube completa, con todos los
   puntos y no una muestra.
2. **Gira** la nube (arrastrar), **desplázala** (clic derecho o Shift + arrastrar) y **acércate**
   (rueda) hasta ver bien el primer punto.
3. **Clic sin arrastrar** sobre el punto: queda marcado como **A**. Gira si hace falta y haz clic
   en el segundo: **B**. Se dibuja la línea con la distancia.
4. A la derecha aparecen:
   - la **distancia 3D**;
   - ΔX, ΔY, ΔZ;
   - X, Y, Z de cada punto;
   - su **ruido**: la dispersión de la superficie alrededor del punto respecto a un plano local
     (ventana de 9 × 9 px). Es la incertidumbre aproximada de la posición. El «±» de la
     distancia combina el de los dos puntos.
5. Ponle un nombre y pulsa **Guardar**. Las mediciones guardadas se dibujan en azul, y un clic en
   la lista muestra cada una. *Exportar .csv* las descarga todas.

**Consejos:**

- Mide sobre la superficie, no en el borde: ahí el ruido es mayor (verás un «±» más grande).
  Si un punto sale con mucho ruido o fuera de lugar, quita los puntos volando con la máscara
  (§19.5).
- Las coordenadas están en el sistema de la **cámara** (mm): Z es la distancia a la cámara. La
  distancia entre dos puntos no depende del sistema.
- Para comprobar la escala, mide algo conocido. Por ejemplo, dos círculos del tablero en una
  pose de `patron` reconstruida, o el ancho de una pieza medida con calibre.
- Si la pose se reconstruye de nuevo (otra máscara o calibración), las mediciones quedan con ⚠.
  *Volver a medir con la nube actual* las recalcula en los mismos píxeles.

## 20. Instalación en otro computador

El proyecto se mueve entre computadores como un repositorio git. Lo que **viaja con el código**:

- el código y la interfaz web;
- la documentación;
- la lista de dependencias (`requirements.txt`);
- la regla udev del proyector (`instalacion/`);
- la **calibración vigente y su historial** (`calibraciones/`).

Lo que **no viaja**, porque pesa mucho o depende del equipo:

- el entorno de Python (`.env/`), que se recrea con `instalar.sh`;
- los datos (`capturas/`, `capturas_ordenadas/`, `resultados/`), que se copian aparte;
- los patrones `.bmp`, que se regeneran solos;
- el SDK de la cámara, que se instala aparte (§20.3).

### 20.1 Requisitos

- **Linux de 64 bits** (probado en Ubuntu 22.04). El procesamiento y la interfaz funcionarían en
  otros sistemas, pero la etapa `lightcrafter` usa `/dev/hidraw`, que solo existe en Linux.
- **Python 3.10** (recomendado). Funciona desde 3.9, pero el wheel de PySpin debe corresponder
  exactamente a la versión de Python. En Ubuntu: `sudo apt install python3.10 python3.10-venv`.
- **git**, y unos 5 GB libres por cada sesión de capturas.

### 20.2 Instalación rápida

```bash
git clone <url-del-repositorio> Tesis      # o copia la carpeta del proyecto
cd Tesis
./instalar.sh                              # entorno .env + dependencias + patrones + verificación
./instalar.sh --udev                       # (opcional) LightCrafter sin sudo; pide la clave
./instalar.sh --pyspin ~/Descargas/spinnaker_python-…-cp310-…whl   # (opcional) cámara, ver §20.3
```

`instalar.sh` se puede ejecutar varias veces: omite lo que ya está hecho. Pasos:

1. Busca Python 3.10 (o 3.x; con `--python RUTA` se elige otro).
2. Crea el entorno `.env/` e instala `requirements.txt`.
3. Opcionalmente, instala PySpin y la regla udev.
4. Genera los patrones si faltan.
5. Ejecuta `verificar.py`.

**Sobre las versiones** (`requirements.txt`): numpy 1.26.4, **opencv-python 4.11.0.86** y
matplotlib 3.10.9.

- numpy tiene que ser < 2 porque PySpin 4.x lo exige.
- OpenCV 4.12+ y 5.x exigen numpy ≥ 2, así que **no se debe actualizar OpenCV** mientras se use
  PySpin 4.x.
- Se verificó que OpenCV 4.11 da exactamente los mismos resultados que la 5.0 con las capturas
  de referencia: mismos errores de calibración y misma planitud de 0.498 mm. Solo cambia
  levemente la calibración conjunta `_J`, que no se usa por defecto.

### 20.3 Cámara FLIR: Spinnaker SDK y PySpin

PySpin es la librería de Python de la cámara. **No está en PyPI**: viene de FLIR (Teledyne) en
dos partes que deben ser **de la misma versión**:

- el **Spinnaker SDK**, con el driver y las librerías del sistema;
- el **wheel de PySpin** para tu versión de Python.

En el equipo original se usan **Spinnaker 4.4.0.246** y el wheel
`spinnaker_python-4.4.0.246-cp310-cp310-linux_x86_64`. Solo hace falta para **capturar**;
organizar, procesar, calibrar, reconstruir y la interfaz funcionan sin él (incluido el modo demo).

Pasos:

1. **Descarga** desde la web de Teledyne FLIR, sección *Spinnaker SDK* (pide una cuenta
   gratuita), dos archivos para *Linux Ubuntu 22.04, amd64*:
   - el paquete del SDK, `spinnaker-<versión>-amd64-pkg…tar.gz`;
   - el paquete de Python para la **misma versión** y para **Python 3.10**
     (`cp310`, `spinnaker_python-<versión>-cp310-…tar.gz`).
2. **Instala el SDK.** Descomprime el paquete y sigue su `README`. En las versiones recientes:

   ```bash
   tar xzf spinnaker-*-amd64-pkg*.tar.gz && cd spinnaker-*-amd64
   sudo sh install_spinnaker.sh
   ```

   Durante la instalación, acepta:
   - añadir tu usuario al grupo `flirimaging` (permisos USB de la cámara);
   - aumentar la memoria USB (`usbfs`), si te lo ofrece.

   Después cierra la sesión y vuelve a entrar, o reinicia. Los nombres exactos pueden cambiar
   entre versiones: si difieren, manda el `README` del paquete.
3. **Comprueba el SDK:** abre **SpinView** (viene con el SDK) y confirma que ve la cámara y
   muestra imagen. Si SpinView no la ve, el problema es del SDK, del cable o de los permisos,
   no del código del proyecto.
4. **Instala PySpin en el entorno del proyecto:** descomprime el paquete de Python y pásale el
   `.whl`:

   ```bash
   ./instalar.sh --pyspin /ruta/spinnaker_python-<versión>-cp310-cp310-linux_x86_64.whl
   ```

5. **Verifica:** `.env/bin/python verificar.py` debe mostrar "PySpin importado" y el modelo de la
   cámara.

**Memoria USB (cámaras USB3).** Si hay frames incompletos o la captura se corta, sube el buffer
USB del kernel a 1000 MB, como recomienda FLIR:

```bash
sudo sh -c 'echo 1000 > /sys/module/usbcore/parameters/usbfs_memory_mb'     # hasta reiniciar
```

Para que sea permanente, añade `usbcore.usbfs_memory_mb=1000` a `GRUB_CMDLINE_LINUX_DEFAULT` en
`/etc/default/grub`, ejecuta `sudo update-grub` y reinicia.

**Problemas frecuentes:**

| Síntoma | Causa | Solución |
|---|---|---|
| `ModuleNotFoundError: PySpin` | El wheel no está instalado en `.env` | Paso 4 |
| `ImportError: libSpinnaker.so…` | Falta el SDK o es de otra versión que el wheel | Instala el SDK de la misma versión (paso 2) |
| `… is not a supported wheel on this platform` | El wheel es de otra versión de Python | Descarga el `cp3XX` que coincida con `.env/bin/python -V` |
| pip pide numpy ≥ 2 o hay conflicto con numpy | Se actualizó OpenCV | Reinstala `requirements.txt` (OpenCV 4.11) |
| SpinView no ve la cámara | Permisos (grupo `flirimaging`), cable o puerto | Cierra y abre sesión tras instalar; usa un puerto USB3 |
| PySpin funciona pero `verificar.py` no detecta la cámara | La cámara está abierta en otro programa | Cierra SpinView y la interfaz web |

### 20.4 Permisos del LightCrafter (regla udev)

El proyector se controla por USB-HID (`/dev/hidrawX`), que por defecto solo puede abrir root.
La regla `instalacion/99-lightcrafter.rules` da acceso al usuario sin sudo:

```bash
./instalar.sh --udev        # copia la regla a /etc/udev/rules.d/ y recarga udev
```

Después desconecta y conecta el USB del proyector. Alternativa temporal, hasta reiniciar:
`sudo chmod a+rw /dev/hidrawX`. El mensaje de error del script indica cuál es la X.

### 20.5 La calibración viaja con el código

La calibración vigente está en **`calibraciones/`**, versionada en git:

- `Estereo_TSC_0_2.npz`;
- `Estereo_TSC_0_2_J.npz`;
- `Estereo_TSC_0_2.json`.

Son unos 15 KB. Así, al clonar el proyecto en otro computador conectado **al mismo montaje** se
puede reconstruir sin recalibrar.

- **Cada recalibración** sobrescribe esos tres archivos, **queda en uso de inmediato** (también
  al calibrar desde *Proceso por etapas*) y guarda una copia en
  `calibraciones/historial/<fecha>/`. Los diagnósticos pesados (`patron_PhasesData.npz` y las
  figuras) quedan en `resultados/calibracion/`, que no se versiona.
- **Después de recalibrar, haz commit**:
  `git add calibraciones && git commit -m "Nueva calibración"`. `verificar.py` avisa si hay
  cambios sin commit.
- **Para usar otra calibración del historial** (por ejemplo, para volver a la anterior o para
  medir capturas hechas con un montaje anterior), hay tres formas:
  - en la interfaz: pestaña **Calibración** → **Calibración en uso** → **Usar esta calibración**;
  - por línea de comandos: `calibracion_estereo.py --listar` muestra el historial (con `*` la que
    está en uso) y `calibracion_estereo.py --activar 20261124_122125` la pone en uso;
  - a mano: copiar sus tres archivos desde `calibraciones/historial/<fecha>/` a
    `calibraciones/`.

  Si la calibración en uso no está en el historial, antes de reemplazarla se respalda en
  `historial/<fecha>_respaldo/`. La reconstrucción detecta el cambio y recalcula las poses en la
  siguiente ejecución.
- **La calibración es del montaje, no del computador.** Si se movió la cámara o el proyector,
  si se reenfocó o si se cambió de equipo físico, hay que recalibrar. `verificar.py` comprueba
  que el período de las franjas y la resolución de la cámara conectada coincidan con los de la
  calibración.
- La variable `TESIS_DIR_CALIBRACION` permite usar otra carpeta de calibración, por ejemplo para
  pruebas.

### 20.6 Los datos

`capturas/` (crudas), `capturas_ordenadas/` y `resultados/` no están en git: pesan varios GB.
Opciones:

- **Copiar solo `capturas/`.** Lo demás se regenera con el pipeline: organizar, fases y
  reconstrucción.
- **Usarlas desde un disco externo** sin copiarlas:
  `TESIS_DIR_DATOS=/media/disco/tesis .env/bin/python interfaz/servidor.py`. La variable vale
  para el pipeline, la interfaz y `verificar.py`.

### 20.7 Verificar la instalación

```bash
.env/bin/python verificar.py                 # todo, incluido el hardware conectado
.env/bin/python verificar.py --sin-hardware  # sin buscar cámara ni proyector
```

Revisa, en orden:

1. versión de Python y entorno virtual;
2. paquetes y versiones;
3. PySpin y la cámara (modelo, serie y resolución);
4. regla udev, detección y respuesta del LightCrafter;
5. los 50 patrones;
6. la calibración: existencia, período, resolución de la cámara, cobertura y cambios sin commit;
7. la carpeta de datos (escritura y espacio libre);
8. el puerto de la interfaz.

Cada problema dice **qué hacer y en qué sección de este manual** está el detalle. Termina con
código 0 si no hay errores (✖); las advertencias (⚠) no impiden usar el sistema.

### 20.8 Lista para mover el proyecto a otro computador

En el equipo de origen:

1. `git status` sin cambios pendientes, en particular en `calibraciones/`.
2. `git push` al repositorio remoto, o copiar la carpeta del proyecto sin `.env/`.
3. Si hacen falta los datos, copiar `capturas/` (o tenerlas en un disco externo).

En el equipo de destino:

1. `git clone …` y `cd Tesis`.
2. `./instalar.sh`. Si se va a capturar, también `--pyspin …` (§20.3); si se va a configurar el
   proyector, `--udev`.
3. `.env/bin/python verificar.py`, con la cámara y el proyector conectados.
4. Prueba rápida sin hardware: interfaz web → *Modo demo* → *Capturar y reconstruir*.
5. Con el montaje real, captura un plano de referencia y comprueba que el error de planitud sea
   el esperado (≈ 0.5 mm). Si es mucho mayor, algo cambió en el montaje: recalibra.

