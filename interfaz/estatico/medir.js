// Pestaña «Medición»: distancia 3D entre dos puntos cualesquiera de la nube de la pose.
// Vista principal: la nube 3D completa (se gira y se hace clic sobre los puntos, visor.elegir).
// Alternativa: marcar sobre la imagen (textura o Z), con zoom; cada píxel reconstruido tiene su
// X, Y, Z en mm. Cada punto se pide al servidor por su píxel (/api/punto) para tener el valor
// exacto y su ruido local. Las mediciones se guardan por pose (mediciones.py).
"use strict";

const md = {
  clave: null, vista: "3d", puntos: [], lista: [], seleccion: null, visor: null, nube: null,
  zoom: 1, dx: 0, dy: 0, arrastre: null, ancho: 1280, alto: 1024, turno: 0,
  rapidas: null, rapSel: null, rapTurno: 0,  // medidas rápidas (procesamiento/medidas.py) y cuál se dibuja
};

async function cargarMedir() {
  const info = infoPose(), clave = `${est.cat}/${est.pose}`;
  $("#md-vacio").classList.toggle("oculto", !!info?.reconstruida);
  $("#md-cuerpo").classList.toggle("oculto", !info?.reconstruida);
  if (!info?.reconstruida) { md.clave = null; return; }
  const v = version("reconstruida");
  if (md.clave === clave && md.version === v) return;
  if (md.clave !== clave) { md.puntos = []; md.seleccion = null; md.zoom = 1; md.dx = md.dy = 0; }
  md.clave = clave; md.version = v;
  md.rapidas = null; md.rapSel = null; md.rapTurno++;
  pintarRapidas();
  mostrarVistaMedir();
  await cargarListaMediciones();
  pintarMedir();
}

function mostrarVistaMedir() {
  const es3d = md.vista === "3d";
  $("#md-3d").classList.toggle("oculto", !es3d);
  $("#md-marco").classList.toggle("oculto", es3d);
  $(".md-zoom-ctl").classList.toggle("oculto", es3d);
  $(".md-ctl3d").classList.toggle("oculto", !es3d);
  $("#md-ayuda").textContent = t(es3d ? "md_ayuda_3d" : "md_ayuda");
  if (es3d) cargarNubeMedir(); else cargarImagenMedir();
}

// ------------------------------------------------------------------ nube 3D
async function cargarNubeMedir() {
  if (!md.visor) {
    try {
      md.visor = new VisorNube($("#md-lienzo"));
    } catch (err) { $("#md-info3d").textContent = err.message; return; }
    md.visor.sinDobleClic = true;  // dos clics seguidos son dos puntos, no «vista inicial»
    md.visor.alClic = clicNube;
    md.visor.alDibujar = pintarCapa3D;
  }
  const clave = `${md.clave}/${md.version}`;
  if (md.nube === clave) return md.visor.dibujar();
  md.nube = clave;
  $("#md-info3d").textContent = t("md_cargando");
  try {
    // la nube completa (no una muestra): se mide sobre todos los puntos
    const r = await fetch(`/api/nube?cat=${est.cat}&pose=${est.pose}&max=2000000&indices=1`);
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
    const buf = await r.arrayBuffer();
    if (md.nube !== clave) return;
    md.visor.cargar(buf, true);
    $("#md-info3d").textContent = t("md_n_puntos", { n: md.visor.n.toLocaleString(locale()) });
  } catch (err) { md.nube = null; $("#md-info3d").textContent = t("error_x", { m: err.message }); }
}

async function clicNube(ev) {
  const v = md.visor;
  const i = v.elegir(ev.clientX, ev.clientY);
  if (i < 0) { $("#md-aviso").textContent = t("md_sin_punto_3d"); return; }
  const pix = v.indices[i], [alto, ancho] = v.forma;
  const fila = Math.floor(pix / ancho), col = pix % ancho;
  if (md.puntos.length >= 2) md.puntos = [];
  md.seleccion = null;
  $("#md-aviso").textContent = "";
  // provisional (de la nube) mientras llega el punto exacto con su ruido
  const [X, Y, Z] = v.punto(i);
  const prov = { fx: col / (ancho - 1), fy: fila / (alto - 1), X, Y, Z, sigma_mm: null };
  md.puntos.push(prov);
  pintarMedir();
  try {
    const p = await api(`/api/punto?cat=${est.cat}&pose=${est.pose}&fx=${prov.fx}&fy=${prov.fy}&radio=1`);
    Object.assign(prov, p);
    pintarMedir();
  } catch { /* se queda el valor de la nube, que es el mismo punto */ }
}

