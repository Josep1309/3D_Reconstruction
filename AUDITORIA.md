# Auditoría del proyecto — 2026-11-24

Rama `auditoria`. Revisión de todo el código (≈ 9 000 líneas de Python y JS), de los datos y de la
interfaz, con análisis estático (`pyflakes`, `vulture`) y pruebas sobre las capturas reales.

Cada hallazgo indica la **evidencia** (`archivo:línea` o medición), el **impacto**, la
**propuesta** y el **esfuerzo**: S = horas, M = un día, L = varios días.

Prioridades:
- **P1**: produce resultados malos sin avisar, o arriesga datos.
- **P2**: molesta o confunde, o hace perder tiempo o disco.
- **P3**: mejora.

---

## 0. Resumen: lo más importante

| # | Prioridad | Hallazgo | Esfuerzo |
|---|---|---|---|
| 1 | P1 | Una calibración mala queda **en uso automáticamente** (hoy: 1037 px y 139 px) | S |
| 2 | P1 | Capturas fallidas (proyector sin secuencia) se guardan y luego **se descartan en silencio** | M |
| 3 | P1 | El servidor acepta POST de cualquier página web (CSRF): podría lanzar capturas o borrar | S |
| 4 | P1 | El tamaño real del tablero **nunca se midió**: ~1 % de error de escala en todo | S (físico) |
| 5 | P1 | La calibración cubre solo el **48–59 % del ancho del proyector** | M (capturas) |
| 6 | P2 | Cada pose ocupa ~217 MB, de los cuales **~100 MB son copias** (AVI duplicado, copia ordenada) | S–M |
| 7 | P2 | La caché de imágenes del servidor puede usar **~1.2 GB de RAM** | S |
| 8 | P2 | «Detener» mata el proceso sin cerrar la cámara | S |
| 9 | P2 | Los ajustes viven solo en el navegador: `pipeline.py` y otros equipos no los ven, y los resultados no dicen con qué ajustes se hicieron | M |
| 10 | P2 | Faltan funciones básicas en la interfaz: exposición de la cámara, descargar la nube, repetir una pose, progreso por pose | M |

---

## 1. Errores reales (producen resultados malos o los ocultan)

### 1.1 [P1] Una calibración mala se pone en uso sin preguntar
- **Evidencia:**
  - `calibracion_estereo.py:631` escribe directamente en `calibraciones/`.
  - Hoy quedaron en uso, una tras otra, `20261124_125854` (RMS estéreo **1037 px**) y
    `20261124_130755` (**139 px**).
  - Toda reconstrucción hecha con ellas es basura.
- **Propuesta:**
  - Guardar siempre en `historial/`, pero **activarla solo si pasa un control**: RMS estéreo
    < 1.5 px y < 3× el de cámara y proyector, al menos 6 poses y cobertura mínima.
  - Si no lo pasa, dejar en uso la anterior y avisar en el registro y en la interfaz:
    «Calibración rechazada: …».
  - Opción para forzarla. **Esfuerzo S.**

### 1.2 [P1] Capturas que fallan se descartan en silencio
- **Evidencia:** 4 capturas del proceso de las 12:54 (`patron/20261124_125439`, `…125611`,
  `plano/…125631`, `…125641`) tienen brillo **constante** en los 50 frames (p. ej. 28.8–29.6).
  - El proyector no estaba proyectando la secuencia, o la cámara no estaba sincronizada.
  - La captura «terminó bien» y el organizador las descartó con «no se encontró el par
    negro → blanco», solo en el registro.
  - El usuario solo ve que le faltan poses.
- **Propuesta:** validar **cada pose justo después de capturarla**, antes de pasar a la
  siguiente. Los cálculos ya existen en `organizar_capturas.verificar_secuencia` y
  `segmentar_secuencias`; solo hay que llamarlos ahí. Se revisaría:
  - que esté el par negro/blanco;
  - el contraste: rango de brillo entre frames;
  - la modulación H y V;
  - el % de píxeles saturados;
  - si la escena se movió.

  Si falla, mostrar en la pausa «Pose 3 inválida: el proyector no está proyectando — ¿repetir?»,
  con botones *Repetir* y *Seguir*. **Esfuerzo M.**

### 1.3 [P2] El aviso de modulación H usa el umbral equivocado
- **Evidencia:** `organizar_capturas.py:556` compara H y V con `GAMMA_TH` (0.15). Para H debería
  usar `GAMMA_TH_Y` (0.03).
  - Las franjas H miden 0.09–0.11 en todas las poses.
  - Por eso se avisa «modulación H baja» en **todas** las poses, y el aviso deja de servir.
