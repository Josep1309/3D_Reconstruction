// Pestaña «Máscara»: por pose, qué píxeles se reconstruyen. Parte de la modulación γ de la fase
// con la que se triangula; se ajusta con un umbral, recortes/exclusiones dibujados, erosión del
// contorno, quitar islas y quedarse con la región más grande. Vista previa en vivo (rojo = lo que
// se quita) y guardado en resultados/<proceso>/fases/<cat>/pose_XX_mascara.png (mascara.py).
"use strict";

const mk = {
  clave: null, estado: null, turno: 0, temporizador: null, vista: "textura",
  p: { umbral: null, recortes: [], exclusiones: [], erosion: 0, min_isla: 0, mayor: false },
  dibujo: null,  // {tipo: "recortes"|"exclusiones", puntos: [[x, y], …]} mientras se dibuja
  guardado: "",
  orden: [],     // tipos de las zonas en el orden en que se agregaron (para «Deshacer»)  // parámetros guardados (JSON) para saber si hay cambios sin guardar
};

const MK_DEFECTO = () => ({ umbral: null, recortes: [], exclusiones: [], erosion: 0, min_isla: 0, mayor: false });

async function cargarMascara() {
  const clave = `${est.cat}/${est.pose}`;
  const info = infoPose();
  $("#mk-vacio").classList.toggle("oculto", !!info?.absoluta);
  $("#mk-cuerpo").classList.toggle("oculto", !info?.absoluta);
  if (!info?.absoluta) { mk.clave = null; return; }
  if (mk.clave === clave && mk.estado) return pintarMascara();
  mk.clave = clave;
  mk.dibujo = null;
  try { mk.estado = await api(`/api/mascara?cat=${est.cat}&pose=${est.pose}`); }
  catch (err) { $("#mk-resultado").textContent = t("error_x", { m: err.message }); return; }
  if (mk.clave !== clave) return;
  const g = mk.estado.parametros;
  mk.p = { ...MK_DEFECTO(), ...(g || {}) };
  mk.guardado = g ? JSON.stringify(soloParametros(mk.p)) : "";
  mk.orden = [...mk.p.recortes.map(() => "recortes"), ...mk.p.exclusiones.map(() => "exclusiones")];
  $("#mk-reconstruir").disabled = est.cat === "patron";
  pintarControlesMascara();
  pintarOtrasPoses();
  previaMascara();
}

const soloParametros = (p) => ({ umbral: p.umbral, recortes: p.recortes, exclusiones: p.exclusiones,
                                 erosion: p.erosion, min_isla: p.min_isla, mayor: p.mayor });

function pintarControlesMascara() {
  const e = mk.estado, p = mk.p;
  $("#mk-fase").textContent = t("mk_fase", { f: e.fase === "ambas" ? "Fx + Fy" : e.fase, u: fmt(e.umbral_actual, 3) });
  const usarUmbral = p.umbral != null;
  $("#mk-umbral-on").checked = usarUmbral;
  $("#mk-umbral").disabled = $("#mk-umbral-n").disabled = !usarUmbral;
  $("#mk-umbral").value = $("#mk-umbral-n").value = usarUmbral ? p.umbral : e.umbral_actual;
  $("#mk-erosion").value = $("#mk-erosion-n").value = p.erosion;
  $("#mk-isla").value = $("#mk-isla-n").value = p.min_isla;
  $("#mk-mayor").checked = p.mayor;
  for (const b of $$("#mk-vista button")) b.classList.toggle("activo", b.dataset.vista === mk.vista);
  pintarHistogramaGamma();
  pintarMascara();
}

// Histograma de γ de los píxeles válidos, con la línea del umbral
function pintarHistogramaGamma() {
  const e = mk.estado, cont = $("#mk-hist");
  const max = Math.max(...e.hist, 1), n = e.hist.length;
  const barras = e.hist.map((c, i) => `<rect x="${i / n}" y="${1 - Math.sqrt(c / max)}" width="${0.9 / n}" height="${Math.sqrt(c / max)}"/>`).join("");
  const u = (mk.p.umbral ?? e.umbral_actual) / e.hist_max;
  cont.innerHTML = `<svg viewBox="0 0 1 1" preserveAspectRatio="none">${barras}<line x1="${u}" x2="${u}" y1="0" y2="1" class="mk-umbral"/></svg>`;
}