function pintarCapa3D() {
  const v = md.visor, capa = $("#md-capa3d");
  if (!v?.n || md.vista !== "3d") { if (capa) capa.innerHTML = ""; return; }
  const mvp = v._matriz();
  const pr = (p) => v.proyectar([p.X, p.Y, p.Z], mvp);
  let s = "";
  for (const m of md.lista) {
    if (m.id === md.seleccion) continue;
    const a = pr(m.a), b = pr(m.b);
    if (a && b) s += `<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" class="md-linea guardada"/>`;
  }
  const act = medicionActual();
  const pts = act ? [act.a, act.b] : md.puntos;
  const sp = pts.map(pr);
  if (sp.length === 2 && sp[0] && sp[1]) {
    s += `<line x1="${sp[0][0]}" y1="${sp[0][1]}" x2="${sp[1][0]}" y2="${sp[1][1]}" class="md-linea"/>`;
    s += `<text x="${(sp[0][0] + sp[1][0]) / 2 + 8}" y="${(sp[0][1] + sp[1][1]) / 2 - 8}" class="md-cota">${fmt(dist3(pts[0], pts[1]), 2)} mm</text>`;
  }
  sp.forEach((q, k) => {
    if (!q) return;
    s += `<circle cx="${q[0]}" cy="${q[1]}" r="6" class="md-punto"/>`;
    s += `<text x="${q[0] + 9}" y="${q[1] - 8}" class="md-etq">${"AB"[k]}</text>`;
  });
  capa.innerHTML = s + capaRapidas3D(pr);
}

