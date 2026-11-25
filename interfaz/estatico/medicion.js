// Pestaña «Profundidad»: medir sobre el mapa Z (punto, distancia, perfil), histograma del error de
// los planos y descargas (.ply, .csv, calibración). Coordenadas en la imagen normalizadas a [0, 1].
"use strict";

const me = { clave: null, modo: "punto", puntos: [], perfil: null };

function figuraZ() { return $('.panel[data-panel="profundidad"] figure[data-tipo="Z"]'); }

function capaZ() {
  const fig = figuraZ(), img = $("img", fig);
  if (!img) return null;
  let capa = $("svg.me-capa", fig);
  if (!capa) {
    capa = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    capa.setAttribute("class", "me-capa");
    capa.setAttribute("viewBox", "0 0 1 1");
    capa.setAttribute("preserveAspectRatio", "none");
    fig.appendChild(capa);
  }
  capa.style.left = img.offsetLeft + "px"; capa.style.top = img.offsetTop + "px";
  capa.style.width = img.clientWidth + "px"; capa.style.height = img.clientHeight + "px";
  return capa;
}

function dibujarCapa() {
  const capa = capaZ();
  if (!capa) return;
  let s = "";
  if (me.perfil) s += `<line x1="${me.perfil.a[0]}" y1="${me.perfil.a[1]}" x2="${me.perfil.b[0]}" y2="${me.perfil.b[1]}" class="me-linea"/>`;
  if (me.puntos.length === 2) s += `<line x1="${me.puntos[0].fx}" y1="${me.puntos[0].fy}" x2="${me.puntos[1].fx}" y2="${me.puntos[1].fy}" class="me-linea dist"/>`;
  me.puntos.forEach((p, i) => { s += `<circle cx="${p.fx}" cy="${p.fy}" r="0.008" class="me-punto"/><text x="${p.fx + 0.012}" y="${p.fy - 0.012}" class="me-txt">${i + 1}</text>`; });
  if (me.pendiente) s += `<circle cx="${me.pendiente[0]}" cy="${me.pendiente[1]}" r="0.008" class="me-punto pend"/>`;
  capa.innerHTML = s;
}

async function alClicZ(e) {
  if (e.target.tagName !== "IMG") return;
  e.stopImmediatePropagation();  // el clic mide (ampliar: botón «Ampliar»)
  const r = e.target.getBoundingClientRect();
  const fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
  const base = `cat=${est.cat}&pose=${est.pose}`;
  try {
    if (me.modo === "perfil") {
      if (!me.pendiente) { me.pendiente = [fx, fy]; me.perfil = null; dibujarCapa(); return; }
      const a = me.pendiente; me.pendiente = null;
      const datos = await api(`/api/perfil?${base}&ax=${a[0]}&ay=${a[1]}&bx=${fx}&by=${fy}`);
      me.perfil = { a, b: [fx, fy], ...datos };
      pintarPerfil();
    } else {
      const p = await api(`/api/punto?${base}&fx=${fx}&fy=${fy}`);
      me.puntos = me.puntos.length >= 2 ? [p] : [...me.puntos, p];
      pintarPuntos();
    }
  } catch (err) { $("#me-estado").textContent = t("error_x", { m: err.message }); }
  dibujarCapa();
}

function pintarPuntos() {
  const cont = $("#me-puntos");
  cont.innerHTML = "";
  me.puntos.forEach((p, i) => {
    const d = document.createElement("div");
    d.className = "me-fila";
    d.textContent = `${i + 1}:  X ${p.X.toFixed(2)}  ·  Y ${p.Y.toFixed(2)}  ·  Z ${p.Z.toFixed(2)} mm   (${t("me_pixel", { c: p.col, f: p.fila })})`;
    cont.appendChild(d);
  });
  if (me.puntos.length === 2) {
    const [a, b] = me.puntos;
    const d3 = Math.hypot(a.X - b.X, a.Y - b.Y, a.Z - b.Z), dz = b.Z - a.Z;
    const d = document.createElement("div");
    d.className = "me-fila me-dist";
    d.textContent = t("me_distancia", { d: d3.toFixed(2), dz: dz.toFixed(2), dxy: Math.hypot(a.X - b.X, a.Y - b.Y).toFixed(2) });
    cont.appendChild(d);
  }
  $("#me-estado").textContent = me.puntos.length === 1 ? t("me_otro_punto") : "";
}

