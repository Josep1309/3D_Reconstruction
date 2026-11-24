// Textos de la interfaz en español e inglés.
// - En el HTML: data-i18n="clave" (texto), data-i18n-aria / data-i18n-title / data-i18n-alt
//   (atributos), y en los botones «?»: data-i18n-ayuda="clave" + data-i18n-etiqueta="clave".
// - En el código: t("clave", {variable: valor}) con marcadores {variable}.
// El idioma elegido se guarda en el navegador; por defecto, español.
"use strict";

const TEXTOS = {
  es: {
    titulo: "Reconstrucción 3D por franjas",
    subtitulo: "Phase shifting · código Gray · triangulación cámara–proyector",
    idioma: "Idioma",
    chip_calib_title: "Calibración en uso",

    medir: "Medir",
    categoria: "Categoría",
    cat_objeto: "Objeto", cat_plano: "Plano de referencia", cat_patron: "Patrón (calibrar)",
    ayuda_categoria: "Qué se va a capturar. Objeto: lo que quieres medir. Plano de referencia: una superficie plana para comprobar la exactitud (error de planitud). Patrón: el tablero de círculos; al capturarlo se recalibra el sistema.",
    poses: "Poses",
    ayuda_poses: "Cuántas capturas distintas se harán en esta medición: varios objetos, o el mismo objeto en distintas posiciones. Para calibrar se recomiendan 10–15 poses del patrón en distintas posiciones e inclinaciones.",
    ciclos: "Ciclos",
    ayuda_ciclos: "Cuántas veces seguidas se proyecta y captura la secuencia completa de 50 patrones en cada pose. Los ciclos se promedian: con 2–4 baja el ruido, útil en superficies oscuras o con franjas de poco contraste. Cada ciclo agrega 2.5 s y la escena no debe moverse mientras tanto.",
    pausa: "Pausa antes de cada pose",
    ayuda_pausa: "Antes de capturar cada pose el proceso se detiene para que acomodes el objeto o el patrón. Continúas con el botón «Continuar» que aparece aquí (o con Enter). Si la desactivas, las poses se capturan seguidas sin esperar.",
    demo: "Modo demo (cámara simulada)",
    ayuda_demo: "Para probar la interfaz sin cámara, proyector ni Arduino: en lugar de capturar, se reproduce una captura ya guardada (eliges cuál en la lista que aparece) y todo el resto del proceso es real. Las capturas simuladas se guardan en capturas/ con el sufijo «_simulada»: bórralas al terminar.",
    fuente_aria: "Captura que reproduce la cámara simulada",
    b_medir: "Capturar y reconstruir",
    nota_patron: "Se recalibrará con todas las poses del patrón y se reconstruirán de nuevo los planos y objetos. Usa 10–15 poses que cubran todo el campo.",
    nota_demo: "Modo demo activo: en vez de usar la cámara se reproducirá la captura elegida arriba. Luego borra las carpetas «…_simulada» de capturas/.",
    sin_capturas: "sin capturas",

    pausa_titulo: "La captura está en pausa.",
    pausa_texto: "Prepara la pose y continúa.",
    continuar: "Continuar ⏎",
    terminar: "Terminar (q)",

    proceso: "Proceso por etapas",
    proceso_nota: "Las etapas siempre se ejecutan en este orden. Marca las que quieras correr.",
    opciones: "Opciones",
    cats_procesar: "Categorías a procesar",
    ayuda_cats: "Qué poses procesan las etapas de fase y de reconstrucción. Las poses del patrón se procesan solas cuando la calibración está marcada.",
    triangulacion: "Triangulación",
    ayuda_triangulacion: "Qué fase se usa para calcular la profundidad. «auto» elige la alineada con la línea base cámara–proyector (aquí Fy, la más sensible a la profundidad). «ambas» combina Fx y Fy; solo conviene si la calibración cubre todo el proyector.",
    fase_auto: "auto (línea base)", fase_ambas: "ambas",
    calibracion: "Calibración",
    ayuda_calibracion: "Qué archivo de calibración usa la reconstrucción. «independiente»: cámara y proyector calibrados por separado y luego su posición relativa (como el MATLAB). «conjunta»: todos los parámetros ajustados a la vez (archivo _J).",
    calib_indep: "independiente", calib_conj: "conjunta (_J)",
    rehacer: "Recalcular todo",
    ayuda_rehacer: "Normalmente las poses ya procesadas se reutilizan y solo se calcula lo nuevo. Márcalo si cambiaste umbrales en configuracion.py y quieres recalcular las fases y la reconstrucción de todas las poses.",
    b_ejecutar: "Ejecutar etapas seleccionadas",
    b_detener: "Detener proceso",
    ayuda_aria: "Ayuda: {x}",

    etapa_patrones: "Generar patrones", etapa_lightcrafter: "Configurar LightCrafter", etapa_captura: "Captura",
    etapa_organizar: "Organizar", etapa_fase_relativa: "Fase envuelta", etapa_fase_absoluta: "Fase desenvuelta",
    etapa_calibracion: "Calibración", etapa_reconstruccion: "Reconstrucción 3D",
    tipo_ocasional: "ocasional", tipo_hardware: "hardware", tipo_opcional: "opcional",
    corta_patrones: "Crea las 50 imágenes que proyecta el LightCrafter.",
    larga_patrones: "Genera los 50 .bmp de la secuencia (franjas desplazadas, código Gray, negro y blanco) en patterns/. Solo hace falta si cambias el período o los bits Gray; después hay que cargarlos en el LightCrafter con el software de TI.",
    corta_lightcrafter: "Ajusta por USB los tiempos del proyector.",
    larga_lightcrafter: "Envía al LightCrafter por USB la exposición y el período de cada patrón (49.7 ms / 50 ms) para sincronizarlo con el pulso de 20 Hz del Arduino. Necesita el proyector conectado y permisos sobre /dev/hidraw.",
    corta_captura: "La cámara toma los 50 patrones de cada pose.",
    larga_captura: "La cámara FLIR captura la secuencia de 50 patrones (por el número de ciclos) de cada pose, disparada por el mismo pulso del Arduino que el proyector. Usa la categoría, poses y ciclos del panel «Medir».",
    corta_organizar: "Ordena los frames crudos en poses H/V.",
    larga_organizar: "Busca el par negro → blanco para saber dónde empieza la secuencia, promedia los ciclos, verifica la calidad y guarda cada pose en capturas_ordenadas/ (franjas horizontales en H/, verticales en V/). Lo ya organizado se omite.",
    corta_fase_relativa: "Fase envuelta φ y contraste γ.",
    larga_fase_relativa: "Con los 18 corrimientos de las franjas calcula, para cada píxel, la fase envuelta φ ∈ [−π, π] y la modulación γ (contraste de las franjas, indica la calidad del píxel).",
    corta_fase_absoluta: "Desenvuelve la fase con el código Gray.",
    larga_fase_absoluta: "Decodifica el código Gray para saber en qué franja está cada píxel y obtiene la fase absoluta Φ = φ + 2πk, es decir la columna (u_p) y la fila (v_p) del proyector que ilumina cada píxel.",
    corta_calibracion: "Calibra cámara y proyector con el patrón.",
    larga_calibracion: "Detecta los círculos del tablero y calibra la cámara, el proyector y su posición relativa. Solo hace falta después de capturar poses del patrón (si se movió o reenfocó algo); si no, la reconstrucción usa la calibración guardada.",
    corta_reconstruccion: "Triangula cada píxel: nube de puntos 3D.",
    larga_reconstruccion: "Intersecta el rayo de cada píxel de la cámara con el plano del proyector dado por la fase y obtiene X, Y, Z en mm. Guarda la nube .ply y, en los planos, el error de planitud.",

    poses_titulo: "Poses",
    cargando: "Cargando…",
    sin_poses_lista: "Todavía no hay poses. Captura una con «Capturar y reconstruir».",
    pose_puntos: "{n} puntos", pose_planitud: "planitud {v} mm",
    cat_nombre_objeto: "objeto", cat_nombre_plano: "plano", cat_nombre_patron: "patrón",
    calib_titulo: "Calibración",
    sin_calib: "Sin calibración", sin_calib_title: "Activa la calibración con poses del patrón",
    estado: "Estado", sin_calib_guardada: "Sin calibración guardada",
    chip_calib: "Calibración: {n} poses · {rms} px", fecha_title: "Fecha: {f}",
    fecha: "Fecha", rms_cam: "RMS cámara", rms_proj: "RMS proyector", rms_st: "RMS estéreo",
    linea_base: "Línea base", cob_u: "Cobertura u_p", cob_v: "Cobertura v_p", tablero: "Tablero",

    estado_inactivo: "Inactivo", estado_esperando: "Esperando confirmación", estado_ejecutando: "Ejecutando: {etapa}",
    estado_iniciando: "Iniciando…", estado_terminado: "Terminado", estado_error: "Error (código {c})",
    sin_conexion: "Sin conexión con el servidor…",

    seguir: "Seguir la última",
    sin_poses: "sin poses", sin_poses_cat: "Sin poses en esta categoría.",
    met_puntos: "Puntos", met_planitud: "Planitud RMS",
    paso_captura: "Captura", paso_envuelta: "Fase envuelta", paso_desenvuelta: "Fase desenvuelta",
    paso_profundidad: "Profundidad", paso_nube: "Nube de puntos",

    vivo_alt: "Vista en vivo de la cámara", vivo_esperando: "Esperando frames…",
    vivo_pausa: "En pausa: prepara la pose y pulsa «Continuar».", vivo_frame: "Frame {i} de {n}",
    fig_franja_V: "Franjas verticales (paso 0)", fig_franja_H: "Franjas horizontales (paso 0)",
    fig_gray_V: "Código Gray V (primer bit)", fig_textura_blanco: "Textura (patrón blanco)",
    explica_envuelta: "Fase relativa φ = −atan2(S, C) de los 18 corrimientos, en [−π, π], y la modulación γ = B/A (contraste de las franjas: calidad de cada píxel).",
    fig_phiX: "Fase envuelta X (franjas V)", fig_phiY: "Fase envuelta Y (franjas H)",
    fig_qX: "Modulación γ X", fig_qY: "Modulación γ Y",
    explica_desenvuelta: "Fase absoluta Φ = φ + 2πk, con el orden de franja k del código Gray. Es proporcional a la columna (Fx) y a la fila (Fy) del proyector que ilumina cada píxel.",
    fig_Fx: "Fase desenvuelta Fx", fig_Fy: "Fase desenvuelta Fy",
    fig_kX: "Orden de franja k (Gray V)", fig_mascara: "Píxeles válidos",
    fig_Z: "Profundidad Z", fig_error: "Error respecto al plano ajustado", fig_textura: "Textura",
    falta_organizada: "Esta pose aún no está organizada.", falta_relativa: "Aún no se calcula la fase envuelta.",
    falta_absoluta: "Aún no se calcula la fase desenvuelta.", falta_reconstruida: "Aún no hay reconstrucción 3D.",
    no_disponible: "No disponible.", error_x: "Error: {m}",

    lienzo: "Nube de puntos 3D", color: "Color", col_prof: "Profundidad", col_tex: "Textura",
    tamano: "Tamaño", vista_inicial: "Vista inicial", vista_title: "Doble clic en el visor también reinicia",
    controles: "arrastra para girar · clic derecho o Shift para desplazar · rueda para acercar",
    sin_nube: "Esta pose aún no tiene reconstrucción 3D.",
    nube_cargando: "Cargando nube…", nube_mostrados: "{n} puntos mostrados", nube_de: " de {t}",
    nube_error: "No se pudo cargar la nube: {m}", webgl_no: "WebGL no disponible en este navegador",
    registro: "Registro del proceso",
    error_config: "No se pudo leer la configuración: {m}",
  },

  en: {
    titulo: "Fringe Projection 3D Reconstruction",
    subtitulo: "Phase shifting · Gray code · camera–projector triangulation",
    idioma: "Language",
    chip_calib_title: "Calibration in use",

    medir: "Measure",
    categoria: "Category",
    cat_objeto: "Object", cat_plano: "Reference plane", cat_patron: "Pattern (calibrate)",
    ayuda_categoria: "What will be captured. Object: what you want to measure. Reference plane: a flat surface used to check accuracy (flatness error). Pattern: the circle board; capturing it recalibrates the system.",
    poses: "Poses",
    ayuda_poses: "How many different captures this measurement will take: several objects, or the same object in different positions. For calibration, 10–15 pattern poses in different positions and tilts are recommended.",
    ciclos: "Cycles",
    ayuda_ciclos: "How many times in a row the full sequence of 50 patterns is projected and captured for each pose. Cycles are averaged: 2–4 reduce noise, useful on dark surfaces or low-contrast fringes. Each cycle adds 2.5 s and the scene must not move meanwhile.",
    pausa: "Pause before each pose",
    ayuda_pausa: "Before capturing each pose the process stops so you can place the object or the pattern. Continue with the “Continue” button that appears here (or Enter). If unchecked, poses are captured back to back without waiting.",
    demo: "Demo mode (simulated camera)",
    ayuda_demo: "Try the interface without camera, projector or Arduino: instead of capturing, a saved capture is replayed (choose which one in the list that appears) and the rest of the process is real. Simulated captures are saved in capturas/ with the “_simulada” suffix: delete them when you finish.",
    fuente_aria: "Capture replayed by the simulated camera",
    b_medir: "Capture and reconstruct",
    nota_patron: "The system will be recalibrated with all pattern poses, and planes and objects will be reconstructed again. Use 10–15 poses covering the whole field.",
    nota_demo: "Demo mode on: the capture chosen above will be replayed instead of using the camera. Afterwards delete the “…_simulada” folders from capturas/.",
    sin_capturas: "no captures",

    pausa_titulo: "Capture is paused.",
    pausa_texto: "Set up the pose and continue.",
    continuar: "Continue ⏎",
    terminar: "Finish (q)",

    proceso: "Step-by-step process",
    proceso_nota: "Stages always run in this order. Check the ones you want to run.",
    opciones: "Options",
    cats_procesar: "Categories to process",
    ayuda_cats: "Which poses the phase and reconstruction stages process. Pattern poses are processed automatically when calibration is checked.",
    triangulacion: "Triangulation",
    ayuda_triangulacion: "Which phase is used to compute depth. “auto” picks the one aligned with the camera–projector baseline (here Fy, the most depth-sensitive). “both” combines Fx and Fy; only worth it if the calibration covers the whole projector.",
    fase_auto: "auto (baseline)", fase_ambas: "both",
    calibracion: "Calibration",
    ayuda_calibracion: "Which calibration file the reconstruction uses. “independent”: camera and projector calibrated separately, then their relative pose (as in MATLAB). “joint”: all parameters fitted together (_J file).",
    calib_indep: "independent", calib_conj: "joint (_J)",
    rehacer: "Recompute everything",
    ayuda_rehacer: "Normally poses already processed are reused and only new ones are computed. Check this if you changed thresholds in configuracion.py and want to recompute the phases and reconstruction of every pose.",
    b_ejecutar: "Run selected stages",
    b_detener: "Stop process",
    ayuda_aria: "Help: {x}",

    etapa_patrones: "Generate patterns", etapa_lightcrafter: "Configure LightCrafter", etapa_captura: "Capture",
    etapa_organizar: "Organize", etapa_fase_relativa: "Wrapped phase", etapa_fase_absoluta: "Unwrapped phase",
    etapa_calibracion: "Calibration", etapa_reconstruccion: "3D reconstruction",
    tipo_ocasional: "occasional", tipo_hardware: "hardware", tipo_opcional: "optional",
    corta_patrones: "Creates the 50 images projected by the LightCrafter.",
    larga_patrones: "Generates the 50 .bmp files of the sequence (shifted fringes, Gray code, black and white) in patterns/. Only needed if you change the period or the Gray bits; they must then be loaded into the LightCrafter with TI's software.",
    corta_lightcrafter: "Sets the projector timing over USB.",
    larga_lightcrafter: "Sends the exposure and period of each pattern (49.7 ms / 50 ms) to the LightCrafter over USB to sync it with the Arduino's 20 Hz pulse. Needs the projector connected and permissions on /dev/hidraw.",
    corta_captura: "The camera takes the 50 patterns of each pose.",
    larga_captura: "The FLIR camera captures the 50-pattern sequence (times the number of cycles) for each pose, triggered by the same Arduino pulse as the projector. Uses the category, poses and cycles from the “Measure” panel.",
    corta_organizar: "Sorts the raw frames into H/V poses.",
    larga_organizar: "Finds the black → white pair to know where the sequence starts, averages cycles, checks quality and saves each pose in capturas_ordenadas/ (horizontal fringes in H/, vertical in V/). Already organized captures are skipped.",
    corta_fase_relativa: "Wrapped phase φ and contrast γ.",
    larga_fase_relativa: "From the 18 fringe shifts it computes, for each pixel, the wrapped phase φ ∈ [−π, π] and the modulation γ (fringe contrast, a measure of pixel quality).",
    corta_fase_absoluta: "Unwraps the phase with the Gray code.",
    larga_fase_absoluta: "Decodes the Gray code to know which fringe each pixel lies on and obtains the absolute phase Φ = φ + 2πk, i.e. the projector column (u_p) and row (v_p) that lights each pixel.",
    corta_calibracion: "Calibrates camera and projector with the pattern.",
    larga_calibracion: "Detects the board circles and calibrates the camera, the projector and their relative pose. Only needed after capturing pattern poses (if something moved or was refocused); otherwise the reconstruction uses the saved calibration.",
    corta_reconstruccion: "Triangulates each pixel: 3D point cloud.",
    larga_reconstruccion: "Intersects each camera pixel's ray with the projector plane given by the phase and obtains X, Y, Z in mm. Saves the .ply cloud and, for planes, the flatness error.",

    poses_titulo: "Poses",
    cargando: "Loading…",
    sin_poses_lista: "No poses yet. Capture one with “Capture and reconstruct”.",
    pose_puntos: "{n} points", pose_planitud: "flatness {v} mm",
    cat_nombre_objeto: "object", cat_nombre_plano: "plane", cat_nombre_patron: "pattern",
    calib_titulo: "Calibration",
    sin_calib: "No calibration", sin_calib_title: "Run the calibration with pattern poses",
    estado: "Status", sin_calib_guardada: "No saved calibration",
    chip_calib: "Calibration: {n} poses · {rms} px", fecha_title: "Date: {f}",
    fecha: "Date", rms_cam: "Camera RMS", rms_proj: "Projector RMS", rms_st: "Stereo RMS",
    linea_base: "Baseline", cob_u: "u_p coverage", cob_v: "v_p coverage", tablero: "Board",

    estado_inactivo: "Idle", estado_esperando: "Waiting for confirmation", estado_ejecutando: "Running: {etapa}",
    estado_iniciando: "Starting…", estado_terminado: "Done", estado_error: "Error (code {c})",
    sin_conexion: "No connection to the server…",

    seguir: "Follow latest",
    sin_poses: "no poses", sin_poses_cat: "No poses in this category.",
    met_puntos: "Points", met_planitud: "RMS flatness",
    paso_captura: "Capture", paso_envuelta: "Wrapped phase", paso_desenvuelta: "Unwrapped phase",
    paso_profundidad: "Depth", paso_nube: "Point cloud",

    vivo_alt: "Live camera view", vivo_esperando: "Waiting for frames…",
    vivo_pausa: "Paused: set up the pose and press “Continue”.", vivo_frame: "Frame {i} of {n}",
    fig_franja_V: "Vertical fringes (step 0)", fig_franja_H: "Horizontal fringes (step 0)",
    fig_gray_V: "Gray code V (first bit)", fig_textura_blanco: "Texture (white pattern)",
    explica_envuelta: "Relative phase φ = −atan2(S, C) from the 18 shifts, in [−π, π], and the modulation γ = B/A (fringe contrast: the quality of each pixel).",
    fig_phiX: "Wrapped phase X (V fringes)", fig_phiY: "Wrapped phase Y (H fringes)",
    fig_qX: "Modulation γ X", fig_qY: "Modulation γ Y",
    explica_desenvuelta: "Absolute phase Φ = φ + 2πk, with the fringe order k from the Gray code. It is proportional to the projector column (Fx) and row (Fy) that lights each pixel.",
    fig_Fx: "Unwrapped phase Fx", fig_Fy: "Unwrapped phase Fy",
    fig_kX: "Fringe order k (Gray V)", fig_mascara: "Valid pixels",
    fig_Z: "Depth Z", fig_error: "Error from the fitted plane", fig_textura: "Texture",
    falta_organizada: "This pose is not organized yet.", falta_relativa: "The wrapped phase has not been computed yet.",
    falta_absoluta: "The unwrapped phase has not been computed yet.", falta_reconstruida: "No 3D reconstruction yet.",
    no_disponible: "Not available.", error_x: "Error: {m}",

    lienzo: "3D point cloud", color: "Color", col_prof: "Depth", col_tex: "Texture",
    tamano: "Size", vista_inicial: "Reset view", vista_title: "Double-clicking the viewer also resets it",
    controles: "drag to rotate · right-click or Shift to pan · wheel to zoom",
    sin_nube: "This pose has no 3D reconstruction yet.",
    nube_cargando: "Loading point cloud…", nube_mostrados: "{n} points shown", nube_de: " of {t}",
    nube_error: "Could not load the point cloud: {m}", webgl_no: "WebGL is not available in this browser",
    registro: "Process log",
    error_config: "Could not read the configuration: {m}",
  },
};