// Lo que se dibuja de la medida rápida elegida: caja (12 aristas y sus tres medidas), esfera
// (contorno aproximado en pantalla) o el segmento de la distancia máxima.
function capaRapidas3D(pr) {
  const r = md.rapidas, sel = md.rapSel;
  if (!r || !sel) return "";
  const P = (x) => pr({ X: x[0], Y: x[1], Z: x[2] });
  const linea = (a, b, cls) => (a && b ? `<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" class="${cls}"/>` : "");
  const texto = (q, txt) => (q ? `<text x="${q[0] + 6}" y="${q[1] - 6}" class="md-cota mr-cota">${txt}</text>` : "");
  if (sel === "dmax") {
    const { a, b, distancia_mm } = r.distancia_maxima, pa = pr(a), pb = pr(b);
    let s = linea(pa, pb, "mr-linea");
    for (const q of [pa, pb]) if (q) s += `<circle cx="${q[0]}" cy="${q[1]}" r="5" class="mr-punto"/>`;
    return s + texto(pa && pb && [(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2], `${fmt(distancia_mm, 2)} mm`);
  }
  if (sel === "esfera" && r.esfera) {
    const c = r.esfera.centro, rad = r.esfera.diametro_mm / 2, [der, arr] = md.visor.ejesPantalla();
    const pc = P(c);
    if (!pc) return "";
    let s = "", pts = [];
    for (let k = 0; k <= 48; k++) {
      const a = (k / 48) * 2 * Math.PI, q = P(c.map((v, i) => v + rad * (Math.cos(a) * der[i] + Math.sin(a) * arr[i])));
      if (q) pts.push(q.join(","));
    }
    s += `<polyline points="${pts.join(" ")}" class="mr-linea"/>`;
    s += `<circle cx="${pc[0]}" cy="${pc[1]}" r="4" class="mr-punto"/>`;
    return s + texto(pc, `Ø ${fmt(r.esfera.diametro_mm, 2)} mm`);
  }
  const caja = sel === "orientada" ? r.caja_orientada : sel === "camara" ? r.caja_camara : null;
  if (!caja) return "";
  const { centro, ejes, medidas_mm: m } = caja;
  const esquina = (k) => P(centro.map((v, i) => v + [0, 1, 2].reduce((acc, e) => acc + ((k >> e) & 1 ? 0.5 : -0.5) * m[e] * ejes[e][i], 0)));
  const esq = [...Array(8).keys()].map(esquina);
  let s = "";
  for (let k = 0; k < 8; k++) for (const e of [0, 1, 2]) if (!((k >> e) & 1)) s += linea(esq[k], esq[k | (1 << e)], "mr-linea");
  // las tres medidas, en las aristas que salen de la esquina 0
  const nombres = sel === "camara" ? ["X", "Y", "Z"] : [t("mr_largo"), t("mr_ancho"), t("mr_espesor")];
  for (const e of [0, 1, 2]) {
    const a = esq[0], b = esq[1 << e];
    if (a && b) s += texto([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], `${nombres[e]} ${fmt(m[e], 1)}`);
  }
  return s;
}

// ------------------------------------------------------------------ medidas rápidas
async function calcularRapidas() {
  const turno = ++md.rapTurno;
  const recorte = $("#mr-recorte").value, principal = $("#mr-principal").checked ? 1 : 0;
  $("#mr-estado").textContent = t("mr_calculando");
  $("#mr-calcular").disabled = true;
  try {
    const r = await api(`/api/medidas_rapidas?cat=${est.cat}&pose=${est.pose}&recorte=${recorte}&principal=${principal}`);
    if (turno !== md.rapTurno) return;
    md.rapidas = r;
    md.rapSel = md.rapSel || "dmax";
  } catch (err) {
    if (turno !== md.rapTurno) return;
    md.rapidas = null;
    $("#mr-estado").textContent = t("error_x", { m: err.message });
  } finally { if (turno === md.rapTurno) $("#mr-calcular").disabled = false; }
  pintarRapidas();
  pintarMedir();
}

function pintarRapidas() {
  const r = md.rapidas, tabla = $("#mr-tabla");
  tabla.classList.toggle("oculto", !r);
  if (!r) { if (!$("#mr-calcular").disabled) $("#mr-estado").textContent = t("mr_ayuda"); return; }
  $("#mr-estado").textContent = t("mr_puntos", { n: r.puntos.toLocaleString(locale()), total: r.puntos_validos.toLocaleString(locale()) });
  const x = (m) => m.map((v) => fmt(v, 1)).join(" × ");
  const filas = [
    ["dmax", t("mr_dmax"), `${fmt(r.distancia_maxima.distancia_mm, 2)} mm`, t("mr_dmax_t")],
    ["orientada", t("mr_orientada"), `${x(r.caja_orientada.medidas_mm)} mm`, t("mr_orientada_t")],
    ["camara", t("mr_camara"), `${x(r.caja_camara.medidas_mm)} mm`, t("mr_camara_t")],
  ];
  if (r.esfera) filas.push(["esfera", t("mr_esfera"), `Ø ${fmt(r.esfera.diametro_mm, 2)} mm · RMS ${fmt(r.esfera.rms_mm, 2)}`, t("mr_esfera_t")]);
  const tb = $("tbody", tabla);
  tb.innerHTML = "";
  for (const [id, nombre, valor, ayuda] of filas) {
    const tr = document.createElement("tr");
    tr.className = id === md.rapSel ? "sel" : "";
    tr.title = ayuda;
    tr.innerHTML = "<th></th><td></td><td></td>";
    $("th", tr).textContent = nombre;
    $("td", tr).textContent = valor;
    if (id === "dmax") {  // se puede guardar como una medición normal (dos puntos reales)
      const b = document.createElement("button");
      b.type = "button"; b.className = "enlace"; b.textContent = t("mr_usar"); b.title = t("mr_usar_t");
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        const { a, b: pb } = r.distancia_maxima;
        md.seleccion = null;
        md.puntos = [{ ...a, sigma_mm: null }, { ...pb, sigma_mm: null }];
        $("#md-nombre").value = t("mr_dmax");
        pintarMedir();
      });
      tr.lastElementChild.append(b);
    }
    tr.addEventListener("click", () => { md.rapSel = md.rapSel === id ? null : id; pintarRapidas(); pintarMedir(); });
    tb.append(tr);
  }
}

function cargarImagenMedir() {
  const img = $("#md-img");
  img.onload = () => { md.ancho = img.naturalWidth; md.alto = img.naturalHeight; aplicarVistaMedir(); pintarMedir(); };
  img.src = `/api/imagen?cat=${est.cat}&pose=${est.pose}&tipo=${md.vista}&ancho=1280&v=${version("reconstruida")}`;
}

async function cargarListaMediciones() {
  try { md.lista = (await api(`/api/mediciones?cat=${est.cat}&pose=${est.pose}`)).mediciones; }
  catch { md.lista = []; }
}

// ------------------------------------------------------------------ zoom y desplazamiento
function aplicarVistaMedir() {
  $("#md-mundo").style.transform = `translate(${md.dx}px, ${md.dy}px) scale(${md.zoom})`;
  $("#md-zoom").textContent = `${Math.round(md.zoom * 100)} %`;
  pintarCapaMedir();
}

