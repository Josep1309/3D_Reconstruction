// Ventana «Ajustes»: tema y parámetros de procesamiento (máscaras, filtros, triangulación).
// Los parámetros se guardan en este navegador y viajan con cada ejecución (conf.ajustes); el
// ejecutor los aplica sobre configuracion.py. Una casilla desactivada = no aplicar ese paso.
"use strict";

// clave: variable de configuracion.py · grupo: sección · unidad · límites del campo
const AJUSTES = [
  { clave: "CAM_EXPOSICION_US", grupo: "cam", min: 100, max: 49000, paso: 100, unidad: "µs", fijo: true },
  { clave: "SUAVIZADO_FASE_PX", grupo: "fase", min: 0.5, max: 6, paso: 0.5, unidad: "px" },
  { clave: "GAMMA_TH", grupo: "fase", min: 0.01, max: 0.9, paso: 0.01, unidad: "γ" },
  { clave: "GAMMA_TH_Y", grupo: "fase", min: 0.005, max: 0.9, paso: 0.005, unidad: "γ" },
  { clave: "UMBRAL_INTENSIDAD", grupo: "fase", min: 1, max: 250, paso: 1, unidad: "0–255" },
  { clave: "BORDE_MASCARA", grupo: "fase", min: 1, max: 200, paso: 1, unidad: "px" },
  { clave: "MED_FILT", grupo: "fase", min: 3, max: 15, paso: 2, unidad: "px" },
  { clave: "ORDEN_BITS_GRAY", grupo: "fase", opciones: ["auto", "lsb", "msb"], fijo: true },
  { clave: "SALTO_MAX_MM", grupo: "rec", min: 0.5, max: 50, paso: 0.5, unidad: "mm" },
  { clave: "Z_RANGO", grupo: "rec", doble: ["Z_MIN_MM", "Z_MAX_MM"], min: 0, max: 5000, paso: 10, unidad: "mm" },
  { clave: "PLANO_UMBRAL_MM", grupo: "rec", min: 0.5, max: 20, paso: 0.5, unidad: "mm", fijo: true },
];

const aj = { defecto: {}, valores: {} };  // valores: {clave: {on, v}} (v: número, par o texto)

function leerGuardados() {
  try { return JSON.parse(localStorage.getItem("ajustes") || "{}"); } catch (_) { return {}; }
}
function guardarAjustes() {
  try { localStorage.setItem("ajustes", JSON.stringify(aj.valores)); } catch (_) { /* sin almacenamiento */ }
  marcarCambios();
}

function valorDefecto(a, p) {
  if (a.doble) return { on: true, v: a.doble.map((k) => p[k]) };
  return { on: true, v: p[a.clave] };
}

function iniciarAjustes(parametros) {
  for (const a of AJUSTES) aj.defecto[a.clave] = valorDefecto(a, parametros);
  const guardados = leerGuardados();
  for (const a of AJUSTES) aj.valores[a.clave] = guardados[a.clave] ?? structuredClone(aj.defecto[a.clave]);
  // Triangulación y calibración (selects del diálogo): también se recuerdan
  for (const id of ["a-fase", "a-calib", "a-calib-poses"]) {
    const g = guardados[`#${id}`];
    if (g && [...$(`#${id}`).options].some((o) => o.value === g)) $(`#${id}`).value = g;
    $(`#${id}`).addEventListener("change", () => { aj.valores[`#${id}`] = $(`#${id}`).value; guardarAjustes(); });
  }
  pintarAjustes();
  $("#b-ajustes").addEventListener("click", () => $("#ajustes").showModal());
  $("#aj-restablecer").addEventListener("click", () => {
    for (const a of AJUSTES) aj.valores[a.clave] = structuredClone(aj.defecto[a.clave]);
    for (const id of ["a-fase", "a-calib", "a-calib-poses"]) delete aj.valores[`#${id}`];
    $("#a-fase").value = est.config.fase; $("#a-calib").value = est.config.calibracion;
    if (typeof est.config.calib_poses === "string") $("#a-calib-poses").value = est.config.calib_poses;
    guardarAjustes();
    pintarAjustes();
  });
  for (const b of $$("[data-tema]")) b.addEventListener("click", () => aplicarTema(b.dataset.tema));
  aplicarTema(temaGuardado());
}

const igual = (x, y) => JSON.stringify(x) === JSON.stringify(y);
const modificado = (clave) => !igual(aj.valores[clave], aj.defecto[clave]);

function pintarAjustes() {
  for (const grupo of ["cam", "fase", "rec"]) {
    const cont = $({ cam: "#aj-cam", fase: "#aj-fase", rec: "#aj-rec" }[grupo]);
    cont.innerHTML = "";
    for (const a of AJUSTES.filter((x) => x.grupo === grupo)) cont.appendChild(filaAjuste(a));
  }
  marcarCambios();
}

