# CLAUDE.md

Tesis: reconstrucción 3D por proyección de franjas (phase shifting + código Gray) con un
proyector TI DLP LightCrafter 4500 (912×1140, DMD en diamante), una cámara FLIR Blackfly S
(1280×1024) y un Arduino que dispara ambos a 20 Hz. Es un port a Python de los scripts de MATLAB
de `Matlab_Codes/Codes/`, que son solo referencia y no se ejecutan. El manual completo está en
`MANUAL.md`.

## Comandos

```bash
.env/bin/python pipeline.py                 # TODO se controla editando la cabecera de pipeline.py
.env/bin/python organizar_capturas.py --simular
.env/bin/python calibracion_estereo.py --help
.env/bin/python reconstruccion_3d.py --categorias objeto --fase Fy
```

- Interfaz web: `.env/bin/python interfaz/servidor.py [--puerto N --sin-navegador]`. Para
  probarla sin hardware ni tocar datos reales, usa
  `TESIS_DIR_DATOS=<copia> … --sin-navegador` y el modo demo (`"simular": "objeto/<carpeta>"` en
  `POST /api/ejecutar`).
- Python 3.10 en `.env/`, creado con `./instalar.sh` desde `requirements.txt`: numpy 1.26,
  **opencv 4.11** y matplotlib, más spinnaker-python (PySpin, solo para capturar).
  - PySpin 4.x exige numpy<2 y OpenCV ≥4.12 exige numpy≥2: **no subas OpenCV**.
  - Se verificó que 4.11 da los mismos resultados que 5.0.
- `.env/bin/python verificar.py [--sin-hardware]` diagnostica la instalación. La guía de problemas
  por etapa está en MANUAL.md §16 e instalación/PySpin en §20. Si agregas un error nuevo,
  documéntalo en la tabla de su etapa.
- Pruebas: `.env/bin/python -m pytest` (≈ 2 s; `tests/`, con datos temporales vía
  `TESIS_DIR_DATOS`, nunca los reales).
  - Cubren decodificación exacta de los patrones, organizar, sesiones, control de calidad de la
    calibración y la seguridad del servidor.
  - Dependencias de desarrollo: `requirements-dev.txt` (`pytest`, `ruff`).
  - Además, verificar con datos reales corriendo el pipeline y mirando:
  - el error de planitud de `plano`, que da ≈ 0.5 mm con la calibración de la misma sesión
    (planos `pose_08`–`15` del 24-nov: 0.45–0.79 mm; los `00`–`07` son del montaje del 30-oct y
    dan ~1.3 mm con la calibración actual)
    (`resultados/reconstruccion/plano/plano_resumen.json`);
  - las figuras de `resultados/`.
- Para correr sin ventanas: `matplotlib.use("Agg")` y `visualizar_pose(..., mostrar=False)`.
- `visualizacion` llama a `plt.show()` y bloquea si no se desactiva.

## Arquitectura

Las etapas corren en un orden fijo desde `pipeline.py` (`ETAPAS`):

`patrones → lightcrafter → captura → organizar → fase_relativa → fase_absoluta → calibracion → reconstruccion → visualizacion`

- `configuracion.py`: parámetros físicos y umbrales. Todos los módulos lo importan como `cfg`.
- `pipeline.py`: qué etapas corren y opciones de flujo. Las etapas son envoltorios
  `etapa_<nombre>()`.
- Datos:
  - `capturas/` (crudas). **Tú nunca las modificas ni las borras.** El usuario sí puede, desde la
    pestaña Archivos (`archivos.py` las mueve a `<DATOS>/papelera/`). Para probar borrados, usa
    una copia con `cp -al` y copia aparte el `manifiesto.json`, que se reescribe;
  - `capturas_ordenadas/` (derivado, con `manifiesto.json`);
  - `resultados/` (derivado).

  Las tres están en `.gitignore`.
- Categorías: `patron` (tablero de 9×12 círculos blancos, 15 mm), `plano` (referencia de
  planitud) y `objeto`.
- La **calibración es opcional**: con `calibracion = False` la reconstrucción usa
  `calibraciones/Estereo_TSC_0_2.npz` (`cfg.DIR_CALIBRACION`), y `pipeline.main()` verifica que
  exista antes de empezar.
  - Solo calibran poses del **mismo montaje**: `CALIBRACION_POSES = "ultima_sesion"` (sesiones
    = capturas separadas por > 2 h). Mezclar sesiones del 30-oct y 24-nov dio 12.8 px de RMS estéreo
    y planos curvos (1.5 mm). Los errores por pose independientes no lo delatan, el estéreo sí
    (`errores_reproyeccion`, pestaña Calibración de la interfaz).
  - `calibraciones/` está **versionada**: viaja con el código. Cada recalibración queda en uso y
    copia a `calibraciones/historial/<fecha>/`. Para usar otra:
    `calibracion_estereo.py --listar` / `--activar <fecha>`, o la pestaña Calibración de la
    interfaz (`POST /api/calibraciones/activar`).
  - Los diagnósticos pesados van a `resultados/calibracion/`. Las fases de `patron` solo se calculan si se calibra.