function zoomMedir(factor, cx, cy) {
  const marco = $("#md-marco").getBoundingClientRect();
  const x = cx - marco.left, y = cy - marco.top;  // punto bajo el cursor: queda fijo
  const nuevo = Math.min(Math.max(md.zoom * factor, 1), 24);
  md.dx = x - ((x - md.dx) * nuevo) / md.zoom;
  md.dy = y - ((y - md.dy) * nuevo) / md.zoom;
  md.zoom = nuevo;
  limitarVistaMedir();
  aplicarVistaMedir();
}

function limitarVistaMedir() {
  const m = $("#md-marco");
  const w = m.clientWidth, h = m.clientHeight;
  md.dx = Math.min(0, Math.max(md.dx, w - w * md.zoom));
  md.dy = Math.min(0, Math.max(md.dy, h - h * md.zoom));
  if (md.zoom === 1) md.dx = md.dy = 0;
}

// ------------------------------------------------------------------ puntos
async function clicMedir(ev) {
  const r = $("#md-img").getBoundingClientRect();
  const fx = (ev.clientX - r.left) / r.width, fy = (ev.clientY - r.top) / r.height;
  if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return;
  if (md.puntos.length >= 2) md.puntos = [];
  md.seleccion = null;
  const turno = ++md.turno;
  let p;
  // radio de búsqueda en px de la imagen original: unos 12 px de pantalla
  const radio = Math.max(2, Math.round((12 / r.width) * md.ancho));
  try { p = await api(`/api/punto?cat=${est.cat}&pose=${est.pose}&fx=${fx}&fy=${fy}&radio=${radio}`); }
  catch (err) { $("#md-aviso").textContent = t("md_sin_punto"); return; }
  if (turno !== md.turno) return;
  $("#md-aviso").textContent = p.ajustado_px > 1.5 ? t("md_ajustado", { n: p.ajustado_px.toFixed(0) }) : "";
  md.puntos.push(p);
  pintarMedir();
}

const dist3 = (a, b) => Math.hypot(a.X - b.X, a.Y - b.Y, a.Z - b.Z);

function medicionActual() {
  if (md.seleccion) return md.lista.find((m) => m.id === md.seleccion) || null;
  if (md.puntos.length < 2) return null;
  const [a, b] = md.puntos;
  return { a, b, distancia_mm: dist3(a, b) };
}

function pintarCapaMedir() {
  const capa = $("#md-capa");
  capa.setAttribute("viewBox", `0 0 ${md.ancho} ${md.alto}`);
  const esc = md.ancho / ($("#md-img").getBoundingClientRect().width || md.ancho);  // px de imagen por px de pantalla
  const r = 6 * esc, ancho = 2 * esc;
  const px = (p) => [p.fx * (md.ancho - 1), p.fy * (md.alto - 1)];
  let s = "";
  // mediciones guardadas (tenues) y la actual (resaltada)
  for (const m of md.lista) {
    if (m.id === md.seleccion) continue;
    const [ax, ay] = px(m.a), [bx, by] = px(m.b);
    s += `<line x1="${ax}" y1="${ay}" x2="${bx}" y2="${by}" class="md-linea guardada" stroke-width="${ancho}"/>`;
  }
  const act = medicionActual();
  const pts = act ? [act.a, act.b] : md.puntos;
  if (pts.length === 2) {
    const [ax, ay] = px(pts[0]), [bx, by] = px(pts[1]);
    s += `<line x1="${ax}" y1="${ay}" x2="${bx}" y2="${by}" class="md-linea" stroke-width="${ancho}"/>`;
  }
  if (md.rapidas && md.rapSel === "dmax") {
    const [ax, ay] = px(md.rapidas.distancia_maxima.a), [bx, by] = px(md.rapidas.distancia_maxima.b);
    s += `<line x1="${ax}" y1="${ay}" x2="${bx}" y2="${by}" class="mr-linea" stroke-width="${ancho}"/>`;
  }
  pts.forEach((p, i) => {
    const [x, y] = px(p);
    s += `<circle cx="${x}" cy="${y}" r="${r}" class="md-punto" stroke-width="${ancho}"/>`;
    s += `<text x="${x + r * 1.4}" y="${y - r * 1.2}" font-size="${14 * esc}" class="md-etq">${"AB"[i]}</text>`;
  });
  capa.innerHTML = s;
}