- **Propuesta:** usar el umbral de cada orientación. **Esfuerzo S.**

### 1.4 [P2] «Detener» deja la cámara sin cerrar
- **Evidencia:** `interfaz/servidor.py:207` envía SIGTERM. `interfaz/ejecutor.py` no lo atrapa,
  así que Python muere sin pasar por los `finally` de `CamaraFLIR.__exit__`: no hay `DeInit`,
  `EndAcquisition` ni `ReleaseInstance`.
  - A veces la siguiente captura falla hasta desconectar la cámara.
- **Propuesta:** en el ejecutor, `signal.signal(SIGTERM, …)` que lance `KeyboardInterrupt`; los
  `with` cierran la cámara solos. **Esfuerzo S.**

### 1.5 [P2] Reorganizar «desde cero» desordena los nombres de pose
- **Evidencia:** `organizar_capturas.py:496`. Con `--rehacer`:
  - se vacía el manifiesto, incluido `ultimo_indice`, y se numera desde 0;
  - no se borran las carpetas `pose_XX` viejas.
- **Impacto:**
  - Las calibraciones guardan nombres de pose; tras reorganizar, `pose_23` puede ser otra
    imagen.
  - Quedan carpetas huérfanas que nada referencia.
- **Propuesta:**
  - Que `rehacer` mueva la carpeta ordenada anterior a la papelera.
  - Que conserve la numeración por fuente: misma captura → mismo nombre.

  **Esfuerzo S.**

### 1.6 [P3] Las capturas fallidas se vuelven a leer en cada ejecución
- **Evidencia:** `organizar_capturas.py:502`. Solo se omiten las fuentes **organizadas**; las
  rechazadas se cargan otra vez (50 TIFF cada una) cada vez que corre *Organizar*, y repiten
  el aviso.
- **Propuesta:** registrar las rechazadas en el manifiesto, con su motivo, y mostrarlas en
  *Archivos* como «rechazada: sin par negro/blanco». **Esfuerzo S.**

---

## 2. Datos y seguridad

### 2.1 [P1] El servidor no comprueba el origen de las peticiones (CSRF)
- **Evidencia:** `interfaz/servidor.py:608`. `_cuerpo()` hace `json.loads` del cuerpo sin mirar
  `Content-Type`, `Origin` ni `Host`.
  - Una página cualquiera abierta en el mismo navegador puede enviar un formulario
    `text/plain` a `http://127.0.0.1:8000/api/ejecutar` o a `/api/archivos/borrar`.
  - Escuchar solo en `127.0.0.1` no protege de esto.
- **Propuesta:**
  - En los POST, exigir `Content-Type: application/json`; eso obliga al navegador a hacer
    *preflight*, y sin CORS queda bloqueado.
  - Exigir también `Origin`/`Host` = `127.0.0.1` o `localhost`; eso cubre además el
    *DNS rebinding*.

  **Esfuerzo S.**

### 2.2 [P2] Varias «fuentes de verdad» de la configuración
Hoy la configuración efectiva sale de cinco lugares:
- `configuracion.py`;
- la cabecera de `pipeline.py`;
- los **ajustes del navegador** (`localStorage`, `interfaz/estatico/ajustes.js:26`);
- `configuracion_elegida.json`;
- `procesos_captura.json`.

Problemas:
- Otro navegador u otro equipo ve otros ajustes.
- `pipeline.py` por terminal ignora los de la interfaz.
- **Ningún resultado dice con qué ajustes se calculó.** La firma está en el `.npz`, pero no se
  muestra.

Propuesta:
- Guardar los ajustes en el servidor (`<DATOS>/ajustes.json`) y que `pipeline.py` también los lea.
- Mostrar en cada pose «calculada con: σ = 1.5, γX ≥ 0.15, Fy…».
- Marcar en la interfaz las poses calculadas con ajustes distintos de los actuales.

**Esfuerzo M.**

### 2.3 [P3] La papelera no se puede restaurar desde la interfaz
Hoy se restaura a mano. Propuesta: listar los lotes de la papelera con un botón **Restaurar**,
que mueva todo de vuelta y vuelva a organizar. **Esfuerzo S.**

---

## 3. Cosas que no tienen sentido o sobran

