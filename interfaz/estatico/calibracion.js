// Pestaña «Calibración»: errores de reproyección de cada pose del tablero (GET /api/calibracion).
// Usa las utilidades globales de app.js ($, api, est, fmt) y t() de i18n.js.
"use strict";

const ec = { datos: null, clave: null, sel: null, error: null, lista: [], turno: 0 };

const escHTML = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const mediana = (v) => { if (!v.length) return 0; const s = [...v].sort((a, b) => a - b), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
// Redondeo «bonito» hacia arriba: 1, 2, 2.5, 5 × 10^k
function redondeoBonito(x) {
  const p = 10 ** Math.floor(Math.log10(x)), f = x / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
}
const fechaCorta = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString(locale(), { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
};

// Una pose es «incoherente» si su error estéreo supera 3 veces la mediana de las usadas (mín. 2 px)
function umbralIncoherente(d) {
  const usadas = d.poses.filter((p) => p.usada).map((p) => p.estereo_px);
  return Math.max(3 * mediana(usadas.length ? usadas : d.poses.map((p) => p.estereo_px)), 2);
}
// Calibración mezclada: el estéreo muy por encima de cámara y proyector por separado
const calibMezclada = (r) => r && r.estereo != null && r.estereo > 3 * Math.max(r.cam || 0, r.proj || 0, 0.3);

async function cargarErroresCalib(forzar = false) {
  const variante = $("#a-calib").value;
  const clave = `${est.calib?.fecha}/${variante}`;
  if (!forzar && ec.clave === clave && (ec.datos || ec.error)) return pintarErroresCalib();
  ec.clave = clave;
  // Se borra lo anterior en el acto: nunca se muestran los errores de otra calibración mientras
  // llegan los nuevos (la primera vez, una calibración antigua tarda unos segundos)
  const turno = ++ec.turno;
  ec.datos = null; ec.error = null;
  pintarErroresCalib();
  cargarListaCalib();
  try {
    const datos = await api(`/api/calibracion?variante=${encodeURIComponent(variante)}`);
    if (turno !== ec.turno) return;  // llegó tarde: ya se pidió otra calibración
    ec.datos = datos;
    const poses = ec.datos.poses;
    if (!poses.some((p) => p.pose === ec.sel)) {  // por defecto, la pose usada con más error
      const usadas = poses.filter((p) => p.usada), lista = usadas.length ? usadas : poses;
      ec.sel = lista.reduce((a, b) => (b.estereo_px > a.estereo_px ? b : a), lista[0])?.pose ?? null;
    }
  } catch (err) {
    if (turno !== ec.turno) return;
    ec.datos = null; ec.error = err.message;
  }
  pintarErroresCalib();
}

// ------------------------------------------------------------------ elegir la calibración en uso
async function cargarListaCalib() {
  const turno = ec.turnoLista = (ec.turnoLista || 0) + 1;
  let lista;
  try { lista = await api("/api/calibraciones"); } catch (err) { lista = []; }
  if (turno !== ec.turnoLista) return;
  ec.lista = lista;
  pintarListaCalib();
}

function pintarListaCalib() {
  const sel = $("#ec-elegir"), previa = sel.value;
  sel.innerHTML = "";
  for (const c of ec.lista) {
    const o = document.createElement("option");
    o.value = c.id;
    const mal = c.control ? !c.control.aprobada : calibMezclada({ cam: c.rms_cam_px, proj: c.rms_proj_px, estereo: c.rms_stereo_px });
    o.textContent = t("ec_opcion", { f: fechaCorta(c.fecha || c.id), n: c.poses.length, e: fmt(c.rms_stereo_px, 2) }) +
      (mal ? ` ⚠ ${t("ec_rechazada")}` : "") + (c.activa ? ` — ${t("ec_en_uso_corto")}` : "");
    sel.appendChild(o);
  }
  if (!ec.lista.length) {
    const o = document.createElement("option"); o.value = ""; o.textContent = t("ec_sin_historial"); sel.appendChild(o);
  }
  const activa = ec.lista.find((c) => c.activa);
  sel.value = ec.lista.some((c) => c.id === previa) && previa !== ec.activaPrevia ? previa : (activa?.id ?? sel.options[0]?.value ?? "");
  ec.activaPrevia = activa?.id;
  actualizarBotonUsar();
}

function actualizarBotonUsar() {
  const c = ec.lista.find((x) => x.id === $("#ec-elegir").value);
  $("#ec-usar").disabled = !c || c.activa || est.ejec.ejecutando;
  pintarOrigenCalib(c);
}

// Imágenes del patrón de las que salió la calibración elegida en el selector
function pintarOrigenCalib(c) {
  const cont = $("#ec-origen");
  const clave = c ? `${c.id}/${IDIOMA}` : "";
  if (cont.dataset.clave === clave) return;
  cont.dataset.clave = clave;
  cont.innerHTML = "";
  if (!c) return;
  const titulo = document.createElement("p");
  titulo.className = "nota";
  titulo.textContent = t("ec_origen", { n: c.poses_info.length, f: c.proceso ? fechaCorta(c.proceso) : "—" });
  cont.appendChild(titulo);
  if (c.control && !c.control.aprobada) {  // por qué no pasó el control de calidad
    const aviso = document.createElement("p");
    aviso.className = "nota aviso";
    aviso.textContent = t("ec_motivos", { m: c.control.motivos.join(" · ") });
    cont.appendChild(aviso);
  }
  const tira = document.createElement("div");
  tira.className = "miniaturas tira";
  const url = (p, ancho) => `/api/imagen?cat=patron&pose=${p.pose}&tipo=textura&ancho=${ancho}`;
  const lista = c.poses_info.filter((p) => p.existe).map((p) => ({
    mini: url(p, 240), url: url(p, 1600),
    titulo: `${p.pose}${p.hora ? " · " + fechaCorta(p.hora) : ""}${p.estereo_px != null ? ` · ${fmt(p.estereo_px, 2)} px` : ""}`,
  }));
  for (const p of c.poses_info) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "mini" + (p.existe ? "" : " borrada");
    b.innerHTML = p.existe ? `<img loading="lazy" alt=""><span></span>` : `<i></i><span></span>`;
    const i = lista.findIndex((x) => x.titulo.startsWith(p.pose + " ") || x.titulo === p.pose);
    if (p.existe) { $("img", b).src = url(p, 240); $("img", b).alt = p.pose; b.addEventListener("click", () => abrirVisor(lista, i)); }
    else { $("i", b).textContent = t("ec_pose_borrada"); b.disabled = true; }
    $("span", b).textContent = p.pose;
    tira.appendChild(b);
  }
  cont.appendChild(tira);
}

async function usarCalibracion() {
  const id = $("#ec-elegir").value;
  if (!id) return;
  const c = ec.lista.find((x) => x.id === id);
  if (c?.control && !c.control.aprobada && !confirm(t("ec_confirmar_rechazada", { m: c.control.motivos.join("\n• ") }))) return;
  $("#ec-usar").disabled = true;
  ec.turno++; ec.datos = null; ec.error = null;  // fuera los errores de la anterior desde ya
  pintarErroresCalib();
  try {
    await api("/api/calibraciones/activar", { id });
    ec.clave = null;  // fuerza a recargar errores y lista con la nueva calibración
    refrescarEstado();
  } catch (err) { agregarLog(`[ERROR] ${err.message}`); actualizarBotonUsar(); }
}

function pintarErroresCalib() {
  const resumen = $("#ec-resumen"), aviso = $("#ec-aviso");
  for (const id of ["#ec-barras", "#ec-tabla", "#ec-res-cam", "#ec-res-proj", "#ec-tit-cam", "#ec-tit-proj", "#ec-esc-cam", "#ec-esc-proj",
    "#ec-cob-proj", "#ec-cob-cam", "#ec-cob-pct", "#ec-cob-nota"]) $(id).innerHTML = "";
  resumen.innerHTML = "";
  aviso.classList.add("oculto");
  const d = ec.datos;
  if (!d) {
    const p = document.createElement("p");
    p.className = "ec-vacio";
    p.textContent = ec.error ? t("ec_sin_datos", { m: ec.error }) : t("cargando");
    resumen.appendChild(p);
    return;
  }
  const umbral = umbralIncoherente(d);
  const usadas = d.poses.filter((p) => p.usada);

  // --- resumen ---
  const criterio = Array.isArray(d.criterio) ? t("ec_criterio_lista") : t(`calib_poses_${d.criterio === "ultima_sesion" ? "ultima" : "todas"}`);
  const items = [
    [t("fecha"), fechaCorta(d.fecha)],
    [t("ec_usadas"), t("ec_usadas_n", { u: usadas.length, n: d.poses.length })],
    [t("calib_poses"), criterio],
    [t("rms_cam"), `${fmt(d.rms.cam, 3)} px`],
    [t("rms_proj"), `${fmt(d.rms.proj, 3)} px`],
    [t("rms_st"), `${fmt(d.rms.estereo, 3)} px`, calibMezclada(d.rms)],
  ];
  for (const [k, v, mal] of items) {
    const s = document.createElement("span");
    s.className = "metrica" + (mal ? " mal" : "");
    s.textContent = k;
    const b = document.createElement("b"); b.textContent = v; s.appendChild(b);
    resumen.appendChild(s);
  }

  // --- avisos ---
  const textos = [];
  if (calibMezclada(d.rms)) textos.push(t("ec_aviso_mezcla", { e: fmt(d.rms.estereo, 1) }));
  const malas = d.poses.filter((p) => p.estereo_px > umbral);
  if (malas.length) {
    const v = malas.map((p) => p.estereo_px);
    textos.push(t("ec_aviso_malas", {
      poses: malas.map((p) => p.pose.replace("pose_", "")).join(", "),
      min: fmt(Math.min(...v), 1), max: fmt(Math.max(...v), 1), med: fmt(mediana(usadas.map((p) => p.estereo_px)), 2),
    }));
    if (malas.every((p) => !p.usada)) textos.push(t("ec_aviso_no_usadas"));
  }
  if (!d.completo) textos.push(t("ec_aviso_incompleto"));
  if (d.faltan?.length) textos.push(t("ec_aviso_faltan", { n: d.faltan.length, l: d.faltan.join(", ") }));
  if (textos.length) { aviso.textContent = textos.join(" "); aviso.classList.remove("oculto"); }
  aviso.style.borderColor = calibMezclada(d.rms) || malas.some((p) => p.usada) ? "" : "var(--aviso)";

  dibujarBarras(d, umbral);
  dibujarTabla(d, umbral);
  dibujarResiduos(d);
  dibujarCobertura(d);
}

function seleccionarPoseCalib(pose) {
  ec.sel = pose;
  for (const g of $$("#ec-barras .grupo")) g.classList.toggle("sel", g.dataset.pose === pose);
  for (const tr of $$("#ec-tabla tbody tr[data-pose]")) tr.classList.toggle("sel", tr.dataset.pose === pose);
  dibujarResiduos(ec.datos);
}

// ------------------------------------------------------------------ gráfico de barras
function dibujarBarras(d, umbral) {
  const n = d.poses.length;
  if (!n) return;
  const izq = 40, der = 8, arriba = 20, abajo = 38, alto = 230, anchoG = Math.max(34, Math.min(56, 820 / n));
  const ancho = izq + n * anchoG + der, base = alto - abajo;
  // Escala: la determinan las poses coherentes; las que se salen se recortan con su valor encima
  const buenas = d.poses.filter((p) => p.estereo_px <= umbral);
  const maximo = Math.max(...(buenas.length ? buenas : d.poses).flatMap((p) => [p.cam_px, p.proj_px, p.estereo_px]), 0.1);
  const ymax = redondeoBonito(maximo * 1.15);
  const y = (v) => base - Math.min(v, ymax) / ymax * (base - arriba);
  let svg = `<svg viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="${escHTML(t("ec_barras"))}">`;
  const paso = ymax / 4;
  for (let v = 0; v <= ymax + 1e-9; v += paso) {
    svg += `<line class="eje" x1="${izq}" x2="${ancho - der}" y1="${y(v)}" y2="${y(v)}" stroke-dasharray="${v ? "3 3" : ""}"/>`;
    svg += `<text x="${izq - 6}" y="${y(v) + 4}" text-anchor="end">${+v.toFixed(2)}</text>`;
  }
  let sesionPrevia = null;
  d.poses.forEach((p, i) => {
    const x0 = izq + i * anchoG;
    if (p.sesion !== undefined && p.sesion !== sesionPrevia) {
      if (sesionPrevia !== null) svg += `<line class="eje" x1="${x0}" x2="${x0}" y1="${arriba - 14}" y2="${alto - 2}" stroke-dasharray="4 3"/>`;
      svg += `<text x="${x0 + 3}" y="${alto - 3}">${escHTML(t("ec_sesion_corta", { n: p.sesion + 1, f: fechaCorta(p.hora) }))}</text>`;
      sesionPrevia = p.sesion;
    }
    const barras = [["cam", p.cam_px], ["proj", p.proj_px], ["est", p.estereo_px]];
    const bw = Math.min(10, (anchoG - 10) / 3), x1 = x0 + (anchoG - 3 * bw - 4) / 2;
    const tip = t("ec_tooltip", { pose: p.pose, c: fmt(p.cam_px, 3), p: fmt(p.proj_px, 3), e: fmt(p.estereo_px, 3) }) + (p.usada ? "" : ` (${t("ec_no_usada")})`);
    svg += `<g class="grupo${p.pose === ec.sel ? " sel" : ""}" data-pose="${escHTML(p.pose)}" opacity="${p.usada ? 1 : 0.5}"><title>${escHTML(tip)}</title>`;
    svg += `<rect class="fondo" x="${x0 + 1}" y="${arriba - 14}" width="${anchoG - 2}" height="${base - arriba + 14}" fill="transparent" rx="4"/>`;
    barras.forEach(([s, v], k) => {
      svg += `<rect x="${x1 + k * (bw + 2)}" y="${y(v)}" width="${bw}" height="${Math.max(base - y(v), 0.5)}" fill="var(--s-${s})" rx="1.5"/>`;
    });
    const peor = Math.max(p.cam_px, p.proj_px, p.estereo_px);
    if (peor > ymax) svg += `<text class="mal" x="${x0 + anchoG / 2}" y="${arriba - 4}" text-anchor="middle">▲${fmt(peor, peor >= 10 ? 0 : 1)}</text>`;
    svg += `<text class="nombre" x="${x0 + anchoG / 2}" y="${base + 14}" text-anchor="middle">${escHTML(p.pose.replace("pose_", ""))}</text>`;
    svg += `</g>`;
  });
  svg += `</svg>`;
  const cont = $("#ec-barras");
  cont.innerHTML = svg;
  for (const g of $$(".grupo", cont)) g.addEventListener("click", () => seleccionarPoseCalib(g.dataset.pose));
}

// ------------------------------------------------------------------ tabla
function dibujarTabla(d, umbral) {
  const cols = [
    ["ec_th_pose"], ["ec_th_cam", "cam_px", 3], ["ec_th_proj", "proj_px", 3], ["ec_th_est", "estereo_px", 3],
    ["ec_th_est_cam", "estereo_cam_px", 2], ["ec_th_est_proj", "estereo_proj_px", 2],
    ["ec_th_dr", "delta_R_grados", 2], ["ec_th_dt", "delta_T_mm", 1], ["ec_th_dist", "distancia_mm", 0],
  ];
  const tabla = $("#ec-tabla");
  const thead = document.createElement("thead"), fila = document.createElement("tr");
  for (const [clave] of cols) {
    const th = document.createElement("th");
    th.textContent = t(clave);
    th.title = t(`${clave}_title`);
    fila.appendChild(th);
  }
  thead.appendChild(fila);
  const tbody = document.createElement("tbody");
  let sesionPrevia = null;
  for (const p of d.poses) {
    if (p.sesion !== undefined && p.sesion !== sesionPrevia) {
      const tr = document.createElement("tr"); tr.className = "separador";
      const td = document.createElement("td"); td.colSpan = cols.length;
      td.textContent = t("ec_sesion", { n: p.sesion + 1, f: fechaCorta(p.hora) });
      tr.appendChild(td); tbody.appendChild(tr);
      sesionPrevia = p.sesion;
    }
    const tr = document.createElement("tr");
    tr.dataset.pose = p.pose;
    tr.className = (p.usada ? "" : "no-usada") + (p.pose === ec.sel ? " sel" : "");
    for (const [, campo, dec] of cols) {
      const td = document.createElement("td");
      if (!campo) td.textContent = p.pose + (p.usada ? "" : ` · ${t("ec_no_usada")}`);
      else {
        td.textContent = fmt(p[campo], dec);
        if (campo.startsWith("estereo") && p[campo] > umbral) td.className = "mal";
      }
      tr.appendChild(td);
    }
    tr.addEventListener("click", () => seleccionarPoseCalib(p.pose));
    tbody.appendChild(tr);
  }
  tabla.append(thead, tbody);
}

// ------------------------------------------------------------------ cobertura y siguiente pose
// El proyector se divide en zonas; una zona está cubierta si caen en ella círculos de las poses
// usadas. Para las vacías se estima dónde quedarían en la imagen de la cámara con un ajuste afín
// proyector -> cámara de todas las correspondencias (aproximado, pero basta para orientar).
const COB_COLS = 4, COB_FILAS = 5, COB_MIN_PUNTOS = 4;

function ajusteAfin(origen, destino) {
  // Mínimos cuadrados de destino = [x y 1]·M para cada coordenada (ecuaciones normales 3×3)
  const ata = [[0, 0, 0], [0, 0, 0], [0, 0, 0]], atb = [[0, 0, 0], [0, 0, 0]];
  origen.forEach(([x, y], i) => {
    const f = [x, y, 1];
    for (let a = 0; a < 3; a++) {
      for (let b = 0; b < 3; b++) ata[a][b] += f[a] * f[b];
      atb[0][a] += f[a] * destino[i][0]; atb[1][a] += f[a] * destino[i][1];
    }
  });
  const resolver = (m, v) => {  // Cramer 3×3
    const det = (q) => q[0][0] * (q[1][1] * q[2][2] - q[1][2] * q[2][1]) - q[0][1] * (q[1][0] * q[2][2] - q[1][2] * q[2][0]) + q[0][2] * (q[1][0] * q[2][1] - q[1][1] * q[2][0]);
    const d = det(m);
    return [0, 1, 2].map((c) => det(m.map((fila, r) => fila.map((x, k) => (k === c ? v[r] : x)))) / d);
  };
  const cx = resolver(ata, atb[0]), cy = resolver(ata, atb[1]);
  return ([x, y]) => [cx[0] * x + cx[1] * y + cx[2], cy[0] * x + cy[1] * y + cy[2]];
}

function dibujarCobertura(d) {
  const usadas = d.poses.filter((p) => p.usada && p.puntos_proj?.length);
  if (!usadas.length) return;
  const [PW, PH] = d.proj_wh, [CW, CH] = d.cam_wh;
  const cuenta = Array.from({ length: COB_FILAS }, () => Array(COB_COLS).fill(0));
  const proj = usadas.flatMap((p) => p.puntos_proj), cam = usadas.flatMap((p) => p.puntos_cam);
  for (const [u, v] of proj) {
    const c = Math.min(COB_COLS - 1, Math.max(0, Math.floor(u / PW * COB_COLS)));
    const f = Math.min(COB_FILAS - 1, Math.max(0, Math.floor(v / PH * COB_FILAS)));
    cuenta[f][c]++;
  }
  // Zonas que la cámara alcanza a ver (el proyector ilumina más de lo que la cámara ve): solo
  // esas se pueden cubrir, así que el porcentaje se calcula sobre ellas
  const aCam = ajusteAfin(proj, cam);
  const gw = PW / COB_COLS, gh = PH / COB_FILAS;
  const enCamara = (c, f) => {
    const [x, y] = aCam([(c + 0.5) * gw, (f + 0.5) * gh]);
    return x >= -0.05 * CW && x <= 1.05 * CW && y >= -0.05 * CH && y <= 1.05 * CH;
  };
  const vacias = [];
  let cubiertas = 0, visibles = 0;
  cuenta.forEach((fila, f) => fila.forEach((n, c) => {
    const visible = enCamara(c, f) || n >= COB_MIN_PUNTOS;
    visibles += visible;
    if (n >= COB_MIN_PUNTOS) cubiertas++; else vacias.push([c, f]);
  }));
  $("#ec-cob-pct").textContent = t("ec_cob_pct", { c: cubiertas, n: visibles, p: Math.round(100 * cubiertas / Math.max(visibles, 1)) });
  // Proyector: zonas verdes (cubiertas) y rojas (vacías) con los círculos de las poses
  const r = PW / 220;
  let svg = `<svg viewBox="${-PW * 0.02} ${-PH * 0.02} ${PW * 1.04} ${PH * 1.04}" role="img">`;
  cuenta.forEach((fila, f) => fila.forEach((n, c) => {
    const ok = n >= COB_MIN_PUNTOS;
    // verde = cubierta · rojo = vacía y alcanzable · gris = fuera del campo de la cámara
    const color = ok ? "rgba(92,194,138,.22)" : enCamara(c, f) ? "rgba(239,111,91,.35)" : "rgba(255,255,255,.05)";
    svg += `<rect x="${c * gw}" y="${f * gh}" width="${gw}" height="${gh}" fill="${color}" stroke="rgba(255,255,255,.25)" stroke-width="${PW / 400}"/>`;
  }));
  for (const [u, v] of proj) svg += `<circle cx="${u}" cy="${v}" r="${r}" fill="rgba(255,255,255,.75)"/>`;
  $("#ec-cob-proj").innerHTML = svg + "</svg>";
  // Cámara: dónde caerían las zonas vacías -> dónde poner el tablero
  const rc = CW / 220;
  let svgc = `<svg viewBox="${-CW * 0.02} ${-CH * 0.02} ${CW * 1.04} ${CH * 1.04}" role="img">`;
  svgc += `<rect x="0" y="0" width="${CW}" height="${CH}" fill="none" stroke="rgba(255,255,255,.3)" stroke-width="${CW / 500}"/>`;
  for (const [x, y] of cam) svgc += `<circle cx="${x}" cy="${y}" r="${rc * 0.7}" fill="rgba(255,255,255,.22)"/>`;
  let fuera = 0, n = 0;
  for (const [c, f] of vacias) {
    const [x, y] = aCam([(c + 0.5) * gw, (f + 0.5) * gh]);
    if (x < -0.05 * CW || x > 1.05 * CW || y < -0.05 * CH || y > 1.05 * CH) { fuera++; continue; }
    n++;
    svgc += `<circle cx="${Math.min(Math.max(x, 0), CW)}" cy="${Math.min(Math.max(y, 0), CH)}" r="${CW / 22}" fill="rgba(242,140,40,.18)" stroke="var(--s-est)" stroke-width="${CW / 300}" stroke-dasharray="${CW / 80} ${CW / 120}"/>`;
    svgc += `<text x="${Math.min(Math.max(x, 0), CW)}" y="${Math.min(Math.max(y, 0), CH) + CW / 70}" text-anchor="middle" font-size="${CW / 28}" fill="#fff">${n}</text>`;
  }
  $("#ec-cob-cam").innerHTML = svgc + "</svg>";
  $("#ec-cob-nota").textContent = n
    ? t("ec_cob_sugerencia", { n }) + (fuera ? " " + t("ec_cob_fuera", { n: fuera }) : "")
    : t("ec_cob_completa") + (fuera ? " " + t("ec_cob_fuera", { n: fuera }) : "");
}

// ------------------------------------------------------------------ vectores de error
function dibujarResiduos(d) {
  const p = d.poses.find((x) => x.pose === ec.sel);
  if (!p) return;
  const lado = (cual, wh, puntos, res, rms) => {
    const [W, H] = wh;
    const todos = d.poses.filter((x) => x.pose !== p.pose).flatMap((x) => x[puntos] || []);
    const mags = (p[res] || []).map(([dx, dy]) => Math.hypot(dx, dy)).sort((a, b) => a - b);
    const p95 = mags.length ? mags[Math.floor(0.95 * (mags.length - 1))] : 1;
    // Escala para que el 95 % de las flechas mida como mucho ~6 % del ancho del sensor
    const crudo = 0.06 * W / Math.max(p95, 1e-6);
    const pot = 10 ** Math.floor(Math.log10(Math.max(crudo, 1)));
    const escala = Math.max(1, [5, 2, 1].map((f) => f * pot).find((v) => v <= crudo) || pot);  // 1, 2, 5 × 10^k
    const r = W / 260, grosor = W / 500;
    let svg = `<svg viewBox="${-W * 0.02} ${-H * 0.02} ${W * 1.04} ${H * 1.04}" role="img">`;
    svg += `<rect x="0" y="0" width="${W}" height="${H}" fill="none" stroke="rgba(255,255,255,.3)" stroke-width="${grosor}"/>`;
    for (const [x, yy] of todos) svg += `<circle cx="${x}" cy="${yy}" r="${r * 0.7}" fill="rgba(255,255,255,.16)"/>`;
    (p[puntos] || []).forEach(([x, yy], i) => {
      const [dx, dy] = p[res][i];
      const x2 = x + dx * escala, y2 = yy + dy * escala;
      svg += `<line x1="${x}" y1="${yy}" x2="${x2}" y2="${y2}" stroke="var(--s-est)" stroke-width="${grosor * 1.6}" stroke-linecap="round"/>`;
      svg += `<circle cx="${x}" cy="${yy}" r="${r}" fill="#ffffff"/>`;
    });
    svg += `</svg>`;
    $(`#ec-res-${cual}`).innerHTML = svg;
    $(`#ec-tit-${cual}`).textContent = t(`ec_res_${cual}`, { pose: p.pose });
    $(`#ec-esc-${cual}`).textContent = t("ec_escala", { s: escala, e: fmt(p[rms], 2) });
  };
  lado("cam", d.cam_wh, "puntos_cam", "res_cam", "estereo_cam_px");
  lado("proj", d.proj_wh, "puntos_proj", "res_proj", "estereo_proj_px");
}