function filaAjuste(a) {
  const val = aj.valores[a.clave];
  const fila = document.createElement("div");
  fila.className = "aj-fila";
  fila.classList.toggle("modificado", modificado(a.clave));
  const id = `aj-${a.clave}`;
  // Nombre (con casilla «aplicar» si el paso se puede desactivar) y ayuda
  const nombre = document.createElement("span");
  nombre.className = "aj-nombre";
  if (!a.fijo) {
    nombre.innerHTML = `<label class="casilla"><input type="checkbox"> <span></span></label>`;
    const casilla = $("input", nombre);
    casilla.checked = val.on;
    casilla.addEventListener("change", () => { val.on = casilla.checked; guardarAjustes(); actualizar(); });
    $("span", nombre).textContent = t(`aj_${a.clave}`);
  } else {
    const l = document.createElement("label"); l.htmlFor = id; l.textContent = t(`aj_${a.clave}`); nombre.appendChild(l);
  }
  const ayuda = document.createElement("button");
  ayuda.type = "button"; ayuda.className = "ayuda"; ayuda.textContent = "?";
  ayuda.dataset.ayuda = t(`ayuda_aj_${a.clave}`);
  ayuda.setAttribute("aria-label", t("ayuda_aria", { x: t(`aj_${a.clave}`) }));
  nombre.appendChild(ayuda);
  fila.appendChild(nombre);
  // Valor
  const control = document.createElement("span");
  control.className = "aj-control";
  const entradas = [];
  if (a.opciones) {
    const sel = document.createElement("select");
    sel.id = id;
    for (const o of a.opciones) { const op = document.createElement("option"); op.value = o; op.textContent = t(`aj_op_${o}`); sel.appendChild(op); }
    sel.value = val.v;
    sel.addEventListener("change", () => { val.v = sel.value; guardarAjustes(); actualizar(); });
    control.appendChild(sel);
  } else {
    const vs = a.doble ? val.v : [val.v];
    vs.forEach((v, k) => {
      const inp = document.createElement("input");
      inp.type = "number"; inp.min = a.min; inp.max = a.max; inp.step = a.paso; inp.value = v;
      inp.id = k ? `${id}-${k}` : id;
      inp.setAttribute("aria-label", t(`aj_${a.clave}`) + (a.doble ? ` (${t(k ? "aj_max" : "aj_min")})` : ""));
      inp.addEventListener("change", () => {
        const x = Number(inp.value);
        if (!Number.isFinite(x)) { inp.value = vs[k]; return; }
        if (a.doble) val.v[k] = x; else val.v = x;
        guardarAjustes(); actualizar();
      });
      if (k) { const s = document.createElement("span"); s.textContent = "–"; control.appendChild(s); }
      control.appendChild(inp);
      entradas.push(inp);
    });
    const u = document.createElement("small"); u.textContent = a.unidad; control.appendChild(u);
  }
  fila.appendChild(control);
  const defecto = document.createElement("small");
  defecto.className = "aj-defecto";
  const d = aj.defecto[a.clave].v;
  defecto.textContent = t("aj_defecto", { v: Array.isArray(d) ? d.join(" – ") : a.opciones ? t(`aj_op_${d}`) : d });
  fila.appendChild(defecto);
  const actualizar = () => {
    for (const e of entradas) e.disabled = !val.on;
    fila.classList.toggle("apagado", !val.on);
    fila.classList.toggle("modificado", modificado(a.clave));
  };
  actualizar();
  return fila;
}

function marcarCambios() {
  const n = AJUSTES.filter((a) => modificado(a.clave)).length;
  const marca = $("#b-ajustes .marca-cambio");
  marca.hidden = n === 0;
  $("#b-ajustes").title = n ? t("aj_n_cambios", { n }) : t("ajustes");
}

// Lo que se envía al ejecutor: {VARIABLE: número | texto | null (= desactivado)}
function ajustesParaEnviar() {
  const salida = {};
  for (const a of AJUSTES) {
    const val = aj.valores[a.clave];
    if (a.doble) a.doble.forEach((k, i) => { salida[k] = val.on ? val.v[i] : null; });
    else salida[a.clave] = val.on || a.fijo ? val.v : null;
  }
  return salida;
}

// Exposición: la cambia también el control de la vista previa (se aplica en vivo a la cámara)
function exposicionActual() { return aj.valores.CAM_EXPOSICION_US?.v ?? 12000; }
function fijarExposicion(us) {
  aj.valores.CAM_EXPOSICION_US = { on: true, v: Math.round(us) };
  guardarAjustes();
  if ($("#ajustes").open) pintarAjustes();
}

// Textos del diálogo que se generan aquí (al cambiar de idioma)
function redibujarAjustes() { if (Object.keys(aj.defecto).length) pintarAjustes(); }

// ============================== tema ==============================
function temaGuardado() {
  try { return localStorage.getItem("tema") || "auto"; } catch (_) { return "auto"; }
}
function aplicarTema(tema) {
  if (tema === "light" || tema === "dark") document.documentElement.dataset.theme = tema;
  else delete document.documentElement.dataset.theme;
  try { localStorage.setItem("tema", tema); } catch (_) { /* sin almacenamiento */ }
  for (const b of $$("[data-tema]")) b.classList.toggle("activo", b.dataset.tema === tema);
  est.visor?.dibujar?.();
}
