// Pestaña «360°»: une varias poses (vistas) del mismo objeto en una sola nube (procesamiento/escaneo.py).
// El usuario elige las vistas (la primera es la referencia), las une y ve el resultado coloreado
// por vista. Si un par no se une solo (objeto liso o vistas que comparten poca superficie), marca
// 3 o más puntos en común en las dos vistas, lado a lado, y se vuelve a unir.
"use strict";

const e3 = {
  lista: [], actual: null, datos: null, sel: [], visor: null, nubeClave: null,
  manual: {},               // {"pose_a|pose_b": [[[x,y,z], [x,y,z]], …]}
  marcar: null,             // {a, b, visorA, visorB, puntos: [[pa, pb]], pendiente: pa|null}
};

// porPose (al abrir la pestaña): muestra el escaneo más reciente que contiene la pose elegida; si
// ninguno la contiene, uno nuevo con esa pose de referencia (y no un escaneo de otras poses).
// Sin porPose (tras unir o borrar) se queda con el escaneo actual.
async function cargarEscaneo(porPose = false) {
  try { e3.lista = (await api("/api/escaneos")).escaneos; } catch { e3.lista = []; }
  const sel = $("#e3-lista");
  sel.innerHTML = "";
  sel.appendChild(new Option(t("e3_nuevo_opcion"), ""));
  for (const e of e3.lista) sel.appendChild(new Option(`${e.nombre} · ${t("e3_n_vistas", { n: (e.unidas || []).length })}`, e.id));
  let id;
  if (porPose) {
    const conPose = e3.lista.filter((e) => est.cat === "objeto" && (e.poses || []).includes(est.pose))
      .sort((a, b) => String(b.fecha).localeCompare(String(a.fecha)));
    id = conPose.some((e) => e.id === e3.actual) ? e3.actual : (conPose[0]?.id || "");
  } else id = e3.lista.some((e) => e.id === e3.actual) ? e3.actual : "";
  sel.value = id;
  // un escaneo nuevo a medio elegir que ya incluye la pose no se pierde (p. ej. al cambiar de idioma)
  const aMedias = !id && !e3.actual && e3.sel.includes(est.pose) ? [...e3.sel] : null;
  await elegirEscaneo(id);
  if (aMedias) { e3.sel = aMedias; pintarVistasE3(); }
}

async function elegirEscaneo(id) {
  e3.actual = id || null;
  e3.mallaClave = null;
  e3.datos = null;
  if (id) {
    try { e3.datos = await api(`/api/escaneo?id=${encodeURIComponent(id)}`); } catch { e3.datos = null; }
  }
  e3.sel = e3.datos ? [...e3.datos.poses] : [];
  // escaneo nuevo: la pose elegida queda de referencia (★), si es de objeto y está reconstruida
  if (!id && est.cat === "objeto" && (est.poses.objeto || []).some((p) => p.pose === est.pose && p.reconstruida)) e3.sel = [est.pose];
  e3.manual = e3.datos?.manual ? structuredClone(e3.datos.manual) : {};
  $("#e3-nombre").value = e3.datos?.nombre || "";
  $("#e3-borrar").disabled = !id;
  $("#e3-ply").classList.toggle("oculto", !id);
  if (id) $("#e3-ply").href = `/api/escaneo/ply?id=${encodeURIComponent(id)}`;
  const hayMalla = !!e3.datos?.malla;
  for (const [sel, ruta] of [["#e3-stl", "stl"], ["#e3-malla-ply", "malla.ply"]]) {
    $(sel).classList.toggle("oculto", !hayMalla);
    if (hayMalla) $(sel).href = `/api/escaneo/${ruta}?id=${encodeURIComponent(id)}`;
  }
  pintarVistasE3();
  pintarResultadoE3();
  mostrarFusionE3();
}

// Nube de puntos, malla TSDF o las dos lado a lado (cámara sincronizada)
function mostrarFusionE3() {
  const modo = e3.fusion || "nube", hayMalla = !!e3.datos?.malla;
  const verNube = modo !== "malla" || !hayMalla, verMalla = hayMalla && modo !== "nube";
  $("#e3-lienzo").closest(".md-3d").classList.toggle("oculto", !verNube);
  $("#e3-3d-malla").classList.toggle("oculto", !verMalla);
  $(".e3-visores").classList.toggle("dos", verNube && verMalla);
  for (const b of $$("#e3-fusion button")) {
    b.classList.toggle("activo", b.dataset.fusion === modo);
    b.disabled = b.dataset.fusion !== "nube" && !hayMalla;
  }
  if (verNube) cargarNubeE3();
  if (verMalla) cargarMallaE3();
}