function graficoLineas(xs, ys, etX, etY) {
  const W = 640, H = 200, iz = 52, ab = 30, ar = 10, de = 10;
  const validos = ys.map((y, i) => [xs[i], y]).filter(([, y]) => y != null);
  if (validos.length < 2) return `<p class="nota">${t("me_sin_datos")}</p>`;
  const xmin = xs[0], xmax = xs.at(-1) || 1;
  let ymin = Math.min(...validos.map((v) => v[1])), ymax = Math.max(...validos.map((v) => v[1]));
  if (ymax - ymin < 0.5) { ymin -= 0.25; ymax += 0.25; }
  const X = (x) => iz + (x - xmin) / (xmax - xmin || 1) * (W - iz - de);
  const Y = (y) => ar + (ymax - y) / (ymax - ymin) * (H - ar - ab);
  let tramo = "", d = "";
  ys.forEach((y, i) => { if (y == null) { d += tramo; tramo = ""; return; } tramo += `${tramo ? "L" : "M"}${X(xs[i]).toFixed(1)},${Y(y).toFixed(1)}`; });
  d += tramo;
  return `<svg viewBox="0 0 ${W} ${H}" class="me-grafico" role="img">
    <line class="eje" x1="${iz}" y1="${H - ab}" x2="${W - de}" y2="${H - ab}"/><line class="eje" x1="${iz}" y1="${ar}" x2="${iz}" y2="${H - ab}"/>
    <text x="${iz - 6}" y="${ar + 8}" text-anchor="end">${ymax.toFixed(1)}</text><text x="${iz - 6}" y="${H - ab}" text-anchor="end">${ymin.toFixed(1)}</text>
    <text x="${iz}" y="${H - 10}">0</text><text x="${W - de}" y="${H - 10}" text-anchor="end">${xmax.toFixed(1)} ${etX}</text>
    <text x="10" y="${(H - ab) / 2}" transform="rotate(-90 10 ${(H - ab) / 2})" text-anchor="middle">${etY}</text>
    <path d="${d}" class="me-curva"/></svg>`;
}

function pintarPerfil() {
  const cont = $("#me-perfil");
  if (!me.perfil) { cont.innerHTML = ""; return; }
  const z = me.perfil.z_mm.filter((v) => v != null);
  cont.innerHTML = `<h4>${t("me_perfil_titulo", { n: z.length })}</h4>` + graficoLineas(me.perfil.s_mm, me.perfil.z_mm, "mm", "Z (mm)") +
    (z.length ? `<p class="nota">${t("me_perfil_stats", { min: Math.min(...z).toFixed(2), max: Math.max(...z).toFixed(2), r: (Math.max(...z) - Math.min(...z)).toFixed(2) })}</p>` : "");
}

async function pintarHistograma() {
  const cont = $("#me-hist");
  cont.innerHTML = "";
  if (est.cat !== "plano" || !infoPose()?.reconstruida) return;
  let h;
  try { h = await api(`/api/histograma?cat=${est.cat}&pose=${est.pose}`); } catch (_) { return; }
  const W = 640, H = 170, ab = 26, max = Math.max(...h.cuentas, 1), n = h.cuentas.length, bw = (W - 20) / n;
  let barras = "";
  h.cuentas.forEach((c, i) => { const alto = (H - ab - 6) * c / max; barras += `<rect x="${10 + i * bw}" y="${H - ab - alto}" width="${Math.max(bw - 1, 1)}" height="${alto}" class="me-barra"/>`; });
  cont.innerHTML = `<h4>${t("me_hist_titulo")}</h4><svg viewBox="0 0 ${W} ${H}" class="me-grafico">${barras}
    <line class="eje" x1="10" y1="${H - ab}" x2="${W - 10}" y2="${H - ab}"/>
    <text x="10" y="${H - 8}">${h.bordes[0].toFixed(2)}</text><text x="${W / 2}" y="${H - 8}" text-anchor="middle">0</text>
    <text x="${W - 10}" y="${H - 8}" text-anchor="end">${h.bordes.at(-1).toFixed(2)} mm</text></svg>
    <p class="nota">${t("me_hist_stats", { rms: h.rms.toFixed(3), p95: h.p95.toFixed(3), max: h.max.toFixed(3), n: h.n.toLocaleString(locale()) })}</p>`;
}

function reiniciarMedicion() {
  me.puntos = []; me.perfil = null; me.pendiente = null;
  pintarPuntos(); pintarPerfil(); dibujarCapa();
}

