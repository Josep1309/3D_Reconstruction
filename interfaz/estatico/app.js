// Interfaz web del sistema de proyección de franjas: control del pipeline y visualización.
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

// Nombres, descripciones y etiquetas de las etapas: ver i18n.js (etapa_*, corta_*, larga_*)
const TIPO_ETAPA = { patrones: "ocasional", lightcrafter: "hardware", captura: "hardware", calibracion: "opcional" };
const nombreEtapa = (e) => t(`etapa_${e}`);
const nombreCat = (c) => t(`cat_nombre_${c}`);

// Qué resultado alimenta cada tipo de imagen (para saber cuándo recargarla)
const FUENTE_TIPO = {
  franja_V: "organizada", franja_H: "organizada", gray_V: "organizada", textura: "absoluta",
  phiX: "relativa", phiY: "relativa", qX: "relativa", qY: "relativa",
  Fx: "absoluta", Fy: "absoluta", kX: "absoluta", mascara: "absoluta",
  Z: "reconstruida", error: "reconstruida",
};
// Pestaña a mostrar cuando aparece un resultado nuevo, y pestaña de cada etapa en curso
const PASO_DE_CAMBIO = { organizada: "captura", relativa: "envuelta", absoluta: "desenvuelta", reconstruida: "nube" };
const PASO_DE_ETAPA = { previa: "camara", captura: "camara", organizar: "captura", fase_relativa: "envuelta", fase_absoluta: "desenvuelta", calibracion: "calibracion", reconstruccion: "profundidad" };

const est = {
  config: null,
  poses: {},           // {cat: [{pose, organizada, relativa, absoluta, reconstruida, puntos, erms_mm, z}]}
  cat: "objeto",
  pose: null,
  paso: "captura",
  ejec: { ejecutando: false },
  versiones: {},       // "cat/pose/fuente" -> contador, para forzar la recarga de imágenes
  nubeCargada: null,
  visor: null,
  calib: null,         // último resumen de calibración (para redibujar al cambiar de idioma)
  vivo: null,          // último {i, n} de la vista en vivo
};

// ============================== utilidades ==============================
async function api(ruta, cuerpo) {
  const r = await fetch(ruta, cuerpo === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo),
  });
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(datos.error || `HTTP ${r.status}`);
  return datos;
}
const version = (fuente, cat = est.cat, pose = est.pose) => est.versiones[`${cat}/${pose}/${fuente}`] || 0;
const infoPose = (cat = est.cat, pose = est.pose) => (est.poses[cat] || []).find((p) => p.pose === pose);
const fmt = (x, d = 1) => (x === null || x === undefined ? "—" : Number(x).toFixed(d));