| Hallazgo | Evidencia | Propuesta |
|---|---|---|
| Dos conceptos de «sesión»: `sesiones_patron` (pausa de 2 h, en calibración) y `sesiones.procesos` (registro / 3 min) | `calibracion_estereo.py:258`, `sesiones.py` | Dentro de la configuración vigente, `CALIBRACION_POSES = "ultima_sesion"` es redundante: hay un solo proceso con patrón. Unificar en `sesiones.py` y simplificar la opción a «todas las de la configuración» o una lista |
| `patterns.py` tiene por defecto `width=1140, height=912` (invertidos: el proyector es 912 × 1140) | `patterns.py:5` | Hoy no afecta, porque `secuencia_patrones.py` los pasa explícitos, pero confunde. Quitar los valores por defecto |
| Código muerto: `recuperar_fase_orientacion`, `apilar_poses`, `cargar_reconstruccion_pose`, `pausar_secuencia`, `CMD_STATUS_HW`, el import `HTTPStatus` | `fase.py:250`, `fase.py:652`, `reconstruccion_3d.py:303`, `servidor.py:42` | Borrar o marcar como API pública |
| Comentario desactualizado: «La reconstrucción usa la última calibración guardada en resultados/calibracion/» (ahora es `calibraciones/`) | `pipeline.py:37` | Corregir |
| README «Estado actual (capturas del 2026-10-30)»: dice línea base 91.6 mm, 0.50 mm y cobertura 43 % | `README.md:58` | Actualizar: hoy son 95.3 mm, 0.62 mm y 59 % |
| `VALORES_ORIGINALES` y el id de reconstrucción que agrega `PLANO_UMBRAL` solo si ≠ 3.0: trucos para no recalcular lo viejo | `configuracion.py:125`, `reconstruccion_3d.py:299` | Aceptable, pero se resuelve mejor con 2.2: guardar los parámetros completos en cada resultado |
| El servidor reconoce las preguntas de `input()` buscando frases en español | `servidor.py:63` (`PROMPTS`) | Si se cambia un texto, la interfaz deja de mostrar «Continuar». Que el pipeline emita una marca explícita (`@@pregunta …`), como ya hace con `@@vivo` |
| La etapa `visualizacion` (ventanas matplotlib) duplica lo que hace la interfaz, y está en `True` por defecto en `pipeline.py` | `pipeline.py:50` | Ponerla en `False` por defecto; la interfaz es la vía principal |

---

## 4. Rendimiento y disco

### 4.1 [P2] ~100 MB duplicados por pose
Medido en `objeto/20261124_132424`:

| Elemento | Tamaño |
|---|---|
| 50 TIFF crudos | 51 MB |
| **AVI FFV1 con los mismos frames** (`GUARDAR_VIDEO = True`, `configuracion.py:60`) | **47 MB** |
| Copia reordenada en `capturas_ordenadas/` (las mismas 50 imágenes, más negro y blanco duplicados) | 52 MB |
| Fases (`.npz` + `.png`) | 69 MB |

- Total ≈ 217 MB por pose. Hoy hay 16 GB en datos.
- Propuestas:
  - `GUARDAR_VIDEO = False`: el organizador descarta el AVI cuando están los TIFF. −22 %.
  - TIFF con compresión sin pérdida (LZW o Deflate) en la captura y en el organizador: típicamente
    −40 a −60 % en imágenes de 8 bits.
  - A mediano plazo: que `capturas_ordenadas/` guarde solo el **orden** (índices, ya están en el
    manifiesto como `indices_origen`) y que las fases lean directamente de `capturas/`.

  **Esfuerzo S** (las dos primeras) / **M** (la última).
- La pestaña *Archivos* podría mostrar el **espacio usado** por configuración y por proceso.

### 4.2 [P2] Caché del servidor: hasta ~1.2 GB de RAM
- **Evidencia:** `interfaz/servidor.py:448`, `lru_cache(maxsize=24)` de `.npz` completos. Medido
  en memoria:
  - `pose_06.npz`: 52 MB;
  - `pose_06_relativa.npz`: 42 MB;
  - la reconstrucción: 17 MB.

  24 entradas ≈ 1.2 GB.
- **Propuesta:** cachear solo las claves que pide cada imagen (2–3 mapas), o usar un límite por
  tamaño de ~300 MB. **Esfuerzo S.**

### 4.3 [P3] Servidor en un solo archivo de 840 líneas
`interfaz/servidor.py` mezcla HTTP, ejecución, imágenes, nube, calibración y archivos. Propuesta:
separarlo en `rutas.py`, `imagenes.py`, `ejecucion.py`, `consultas.py`. **Esfuerzo M** (sin
cambios de comportamiento).

