// Pestaña «Nube de puntos»: elegir el método de reconstrucción (procesamiento/metodos.py) y
// compararlos. «Comparar» muestra hasta 4 visores lado a lado, con la cámara sincronizada (al
// girar uno giran todos) y el mismo centro, más una tabla con todos los métodos de la pose:
// puntos, rango de Z, diferencia con el estéreo y, en los planos, la planitud.
"use strict";

const nm = {
  metodo: "estereo", lista: [], comparando: false,
  elegidos: ["estereo", "estereo_ambas", "hib_rac_virtual", "hib_rac_medidos"],
  visores: {}, sincronizando: false, clave: null, tabla: null,
};

const nombreMetodo = (id) => {
  const k = `metodo_${id}`, txt = t(k);
  return txt !== k ? txt : nm.lista.find((m) => m.id === id)?.nombre || id;
};

async function cargarListaMetodos() {
  try { nm.lista = (await api("/api/metodos")).metodos; } catch { nm.lista = [{ id: "estereo", nombre: "Estéreo (Fy)" }]; }
  const sel = $("#n-metodo");
  sel.innerHTML = "";
  for (const m of nm.lista) sel.appendChild(new Option(nombreMetodo(m.id), m.id));
  sel.value = nm.metodo;
  pintarElegirMetodos();
}

function pintarElegirMetodos() {
  const cont = $("#nm-elegir");
  cont.innerHTML = "";
  // atajos: todos / los 4 principales
  for (const [txt, ids] of [[t("nm_todos"), nm.lista.map((m) => m.id)],
                            [t("nm_principales"), ["estereo", "estereo_ambas", "hib_rac_virtual", "hib_rac_medidos"]]]) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "nm-atajo"; b.textContent = txt;
    b.addEventListener("click", () => { nm.elegidos = ids; pintarElegirMetodos(); nm.clave = null; cargarComparacion(); });
    cont.appendChild(b);
  }
  for (const m of nm.lista) {
    const l = document.createElement("label");
    l.className = "casilla";
    l.innerHTML = `<input type="checkbox"> <span></span>`;
    $("input", l).checked = nm.elegidos.includes(m.id);
    $("span", l).textContent = nombreMetodo(m.id);
    $("input", l).addEventListener("change", (ev) => {
      if (ev.target.checked) nm.elegidos = nm.lista.map((x) => x.id).filter((x) => x === m.id || nm.elegidos.includes(x));
      else nm.elegidos = nm.elegidos.filter((x) => x !== m.id);
      pintarElegirMetodos();
      nm.clave = null;
      cargarComparacion();
    });
    cont.appendChild(l);
  }
}

// ------------------------------------------------------------------ comparación lado a lado
async function cargarComparacion() {
  const clave = `${est.cat}/${est.pose}/${version("reconstruida")}/${nm.elegidos.join(",")}`;
  if (nm.clave === clave) { Object.values(nm.visores).forEach((v) => v.dibujar()); return; }
  nm.clave = clave;
  nm.tabla = null;
  $("#nm-tabla tbody").innerHTML = "";
  $("#nm-tabla-estado").textContent = "";
  const rejilla = $("#nm-rejilla");
  rejilla.innerHTML = "";
  rejilla.dataset.n = nm.elegidos.length;
  nm.visores = {};
  if (!est.pose || !infoPose()?.reconstruida) { rejilla.innerHTML = `<p class="nota">${t("sin_nube")}</p>`; return; }
  for (const id of nm.elegidos) {
    const celda = document.createElement("div");
    celda.className = "nm-celda";
    celda.innerHTML = `<div class="nm-titulo"><b></b><small></small></div><div class="md-3d"><canvas></canvas><p class="visor-info"></p></div>`;
    $("b", celda).textContent = nombreMetodo(id);
    rejilla.appendChild(celda);
    let v;
    try { v = new VisorNube($("canvas", celda)); } catch (err) { $(".visor-info", celda).textContent = err.message; continue; }
    v.setTamano(+$("#n-tam").value);
    v.setColor($(".visor-herramientas .color .activo")?.dataset.color || "profundidad");
    v.alMover = () => sincronizar(v);
    nm.visores[id] = v;
  }
  // el estéreo primero: su centro es el común (así todos miran exactamente al mismo lugar)
  let centro = null;
  const orden = [...nm.elegidos].sort((a, b) => (a === "estereo" ? -1 : b === "estereo" ? 1 : 0));
  for (const id of orden) {
    const v = nm.visores[id];
    if (!v) continue;
    const celda = v.canvas.closest(".nm-celda"), info = $(".visor-info", celda);
    info.textContent = id === "estereo" ? t("nube_cargando") : t("nm_calculando", { m: nombreMetodo(id) });
    try {
      // con muchos visores, menos puntos en cada uno (todos a la vez siguen fluidos)
      const max = nm.elegidos.length > 4 ? 150000 : 250000;
      const r = await fetch(`/api/nube?cat=${est.cat}&pose=${est.pose}&max=${max}&metodo=${id}`);
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
      const buf = await r.arrayBuffer();
      if (nm.clave !== clave) return;
      v.cargar(buf, false, centro);
      centro = centro || v.centro;
      const primero = Object.values(nm.visores).find((x) => x !== v && x.n);
      if (primero) { nm.sincronizando = true; v.vista = primero.vista; nm.sincronizando = false; }
      info.textContent = t("nube_mostrados", { n: v.n.toLocaleString(locale()) });
    } catch (err) { info.textContent = t("error_x", { m: err.message }); }
  }
  calcularTablaMetodos(nm.elegidos);
}