// ------------------------------------------------------------------ comparar
async function cargarComparar() {
  const sel = $("#cmp-ref"), previa = sel.value;
  let copias = [];
  try { copias = await api(`/api/comparaciones?cat=${est.cat}`); } catch (_) { /* sin copias */ }
  const opciones = [`<option value="">${escHTML(t("cmp_elegir"))}</option>`];
  for (const c of copias.filter((c) => c.pose === est.pose)) {
    opciones.push(`<option value="copia:${c.id}">${escHTML(t("cmp_copia", { f: fechaCorta(c.fecha), a: c.calculada_con || "" }))}</option>`);
  }
  for (const p of (est.poses[est.cat] || []).filter((p) => p.reconstruida && p.pose !== est.pose)) {
    opciones.push(`<option value="pose:${p.pose}">${escHTML(t("cmp_otra_pose", { p: p.pose + (p.nota ? " · " + p.nota : "") }))}</option>`);
  }
  sel.innerHTML = opciones.join("");
  if ([...sel.options].some((o) => o.value === previa)) sel.value = previa;
  await pintarComparacion();
}

async function pintarComparacion() {
  const ref = $("#cmp-ref").value, fig = $("#cmp-fig"), stats = $("#cmp-stats");
  $("img", fig)?.remove();
  stats.innerHTML = ""; $("#cmp-escala").textContent = "";
  if (!ref) { stats.textContent = t("cmp_ayuda"); return; }
  try {
    const r = await fetch(`/api/imagen?cat=${est.cat}&pose=${est.pose}&tipo=${encodeURIComponent("dif:" + ref)}&ancho=1000`);
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
    const img = document.createElement("img");
    img.src = URL.createObjectURL(await r.blob());
    img.addEventListener("click", () => fig.classList.toggle("ampliada"));
    fig.prepend(img);
    $("#cmp-escala").textContent = traducirEscala(decodeURIComponent(r.headers.get("X-Escala") || ""));
    const s = await api(`/api/comparar?cat=${est.cat}&pose=${est.pose}&ref=${encodeURIComponent(ref)}`);
    const filas = [
      t("cmp_puntos", { a: s.puntos_actual.toLocaleString(locale()), b: s.puntos_ref.toLocaleString(locale()), c: s.comunes.toLocaleString(locale()) }),
      t("cmp_solo", { a: s.solo_actual.toLocaleString(locale()), b: s.solo_ref.toLocaleString(locale()) }),
    ];
    if (s.rms != null) filas.push(t("cmp_dif_stats", { m: s.media.toFixed(3), rms: s.rms.toFixed(3), p95: s.p95.toFixed(3), max: s.max.toFixed(2) }));
    for (const f of filas) { const d = document.createElement("div"); d.className = "me-fila"; d.textContent = f; stats.appendChild(d); }
  } catch (err) { stats.textContent = t("error_x", { m: err.message }); }
}

// Al mostrar la pestaña o cambiar de pose
function cargarMedicion() {
  const clave = `${est.cat}/${est.pose}/${version("reconstruida")}`;
  const hay = !!infoPose()?.reconstruida;
  $("#medicion").classList.toggle("oculto", !hay);
  $("#comparar").classList.toggle("oculto", !hay);
  for (const id of ["#me-ply", "#me-csv"]) $(id).href = `/api/descargar?tipo=${id === "#me-ply" ? "ply" : "csv"}&cat=${est.cat}&pose=${est.pose}`;
  if (me.clave !== clave) { me.clave = clave; reiniciarMedicion(); pintarHistograma(); if (hay) cargarComparar(); }
  setTimeout(dibujarCapa, 300);  // cuando la imagen ya tiene tamaño
}

function iniciarMedicion() {
  figuraZ().addEventListener("click", alClicZ, true);
  for (const b of $$("#me-modo button")) b.addEventListener("click", () => {
    me.modo = b.dataset.modo;
    $$("#me-modo button").forEach((x) => x.classList.toggle("activo", x === b));
    me.pendiente = null;
    $("#me-estado").textContent = t(me.modo === "perfil" ? "me_ayuda_perfil" : "me_ayuda_punto");
    dibujarCapa();
  });
  $("#me-limpiar").addEventListener("click", reiniciarMedicion);
  $("#me-ampliar").addEventListener("click", () => { figuraZ().classList.toggle("ampliada"); setTimeout(dibujarCapa, 50); });
  $("#me-calib").href = "/api/descargar?tipo=calibracion";
  $("#cmp-ref").addEventListener("change", pintarComparacion);
  $("#cmp-guardar").addEventListener("click", async () => {
    try {
      const c = await api("/api/comparacion/guardar", { cat: est.cat, pose: est.pose });
      agregarLog(`[OK] ${t("cmp_guardada", { p: est.pose })}`);
      await cargarComparar();
      $("#cmp-ref").value = `copia:${c.id}`;
      pintarComparacion();
    } catch (err) { agregarLog(`[ERROR] ${err.message}`); }
  });
  window.addEventListener("resize", dibujarCapa);
}