function pintarMascara() {
  // Polígonos guardados y el que se está dibujando
  const capa = $("#mk-capa");
  const pts = (pol) => pol.map(([x, y]) => `${x},${y}`).join(" ");
  let s = "";
  for (const pol of mk.p.recortes) s += `<polygon points="${pts(pol)}" class="mk-recorte"/>`;
  for (const pol of mk.p.exclusiones) s += `<polygon points="${pts(pol)}" class="mk-exclusion"/>`;
  if (mk.dibujo?.puntos.length) {
    s += `<polyline points="${pts(mk.dibujo.puntos)}" class="mk-dibujo ${mk.dibujo.tipo}"/>`;
    const [x0, y0] = mk.dibujo.puntos[0];
    s += `<circle cx="${x0}" cy="${y0}" r="0.008" class="mk-inicio"/>`;
  }
  capa.innerHTML = s;
  const n = mk.p.recortes.length + mk.p.exclusiones.length;
  $("#mk-zonas").textContent = n ? t("mk_n_zonas", { r: mk.p.recortes.length, e: mk.p.exclusiones.length }) : t("mk_sin_zonas");
  $("#mk-deshacer").disabled = !n && !mk.dibujo;
  $("#mk-dibujando").classList.toggle("oculto", !mk.dibujo);
  $("#mk-lienzo").classList.toggle("dibujando", !!mk.dibujo);
  for (const b of $$("[data-dibujar]")) b.classList.toggle("activo", mk.dibujo?.tipo === b.dataset.dibujar);
  const cambios = JSON.stringify(soloParametros(mk.p)) !== mk.guardado;
  $("#mk-estado").textContent = mk.estado?.parametros ? (cambios ? t("mk_guardada_cambios") : t("mk_guardada")) : t("mk_sin_mascara");
  $("#mk-estado").classList.toggle("aviso", cambios && !!mk.estado?.parametros);
  $("#mk-borrar").disabled = !mk.estado?.parametros;
}

function pintarOtrasPoses() {
  const cont = $("#mk-otras");
  cont.innerHTML = "";
  for (const p of est.poses[est.cat] || []) {
    if (p.pose === est.pose || !p.absoluta) continue;
    const l = document.createElement("label");
    l.className = "casilla";
    l.innerHTML = `<input type="checkbox"> <span></span>`;
    $("input", l).value = p.pose;
    $("span", l).textContent = p.pose.replace("pose_", "");
    cont.appendChild(l);
  }
  $("#mk-otras-fila").classList.toggle("oculto", !cont.children.length);
}

function cambioMascara() {
  pintarMascara();
  pintarHistogramaGamma();
  clearTimeout(mk.temporizador);
  mk.temporizador = setTimeout(previaMascara, 120);
}

async function previaMascara() {
  if (!mk.estado) return;
  const turno = ++mk.turno, clave = mk.clave;
  let r;
  try {
    r = await api("/api/mascara/previa", { cat: est.cat, pose: est.pose, parametros: soloParametros(mk.p), vista: mk.vista });
  } catch (err) { $("#mk-resultado").textContent = t("error_x", { m: err.message }); return; }
  if (turno !== mk.turno || clave !== mk.clave) return;  // llegó tarde: ya se pidió otra
  $("#mk-img").src = r.imagen;
  const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
  let texto = t("mk_conserva", { c: r.conservados.toLocaleString(), v: r.validos.toLocaleString(), p: pct(r.conservados, r.validos) });
  if (r.puntos_actuales != null) {
    texto += " · " + t("mk_nube", { q: r.puntos_quedan.toLocaleString(), a: r.puntos_actuales.toLocaleString(),
                                    d: (r.puntos_actuales - r.puntos_quedan).toLocaleString() });
  }
  $("#mk-resultado").textContent = texto;
}

// ------------------------------------------------------------------ dibujo de zonas
function coordenadas(ev) {
  const r = $("#mk-img").getBoundingClientRect();
  return [Math.min(Math.max((ev.clientX - r.left) / r.width, 0), 1), Math.min(Math.max((ev.clientY - r.top) / r.height, 0), 1)];
}

function cerrarDibujo() {
  const d = mk.dibujo;
  mk.dibujo = null;
  if (d && d.puntos.length >= 3) {
    mk.p[d.tipo] = [...mk.p[d.tipo], d.puntos.map(([x, y]) => [+x.toFixed(4), +y.toFixed(4)])];
    mk.orden.push(d.tipo);
  }
  cambioMascara();
}

function clicLienzo(ev) {
  if (!mk.dibujo) return;
  const p = coordenadas(ev), d = mk.dibujo;
  if (d.puntos.length >= 3) {  // clic cerca del primer punto: cierra
    const r = $("#mk-img").getBoundingClientRect();
    const [x0, y0] = d.puntos[0];
    if (Math.hypot((p[0] - x0) * r.width, (p[1] - y0) * r.height) < 12) return cerrarDibujo();
  }
  d.puntos.push(p);
  pintarMascara();
}