function sincronizar(origen) {
  if (nm.sincronizando) return;
  nm.sincronizando = true;
  for (const v of Object.values(nm.visores)) if (v !== origen && v.n) v.vista = origen.vista;
  nm.sincronizando = false;
}

// ------------------------------------------------------------------ tabla de estadísticas
async function calcularTablaMetodos(lista) {
  const clave = nm.clave;
  $("#nm-tabla-estado").textContent = t("nm_calculando_tabla");
  $("#nm-calcular").disabled = true;
  let d;
  try { d = await api(`/api/metodos/comparar?cat=${est.cat}&pose=${est.pose}&metodos=${lista.join(",")}`); }
  catch (err) { $("#nm-tabla-estado").textContent = t("error_x", { m: err.message }); $("#nm-calcular").disabled = false; return; }
  finally { $("#nm-calcular").disabled = false; }
  if (clave !== nm.clave) return;
  nm.tabla = { ...(nm.tabla || {}), ...d };
  $("#nm-tabla-estado").textContent = "";
  pintarTablaMetodos();
  // títulos de los visores con lo esencial
  for (const [id, v] of Object.entries(nm.visores)) {
    const s = nm.tabla[id];
    const celda = v.canvas.closest(".nm-celda");
    if (s && !s.error) {
      $("small", celda).textContent = (s.planitud_mm != null ? `${t("nm_col_planitud")} ${fmt(s.planitud_mm, 3)} mm · ` : "") +
        (id !== "estereo" && s.dif_mediana_mm != null ? `Δ ${fmt(s.dif_mediana_mm, 2)} mm` : "");
    }
  }
}

function pintarTablaMetodos() {
  const tb = $("#nm-tabla tbody");
  tb.innerHTML = "";
  const filas = Object.entries(nm.tabla || {});
  const mejor = Math.min(...filas.map(([, s]) => (s.en_ajuste ? Infinity : s.planitud_mm ?? Infinity)));
  let hayAjuste = false;
  for (const [id, s] of filas) {
    const tr = document.createElement("tr");
    tr.innerHTML = "<td></td><td></td><td></td><td></td><td></td>";
    const c = tr.children;
    c[0].textContent = nombreMetodo(id);
    if (s.error) { c[1].colSpan = 4; c[1].textContent = s.error; tb.appendChild(tr); continue; }
    c[1].textContent = s.puntos.toLocaleString(locale());
    c[2].textContent = s.z ? `${fmt(s.z[0], 1)}–${fmt(s.z[1], 1)}` : "—";
    c[3].textContent = id === "estereo" ? "—" : `${fmt(s.dif_mediana_mm, 3)} · ${fmt(s.dif_p95_mm, 3)}`;
    c[4].textContent = s.planitud_mm != null ? `${fmt(s.planitud_mm, 3)} mm${s.en_ajuste ? " *" : ""}` : "—";
    if (s.en_ajuste) { c[4].title = t("nm_en_ajuste"); hayAjuste = true; }
    if (s.planitud_mm != null && s.planitud_mm === mejor) c[4].classList.add("nm-mejor");
    tr.addEventListener("click", () => { nm.metodo = id; $("#n-metodo").value = id; salirComparacion(); });
    tr.title = t("nm_ver_metodo");
    tb.appendChild(tr);
  }
  $("#nm-tabla-estado").textContent = hayAjuste ? t("nm_en_ajuste") : "";
}

function salirComparacion() {
  nm.comparando = false;
  $("#nm-comparar").classList.add("oculto");
  $("#n-comparar").classList.remove("activo");
  cargarNube();
}

function iniciarMetodos() {
  cargarListaMetodos();
  $("#n-metodo").addEventListener("change", (ev) => { nm.metodo = ev.target.value; if (nm.comparando) salirComparacion(); else cargarNube(); });
  $("#n-comparar").addEventListener("click", () => {
    nm.comparando = !nm.comparando;
    $("#nm-comparar").classList.toggle("oculto", !nm.comparando);
    $("#n-comparar").classList.toggle("activo", nm.comparando);
    nm.clave = null;
    cargarNube();
  });
  $("#nm-calcular").addEventListener("click", () => calcularTablaMetodos(nm.lista.map((m) => m.id)));
  // color y tamaño también en los visores de la comparación
  for (const b of $$(".visor-herramientas .color button")) {
    b.addEventListener("click", () => Object.values(nm.visores).forEach((v) => v.setColor(b.dataset.color)));
  }
  $("#n-tam").addEventListener("input", (ev) => Object.values(nm.visores).forEach((v) => v.setTamano(+ev.target.value)));
}
