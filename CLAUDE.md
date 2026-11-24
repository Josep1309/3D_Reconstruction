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
- No hay tests automáticos. La verificación se hace corriendo el pipeline sobre las capturas
  existentes y mirando:
  - el error de planitud de `plano`, que hoy da ≈ 0.50 mm de media
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
  - `capturas/` (crudas, **nunca modificar ni borrar**);
  - `capturas_ordenadas/` (derivado, con `manifiesto.json`);
  - `resultados/` (derivado).

  Las tres están en `.gitignore`.
- Categorías: `patron` (tablero de 9×12 círculos blancos, 15 mm), `plano` (referencia de
  planitud) y `objeto`.
- La **calibración es opcional**: con `calibracion = False` la reconstrucción usa
  `calibraciones/Estereo_TSC_0_2.npz` (`cfg.DIR_CALIBRACION`), y `pipeline.main()` verifica que
  exista antes de empezar.
  - `calibraciones/` está **versionada**: viaja con el código. Cada recalibración copia a
    `calibraciones/historial/<fecha>/`.
  - Los diagnósticos pesados van a `resultados/calibracion/`. Las fases de `patron` solo se calculan si se calibra.
- **Caché en todas las etapas de proceso:**
  - las de fase omiten las poses cuyo `.npz` es más reciente que sus imágenes
    (`fase._actualizado`);
  - la reconstrucción omite las poses cuyo `<cat>_pose_XX.npz` es más reciente que su fase y
    tiene el mismo id (calibración y fecha, fase y filtros) en `<cat>_resumen.json`;
  - `organizar` es incremental mediante el manifiesto.

  Tras cambiar umbrales, usa `REHACER = True` en `pipeline.py`.
- Las poses se procesan en hilos (`fase._en_paralelo`, máximo 4; ~200 MB por pose).

- `interfaz/`:
  - `servidor.py`: HTTP con la librería estándar, SSE, `vigilar()` sobre los archivos de
    resultados, imágenes generadas desde los `.npz`;
  - `ejecutor.py`: corre `pipeline.main()` en un subproceso y aplica la configuración JSON;
  - `estatico/`: HTML, CSS y JS sin dependencias, con un visor WebGL propio en `nube.js`;
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