---

## 5. Precisión y método

### 5.1 [P1] Medir el tablero
`PATRON_DISTANCIA_MM = 15.0` nunca se midió. La calibración da fx/fy de la cámara = 1.0098, y
MATLAB tenía comentada la corrección 15.0588 × 14.909. Un error de escala del tablero se traslada
**tal cual** a todas las medidas, ~1 %: 0.15 mm en 15 mm, 5 mm en 500 mm de profundidad.

Medir con calibre la distancia entre el primer y el último círculo de una fila y de una columna,
y ponerla en `(dx, dy)`.

### 5.2 [P1 → P3] Cobertura del proyector

> **Corrección (Fase 3).** El mapa de cobertura de la pestaña Calibración muestra que 8 de las 9
> zonas sin cubrir caen **fuera del campo de la cámara**: el proyector ilumina más de lo que la
> cámara ve. De las zonas visibles, la calibración en uso cubre 11 de 12 (92 %). Falta solo el
> borde izquierdo de la imagen. Baja a P3.

Las poses del patrón de la calibración en uso cubren `u_p` 224–760 de 912 (59 %) y `v_p`
176–1073. Fuera de ese rango el modelo se extrapola. El 7–9 % de los puntos de los planos cae
fuera del rango calibrado.

Propuesta:
- Capturar el patrón también en los **bordes izquierdo y derecho** del campo, con inclinaciones
  de ±20–30°.
- En la interfaz: un **mapa de cobertura** del proyector, que muestre las zonas sin cubrir y
  sugiera dónde poner el tablero en la siguiente pose. Ver 6.6.

### 5.3 [P2] Franjas horizontales con poco contraste
- La modulación H es ~0.1, contra ~0.54 en V.
- `GAMMA_TH_Y` tuvo que bajarse a 0.03.
- La calibración da fy ≈ 2·fx en el proyector (1123 contra 2209 px), lo que confirma que en el DMD
  en diamante **las filas están a medio paso**.
- Así, un período de 18 filas equivale a ~9 px efectivos: casi en el límite de lo que la óptica
  resuelve.

Propuestas, en orden de facilidad:
1. Capturar 2–4 ciclos por pose (`CICLOS_POR_CAPTURA`); ya se promedian.
2. Período **H de 36 filas**, distinto del de V. Requiere generar una secuencia nueva y parametrizar
   `PERIODO` por orientación.
3. Comparar Fy contra Fx en planos con las dos coberturas completas, después de 5.2.

### 5.4 [P2] Validación con algo de medida conocida
La planitud (0.6 mm) mide ruido y curvatura, pero **no la escala**. Propuesta: medir un bloque
patrón o un escalón de altura conocida. Un modo «verificación» que reporte la distancia entre
dos planos ajustados.

### 5.5 [P3] Saturación
En la vista previa se vio un 4.5 % de píxeles saturados en el objeto. Hoy la exposición solo se
cambia en `configuracion.py`; ver 6.2.

---

## 6. Interfaz: más amigable y con toda la información

### 6.1 [P1] Resultado de cada pose al capturarla
Ligado a 1.2. Después de cada pose, una tarjeta:
- ✔ secuencia completa, contraste H/V, % saturado, escena estable;
- o ✖ con la causa y los botones **Repetir pose** y **Seguir**.

Además:
- En la pausa, poder **repetir la pose anterior**: hoy solo hay *Continuar* y *Terminar*.
- Si `GetNextImage` agota el tiempo a mitad de la captura (Arduino apagado), hoy se aborta todo
  el plan. Mejor: avisar y permitir reintentar esa pose.

### 6.2 [P2] Control de la cámara desde la vista previa
- Control deslizante de **exposición** (hoy fija en `CAM_EXPOSICION_US = 12000`), con el % de
  saturación y el histograma en vivo.
- Un indicador de **enfoque**: varianza del laplaciano sobre las franjas.

### 6.3 [P2] Panel de inicio o estado del sistema
Una pestaña o tarjeta «Estado» que reúna:
- cámara conectada, LightCrafter conectado, permisos y patrones (lo que hace `verificar.py`, con
  un botón *Comprobar*);
- calibración en uso con un semáforo según su calidad y cobertura;
- configuración vigente y último proceso;
- espacio en disco;
- una **lista de comprobación** antes de medir: proyector encendido con la secuencia cargada,
  Arduino, exposición, tablero medido.