// Las escalas de las imágenes las genera el servidor en español
const ESCALAS_EN = [
  [/^intensidad$/, "intensity"],
  [/^bit Gray$/, "Gray bit"],
  [/^orden /, "order "],
  [/^gris: nada · azul: solo X · verde: solo Y · blanco: ambas$/, "gray: none · blue: X only · green: Y only · white: both"],
];

let IDIOMA = (() => {
  try {
    const guardado = localStorage.getItem("idioma");
    if (guardado in TEXTOS) return guardado;
  } catch (_) { /* almacenamiento no disponible */ }
  return "es";  // por defecto español; el inglés queda guardado cuando se elige
})();

function t(clave, vars = {}) {
  const texto = TEXTOS[IDIOMA][clave] ?? TEXTOS.es[clave] ?? clave;
  return texto.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? vars[k] : `{${k}}`));
}

function traducirEscala(s) {
  if (IDIOMA !== "en") return s;
  for (const [patron, reemplazo] of ESCALAS_EN) s = s.replace(patron, reemplazo);
  return s;
}

const locale = () => (IDIOMA === "es" ? "es" : "en");

function aplicarIdioma(raiz = document) {
  document.documentElement.lang = IDIOMA;
  document.title = t("titulo");
  for (const el of raiz.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const el of raiz.querySelectorAll("[data-i18n-aria]")) el.setAttribute("aria-label", t(el.dataset.i18nAria));
  for (const el of raiz.querySelectorAll("[data-i18n-title]")) el.title = t(el.dataset.i18nTitle);
  for (const el of raiz.querySelectorAll("[data-i18n-alt]")) el.alt = t(el.dataset.i18nAlt);
  for (const el of raiz.querySelectorAll("[data-i18n-ayuda]")) {
    el.dataset.ayuda = t(el.dataset.i18nAyuda);
    if (el.dataset.i18nEtiqueta) el.setAttribute("aria-label", t("ayuda_aria", { x: t(el.dataset.i18nEtiqueta) }));
  }
  for (const b of document.querySelectorAll("[data-idioma]")) {
    b.classList.toggle("activo", b.dataset.idioma === IDIOMA);
    b.setAttribute("aria-pressed", String(b.dataset.idioma === IDIOMA));
  }
}

function cambiarIdioma(nuevo) {
  if (!(nuevo in TEXTOS) || nuevo === IDIOMA) return;
  IDIOMA = nuevo;
  try { localStorage.setItem("idioma", nuevo); } catch (_) { /* sin almacenamiento: solo esta sesión */ }
  aplicarIdioma();
  document.dispatchEvent(new CustomEvent("idioma"));
}

window.t = t;