// ============================== registro ==============================
const log = $("#log");
function agregarLog(texto) {
  if (/MANUAL\.md §/.test(texto)) est.ultimaAyuda = texto;
  const span = document.createElement("span");
  if (/\[ERROR\]|Traceback|✖|Error:/.test(texto)) span.className = "l-error";
  else if (/\[AVISO\]|\[WARN\]/.test(texto)) span.className = "l-aviso";
  else if (/\[OK\]|✔/.test(texto)) span.className = "l-ok";
  else if (/^# ETAPA|^▶/.test(texto)) span.className = "l-etapa";
  span.textContent = texto + "\n";
  const abajo = log.scrollTop + log.clientHeight >= log.scrollHeight - 30;
  log.appendChild(span);
  while (log.childNodes.length > 3000) log.removeChild(log.firstChild);
  if (abajo) log.scrollTop = log.scrollHeight;
}

// ============================== exposición y nitidez (vista previa) ==============================
// Escala logarítmica: 100 µs … 49 ms en el control deslizante (0…1000)
const EXP_MIN = 100, EXP_MAX = 49000;
const expAControl = (us) => Math.round(1000 * Math.log(us / EXP_MIN) / Math.log(EXP_MAX / EXP_MIN));
const controlAExp = (v) => Math.round(EXP_MIN * (EXP_MAX / EXP_MIN) ** (v / 1000) / 100) * 100;
let temporizadorExp = null;

function iniciarExposicion() {
  const control = $("#v-exposicion");
  const mostrar = (us) => { $("#v-exposicion-valor").textContent = `${(us / 1000).toFixed(1)} ms`; };
  control.value = expAControl(exposicionActual());
  mostrar(exposicionActual());
  control.addEventListener("input", () => {
    const us = controlAExp(+control.value);
    mostrar(us);
    clearTimeout(temporizadorExp);
    temporizadorExp = setTimeout(async () => {  // se aplica al soltar o tras una pausa breve
      fijarExposicion(us);
      try { await api("/api/camara", { exposicion_us: us }); } catch (err) { agregarLog(`[ERROR] ${err.message}`); }
      est.nitidezMax = 0;  // la escala de nitidez cambia con la exposición
    }, 250);
  });
}

function pintarNitidez(valor) {
  if (valor == null) return;
  est.nitidezMax = Math.max(est.nitidezMax || 0, valor);
  const m = $("#v-nitidez");
  m.max = est.nitidezMax || 1; m.value = valor;
  m.optimum = est.nitidezMax; m.high = 0.9 * est.nitidezMax; m.low = 0.6 * est.nitidezMax;
  $("#v-nitidez-valor").textContent = `${Math.round(valor)}`;
}

// Herramientas del registro: filtro, descarga y limpieza
function iniciarRegistro() {
  $("#log-filtro").addEventListener("change", (e) => { log.dataset.filtro = e.target.value; });
  for (const id of ["#log-filtro", "#log-descargar", "#log-limpiar"]) $(id).addEventListener("click", (e) => e.stopPropagation());
  $("#log-descargar").addEventListener("click", () => {
    const texto = [...log.childNodes].map((n) => n.textContent).join("");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([texto], { type: "text/plain;charset=utf-8" }));
    a.download = `registro_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.txt`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  $("#log-limpiar").addEventListener("click", () => { log.innerHTML = ""; });
}

// ============================== estado de ejecución ==============================
function pintarEjecucion(e) {
  est.ejec = e;
  const chip = $("#chip-estado");
  let clase = "chip-inactivo", texto = t("estado_inactivo");
  if (e.ejecutando && e.etapa === "previa") { clase = "chip-activo"; texto = t("estado_previa"); }
  else if (e.ejecutando && e.esperando) { clase = "chip-espera"; texto = t("estado_esperando"); }
  else if (e.ejecutando) {
    clase = "chip-activo";
    texto = e.etapa ? t("estado_ejecutando", { etapa: nombreEtapa(e.etapa) }) : t("estado_iniciando");
    const p = e.progreso;
    if (p && p.n) texto += ` · ${nombreCat(p.cat)} ${p.i}/${p.n}` + (p.restante_s ? ` · ~${formatoDuracion(p.restante_s)}` : "");
  }
  else if (e.codigo === 0) { clase = "chip-ok"; texto = t("estado_terminado"); }
  else if (e.codigo !== null && e.codigo !== undefined) { clase = "chip-error"; texto = t("estado_error", { c: e.codigo }); }
  chip.className = `chip ${clase}`;
  $("b", chip).textContent = texto;

  const previa = e.ejecutando && e.etapa === "previa";
  const capturando = e.ejecutando && (e.etapa === "captura" || previa);
  const pausaCaptura = e.ejecutando && e.esperando && !previa;
  $("#b-medir").disabled = e.ejecutando;
  $("#b-ejecutar").disabled = e.ejecutando;
  $("#b-previa").disabled = e.ejecutando;
  $("#b-detener").classList.toggle("oculto", !e.ejecutando || previa);
  $("#pausa").classList.toggle("oculto", !pausaCaptura);
  $("#vivo-pausa").classList.toggle("oculto", !pausaCaptura);
  $("#b-cerrar-previa").classList.toggle("oculto", !previa);
  pintarPausa(pausaCaptura ? e.meta : undefined);
  pintarTextoVivo();
  pintarCalidades();
  pintarAvisoError(e);

  $("#vivo").classList.toggle("oculto", !capturando);
  $("#camara-inactiva").classList.toggle("oculto", capturando);
  if (!capturando) { est.vivo = null; $("#vivo").classList.remove("previa"); $("#vivo-img").removeAttribute("src"); }
  if (capturando && e.esperando && !est.vivo?.previa) {
    // Entre poses: se limpia la vista hasta que llegue la vista previa de la cámara
    est.vivo = null;
    $("#vivo-img").removeAttribute("src");
    $("#vivo-progreso").value = 0;
    pintarTextoVivo();
  }
  // Mientras la cámara está activa se muestra su pestaña (aunque «seguir» esté desactivado)
  if (capturando) mostrarPaso("camara");
  marcarEtapaEnCurso(e.ejecutando ? e.etapa : null, e.progreso);
  pintarAvance(e);
  actualizarBotonUsar();
  if (rc.datos) pintarResumenRc();
  pintarPasos();
  if (!e.ejecutando) refrescarEstado();
}

// ============================== inventario de poses ==============================
let refrescoPendiente = null;
function refrescarEstado() {
  clearTimeout(refrescoPendiente);
  refrescoPendiente = setTimeout(async () => {
    try {
      const d = await api("/api/estado");
      est.poses = d.poses;
      est.calib = d.calibracion;
      est.vigente = d.vigente;
      pintarCalibracion(d.calibracion);
      pintarListaPoses();
      pintarSelectores();
      if (est.paso === "archivos" && !est.ejec.ejecutando) cargarArchivos();
      if (est.paso === "captura") cargarCarpetasPose();
      pintarPasos();
      pintarMetricas();
    } catch (err) { agregarLog(`[ERROR] estado: ${err.message}`); }
  }, 150);
}

function pintarCalibracion(c) {
  const chip = $("#chip-calib"), dl = $("#calib-detalle");
  if (!c) {
    chip.classList.remove("chip-error");
    chip.textContent = t("sin_calib"); chip.title = t("sin_calib_title");
    dl.innerHTML = "";
    const dt = document.createElement("dt"); dt.textContent = t("estado");
    const dd = document.createElement("dd"); dd.textContent = t("sin_calib_guardada");
    dl.append(dt, dd);
    return;
  }
  chip.textContent = t("chip_calib", { n: c.poses?.length ?? "?", rms: fmt(c.rms_stereo_indep_px, 2) });
  chip.title = t("fecha_title", { f: c.fecha || "?" });
  // Estéreo muy por encima de cámara y proyector: poses de montajes distintos (planos curvos)
  const mezclada = calibMezclada({ cam: c.rms_cam_px, proj: c.rms_proj_px, estereo: c.rms_stereo_indep_px });
  chip.classList.toggle("chip-error", mezclada);
  if (mezclada) chip.title += " · " + t("chip_calib_mal");
  $('#pasos [data-paso="calibracion"]').classList.toggle("alerta", mezclada);
  if (est.paso === "calibracion") cargarErroresCalib();
  const filas = [
    [t("fecha"), (c.fecha || "—").replace("T", " ")],
    [t("poses"), c.poses?.length],
    [t("rms_cam"), `${fmt(c.rms_cam_px, 3)} px`],
    [t("rms_proj"), `${fmt(c.rms_proj_px, 3)} px`],
    [t("rms_st"), `${fmt(c.rms_stereo_indep_px, 3)} px`],
    [t("linea_base"), `${fmt(c.linea_base_mm, 1)} mm`],
    ["T", c.T_mm ? c.T_mm.map((v) => fmt(v, 1)).join(", ") + " mm" : "—"],
    [t("cob_u"), c.cobertura_up_px ? c.cobertura_up_px.map((v) => fmt(v, 0)).join(" – ") + " px" : "—"],
    [t("cob_v"), c.cobertura_vp_px ? c.cobertura_vp_px.map((v) => fmt(v, 0)).join(" – ") + " px" : "—"],
    [t("tablero"), c.center_distance_mm ? [].concat(c.center_distance_mm).map((v) => fmt(v, 3)).join(" × ") + " mm" : "—"],
  ];
  dl.innerHTML = "";
  for (const [k, v] of filas) {
    const dt = document.createElement("dt"); dt.textContent = k;
    const dd = document.createElement("dd"); dd.textContent = v ?? "—";
    dl.append(dt, dd);
  }
}

function pintarListaPoses() {
  const cont = $("#lista-poses");
  cont.innerHTML = "";
  let alguna = false;
  const v = est.vigente;
  if (v) {  // solo se muestran (y procesan) las poses del último proceso con patrón en adelante
    const nota = document.createElement("p");
    nota.className = "nota vigente";
    const desde = new Date(v.desde).toLocaleString(locale(), { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
    nota.textContent = (v.manual ? t("vigente_nota_manual") : t(v.auto ? "vigente_nota" : "vigente_nota_elegida", { f: desde })) + (v.procesos_ocultos && !v.manual ? " " + t("vigente_ocultos", { n: v.procesos_ocultos }) : "");
    nota.title = t("vigente_title");
    cont.appendChild(nota);
  }
  for (const [cat, poses] of Object.entries(est.poses)) {
    if (!poses.length) continue;
    alguna = true;
    const bloque = document.createElement("div");
    bloque.innerHTML = `<h3></h3><div class="poses"></div>`;
    $("h3", bloque).textContent = `${nombreCat(cat)} · ${poses.length}`;
    for (const p of poses) {
      const b = document.createElement("button");
      b.className = "pose-btn" + (cat === est.cat && p.pose === est.pose ? " sel" : "") + (p.ajustes_ok === false ? " otros-ajustes" : "");
      const etapas = ["organizada", "relativa", "absoluta", "reconstruida"];
      b.title = `${nombreCat(cat)}/${p.pose}` + (p.puntos ? ` · ${t("pose_puntos", { n: p.puntos.toLocaleString(locale()) })}` : "") +
        (p.erms_mm ? ` · ${t("pose_planitud", { v: fmt(p.erms_mm, 3) })}` : "") +
        (p.calculada_con ? `\n${t("pose_calculada_con", { a: p.calculada_con })}` : "") +
        (p.ajustes_ok === false ? `\n⚠ ${t("pose_otros_ajustes")}` : "");
      if (p.nota) b.title = `${p.nota}\n${b.title}`;
      b.innerHTML = `${p.pose.replace("pose_", "")}<span class="puntitos">${etapas.map((k) => `<i class="${p[k] ? "si" : ""}"></i>`).join("")}</span>`;
      b.addEventListener("click", () => { $("#v-seguir").checked = false; seleccionar(cat, p.pose); });
      $(".poses", bloque).appendChild(b);
    }
    cont.appendChild(bloque);
  }
  if (!alguna) {
    const nota = document.createElement("p");
    nota.className = "nota"; nota.textContent = t("sin_poses_lista");
    cont.appendChild(nota);
  }
}

function pintarSelectores() {
  const sc = $("#v-categoria"), sp = $("#v-pose");
  const cats = Object.keys(est.poses);
  sc.innerHTML = cats.map((c) => `<option value="${c}">${nombreCat(c)}</option>`).join("");
  if (!cats.includes(est.cat)) est.cat = cats.find((c) => est.poses[c].length) || cats[0];
  sc.value = est.cat;
  const poses = (est.poses[est.cat] || []).map((p) => p.pose);
  if (!poses.includes(est.pose)) est.pose = poses[poses.length - 1] || null;
  const notaDe = (p) => (est.poses[est.cat] || []).find((x) => x.pose === p)?.nota;
  sp.innerHTML = poses.length ? poses.map((p) => `<option value="${p}">${p}${notaDe(p) ? " · " + escHTML(notaDe(p)) : ""}</option>`).join("")
    : `<option value=''>${t("sin_poses")}</option>`;
  sp.value = est.pose || "";
}

function pintarMetricas() {
  const p = infoPose(), m = $("#metricas");
  m.innerHTML = "";
  if (!p) return;
  const items = [];
  if (p.nota) items.push([t("met_nota"), p.nota]);
  if (p.puntos) items.push([t("met_puntos"), p.puntos.toLocaleString(locale())]);
  if (p.z && p.z[0] !== null && p.z[0] !== undefined) items.push(["Z", `${fmt(p.z[0])}–${fmt(p.z[1])} mm`]);
  if (p.erms_mm) items.push([t("met_planitud"), `${fmt(p.erms_mm, 3)} mm`]);
  if (p.ajustes_ok === false) items.push([t("met_ajustes"), t("met_ajustes_otros"), "aviso", p.calculada_con]);
  for (const [k, v, clase, titulo] of items) {
    const d = document.createElement("span");
    d.className = "metrica" + (clase ? ` ${clase}` : "");
    if (titulo) d.title = titulo;
    d.textContent = k;
    const b = document.createElement("b"); b.textContent = v; d.appendChild(b);
    m.appendChild(d);
  }
}

function pintarPasos() {
  const p = infoPose() || {};
  const hecho = { captura: p.organizada, envuelta: p.relativa, desenvuelta: p.absoluta, mascara: p.mascara, profundidad: p.reconstruida, nube: p.reconstruida, medir: p.reconstruida };
  const enCurso = est.ejec.ejecutando ? PASO_DE_ETAPA[est.ejec.etapa] : null;
  for (const b of $$("#pasos button")) {
    const paso = b.dataset.paso;
    b.classList.toggle("hecho", !!hecho[paso]);
    b.classList.toggle("en-curso", paso === enCurso || (enCurso === "profundidad" && paso === "nube"));
    b.setAttribute("aria-selected", String(paso === est.paso));
  }
}

// ============================== selección y paneles ==============================
function seleccionar(cat, pose) {
  const cambio = cat !== est.cat || pose !== est.pose;
  est.cat = cat; est.pose = pose;
  pintarSelectores(); pintarListaPoses(); pintarPasos(); pintarMetricas();
  if (cambio) cargarPanel();
}

function mostrarPaso(paso) {
  if (est.paso === paso) return;
  est.paso = paso;
  for (const s of $$(".panel")) s.classList.toggle("visible", s.dataset.panel === paso);
  pintarPasos();
  cargarPanel();
}

function cargarPanel() {
  const panel = $(`.panel[data-panel="${est.paso}"]`);
  if (!panel) return;
  if (est.paso === "nube") return cargarNube();
  if (est.paso === "calibracion") { cargarRecalibrar(); return cargarErroresCalib(); }
  if (est.paso === "captura") return cargarCarpetasPose();
  if (est.paso === "archivos") return cargarArchivos();
  if (est.paso === "sistema") return cargarSistema();
  if (est.paso === "profundidad") cargarMedicion();
  if (est.paso === "mascara") return cargarMascara();
  if (est.paso === "medir") return cargarMedir();
  for (const fig of $$("figure[data-tipo]", panel)) cargarFigura(fig);
}

async function cargarFigura(fig, intento = 0) {
  const tipo = fig.dataset.tipo, fuente = FUENTE_TIPO[tipo];
  const solo = fig.dataset.solo;
  fig.classList.toggle("oculto", !!solo && solo !== est.cat);
  if (solo && solo !== est.cat) return;
  const clave = `${est.cat}/${est.pose}/${tipo}/${version(fuente)}/${version("organizada")}/${IDIOMA}`;
  if (fig.dataset.clave === clave) return;
  fig.dataset.clave = clave;
  const caption = $("figcaption", fig);
  let small = $("small", caption);
  if (!small) { small = document.createElement("small"); caption.appendChild(small); }
  const ponerVacio = (msg) => {
    $("img", fig)?.remove();
    let v = $(".vacio", fig);
    if (!v) { v = document.createElement("div"); v.className = "vacio"; fig.prepend(v); }
    v.textContent = msg; small.textContent = "";
  };
  if (!est.pose) return ponerVacio(t("sin_poses_cat"));
  if (!$("img", fig)) ponerVacio(t("cargando"));
  try {
    const r = await fetch(`/api/imagen?cat=${est.cat}&pose=${est.pose}&tipo=${tipo}&ancho=1000`);
    if (fig.dataset.clave !== clave) return;  // ya se pidió otra cosa
    if (r.status === 503 && intento < 5) { fig.dataset.clave = ""; return setTimeout(() => cargarFigura(fig, intento + 1), 800); }
    if (!r.ok) return ponerVacio(fuente ? t(`falta_${fuente}`) : t("no_disponible"));
    const url = URL.createObjectURL(await r.blob());
    $(".vacio", fig)?.remove();
    let img = $("img", fig);
    if (!img) {
      img = document.createElement("img");
      img.alt = $("figcaption span", fig).textContent;
      img.addEventListener("click", () => fig.classList.toggle("ampliada"));
      fig.prepend(img);
    }
    const anterior = img.src;
    img.src = url;
    if (anterior.startsWith("blob:")) URL.revokeObjectURL(anterior);
    small.textContent = traducirEscala(decodeURIComponent(r.headers.get("X-Escala") || ""));
  } catch (err) { ponerVacio(t("error_x", { m: err.message })); }
}

async function cargarNube() {
  if (!est.visor) {
    try { est.visor = new VisorNube($("#lienzo")); }
    catch (err) { $("#n-vacio").textContent = err.message; $("#n-vacio").classList.remove("oculto"); return; }
  }
  const clave = `${est.cat}/${est.pose}/${version("reconstruida")}`;
  if (est.nubeCargada === clave) { textoNube(); return est.visor.dibujar(); }
  est.nubeCargada = clave;
  const vacio = $("#n-vacio"), info = $("#n-info");
  if (!est.pose || !infoPose()?.reconstruida) {
    est.visor.vaciar(); vacio.classList.remove("oculto"); vacio.textContent = t("sin_nube"); info.textContent = ""; return;
  }
  info.textContent = t("nube_cargando");
  try {
    const r = await fetch(`/api/nube?cat=${est.cat}&pose=${est.pose}&max=400000`);
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
    const buf = await r.arrayBuffer();
    if (est.nubeCargada !== clave) return;
    est.visor.cargar(buf);
    vacio.classList.add("oculto");
    textoNube();
  } catch (err) {
    est.nubeCargada = null;
    vacio.textContent = t("nube_error", { m: err.message });
    vacio.classList.remove("oculto");
  }
}

// Texto bajo la vista en vivo: vista previa (encuadre) o número de frame durante la captura
// «[patron] Prepara la pose 3/12 …» -> "Patrón · pose 3 de 12"
function poseEnPausa() {
  const meta = est.ejec.meta;
  if (!meta?.cat || !meta.i) return "";
  const cat = nombreCat(meta.cat);
  return t("pausa_pose", { cat: cat.charAt(0).toUpperCase() + cat.slice(1), i: meta.i, n: meta.n });
}

// Botones de la pausa según lo que pregunta el proceso (meta.tipo, ver capturar_patrones.preguntar)
function opcionesPausa(meta) {
  switch (meta?.tipo) {
    case "invalida": return [{ k: "b_repetir_pose", r: "r", p: true }, { k: "b_guardar_igual", r: "s" }, { k: "terminar", r: "q" }];
    case "reintentar": return [{ k: "b_reintentar", r: "", p: true }, { k: "terminar", r: "q" }];
    case "categoria": return [{ k: "b_plano", r: "p" }, { k: "b_objeto", r: "o", p: true }, { k: "b_omitir", r: "s" }];
    default: {
      const ops = [{ k: "continuar", r: "", p: true }];
      if (meta?.puede_repetir) ops.push({ k: "b_repetir_anterior", r: "r" });
      ops.push({ k: "terminar", r: "q" });
      return ops;
    }
  }
}

const responder = (texto) => api("/api/entrada", { texto }).catch((e) => agregarLog(`[ERROR] ${e.message}`));

function pintarPausa(meta) {
  const visible = meta !== undefined;
  $("#pausa").classList.toggle("oculto", !visible);
  $("#pausa").classList.toggle("invalida", ["invalida", "reintentar"].includes(meta?.tipo));
  if (!visible) return;
  const tipo = meta?.tipo || "pose";
  $("#pausa-titulo").textContent = t(`pausa_titulo_${tipo}`, { i: meta?.i ?? "", f: meta?.fuente ?? "" });
  $("#pausa-pose").textContent = tipo === "pose" ? poseEnPausa() : "";
  const ultima = est.ejec.calidades?.at(-1);
  $("#pausa-texto").textContent = tipo === "pose" ? t("pausa_texto") + (ultima && meta?.puede_repetir ? " " + t("pausa_ultima", { r: resumenCalidad(ultima) }) : "")
    : tipo === "categoria" ? meta.fuente : "";
  const motivos = $("#pausa-motivos");
  motivos.innerHTML = "";
  for (const m of meta?.motivos || (meta?.error ? [meta.error] : [])) {
    const li = document.createElement("li"); li.textContent = m; motivos.appendChild(li);
  }
  const clave = JSON.stringify(meta) + IDIOMA;
  for (const cont of [$("#pausa-botones"), $("#vivo-pausa")]) {
    if (cont.dataset.clave === clave) continue;
    cont.dataset.clave = clave;
    cont.innerHTML = "";
    for (const op of opcionesPausa(meta)) {
      const b = document.createElement("button");
      b.type = "button"; b.textContent = t(op.k); if (op.p) b.className = "primario";
      b.dataset.respuesta = op.r;
      b.addEventListener("click", () => responder(op.r));
      cont.appendChild(b);
    }
  }
  $("#pausa-botones .primario")?.focus();
}

// Control de calidad de cada pose capturada (servidor: evento «calidad» y estado.calidades)
function resumenCalidad(c) {
  if (!c.ok) return "✖ " + (c.motivos || []).join("; ");
  const partes = [`✔ H ${fmt(c.modulacion_H, 2)} · V ${fmt(c.modulacion_V, 2)}`];
  if (c.saturado != null) partes.push(t("cal_saturado", { p: (100 * c.saturado).toFixed(1) }));
  return partes.join(" · ") + (c.avisos?.length ? " ⚠ " + c.avisos.join("; ") : "");
}

function pintarCalidades() {
  const lista = est.ejec.calidades || [];
  $("#calidad-poses").classList.toggle("oculto", !lista.length);
  const ol = $("#calidad-lista");
  ol.innerHTML = "";
  for (const c of [...lista].reverse()) {
    const li = document.createElement("li");
    li.className = c.ok ? (c.avisos?.length ? "aviso" : "ok") : "mal";
    const cat = nombreCat(c.cat);
    li.innerHTML = "<b></b> <span></span>";
    $("b", li).textContent = `${cat.charAt(0).toUpperCase() + cat.slice(1)} ${c.i}/${c.n}`;
    $("span", li).textContent = resumenCalidad(c);
    ol.appendChild(li);
  }
}

function formatoDuracion(s) {
  return s >= 90 ? `${Math.round(s / 60)} min` : `${Math.round(s)} s`;
}

// Aviso destacado cuando el proceso termina con error (con enlace al manual si lo indica)
function pintarAvisoError(e) {
  const hay = !e.ejecutando && e.codigo != null && e.codigo !== 0 && est.errorCerrado !== e.error;
  $("#aviso-error").classList.toggle("oculto", !hay);
  if (!hay) return;
  $("#aviso-error-texto").textContent = (e.error || t("estado_error", { c: e.codigo })).replace(/^\[ERROR\]\s*/, "");
  const seccion = /§(\d+(?:\.\d+)?)/.exec(est.ultimaAyuda || e.error || "");
  $("#aviso-error-manual").classList.toggle("oculto", !seccion);
  $("#aviso-error-manual").dataset.seccion = seccion ? seccion[1] : "";
}

function pintarTextoVivo() {
  const v = est.vivo, txt = $("#vivo-texto");
  const pose = est.ejec.esperando && est.ejec.etapa === "captura" ? poseEnPausa() : "";
  const saturado = !!(v?.previa && v.saturacion > 0.005);
  txt.classList.toggle("saturado", saturado);
  if (!v) txt.textContent = est.ejec.etapa === "previa" ? t("vivo_iniciando")
    : est.ejec.esperando ? t("vivo_pausa") : t("vivo_esperando");
  else if (v.previa) txt.textContent = (pose ? pose + " — " : "") +
    t(est.ejec.etapa === "previa" ? "vivo_previa_sola" : "vivo_previa") +
    (saturado ? " · " + t("vivo_saturados", { p: (100 * v.saturacion).toFixed(1) }) : "") +
    // Al capturar el patrón: ¿se ve el tablero completo? (si no, la pose no servirá para calibrar)
    (est.ejec.meta?.cat === "patron" && v.tablero != null
      ? " · " + (v.tablero ? t("vivo_tablero_si", { n: v.tablero }) : t("vivo_tablero_no")) : "");
  else txt.textContent = t("vivo_frame", v);
  txt.classList.toggle("sin-tablero", est.ejec.meta?.cat === "patron" && v?.tablero === 0);
}

// Texto bajo el visor: puntos mostrados y controles (se redibuja al cambiar de idioma)
function textoNube() {
  const info = $("#n-info");
  if (!est.visor || !est.visor.n) { info.textContent = t("controles"); return; }
  const total = infoPose()?.puntos;
  info.textContent = t("nube_mostrados", { n: est.visor.n.toLocaleString(locale()) }) +
    (total ? t("nube_de", { t: total.toLocaleString(locale()) }) : "") + " · " + t("controles");
}

// ============================== eventos del servidor ==============================
function conectarEventos() {
  const es = new EventSource("/api/eventos");
  es.addEventListener("log", (e) => agregarLog(JSON.parse(e.data).texto));
  es.addEventListener("estado", (e) => pintarEjecucion(JSON.parse(e.data)));
  es.addEventListener("calidad", (e) => {
    const c = JSON.parse(e.data);
    est.ejec.calidades = [...(est.ejec.calidades || []), c];
    pintarCalidades();
    if (!c.ok) agregarLog(`[AVISO] ${t("cal_invalida", { i: c.i })}`);
  });
  es.addEventListener("vivo", (e) => {
    const d = JSON.parse(e.data);
    const vivo = $("#vivo");
    if (d.previa) {
      est.vivo = { previa: true, saturacion: d.saturacion, nitidez: d.nitidez, tablero: d.tablero };
      pintarNitidez(d.nitidez);
      vivo.classList.add("previa");
    } else {
      est.vivo = { i: d.i, n: d.n };
      vivo.classList.remove("previa");
      const prog = $("#vivo-progreso"); prog.max = d.n; prog.value = d.i;
    }
    pintarTextoVivo();
    const img = $("#vivo-img");
    if (!img.dataset.cargando) {
      img.dataset.cargando = "1";
      img.onload = () => {
        delete img.dataset.cargando;
        if (img.naturalHeight) $(".vivo-marco").style.setProperty("--ar", img.naturalWidth / img.naturalHeight);
      };
      img.onerror = () => delete img.dataset.cargando;
      img.src = `/api/vivo.jpg?t=${Date.now()}`;
    }
  });
  es.addEventListener("cambio", (e) => {
    const { cat, pose, tipo } = JSON.parse(e.data);
    const k = `${cat}/${pose}/${tipo}`;
    est.versiones[k] = (est.versiones[k] || 0) + 1;
    refrescarEstado();
    if ($("#v-seguir").checked) {
      seleccionar(cat, pose);
      const paso = PASO_DE_CAMBIO[tipo];
      if (paso && !(tipo === "organizada" && est.ejec.etapa === "captura")) mostrarPaso(paso);
    }
    if (cat === est.cat && pose === est.pose) setTimeout(cargarPanel, 200);
  });
  es.onerror = () => { $("#chip-estado b").textContent = t("sin_conexion"); };
  es.onopen = () => refrescarEstado();
}

// ============================== secuencia de etapas ==============================
function construirSecuencia(etapas) {
  const lista = $("#etapas");
  lista.innerHTML = "";
  let n = 0;
  for (const [etapa, activa] of Object.entries(etapas)) {
    if (etapa === "visualizacion") continue;
    const tipo = TIPO_ETAPA[etapa];
    const li = document.createElement("li");
    li.dataset.etapa = etapa;
    // Los textos llevan data-i18n: aplicarIdioma() los cambia sin reconstruir la lista
    li.innerHTML = `
      <span class="num" aria-hidden="true">${++n}</span>
      <label class="casilla"><input type="checkbox" value="${etapa}"> <span><span data-i18n="etapa_${etapa}"></span>${
        tipo ? `<span class="etiqueta-tipo ${tipo === "opcional" ? "opcional" : ""}" data-i18n="tipo_${tipo}"></span>` : ""}</span></label>
      <button type="button" class="ayuda" data-i18n-ayuda="larga_${etapa}" data-i18n-etiqueta="etapa_${etapa}">?</button>
      <small data-i18n="corta_${etapa}"></small>`;
    aplicarIdioma(li);
    const casilla = $("input", li);
    casilla.checked = !!activa;
    li.classList.toggle("activa", casilla.checked);
    casilla.addEventListener("change", () => li.classList.toggle("activa", casilla.checked));
    li.addEventListener("click", () => setTimeout(() => li.classList.toggle("activa", casilla.checked)));
    lista.appendChild(li);
  }
}

// ------------------------------------------------------------------ panel de avance
// Etapas de la ejecución (✓ hechas, la actual, las que faltan), barra total, paso actual y barra
// de la etapa (poses/capturas i de n, o «en curso» si la etapa no tiene contador).
const av = { recibido: 0, cerrado: false, ocultar: null, ultimo: null };
const reloj = (s) => (s < 60 ? `${Math.floor(s)} s` : `${Math.floor(s / 60)} min ${String(Math.floor(s % 60)).padStart(2, "0")} s`);

function pintarAvance(e) {
  const panel = $("#avance");
  if (e.ejecutando && av.ultimo && !av.ultimo.ejecutando) av.cerrado = false;  // ejecución nueva
  av.ultimo = e;
  av.recibido = Date.now();
  clearTimeout(av.ocultar);
  const plan = e.plan || [];
  const visible = plan.length > 0 && e.etapa !== "previa" && !av.cerrado;
  panel.classList.toggle("oculto", !visible);
  if (!visible) return;
  const hechas = e.hechas || {};
  const terminado = !e.ejecutando, ok = terminado && e.codigo === 0;
  panel.classList.toggle("ok", ok);
  panel.classList.toggle("error", terminado && !ok);

  // etapas
  const lista = $("#av-etapas");
  lista.innerHTML = "";
  plan.forEach((et, k) => {
    const li = document.createElement("li");
    const estado = et in hechas ? "hecha" : e.ejecutando && et === e.etapa ? "actual" : terminado && et === e.fallida ? "fallo" : "pendiente";
    li.className = estado;
    li.innerHTML = `<i></i><span></span><small></small>`;
    $("i", li).textContent = estado === "hecha" ? "✓" : estado === "fallo" ? "✕" : String(k + 1);
    $("span", li).textContent = nombreEtapa(et);
    if (et in hechas) $("small", li).textContent = reloj(hechas[et]);
    lista.appendChild(li);
  });

  // barra total: etapas hechas + fracción de la actual
  const p = e.progreso;
  const frac = e.ejecutando && p && p.n ? (p.fraccion_etapa ?? p.i / p.n) : 0;
  const nHechas = plan.filter((et) => et in hechas).length;
  $("#av-total").value = ok ? 1000 : Math.round(1000 * (nHechas + frac) / plan.length);

  if (terminado) {
    $("#av-titulo").textContent = ok ? t("av_terminado") : t("av_fallo", { etapa: nombreEtapa(e.fallida || "") });
    $("#av-tiempo").textContent = e.duracion ? reloj(e.duracion) : "";
    $("#av-paso").textContent = ok ? t("av_listo") : (e.error || "");
    $("#av-detalle").textContent = "";
    $("#av-etapa").classList.add("oculto");
    if (ok) av.ocultar = setTimeout(() => { av.cerrado = true; panel.classList.add("oculto"); }, 20000);
    return;
  }
  const k = Math.max(plan.indexOf(e.etapa), 0);
  $("#av-titulo").textContent = e.etapa
    ? t("av_etapa_de", { k: k + 1, n: plan.length, etapa: nombreEtapa(e.etapa) }) + (e.esperando ? ` · ${t("estado_esperando")}` : "")
    : t("estado_iniciando");
  $("#av-paso").textContent = e.paso || (e.etapa ? nombreEtapa(e.etapa) : "");
  const barra = $("#av-etapa");
  barra.classList.remove("oculto");
  if (p && p.n) {
    barra.max = p.n; barra.value = p.i;
    $("#av-detalle").textContent = `${p.cat ? nombreCat(p.cat) + " · " : ""}${p.i}/${p.n}` +
      (p.restante_s ? ` · ${t("av_restante", { t: formatoDuracion(p.restante_s) })}` : "");
  } else {
    barra.removeAttribute("value");  // indeterminada: la etapa avanza sin contador
    $("#av-detalle").textContent = "";
  }
  tickAvance();
}

// Tiempo transcurrido, actualizado cada segundo mientras corre (el servidor solo avisa en cambios)
function tickAvance() {
  const e = av.ultimo;
  if (!e?.ejecutando) return;
  const extra = (Date.now() - av.recibido) / 1000;
  const total = e.segundos != null ? e.segundos + extra : null, etapa = e.segundos_etapa != null ? e.segundos_etapa + extra : null;
  $("#av-tiempo").textContent = [etapa != null ? t("av_en_etapa", { t: reloj(etapa) }) : "",
                                 total != null ? t("av_total", { t: reloj(total) }) : ""].filter(Boolean).join(" · ");
}

function iniciarAvance() {
  $("#av-cerrar").addEventListener("click", () => { av.cerrado = true; $("#avance").classList.add("oculto"); });
  setInterval(tickAvance, 1000);
}

function marcarEtapaEnCurso(etapa, progreso) {
  for (const li of $$("#etapas li")) {
    const activa = li.dataset.etapa === etapa;
    li.classList.toggle("en-curso", activa);
    let barra = $(".prog", li);
    if (activa && progreso?.n) {
      if (!barra) { barra = document.createElement("progress"); barra.className = "prog"; li.appendChild(barra); }
      barra.max = progreso.n; barra.value = progreso.i;
    } else barra?.remove();
  }
}

// ============================== ayudas contextuales ==============================
// Un botón «?» muestra su texto (data-ayuda) en una burbuja: al pasar el mouse, al enfocarlo con
// el teclado o al tocarlo. La burbuja se posiciona dentro de la ventana para no desbordarla.
function iniciarAyudas() {
  const burbuja = $("#burbuja");
  let actual = null, fijada = false;
  const mostrar = (boton) => {
    actual?.setAttribute("aria-expanded", "false");
    actual = boton;
    burbuja.textContent = boton.dataset.ayuda;
    burbuja.hidden = false;
    burbuja.id = "burbuja";
    boton.setAttribute("aria-describedby", "burbuja");
    boton.setAttribute("aria-expanded", "true");
    const r = boton.getBoundingClientRect(), b = burbuja.getBoundingClientRect(), m = 12;
    let x = r.left + r.width / 2 - b.width / 2;
    x = Math.max(m, Math.min(x, window.innerWidth - b.width - m));
    let y = r.bottom + 8;
    if (y + b.height > window.innerHeight - m) y = r.top - b.height - 8;  // si no cabe abajo, arriba
    burbuja.style.left = `${x}px`;
    burbuja.style.top = `${Math.max(m, y)}px`;
  };
  const ocultar = () => {
    burbuja.hidden = true;
    actual?.setAttribute("aria-expanded", "false");
    actual?.removeAttribute("aria-describedby");
    actual = null; fijada = false;
  };
  document.addEventListener("mouseover", (e) => {
    const b = e.target.closest?.(".ayuda");
    if (b) mostrar(b);
  });
  document.addEventListener("mouseout", (e) => {
    const b = e.target.closest?.(".ayuda");
    if (b && !fijada && !b.contains(e.relatedTarget)) ocultar();
  });
  document.addEventListener("focusin", (e) => { if (e.target.matches?.(".ayuda")) mostrar(e.target); });
  document.addEventListener("focusout", (e) => { if (e.target.matches?.(".ayuda")) ocultar(); });
  document.addEventListener("click", (e) => {
    const b = e.target.closest?.(".ayuda");
    if (b) {  // tocar (pantallas táctiles) fija o suelta la burbuja
      e.preventDefault();
      if (actual === b && fijada) ocultar(); else { mostrar(b); fijada = true; }
    } else if (fijada) ocultar();
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") ocultar(); });
  window.addEventListener("scroll", ocultar, true);
}

// ============================== acciones ==============================
async function ejecutar(conf) {
  try {
    if ($("#v-seguir").checked && conf.captura?.categoria && conf.etapas?.captura && !conf.captura.plan) {
      est.cat = conf.captura.categoria === "patron" ? "patron" : conf.captura.categoria;
    }
    $("#registro").open = true;
    await api("/api/ejecutar", conf);
  } catch (err) { agregarLog(`[ERROR] ${err.message}`); }
}

function confMedir() {
  const cat = $("#m-categoria").value;
  const calibrar = cat === "patron";
  return {
    etapas: {
      patrones: false, lightcrafter: false, captura: true, organizar: true, fase_relativa: true,
      fase_absoluta: true, calibracion: calibrar, reconstruccion: true,
    },
    // Tras recalibrar se reconstruyen planos y objetos (cambia la calibración); si no, solo lo medido
    categorias: calibrar ? ["plano", "objeto"] : [cat],
    captura: { categoria: cat, poses: +$("#m-poses").value || 1, ciclos: +$("#m-ciclos").value || 1, esperar_enter: $("#m-pausa").checked },
    rehacer: false, fase: $("#a-fase").value, calibracion: $("#a-calib").value, ...posesCalib(),
    ajustes: ajustesParaEnviar(),
    simular: $("#m-demo").checked ? $("#m-fuente").value : null,
  };
}

// Poses del patrón para calibrar; «lista» = la lista fija de pipeline.py (no se envía)
const posesCalib = () => ($("#a-calib-poses").value === "lista" ? {} : { calib_poses: $("#a-calib-poses").value });

// Plan de captura del «Proceso por etapas»: {categoria: poses} de las categorías activas
function planAvanzado() {
  const plan = {};
  for (const c of $$("#plan input[name=cat]:checked")) {
    plan[c.value] = Math.max(1, +$(`#plan .plan-poses[data-cat=${c.value}]`).value || 1);
  }
  return plan;
}

function confAvanzada() {
  const etapas = {};
  for (const c of $$("#etapas input")) etapas[c.value] = c.checked;
  const plan = planAvanzado();
  const categorias = Object.keys(plan);
  return {
    etapas,
    categorias,  // también deciden qué se procesa (el patrón solo se procesa si se calibra)
    captura: {
      plan, categoria: categorias.find((c) => c !== "patron") || categorias[0],
      ciclos: +$("#a-ciclos").value || 1, esperar_enter: $("#a-pausa").checked,
    },
    rehacer: $("#a-rehacer").checked, fase: $("#a-fase").value, calibracion: $("#a-calib").value, ...posesCalib(),
    ajustes: ajustesParaEnviar(),
    simular: $("#m-demo").checked ? $("#m-fuente").value : null,
  };
}

// Avisos del «Proceso por etapas» según las categorías y etapas marcadas. Devuelve false si no
// se puede ejecutar.
function notaAvanzada() {
  const plan = planAvanzado(), cats = Object.keys(plan);
  const etapa = (e) => $(`#etapas input[value=${e}]`)?.checked;
  for (const i of $$("#plan .plan-poses")) i.disabled = !plan[i.dataset.cat];
  const avisos = [];
  let valido = true;
  if (!cats.length) { avisos.push(t("aviso_sin_categorias")); valido = false; }
  else {
    if (etapa("captura")) {
      avisos.push(t("aviso_plan", { plan: cats.map((c) => `${nombreCat(c)} × ${plan[c]}`).join(" → ") }));
      if (plan.patron && !etapa("calibracion")) avisos.push(t("aviso_patron_sin_calib"));
    }
    if (etapa("calibracion") && !plan.patron && etapa("captura")) avisos.push(t("aviso_calib_sin_patron"));
    if (etapa("calibracion")) avisos.push(t("aviso_calib_en_uso"));
    if (etapa("reconstruccion") && !cats.some((c) => c !== "patron")) avisos.push(t("aviso_sin_reconstruir"));
  }
  const nota = $("#a-nota");
  nota.textContent = avisos.join(" ");
  nota.classList.toggle("aviso", !valido || avisos.length > 1);
  return valido;
}

function notaMedir() {
  const cat = $("#m-categoria").value, nota = $("#m-nota");
  const partes = [];
  if (cat === "patron") partes.push(t("nota_patron"));
  if ($("#m-demo").checked) partes.push(t("nota_demo"));
  nota.textContent = partes.join(" ");
  nota.classList.toggle("aviso", partes.length > 0);
  $("#m-fuente").classList.toggle("oculto", !$("#m-demo").checked);
}

// Al cambiar de idioma: aplicarIdioma() ya tradujo el HTML fijo; aquí se redibuja lo dinámico
function redibujarTextos() {
  pintarEjecucion(est.ejec);
  pintarCalibracion(est.calib);
  pintarListaPoses(); pintarSelectores(); pintarMetricas(); notaMedir(); notaAvanzada(); textoNube();
  pintarTextoVivo();
  if (est.paso === "calibracion") { pintarErroresCalib(); pintarListaCalib(); }
  if (est.paso === "archivos") pintarArchivos();
  redibujarAjustes();
  if (!$("#n-vacio").classList.contains("oculto") && !est.visor?.n) $("#n-vacio").textContent = t("sin_nube");
  cargarPanel();  // recarga las figuras visibles (textos de escala y avisos en el nuevo idioma)
}

// ============================== inicio ==============================
async function iniciar() {
  aplicarIdioma();
  $("#chip-estado b").textContent = t("estado_inactivo");
  try { est.config = await api("/api/config"); }
  catch (err) { agregarLog(`[ERROR] ${t("error_config", { m: err.message })}`); return; }
  const c = est.config;
  construirSecuencia(c.etapas);
  for (const i of $$("#plan input[name=cat]")) i.checked = c.categorias.includes(i.value);
  $("#a-ciclos").value = c.captura.ciclos;
  $("#avanzado").addEventListener("change", notaAvanzada);
  $("#avanzado").addEventListener("input", notaAvanzada);
  notaAvanzada();
  $("#a-fase").value = c.fase; $("#a-calib").value = c.calibracion; $("#a-rehacer").checked = c.rehacer;
  iniciarVisor();
  iniciarArchivos();
  iniciarAvance();
  iniciarMascara();
  iniciarMedir();
  if (Array.isArray(c.calib_poses)) {  // lista explícita en pipeline.py
    const o = document.createElement("option");
    o.value = "lista"; o.dataset.i18n = "calib_poses_lista"; o.textContent = t("calib_poses_lista");
    o.title = c.calib_poses.join(", ");
    $("#a-calib-poses").appendChild(o);
    $("#a-calib-poses").value = "lista";
  } else if (c.calib_poses) $("#a-calib-poses").value = c.calib_poses;
  $("#a-calib").addEventListener("change", () => { if (est.paso === "calibracion") cargarErroresCalib(); });
  $("#ec-elegir").addEventListener("change", actualizarBotonUsar);
  $("#ec-usar").addEventListener("click", usarCalibracion);
  $("#b-ver-calib").addEventListener("click", () => mostrarPaso("calibracion"));
  await iniciarAjustes(c.parametros);  // después de fijar los selects con los valores de pipeline.py
  iniciarExposicion();
  $("#m-ciclos").value = c.captura.ciclos;
  const fuentes = c.fuentes_demo;
  $("#m-fuente").innerHTML = fuentes.map((f) => `<option>${f}</option>`).join("") || `<option value=''>${t("sin_capturas")}</option>`;
  const preferida = fuentes.find((f) => f.startsWith("objeto/")); if (preferida) $("#m-fuente").value = preferida;

  $("#b-medir").addEventListener("click", () => ejecutar(confMedir()));
  $("#b-ejecutar").addEventListener("click", () => {
    if (!notaAvanzada()) { $("#a-nota").scrollIntoView({ block: "nearest" }); return; }
    ejecutar(confAvanzada());
  });
  $("#b-detener").addEventListener("click", () => api("/api/detener", {}).catch((e) => agregarLog(`[ERROR] ${e.message}`)));
  $("#b-cerrar-previa").addEventListener("click", () => responder(""));
  $("#aviso-error-cerrar").addEventListener("click", () => { est.errorCerrado = est.ejec.error; pintarAvisoError(est.ejec); });
  $("#aviso-error-manual").addEventListener("click", () => window.abrirManual?.($("#aviso-error-manual").dataset.seccion));
  iniciarRegistro();
  iniciarManual();
  iniciarSistema();
  iniciarMedicion();
  iniciarRecalibrar();
  $("#b-previa").addEventListener("click", () =>
    ejecutar({ solo_previa: true, simular: $("#m-demo").checked ? $("#m-fuente").value : null }));
  for (const id of ["#m-categoria", "#m-demo"]) $(id).addEventListener("change", notaMedir);
  $("#v-categoria").addEventListener("change", (e) => { $("#v-seguir").checked = false; const ps = est.poses[e.target.value] || []; seleccionar(e.target.value, ps.length ? ps[ps.length - 1].pose : null); });
  $("#v-pose").addEventListener("change", (e) => { $("#v-seguir").checked = false; seleccionar(est.cat, e.target.value); });
  for (const b of $$("#pasos button")) b.addEventListener("click", () => mostrarPaso(b.dataset.paso));
  for (const b of $$(".segmentado.color button")) b.addEventListener("click", () => {
    $$(".segmentado.color button").forEach((x) => x.classList.toggle("activo", x === b));
    est.visor?.setColor(b.dataset.color);
  });
  for (const b of $$("[data-idioma]")) b.addEventListener("click", () => cambiarIdioma(b.dataset.idioma));
  document.addEventListener("idioma", redibujarTextos);
  $("#n-tam").addEventListener("input", (e) => est.visor?.setTamano(+e.target.value));
  $("#n-reiniciar").addEventListener("click", () => est.visor?.reiniciar());
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $$("figure.ampliada").forEach((f) => f.classList.remove("ampliada"));
    if (e.key === "Enter" && est.ejec.esperando && !["INPUT", "BUTTON", "SELECT"].includes(document.activeElement?.tagName)) {
      const primario = opcionesPausa(est.ejec.meta).find((o) => o.p);
      if (primario) responder(primario.r);
    }
  });
  aplicarIdioma();
  textoNube();
  $("#vivo-texto").textContent = t("vivo_esperando");
  const reticula = () => $("#vivo").classList.toggle("con-reticula", $("#v-reticula").checked);
  $("#v-reticula").addEventListener("change", reticula);
  reticula();
  notaMedir();
  iniciarAyudas();

  // Pestaña inicial
  est.paso = null;
  const d = await api("/api/estado");
  est.poses = d.poses;
  est.calib = d.calibracion;
  est.vigente = d.vigente;
  pintarCalibracion(d.calibracion);
  if (!(est.poses.objeto || []).length) est.cat = Object.keys(est.poses).find((k) => est.poses[k].length) || "objeto";
  // Enlace directo: #paso=envuelta&cat=plano&pose=pose_03 (fija la pose y desactiva «seguir»)
  const h = new URLSearchParams(location.hash.slice(1));
  if (h.get("cat") && est.poses[h.get("cat")]) est.cat = h.get("cat");
  if (h.get("pose")) { est.pose = h.get("pose"); $("#v-seguir").checked = false; }
  pintarSelectores(); pintarListaPoses(); pintarMetricas();
  mostrarPaso(h.get("paso") || (infoPose()?.reconstruida ? "nube" : "captura"));
  window.addEventListener("hashchange", () => {  // enlaces directos sin recargar la página
    const h2 = new URLSearchParams(location.hash.slice(1));
    if (h2.get("pose")) $("#v-seguir").checked = false;
    seleccionar(h2.get("cat") && est.poses[h2.get("cat")] ? h2.get("cat") : est.cat, h2.get("pose") || est.pose);
    if (h2.get("paso")) mostrarPaso(h2.get("paso"));
  });
  pintarEjecucion(d.ejecucion);
  conectarEventos();
}

iniciar();
