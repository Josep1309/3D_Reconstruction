// Pestaña «Sistema»: comprobaciones de verificar.py, lista de comprobación antes de medir y disco.
"use strict";

const si = { datos: null, conHw: false };
const ICONO = { ok: "✔", aviso: "⚠", error: "✖", info: "·" };

async function cargarSistema(conHw = si.conHw, forzar = false) {
  si.conHw = conHw;
  $("#si-resumen").textContent = t(conHw ? "si_buscando" : "cargando");
  try { si.datos = await api(`/api/sistema?hw=${conHw ? 1 : 0}${forzar ? "&forzar=1" : ""}`); }
  catch (err) { $("#si-resumen").textContent = t("error_x", { m: err.message }); return; }
  pintarSistema();
}

function buscar(grupo, nivel) {
  return (si.datos?.resultados || []).filter((r) => r.grupo.includes(grupo) && (!nivel || r.nivel === nivel));
}

function pintarSistema() {
  const d = si.datos;
  if (!d) return;
  const r = d.resumen;
  $("#si-resumen").textContent = t("si_resumen", { ok: r.ok, a: r.aviso, e: r.error, h: d.hora }) +
    (d.con_hardware ? "" : " · " + t("si_sin_hw"));
  $("#si-resumen").className = "ar-vigente " + (r.error ? "mal" : r.aviso ? "aviso" : "bien");

  // --- lista de comprobación: automática donde se puede, a mano el resto ---
  const tablero = aj.valores.TABLERO?.v, tableroMedido = tablero && !(tablero[0] === 15 && tablero[1] === 15);
  const estadoHw = (grupo) => (!d.con_hardware ? null : buscar(grupo).some((x) => x.nivel === "error" || x.nivel === "aviso") ? false : true);
  const auto = [
    ["si_c_calib", buscar("Calibración", "aviso").length + buscar("Calibración", "error").length === 0, "calibracion"],
    ["si_c_tablero", tableroMedido, "ajustes"],
    ["si_c_camara", estadoHw("Cámara"), null],
    ["si_c_proyector", estadoHw("LightCrafter"), null],
    ["si_c_patrones", buscar("Patrones", "ok").length > 0, null],
  ];
  const manuales = ["si_m_secuencia", "si_m_arduino", "si_m_enfoque", "si_m_saturacion"];
  let marcados = {};
  try { marcados = JSON.parse(sessionStorage.getItem("checklist") || "{}"); } catch (_) { /* sin almacenamiento */ }
  const ul = $("#si-checklist");
  ul.innerHTML = "";
  for (const [clave, ok, ir] of auto) {
    const li = document.createElement("li");
    li.className = ok === null ? "pendiente" : ok ? "bien" : "mal";
    li.innerHTML = `<span class="si-icono"></span><span></span>`;
    $(".si-icono", li).textContent = ok === null ? "?" : ok ? "✔" : "⚠";
    li.lastElementChild.textContent = t(clave) + (ok === null ? ` (${t("si_sin_comprobar")})` : "");
    if (ir && !ok) {
      const b = document.createElement("button");
      b.type = "button"; b.textContent = t("si_revisar");
      b.addEventListener("click", () => (ir === "ajustes" ? $("#ajustes").showModal() : mostrarPaso(ir)));
      li.appendChild(b);
    }
    ul.appendChild(li);
  }
  for (const clave of manuales) {
    const li = document.createElement("li");
    li.className = "a-mano";
    li.innerHTML = `<label class="casilla"><input type="checkbox"> <span></span></label>`;
    $("span", li).textContent = t(clave);
    const c = $("input", li);
    c.checked = !!marcados[clave];
    c.addEventListener("change", () => {
      marcados[clave] = c.checked;
      try { sessionStorage.setItem("checklist", JSON.stringify(marcados)); } catch (_) { /* sin almacenamiento */ }
    });
    ul.appendChild(li);
  }

  // --- disco ---
  const disco = $("#si-disco");
  disco.innerHTML = "";
  const total = d.disco.total, usadoDatos = Object.values(d.disco.carpetas).reduce((a, b) => a + b, 0);
  const fila = (nombre, bytes, max) => {
    const div = document.createElement("div");
    div.className = "si-disco-fila";
    div.innerHTML = `<span></span><meter min="0"></meter><b></b>`;
    $("span", div).textContent = nombre;
    $("meter", div).max = max; $("meter", div).value = bytes;
    $("b", div).textContent = megas(bytes);
    disco.appendChild(div);
  };
  for (const [nombre, bytes] of Object.entries(d.disco.carpetas)) fila(nombre, bytes, Math.max(usadoDatos, 1));
  const libre = document.createElement("p");
  libre.className = "nota" + (d.disco.libre < 20e9 ? " aviso" : "");
  libre.textContent = t("si_libre", { l: megas(d.disco.libre), t: megas(total), p: megas(usadoDatos) });
  disco.appendChild(libre);
  if (d.disco.carpetas.papelera > 0) {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = t("si_ver_papelera");
    b.addEventListener("click", () => mostrarPaso("archivos"));
    disco.appendChild(b);
  }

  // --- comprobaciones por grupo ---
  const cont = $("#si-grupos");
  cont.innerHTML = "";
  const grupos = new Map();
  for (const x of d.resultados) { if (!grupos.has(x.grupo)) grupos.set(x.grupo, []); grupos.get(x.grupo).push(x); }
  for (const [grupo, items] of grupos) {
    const sec = document.createElement("section");
    sec.className = "tarjeta si-grupo";
    const h = document.createElement("h3"); h.textContent = grupo; sec.appendChild(h);
    for (const x of items) {
      const p = document.createElement("div");
      p.className = `si-item ${x.nivel}`;
      p.innerHTML = `<span class="si-icono"></span><div class="si-texto"><span class="si-msg"></span></div>`;
      $(".si-icono", p).textContent = ICONO[x.nivel];
      $(".si-msg", p).textContent = x.texto;
      if (x.solucion) { const s = document.createElement("small"); s.textContent = "→ " + x.solucion; $(".si-texto", p).appendChild(s); }
      if (x.seccion) {
        const a = document.createElement("button");
        a.type = "button"; a.className = "enlace"; a.textContent = `MANUAL ${x.seccion}`;
        a.addEventListener("click", () => abrirManual(x.seccion.replace("§", "")));
        $(".si-texto", p).appendChild(a);
      }
      sec.appendChild(p);
    }
    cont.appendChild(sec);
  }
}

function iniciarSistema() {
  $("#si-hw").addEventListener("click", () => cargarSistema(true, true));
  $("#si-recargar").addEventListener("click", () => cargarSistema(si.conHw, true));
}