function pintarMedir() {
  if (md.vista === "3d") pintarCapa3D(); else pintarCapaMedir();
  const act = medicionActual();
  const fila = (etq, p) => p ? `<tr><th>${etq}</th><td>${fmt(p.X, 2)}</td><td>${fmt(p.Y, 2)}</td><td>${fmt(p.Z, 2)}</td><td>${p.sigma_mm != null ? "±" + fmt(p.sigma_mm, 3) : "—"}</td></tr>` : "";
  const [a, b] = act ? [act.a, act.b] : md.puntos;
  $("#md-tabla tbody").innerHTML = fila("A", a) + fila("B", b);
  $("#md-tabla").classList.toggle("oculto", !a);
  if (act) {
    const { a: pa, b: pb } = act;
    const sig = pa.sigma_mm != null && pb.sigma_mm != null ? Math.hypot(pa.sigma_mm, pb.sigma_mm) : null;
    $("#md-distancia").innerHTML = "";
    $("#md-distancia").append(`${fmt(act.distancia_mm, 3)} mm`);
    if (sig != null) { const s = document.createElement("small"); s.textContent = ` ± ${fmt(sig, 3)}`; $("#md-distancia").append(s); }
    $("#md-deltas").textContent = `ΔX ${fmt(pb.X - pa.X, 2)} · ΔY ${fmt(pb.Y - pa.Y, 2)} · ΔZ ${fmt(pb.Z - pa.Z, 2)} mm`;
  } else {
    $("#md-distancia").textContent = "—";
    $("#md-deltas").textContent = md.puntos.length ? t("md_falta_b") : t("md_marca_a");
  }
  $("#md-guardar").disabled = !(md.puntos.length === 2 && !md.seleccion);
  pintarListaMediciones();
}

function pintarListaMediciones() {
  const cont = $("#md-lista");
  cont.innerHTML = "";
  const viejas = md.lista.filter((m) => m.desactualizada).length;
  $("#md-actualizar").classList.toggle("oculto", !viejas);
  $("#md-csv").classList.toggle("oculto", !md.lista.length);
  if (!md.lista.length) { cont.innerHTML = `<p class="nota">${t("md_sin_guardadas")}</p>`; return; }
  for (const m of md.lista) {
    const li = document.createElement("div");
    li.className = "md-item" + (m.id === md.seleccion ? " sel" : "") + (m.desactualizada ? " vieja" : "");
    li.innerHTML = `<button type="button" class="md-ver"><b></b><span></span></button><button type="button" class="md-x">×</button>`;
    $("b", li).textContent = m.nombre || t("md_sin_nombre");
    $("span", li).textContent = `${fmt(m.distancia_mm, 3)} mm` + (m.desactualizada ? " ⚠" : "");
    li.title = m.desactualizada ? t("md_desactualizada") : fechaHora(m.fecha);
    $(".md-x", li).setAttribute("aria-label", t("md_borrar"));
    $(".md-ver", li).addEventListener("click", () => { md.seleccion = md.seleccion === m.id ? null : m.id; md.puntos = []; pintarMedir(); });
    $(".md-x", li).addEventListener("click", async () => {
      if (!confirm(t("md_confirmar_borrar", { n: m.nombre || fmt(m.distancia_mm, 2) + " mm" }))) return;
      md.lista = (await api("/api/mediciones/borrar", { cat: est.cat, pose: est.pose, id: m.id })).mediciones;
      if (md.seleccion === m.id) md.seleccion = null;
      pintarMedir();
    });
    cont.appendChild(li);
  }
}

async function guardarMedicionActual() {
  if (md.puntos.length !== 2) return;
  const [a, b] = md.puntos;
  try {
    md.lista = (await api("/api/mediciones/guardar", { cat: est.cat, pose: est.pose,
      medicion: { nombre: $("#md-nombre").value, a, b } })).mediciones;
  } catch (err) { alert(t("error_x", { m: err.message })); return; }
  $("#md-nombre").value = "";
  md.puntos = [];
  md.seleccion = md.lista[md.lista.length - 1]?.id ?? null;
  pintarMedir();
}