async function cargarMallaE3() {
  if (!e3.visorMalla) {
    try { e3.visorMalla = new VisorNube($("#e3-lienzo-malla")); } catch (err) { $("#e3-info-malla").textContent = err.message; return; }
    e3.visorMalla.setColor("textura");
    const sync = (o, d) => { if (!e3.sinc && d?.n) { e3.sinc = true; d.vista = o.vista; e3.sinc = false; } };
    e3.visorMalla.alMover = () => sync(e3.visorMalla, e3.visor);
    if (e3.visor) e3.visor.alMover = () => sync(e3.visor, e3.visorMalla);
  }
  const clave = `${e3.actual}/${e3.datos?.fecha}`;
  if (e3.mallaClave === clave) return e3.visorMalla.dibujar();
  e3.mallaClave = clave;
  const m = e3.datos.malla;
  $("#e3-info-malla").textContent = t("md_cargando");
  try {
    const r = await fetch(`/api/escaneo/malla?id=${encodeURIComponent(e3.actual)}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const buf = await r.arrayBuffer();
    if (clave !== e3.mallaClave) return;
    e3.visorMalla.cargarMalla(buf, e3.visor?.n ? e3.visor.centro : null);
    if (e3.visor?.n) e3.visorMalla.vista = e3.visor.vista;
    $("#e3-info-malla").textContent = t("e3_malla_info", { v: m.vertices.toLocaleString(locale()), c: m.caras.toLocaleString(locale()), d: m.voxel_mm });
  } catch (err) { e3.mallaClave = null; $("#e3-info-malla").textContent = t("error_x", { m: err.message }); }
}

// ------------------------------------------------------------------ elegir vistas
function pintarVistasE3() {
  const cont = $("#e3-vistas");
  cont.innerHTML = "";
  for (const p of est.poses.objeto || []) {
    if (!p.reconstruida) continue;
    const orden = e3.sel.indexOf(p.pose);
    const l = document.createElement("label");
    l.className = "rc-pose" + (orden >= 0 ? " sel" : "");
    l.innerHTML = `<img loading="lazy" alt=""><input type="checkbox"><span></span>`;
    $("img", l).src = `/api/imagen?cat=objeto&pose=${p.pose}&tipo=textura&ancho=160`;
    $("input", l).checked = orden >= 0;
    $("span", l).textContent = p.pose.replace("pose_", "") + (orden === 0 ? " ★" : orden > 0 ? ` (${orden + 1})` : "");
    l.title = orden === 0 ? t("e3_referencia") : "";
    $("input", l).addEventListener("change", (ev) => {
      if (ev.target.checked) e3.sel.push(p.pose); else e3.sel = e3.sel.filter((x) => x !== p.pose);
      pintarVistasE3();
    });
    cont.appendChild(l);
  }
  if (!cont.children.length) cont.innerHTML = `<p class="nota">${t("e3_sin_poses")}</p>`;
  $("#e3-unir").disabled = est.ejec.ejecutando || e3.sel.length < 2 || !$("#e3-nombre").value.trim();
  $("#e3-sel-resumen").textContent = e3.sel.length ? t("e3_sel", { n: e3.sel.length, r: e3.sel[0] }) : t("e3_elige");
}

function unirE3() {
  const nombre = $("#e3-nombre").value.trim();
  if (!nombre || e3.sel.length < 2) return;
  // mismo nombre de carpeta que rutas.etiqueta_carpeta
  e3.actual = nombre.normalize("NFKD").replace(/[^\x00-\x7f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "").slice(0, 40).replace(/-+$/, "");
  e3.esperando = true;
  ejecutar({ escaneo: { nombre, poses: e3.sel, manual: e3.manual }, etapas: {} });
}

// ------------------------------------------------------------------ resultado
function pintarResultadoE3() {
  const d = e3.datos, res = $("#e3-resultado"), tabla = $("#e3-pares tbody");
  tabla.innerHTML = "";
  $("#e3-leyenda").innerHTML = "";
  if (!d) {
    res.textContent = e3.actual ? "" : t("e3_ayuda");
    if (!e3.actual && e3.lista.length) res.textContent += " " + t("e3_otros");
    return;
  }
  res.textContent = t("e3_resumen", { u: d.unidas.length, n: d.poses.length, p: (d.puntos || 0).toLocaleString(),
                                      r: d.rms_mm != null ? fmt(d.rms_mm, 3) : "—" });
  if (d.sueltas?.length) res.textContent += " " + t("e3_sueltas", { l: d.sueltas.join(", ") });
  // leyenda de colores (en el orden de la nube)
  d.unidas.forEach((p, k) => {
    const c = COLORES_VISTA[k % COLORES_VISTA.length].map((x) => Math.round(x * 255));
    const s = document.createElement("span");
    s.innerHTML = `<i style="background:rgb(${c})"></i>${p}`;
    $("#e3-leyenda").appendChild(s);
  });
  for (const [clave, r] of Object.entries(d.pares || {})) {
    const [a, b] = clave.split("|");
    const tr = document.createElement("tr");
    tr.className = r.ok ? "" : "falla";
    const nm = (e3.manual[clave] || []).length;
    tr.innerHTML = `<td>${a.replace("pose_", "")}+${b.replace("pose_", "")}</td><td></td><td></td><td></td><td></td><td></td>`;
    const c = tr.children;
    c[1].textContent = r.ok ? "✓" : "✕";
    c[1].title = r.motivo || "";
    c[2].textContent = r.metodo === "manual" ? t("e3_manual") : t("e3_textura");
    c[3].textContent = r.rms_mm != null && isFinite(r.rms_mm) ? fmt(r.rms_mm, 3) : "—";
    c[4].textContent = r.solape != null ? `${Math.round(100 * r.solape)} %` : "—";
    const b1 = document.createElement("button");
    b1.type = "button"; b1.className = "e3-marcar";
    b1.textContent = nm ? `✎ ${nm}` : "✎";
    b1.title = nm ? t("e3_puntos_n", { n: nm }) : t("e3_marcar");
    b1.addEventListener("click", () => abrirMarcar(a, b));
    c[5].appendChild(b1);
    tabla.appendChild(tr);
  }
}

async function cargarNubeE3() {
  if (!e3.visor) {
    try { e3.visor = new VisorNube($("#e3-lienzo")); } catch (err) { $("#e3-info").textContent = err.message; return; }
    e3.visor.setColor("vista");
    e3.visor.alMover = () => { if (!e3.sinc && e3.visorMalla?.n) { e3.sinc = true; e3.visorMalla.vista = e3.visor.vista; e3.sinc = false; } };
  }
  const clave = e3.actual && e3.datos ? `${e3.actual}/${e3.datos.fecha}` : null;
  if (clave === e3.nubeClave) return e3.visor.dibujar();
  e3.nubeClave = clave;
  if (!clave) { e3.visor.vaciar(); $("#e3-info").textContent = ""; return; }
  $("#e3-info").textContent = t("md_cargando");
  try {
    const r = await fetch(`/api/escaneo/nube?id=${encodeURIComponent(e3.actual)}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const buf = await r.arrayBuffer();
    if (clave !== e3.nubeClave) return;
    const n = new DataView(buf).getUint32(0, true);
    e3.visor.cargar(buf);
    e3.visor.setEtiquetas(new Uint8Array(buf, 4 + n * 13, n));
    $("#e3-info").textContent = t("nube_mostrados", { n: n.toLocaleString(locale()) });
  } catch (err) { e3.nubeClave = null; $("#e3-info").textContent = t("error_x", { m: err.message }); }
}

// ------------------------------------------------------------------ marcar puntos en común
async function abrirMarcar(a, b) {
  const m = e3.marcar = { a, b, puntos: structuredClone(e3.manual[`${a}|${b}`] || []), pendiente: null };
  $("#e3-marcar").classList.remove("oculto");
  $("#e3-marcar-titulo").textContent = t("e3_marcar_titulo", { a, b });
  for (const [lado, pose] of [["A", a], ["B", b]]) {
    const lienzo = $(`#e3-lienzo-${lado}`);
    if (!m[`visor${lado}`]) {
      const v = new VisorNube(lienzo);
      v.sinDobleClic = true;
      v.alClic = (ev) => clicMarcar(lado, v, ev);
      v.alDibujar = () => pintarMarcas(lado, v);
      m[`visor${lado}`] = v;
    }
    const r = await fetch(`/api/nube?cat=objeto&pose=${pose}&max=800000`);
    if (e3.marcar !== m) return;
    m[`visor${lado}`].cargar(await r.arrayBuffer());
    m[`visor${lado}`].setColor("textura");
  }
  pintarListaMarcas();
  $("#e3-marcar").scrollIntoView({ block: "nearest" });
}

function clicMarcar(lado, v, ev) {
  const m = e3.marcar;
  const i = v.elegir(ev.clientX, ev.clientY);
  if (i < 0) return;
  const p = v.punto(i).map((x) => +x.toFixed(3));
  if (lado === "A") m.pendiente = p;          // primero en A…
  else if (m.pendiente) {                      // …luego el mismo lugar en B
    m.puntos.push([m.pendiente, p]);
    m.pendiente = null;
  } else return;
  pintarListaMarcas();
  m.visorA.dibujar(); m.visorB.dibujar();
}

function pintarMarcas(lado, v) {
  const m = e3.marcar, capa = $(`#e3-capa-${lado}`);
  if (!m || !v.n) return;
  const mvp = v._matriz();
  let s = "";
  const pts = m.puntos.map((par) => par[lado === "A" ? 0 : 1]);
  if (lado === "A" && m.pendiente) pts.push(m.pendiente);
  pts.forEach((p, k) => {
    const q = v.proyectar(p, mvp);
    if (!q) return;
    s += `<circle cx="${q[0]}" cy="${q[1]}" r="6" class="md-punto"/><text x="${q[0] + 8}" y="${q[1] - 7}" class="md-etq">${k + 1}</text>`;
  });
  capa.innerHTML = s;
}

function pintarListaMarcas() {
  const m = e3.marcar;
  $("#e3-marcar-estado").textContent = (m.pendiente ? t("e3_ahora_b") : t("e3_ahora_a")) + " · " + t("e3_n_pares", { n: m.puntos.length });
  $("#e3-marcar-guardar").disabled = m.puntos.length < 3;
}

function iniciarEscaneo() {
  $("#e3-lista").addEventListener("change", (ev) => elegirEscaneo(ev.target.value));
  $("#e3-nombre").addEventListener("input", pintarVistasE3);
  $("#e3-unir").addEventListener("click", unirE3);
  $("#e3-borrar").addEventListener("click", async () => {
    if (!e3.actual || !confirm(t("e3_confirmar_borrar", { n: e3.datos?.nombre || e3.actual }))) return;
    await api("/api/escaneo/borrar", { id: e3.actual });
    e3.actual = null;
    cargarEscaneo();
  });
  for (const b of $$("#e3-color button")) {
    b.addEventListener("click", () => {
      for (const x of $$("#e3-color button")) x.classList.toggle("activo", x === b);
      e3.visor?.setColor(b.dataset.color);
      // la malla no tiene «por vista»: textura o profundidad
      e3.visorMalla?.setColor(b.dataset.color === "vista" ? "textura" : b.dataset.color);
    });
  }
  for (const b of $$("#e3-fusion button")) {
    b.addEventListener("click", () => { e3.fusion = b.dataset.fusion; mostrarFusionE3(); });
  }
  $("#e3-tam").addEventListener("input", (ev) => e3.visor?.setTamano(+ev.target.value));
  $("#e3-vista-inicial").addEventListener("click", () => { e3.visor?.reiniciar(); e3.visorMalla?.reiniciar(); });
  $("#e3-marcar-deshacer").addEventListener("click", () => {
    const m = e3.marcar;
    if (m.pendiente) m.pendiente = null; else m.puntos.pop();
    pintarListaMarcas(); m.visorA.dibujar(); m.visorB.dibujar();
  });
  $("#e3-marcar-cerrar").addEventListener("click", () => { $("#e3-marcar").classList.add("oculto"); e3.marcar = null; });
  $("#e3-marcar-guardar").addEventListener("click", () => {
    const m = e3.marcar;
    e3.manual[`${m.a}|${m.b}`] = m.puntos;
    $("#e3-marcar").classList.add("oculto");
    e3.marcar = null;
    pintarResultadoE3();
    unirE3();  // se vuelve a unir con los puntos nuevos
  });
}