function iniciarMascara() {
  const enlazar = (rango, numero, campo, entero = true) => {
    const poner = (v) => { mk.p[campo] = entero ? Math.round(+v || 0) : +v; $(rango).value = $(numero).value = mk.p[campo]; cambioMascara(); };
    $(rango).addEventListener("input", () => poner($(rango).value));
    $(numero).addEventListener("change", () => poner($(numero).value));
  };
  enlazar("#mk-erosion", "#mk-erosion-n", "erosion");
  enlazar("#mk-isla", "#mk-isla-n", "min_isla");
  enlazar("#mk-umbral", "#mk-umbral-n", "umbral", false);
  $("#mk-umbral-on").addEventListener("change", (e) => {
    mk.p.umbral = e.target.checked ? +$("#mk-umbral").value : null;
    $("#mk-umbral").disabled = $("#mk-umbral-n").disabled = !e.target.checked;
    cambioMascara();
  });
  $("#mk-mayor").addEventListener("change", (e) => { mk.p.mayor = e.target.checked; cambioMascara(); });
  for (const b of $$("#mk-vista button")) {
    b.addEventListener("click", () => { mk.vista = b.dataset.vista; pintarControlesMascara(); previaMascara(); });
  }
  for (const b of $$("[data-dibujar]")) {
    b.addEventListener("click", () => {
      if (mk.dibujo?.tipo === b.dataset.dibujar) return cerrarDibujo();
      mk.dibujo = { tipo: b.dataset.dibujar, puntos: [] };
      pintarMascara();
    });
  }
  $("#mk-lienzo").addEventListener("click", clicLienzo);
  $("#mk-lienzo").addEventListener("dblclick", (e) => { e.preventDefault(); if (mk.dibujo) { mk.dibujo.puntos.pop(); cerrarDibujo(); } });
  document.addEventListener("keydown", (e) => {
    if (est.paso !== "mascara" || !mk.dibujo) return;
    if (e.key === "Enter") cerrarDibujo();
    if (e.key === "Escape") { mk.dibujo = null; pintarMascara(); }
  });
  $("#mk-deshacer").addEventListener("click", () => {
    if (mk.dibujo) { mk.dibujo.puntos.pop(); if (!mk.dibujo.puntos.length) mk.dibujo = null; return pintarMascara(); }
    // quita la última zona agregada (de cualquiera de los dos tipos)
    const tipo = mk.orden.pop() || (mk.p.exclusiones.length ? "exclusiones" : "recortes");
    mk.p[tipo] = mk.p[tipo].slice(0, -1);
    cambioMascara();
  });
  $("#mk-sin-zonas").addEventListener("click", () => { mk.p.recortes = []; mk.p.exclusiones = []; mk.orden = []; mk.dibujo = null; cambioMascara(); });
  $("#mk-reiniciar").addEventListener("click", () => { mk.p = MK_DEFECTO(); mk.orden = []; mk.dibujo = null; pintarControlesMascara(); previaMascara(); });
  $("#mk-guardar").addEventListener("click", () => guardarMascara(false));
  $("#mk-reconstruir").addEventListener("click", () => guardarMascara(true));
  $("#mk-borrar").addEventListener("click", borrarMascara);
  $("#mk-todas").addEventListener("change", (e) => { for (const c of $$("#mk-otras input")) c.checked = e.target.checked; });
}

const otrasMarcadas = () => $$("#mk-otras input").filter((c) => c.checked).map((c) => c.value);

async function guardarMascara(reconstruir) {
  if (mk.dibujo) cerrarDibujo();
  const poses = otrasMarcadas();
  try {
    await api("/api/mascara/guardar", { cat: est.cat, pose: est.pose, parametros: soloParametros(mk.p), poses });
  } catch (err) { alert(t("error_x", { m: err.message })); return; }
  mk.estado.parametros = soloParametros(mk.p);
  mk.guardado = JSON.stringify(soloParametros(mk.p));
  pintarMascara();
  $("#mk-resultado").textContent = t("mk_guardada_en", { n: 1 + poses.length });
  if (reconstruir) reconstruirConMascara([est.pose, ...poses]);
}

async function borrarMascara() {
  const poses = otrasMarcadas();
  if (!confirm(t("mk_confirmar_borrar", { n: 1 + poses.length }))) return;
  try { await api("/api/mascara/borrar", { cat: est.cat, pose: est.pose, poses }); }
  catch (err) { alert(t("error_x", { m: err.message })); return; }
  mk.estado.parametros = null;
  mk.guardado = "";
  mk.p = MK_DEFECTO();
  mk.orden = [];
  pintarControlesMascara();
  previaMascara();
}

function reconstruirConMascara() {
  // Solo la reconstrucción de esta categoría: la caché recalcula las poses cuya máscara cambió
  ejecutar({
    etapas: { patrones: false, lightcrafter: false, captura: false, organizar: false, fase_relativa: false,
              fase_absoluta: false, calibracion: false, reconstruccion: true },
    categorias: [est.cat === "patron" ? "objeto" : est.cat],
    rehacer: false, fase: $("#a-fase").value, calibracion: $("#a-calib").value, ajustes: ajustesParaEnviar(),
  });
}