### 6.4 [P2] Progreso y errores visibles
- Barra de progreso por etapa con **N de M poses** y tiempo estimado. Hoy se resalta la etapa,
  pero no cuánto le falta.
- Cuando algo falla: un **aviso destacado** (no solo una línea roja en el registro) con la causa
  y un enlace a la sección del manual. El pipeline ya imprime `AYUDA_ETAPA`.
- Registro con filtro (errores, avisos, todo), búsqueda y botón **Descargar registro**.

### 6.5 [P2] Exportar y medir
- **Descargar** la nube (`.ply`), el mapa de profundidad (PNG o CSV) y un **informe** de la
  calibración. Hoy no se puede descargar nada desde la interfaz.
- En la nube y en el mapa Z:
  - clic para leer X, Y, Z;
  - distancia entre dos puntos;
  - **perfil** a lo largo de una línea;
  - recorte de una región.
- En los planos: histograma del error y estadísticas (RMS, P95, máximo).

### 6.6 [P2] Ayuda para calibrar mejor
- En la pestaña Calibración, el **mapa de cobertura** del proyector con las zonas vacías
  resaltadas, el % cubierto y una flecha de «siguiente pose sugerida».
- Mientras se captura el patrón: indicar en la vista previa si el tablero se detecta.
  `detectar_puntos_tablero` ya existe y tarda ~50 ms.

### 6.7 [P3] Comparar
- Ver dos poses o dos ajustes **lado a lado**, o su **diferencia** de Z. Es muy útil con los
  ajustes nuevos: «sin máscara contra con máscara».
- Ver la evolución del error de planitud por fecha y calibración.

### 6.8 [P3] Organización
- **Nombre o nota** para cada objeto o proceso («pieza A, cara superior»), en vez de solo
  `pose_06`.
- Espacio en disco por proceso en *Archivos*; restaurar desde la papelera (2.3); capturas
  rechazadas visibles (1.6).

### 6.9 [P3] Ayuda integrada
- El manual completo dentro de la interfaz, con enlaces desde cada «?» a su sección.
- Atajos de teclado documentados (Enter, Esc, ← →) con `?`.
- Un recorrido de primera vez: «1. Comprueba el sistema → 2. Calibra → 3. Mide».

---

## 7. Pruebas y mantenimiento

### 7.1 [P2] No hay pruebas automáticas
Cada cambio se verificó a mano, y varios fallos de esta semana los habría detectado una prueba:
la caché que ignoraba ajustes, los errores de otra calibración o el umbral H. Propuesta, con
`pytest` y un juego de datos pequeño (2 poses del patrón, 1 plano, 1 objeto, ~300 MB) fuera del
repositorio:
- decodificar los `.bmp` del proyector da error 0.000 px (ya es una verificación manual en
  `CLAUDE.md`);
- el pipeline completo sobre el juego reproduce RMS estéreo y planitud con tolerancias;
- el organizador con frames perdidos, ciclos partidos y capturas sin proyección;
- la caché: cambiar un ajuste recalcula, volver al valor anterior también;
- la API: borrar, elegir configuración y activar calibración, sobre una copia.

**Esfuerzo M.**

### 7.2 [P3] Análisis estático
`pyflakes` y `vulture` están limpios salvo el código muerto de §3. Agregar `ruff` con una
configuración mínima a `requirements-dev.txt`.

---

## 8. Plan sugerido

**Fase 1 — rápida (≈ 1 día), corrige lo que da resultados malos o arriesga datos:**
1.1 control de calidad de la calibración · 1.3 umbral H · 1.4 cerrar la cámara al detener ·
2.1 protección CSRF · 4.2 caché del servidor · §3 limpieza y documentación desactualizada ·
`GUARDAR_VIDEO = False`.

**Fase 2 — captura confiable (≈ 2–3 días):**
1.2 + 6.1 validación por pose con *Repetir* · 6.2 exposición desde la interfaz · 1.6 capturas
rechazadas · 6.4 progreso y avisos de error · 7.1 pruebas mínimas.

**Fase 3 — precisión (trabajo en el laboratorio + código):**
5.1 medir el tablero · 5.2 recalibrar con cobertura completa + 6.6 mapa de cobertura · 5.3 ciclos
y período H · 5.4 pieza de referencia.

**Fase 4 — interfaz completa:**
6.3 estado del sistema · 6.5 exportar y medir · 2.2 ajustes en el servidor y procedencia ·
6.7 comparar · 6.8 notas · 6.9 ayuda integrada · 4.1 compresión y menos copias · 4.3 dividir el
servidor.