function exportarMediciones() {
  const cab = "pose,nombre,distancia_mm,Ax,Ay,Az,Bx,By,Bz,dX,dY,dZ,sigmaA_mm,sigmaB_mm,fecha";
  const n = (x) => (x == null ? "" : Number(x).toFixed(4));
  const filas = md.lista.map((m) => [est.pose, `"${(m.nombre || "").replace(/"/g, '""')}"`, n(m.distancia_mm),
    n(m.a.X), n(m.a.Y), n(m.a.Z), n(m.b.X), n(m.b.Y), n(m.b.Z), n(m.b.X - m.a.X), n(m.b.Y - m.a.Y), n(m.b.Z - m.a.Z),
    n(m.a.sigma_mm), n(m.b.sigma_mm), m.fecha].join(","));
  const blob = new Blob([[cab, ...filas].join("\n") + "\n"], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `mediciones_${est.cat}_${est.pose}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function iniciarMedir() {
  const marco = $("#md-marco");
  marco.addEventListener("wheel", (e) => { e.preventDefault(); zoomMedir(e.deltaY < 0 ? 1.25 : 0.8, e.clientX, e.clientY); }, { passive: false });
  marco.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    md.arrastre = { x: e.clientX, y: e.clientY, dx: md.dx, dy: md.dy, movido: false };
    marco.setPointerCapture(e.pointerId);
  });
  marco.addEventListener("pointermove", (e) => {
    const a = md.arrastre;
    if (!a) return;
    if (Math.hypot(e.clientX - a.x, e.clientY - a.y) > 4) a.movido = true;
    if (a.movido && md.zoom > 1) {
      md.dx = a.dx + e.clientX - a.x; md.dy = a.dy + e.clientY - a.y;
      limitarVistaMedir(); aplicarVistaMedir();
      marco.classList.add("arrastrando");
    }
  });
  marco.addEventListener("pointerup", (e) => {
    const a = md.arrastre;
    md.arrastre = null;
    marco.classList.remove("arrastrando");
    if (a && !a.movido) clicMedir(e);
  });
  $("#md-mas").addEventListener("click", () => { const r = marco.getBoundingClientRect(); zoomMedir(1.5, r.left + r.width / 2, r.top + r.height / 2); });
  $("#md-menos").addEventListener("click", () => { const r = marco.getBoundingClientRect(); zoomMedir(1 / 1.5, r.left + r.width / 2, r.top + r.height / 2); });
  $("#md-ajustar").addEventListener("click", () => { md.zoom = 1; md.dx = md.dy = 0; aplicarVistaMedir(); });
  $("#md-limpiar").addEventListener("click", () => {
    md.puntos = []; md.seleccion = null; $("#md-aviso").textContent = "";
    // también las medidas rápidas (y un cálculo en curso, que ya no se mostrará)
    md.rapidas = null; md.rapSel = null; md.rapTurno++; $("#mr-calcular").disabled = false;
    pintarRapidas();
    pintarMedir();
  });
  $("#md-guardar").addEventListener("click", guardarMedicionActual);
  $("#md-nombre").addEventListener("keydown", (e) => { if (e.key === "Enter") guardarMedicionActual(); });
  $("#md-csv").addEventListener("click", exportarMediciones);
  $("#md-actualizar").addEventListener("click", async () => {
    const r = await api("/api/mediciones/actualizar", { cat: est.cat, pose: est.pose });
    md.lista = r.mediciones;
    if (r.fallidas?.length) alert(t("md_fallidas", { l: r.fallidas.join(", ") }));
    pintarMedir();
  });
  for (const b of $$("#md-vista button")) {
    b.addEventListener("click", () => {
      md.vista = b.dataset.vista;
      for (const x of $$("#md-vista button")) x.classList.toggle("activo", x === b);
      mostrarVistaMedir();
      pintarMedir();
    });
  }
  window.addEventListener("resize", () => { if (est.paso === "medir" && md.vista !== "3d") { limitarVistaMedir(); aplicarVistaMedir(); } });
  for (const b of $$("#md-color button")) {
    b.addEventListener("click", () => {
      for (const x of $$("#md-color button")) x.classList.toggle("activo", x === b);
      md.visor?.setColor(b.dataset.color);
    });
  }
  $("#md-tam").addEventListener("input", (e) => md.visor?.setTamano(+e.target.value));
  $("#md-vista-inicial").addEventListener("click", () => md.visor?.reiniciar());
  enlazarVistas($("#md-vistas"), () => md.visor);
  $("#mr-calcular").addEventListener("click", calcularRapidas);
  for (const id of ["#mr-recorte", "#mr-principal"]) $(id).addEventListener("change", () => { if (md.rapidas) calcularRapidas(); });
  pintarRapidas();
  for (const b of $$("[data-manual]")) b.addEventListener("click", () => abrirManual(b.dataset.manual));
}
