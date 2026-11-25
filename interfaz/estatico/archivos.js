// Pestaña «Archivos»: capturas por configuración y proceso, sus imágenes crudas, elegir la
// configuración en uso y mover lo viejo a la papelera (GET /api/archivos, POST /api/archivos/…).
"use strict";

const ar = { datos: null, sel: new Set(), abiertas: new Set(), viendo: null };

const fechaHora = (iso, conDia = true) => {
  const d = new Date(iso);
  if (isNaN(d)) return iso || "—";
  return d.toLocaleString(locale(), conDia ? { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }
    : { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};
const megas = (b) => (b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${Math.round(b / 1e6)} MB`);

async function cargarArchivos() {
  try { ar.datos = await api("/api/archivos"); }
  catch (err) { ar.datos = null; $("#ar-contenido").textContent = t("error_x", { m: err.message }); return; }
  const existentes = new Set(ar.datos.procesos.flatMap((p) => p.items.map((i) => i.carpeta)));
  for (const c of [...ar.sel]) if (!existentes.has(c)) ar.sel.delete(c);
  if (!ar.abiertas.size && ar.datos.vigente) ar.abiertas.add(ar.datos.vigente.proceso);
  pintarArchivos();
}

function pintarArchivos() {
  const d = ar.datos;
  if (!d) return;
  if (ar.viendo) return verCaptura(ar.viendo);
  // --- barra: configuración en uso y papelera ---
  const barra = $("#ar-barra");
  barra.innerHTML = "";
  const v = d.vigente;
  const info = document.createElement("span");
  info.className = "ar-vigente";
  info.textContent = v ? t(v.auto ? "ar_vigente_auto" : "ar_vigente_elegida", { f: fechaHora(v.desde) }) : t("ar_sin_capturas");
  barra.appendChild(info);
  if (v && !v.auto) {
    const b = boton(t("ar_volver_ultima"), () => elegirConfiguracion(null));
    barra.appendChild(b);
  }
  const papelera = document.createElement("span");
  papelera.className = "ar-papelera";
  papelera.textContent = d.papelera.lotes ? t("ar_papelera", { n: d.papelera.lotes, t: megas(d.papelera.bytes) }) : t("ar_papelera_vacia");
  barra.appendChild(papelera);
  if (d.papelera.lotes) barra.appendChild(boton(t("ar_vaciar"), vaciarPapelera, "peligro"));

  // --- configuraciones (de la más reciente a la más antigua), cada una con sus procesos ---
  const cont = $("#ar-contenido");
  cont.innerHTML = "";
  const grupos = new Map();
  for (const p of d.procesos) {
    if (!grupos.has(p.configuracion)) grupos.set(p.configuracion, []);
    grupos.get(p.configuracion).push(p);
  }
  for (const [config, procesos] of [...grupos.entries()].reverse()) cont.appendChild(bloqueConfiguracion(config, procesos));
  pintarSeleccion();
}

function boton(texto, accion, clase = "") {
  const b = document.createElement("button");
  b.type = "button"; b.textContent = texto; if (clase) b.className = clase;
  b.addEventListener("click", accion);
  return b;
}

function bloqueConfiguracion(config, procesos) {
  const vigente = procesos.some((p) => p.vigente);
  const det = document.createElement("details");
  det.className = "ar-config" + (vigente ? " vigente" : "");
  det.open = ar.abiertas.has(config);
  det.addEventListener("toggle", () => { if (det.open) ar.abiertas.add(config); else ar.abiertas.delete(config); });
  const sum = document.createElement("summary");
  const cuenta = { patron: 0, plano: 0, objeto: 0 };
  for (const p of procesos) for (const i of p.items) cuenta[i.cat] = (cuenta[i.cat] || 0) + 1;
  const calibs = procesos.flatMap((p) => p.calibraciones);
  sum.innerHTML = `<b></b><span class="ar-cuenta"></span><span class="ar-etiquetas"></span>`;
  $("b", sum).textContent = t(procesos[0].patron ? "ar_config" : "ar_config_sin_patron", { f: fechaHora(config) });
  $(".ar-cuenta", sum).textContent = Object.entries(cuenta).filter(([, n]) => n).map(([c, n]) => `${nombreCat(c)} ${n}`).join(" · ");
  const etiquetas = $(".ar-etiquetas", sum);
  if (vigente) etiquetas.appendChild(etiqueta(t("ar_en_uso"), "ok"));
  if (calibs.some((c) => c.activa)) etiquetas.appendChild(etiqueta(t("ar_calib_en_uso"), "ok"));
  else if (calibs.length) etiquetas.appendChild(etiqueta(t("ar_n_calibs", { n: calibs.length })));
  else if (procesos[0].patron) etiquetas.appendChild(etiqueta(t("ar_sin_calib"), "aviso"));
  det.appendChild(sum);

  const acciones = document.createElement("div");
  acciones.className = "ar-acciones";
  if (!vigente) acciones.appendChild(boton(t("ar_usar_config"), () => elegirConfiguracion(config), "primario"));
  const todas = procesos.flatMap((p) => p.items.map((i) => i.carpeta));
  acciones.appendChild(boton(t("ar_sel_config"), () => { todas.forEach((c) => ar.sel.add(c)); pintarArchivos(); }));
  det.appendChild(acciones);
  for (const p of [...procesos].reverse()) det.appendChild(bloqueProceso(p));
  return det;
}

function etiqueta(texto, tipo = "") {
  const s = document.createElement("span");
  s.className = `ar-etiqueta ${tipo}`; s.textContent = texto;
  return s;
}

function bloqueProceso(p) {
  const div = document.createElement("section");
  div.className = "ar-proceso";
  const cab = document.createElement("header");
  const todas = p.items.map((i) => i.carpeta);
  const marcadas = todas.filter((c) => ar.sel.has(c)).length;
  cab.innerHTML = `<label class="casilla"><input type="checkbox"> <b></b></label><small></small>`;
  const casilla = $("input", cab);
  casilla.checked = marcadas === todas.length;
  casilla.indeterminate = marcadas > 0 && marcadas < todas.length;
  casilla.setAttribute("aria-label", t("ar_sel_proceso"));
  casilla.addEventListener("change", () => { todas.forEach((c) => (casilla.checked ? ar.sel.add(c) : ar.sel.delete(c))); pintarArchivos(); });
  $("b", cab).textContent = t("ar_proceso", { a: fechaHora(p.id), b: fechaHora(p.fin, false) });
  $("small", cab).textContent = p.registrado ? "" : t("ar_sin_registro");
  if (p.calibraciones.length) {
    $("small", cab).textContent += (p.registrado ? "" : " · ") + t("ar_calibs", { l: p.calibraciones.map((c) => c.id + (c.activa ? " ✓" : "")).join(", ") });
  }
  div.appendChild(cab);
  const tabla = document.createElement("div");
  tabla.className = "ar-items";
  for (const it of p.items) tabla.appendChild(filaCaptura(it));
  div.appendChild(tabla);
  return div;
}

function filaCaptura(it) {
  const fila = document.createElement("div");
  fila.className = "ar-item" + (ar.sel.has(it.carpeta) ? " sel" : "") + (it.existe ? "" : " sin-captura");
  fila.innerHTML = `<label class="casilla"><input type="checkbox"></label><span class="ar-cat"></span><span class="ar-hora"></span><span class="ar-nombre"></span><span class="ar-poses"></span><span class="ar-botones"></span>`;
  const casilla = $("input", fila);
  casilla.checked = ar.sel.has(it.carpeta);
  casilla.setAttribute("aria-label", t("ar_sel_captura", { c: it.carpeta }));
  casilla.addEventListener("change", () => { if (casilla.checked) ar.sel.add(it.carpeta); else ar.sel.delete(it.carpeta); pintarArchivos(); });
  $(".ar-cat", fila).textContent = nombreCat(it.cat);
  $(".ar-cat", fila).dataset.cat = it.cat;
  $(".ar-hora", fila).textContent = fechaHora(it.hora, false);
  $(".ar-nombre", fila).textContent = it.carpeta.split("/")[1];
  const poses = $(".ar-poses", fila);
  if (!it.existe) poses.textContent = t("ar_captura_borrada");
  else if (it.rechazo) { const e = etiqueta(t("ar_rechazada"), "error"); e.title = it.rechazo; poses.append(e, Object.assign(document.createElement("small"), { className: "ar-motivo", textContent: it.rechazo })); }
  else if (!it.poses.length) poses.appendChild(etiqueta(t("ar_no_organizada"), "aviso"));
  if (it.pureza != null && it.pureza < 0.5) {  // secuencia poco confiable: frame perdido o sin proyección
    const e = etiqueta(t("ar_dudosa", { p: it.pureza.toFixed(2) }), "aviso");
    e.title = t("ar_dudosa_title");
    poses.appendChild(e);
  }
  for (const p of it.poses) {
    const s = document.createElement("span");
    s.className = "ar-pose";
    const pasos = ["organizada", "relativa", "absoluta", "reconstruida"];
    s.innerHTML = `${p.pose}<span class="puntitos">${pasos.map((k) => `<i class="${p[k] ? "si" : ""}"></i>`).join("")}</span>`;
    s.title = pasos.filter((k) => p[k]).map((k) => t(`ar_paso_${k}`)).join(" · ") || t("ar_nada");
    poses.appendChild(s);
  }
  if (it.existe) $(".ar-botones", fila).appendChild(boton(t("ar_ver"), () => { ar.viendo = it; verCaptura(it); }));
  return fila;
}

function verCaptura(it) {
  const cont = $("#ar-contenido");
  $("#ar-barra").innerHTML = "";
  cont.dataset.abierta = "captura";
  const carpeta = { id: "captura", nombre: `${nombreCat(it.cat)} · ${it.carpeta.split("/")[1]}`, items: () => itemsDeCaptura(it.carpeta) };
  pintarCarpeta(cont, carpeta, [], { raiz: t("paso_archivos") });
  // «Volver» de la miga regresa al listado
  $(".miga button", cont).onclick = () => { ar.viendo = null; delete cont.dataset.abierta; pintarArchivos(); };
}

function pintarSeleccion() {
  const n = ar.sel.size;
  $("#ar-seleccion").classList.toggle("oculto", n === 0);
  if (!n) return;
  const items = ar.datos.procesos.flatMap((p) => p.items).filter((i) => ar.sel.has(i.carpeta));
  const poses = items.reduce((s, i) => s + i.poses.length, 0);
  $("#ar-sel-texto").textContent = t("ar_seleccion", { n, p: poses });
}

async function borrarSeleccion() {
  const d = ar.datos;
  const items = d.procesos.flatMap((p) => p.items).filter((i) => ar.sel.has(i.carpeta));
  const poses = items.reduce((s, i) => s + i.poses.length, 0);
  let texto = t("ar_confirmar", { n: items.length, p: poses });
  // ¿Hay poses del patrón usadas por la calibración en uso?
  const usadas = new Set((est.calib?.poses) || []);
  const patronUsadas = items.filter((i) => i.cat === "patron" && i.poses.some((p) => usadas.has(p.pose)));
  if (patronUsadas.length) texto += "\n\n" + t("ar_confirmar_calib", { n: patronUsadas.length });
  if (items.some((i) => d.procesos.find((p) => p.vigente && p.items.includes(i)))) texto += "\n\n" + t("ar_confirmar_vigente");
  if (!confirm(texto)) return;
  try {
    await api("/api/archivos/borrar", { carpetas: [...ar.sel] });
    ar.sel.clear();
  } catch (err) { agregarLog(`[ERROR] ${err.message}`); }
  await cargarArchivos();
  refrescarEstado();
}

async function vaciarPapelera() {
  if (!confirm(t("ar_confirmar_vaciar", { t: megas(ar.datos.papelera.bytes) }))) return;
  try { await api("/api/archivos/vaciar_papelera", {}); } catch (err) { agregarLog(`[ERROR] ${err.message}`); }
  cargarArchivos();
}

async function elegirConfiguracion(proceso) {
  try {
    const r = await api("/api/configuracion/elegir", { proceso });
    if (!r.calibracion) alert(t("ar_aviso_sin_calib"));
  } catch (err) { agregarLog(`[ERROR] ${err.message}`); }
  ar.abiertas.clear();
  ec.clave = null;  // la pestaña Calibración se recarga con la nueva
  await cargarArchivos();
  refrescarEstado();
}

function iniciarArchivos() {
  $("#ar-sel-limpiar").addEventListener("click", () => { ar.sel.clear(); pintarArchivos(); });
  $("#ar-sel-borrar").addEventListener("click", borrarSeleccion);
}