- **Solo la configuración vigente** (`sesiones.py`, `SOLO_CONFIGURACION_ACTUAL = True`):
  `fase.listar_poses`, `fase.cargar_fases_categoria`, la reconstrucción y la interfaz filtran a
  las poses de una configuración, que va de un proceso con patrón hasta el siguiente. Por defecto
  es la última; `configuracion_elegida.json` fija otra.
  - `etapa_captura` registra cada proceso en `<DATOS>/procesos_captura.json`. Sin registro, una
    pausa > 3 min separa procesos, salvo que siga el patrón.
  - Al activar una calibración también cambia la configuración, y viceversa.
- **Ajustes de la interfaz:** `conf["ajustes"]` sobrescribe variables de `cfg`
  (`ejecutor.aplicar_ajustes`, null = desactivado).
  - Las fases guardan una `firma` de sus parámetros. Si falta, se asume la de
    `cfg.VALORES_ORIGINALES`.
  - El id de la reconstrucción incluye z, salto y `PLANO_UMBRAL_MM`. Por eso cambiar un ajuste
    recalcula solo lo afectado.
- **Caché en todas las etapas de proceso:**
  - las de fase omiten las poses cuyo `.npz` es más reciente que sus imágenes
    (`fase._actualizado`);
  - la reconstrucción omite las poses cuyo `<cat>_pose_XX.npz` es más reciente que su fase y
    tiene el mismo id (calibración y fecha, fase y filtros) en `<cat>_resumen.json`;
  - `organizar` es incremental mediante el manifiesto.

  Tras cambiar umbrales, usa `REHACER = True` en `pipeline.py`.
- Las poses se procesan en hilos (`fase._en_paralelo`, máximo 4; ~200 MB por pose).

- `interfaz/`:
  - servidor HTTP con la librería estándar, en módulos que se importan en este orden:
    - `comun.py`: rutas, `_archivos_pose` y `listar_poses`;
    - `ejecucion.py`: subproceso del pipeline, SSE y marcas `@@…`;
    - `imagenes.py`: imágenes, nube y medición, con una caché de mapas de 400 MB;
    - `consultas.py`: inventario, archivos, calibración, sistema, comparaciones y `vigilar()`;
    - `servidor.py`: rutas HTTP (`Manejador`, con la seguridad: host y POST JSON) y `main()`;
  - `ejecutor.py`: corre `pipeline.main()` en un subproceso y aplica la configuración JSON;
  - `estatico/`: HTML, CSS y JS sin dependencias, en scripts clásicos que comparten globales y se
    cargan antes que `app.js`:
    - `nube.js`: visor WebGL propio;
    - `galeria.js`: visor de imágenes y explorador de carpetas;
    - `ajustes.js`: diálogo ⚙ y tema (`data-theme` en `<html>`);
    - `archivos.js`: pestaña Archivos;
    - `calibracion.js`: pestaña Calibración;
  - textos de la interfaz en español e inglés en `estatico/i18n.js`. Todo texto visible nuevo va
    allí, en los dos idiomas: `data-i18n` en el HTML y `t("clave")` en el JS.

  No agregues dependencias de CDN: el equipo del laboratorio puede no tener internet.
- `configuracion.DATOS` sale de `TESIS_DIR_DATOS` (por defecto, la raíz del proyecto).

## Convenciones y decisiones no obvias

- X / `V/` / `Fx` / `u_p` = franjas verticales (columna del proyector).
  Y / `H/` / `Fy` / `v_p` = franjas horizontales (fila).
- Secuencia de 50 frames: `[H: 18 corrimientos + 6 Gray][V: 18 + 6][negro][blanco]`. Cada
  carpeta de pose tiene `P18_F00..F25` = 18 corrimientos, 6 Gray, negro y blanco.
- Los bits Gray llegan en orden LSB→MSB con la secuencia cargada en el proyector, aunque los
  `.bmp` son MSB primero. `ORDEN_BITS_GRAY = "auto"` lo detecta.
- `u_p = Φ·P/2π + c`, con `c = 4` px (centro de la franja blanca de la onda cuadrada). Decodificar
  los `.bmp` da error 0.000 px; mantén esa verificación si tocas `fase.py`.
- El filtro Hanning de `ComputeNStepPhase.m` se eliminó a propósito: matemáticamente es solo una
  rotación de fase constante (−0.015 px). No lo reintroduzcas.
- `SUAVIZADO_FASE_PX = 1.5` filtra S y C (no la fase). B y γ se calculan **sin** suavizar para
  que los umbrales no cambien de significado.
- `FASE_TRIANGULACION = "auto"` elige Fy porque la línea base es vertical
  (T ≈ (25, −88, −6) mm). `"ambas"` era peor: la calibración solo cubre u_p 364–753, y fuera de
  ese rango Fx tiene sesgos de 10–20 mm.
- `GAMMA_TH_Y = 0.03` es bajo porque las franjas H tienen poco contraste en el DMD en diamante;
  es un compromiso entre cobertura y error, documentado en `configuracion.py`.
- El tablero probablemente mide 15.0588 × 14.909 mm, no 15 × 15 (fx/fy de la cámara = 1.0098).
  `PATRON_DISTANCIA_MM` acepta `(dx, dy)`, pero sigue en 15.0 hasta que se mida físicamente.
- Formato de calibración: `X_p = R·X_c + T` en mm, distorsión `[k1, k2, p1, p2, k3]` (OpenCV).
  También se guardan `Kr1/Kt1/Kr2/Kt2` como en MATLAB.
- El código y los mensajes están en español; mantenlo así.
- `configurar_lightcrafter.py` necesita permisos sobre `/dev/hidrawX`, y la captura necesita
  hardware real. No se pueden probar sin el montaje.
