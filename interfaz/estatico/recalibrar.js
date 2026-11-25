// «Recalibrar con capturas elegidas» (pestaña Calibración): el usuario marca a mano, viendo la
// miniatura de cada una, las poses del
// patrón para calibrar y las de plano/objeto para reconstruir, de cualquier fecha o proceso. Se
// ejecuta con conf.seleccion (el ejecutor la fija como configuración en uso) y calib_poses.
"use strict";

const rc = { datos: null, sel: { patron: new Set(), plano: new Set(), objeto: new Set() }, iniciada: false };
const RC_MIN_PATRON = 6;  // = CALIB_POSES_MIN de configuracion.py

async function cargarRecalibrar() {
  if (!$("#rc").open) return;
  try { rc.datos = await api("/api/archivos"); } catch (err) { $("#rc-grupos").textContent = t("error_x", { m: err.message }); return; }
  if (!rc.iniciada) {  // de entrada: la configuración en uso (lo que se está viendo)
    rc.iniciada = true;
    for (const [cat, poses] of Object.entries(est.poses || {})) {
      for (const p of poses) if (p.absoluta || p.organizada) rc.sel[cat]?.add(p.pose);
    }
  }
  pintarRecalibrar();
}

// Poses organizadas por categoría, agrupadas por proceso (la fecha ayuda a reconocerlas)
function posesPorProceso(cat) {
  const grupos = [];
  for (const p of rc.datos?.procesos || []) {
    const poses = [];
    for (const it of p.items.filter((i) => i.cat === cat)) {
      for (const ps of it.poses.filter((x) => x.organizada)) {
        poses.push({ pose: ps.pose, hora: it.hora, dudosa: it.pureza != null && it.pureza < 0.5, nota: it.nota,
                     procesada: ps.absoluta });
      }
    }
    if (poses.length) grupos.push({ id: p.id, nota: p.nota, poses });
  }
  return grupos.reverse();  // lo más reciente arriba
}

function pintarRecalibrar() {
  const cont = $("#rc-grupos");
  cont.innerHTML = "";
  for (const cat of ["patron", "plano", "objeto"]) {
    const sec = document.createElement("section");
    sec.className = "rc-cat";
    const h = document.createElement("h4");
    h.textContent = t(`rc_cat_${cat}`);
    sec.appendChild(h);
    const grupos = posesPorProceso(cat);
    if (!grupos.length) { const p = document.createElement("p"); p.className = "nota"; p.textContent = t("rc_sin_poses"); sec.appendChild(p); }
    for (const g of grupos) {
      const bloque = document.createElement("div");
      bloque.className = "rc-proceso";
      const todas = g.poses.map((x) => x.pose);
      const marcadas = todas.filter((x) => rc.sel[cat].has(x)).length;
      const cab = document.createElement("label");
      cab.className = "casilla rc-cab";
      cab.innerHTML = `<input type="checkbox"> <b></b> <small></small>`;
      const c = $("input", cab);
      c.checked = marcadas === todas.length; c.indeterminate = marcadas > 0 && marcadas < todas.length;
      c.addEventListener("change", () => { todas.forEach((x) => (c.checked ? rc.sel[cat].add(x) : rc.sel[cat].delete(x))); pintarRecalibrar(); });
      $("b", cab).textContent = fechaHora(g.id);
      $("small", cab).textContent = (g.nota ? g.nota + " · " : "") + t("ar_n_poses", { n: todas.length });
      bloque.appendChild(cab);
      const fila = document.createElement("div");
      fila.className = "rc-poses";
      for (const x of g.poses) {
        const l = document.createElement("label");
        l.className = "rc-pose" + (x.dudosa ? " dudosa" : "") + (rc.sel[cat].has(x.pose) ? " sel" : "");
        l.title = `${x.pose} · ${fechaHora(x.hora)}` + (x.nota ? ` · ${x.nota}` : "") + (x.dudosa ? ` · ${t("rc_dudosa")}` : "") +
          (x.procesada ? "" : ` · ${t("rc_sin_procesar")}`);
        // Miniatura de la imagen blanca de cada pose (patrón, plano u objeto) para reconocerla
        l.innerHTML = `<img loading="lazy" alt=""><input type="checkbox"><span></span>`;
        $("img", l).src = `/api/imagen?cat=${cat}&pose=${x.pose}&tipo=textura&ancho=160`;
        $("img", l).alt = `${cat} ${x.pose}`;
        const ck = $("input", l);
        ck.checked = rc.sel[cat].has(x.pose);
        ck.addEventListener("change", () => { if (ck.checked) rc.sel[cat].add(x.pose); else rc.sel[cat].delete(x.pose); pintarRecalibrar(); });
        $("span", l).textContent = x.pose.replace("pose_", "") + (x.dudosa ? " ⚠" : "");
        fila.appendChild(l);
      }
      bloque.appendChild(fila);
      sec.appendChild(bloque);
    }
    cont.appendChild(sec);
  }
  pintarResumenRc();
}

function pintarResumenRc() {
  const n = { patron: rc.sel.patron.size, plano: rc.sel.plano.size, objeto: rc.sel.objeto.size };
  const partes = [];
  if (n.patron) partes.push(t("rc_calibrar_con", { n: n.patron }));
  else partes.push(t("rc_sin_calibrar"));
  if (n.plano + n.objeto) partes.push(t("rc_reconstruir", { p: n.plano, o: n.objeto }));
  const avisos = [];
  if (n.patron && n.patron < RC_MIN_PATRON) avisos.push(t("rc_pocas", { n: RC_MIN_PATRON }));
  const dudosas = posesPorProceso("patron").flatMap((g) => g.poses).filter((x) => x.dudosa && rc.sel.patron.has(x.pose)).length;
  if (dudosas) avisos.push(t("rc_dudosas", { n: dudosas }));
  $("#rc-resumen").textContent = partes.join(" · ") + (avisos.length ? " — ⚠ " + avisos.join(" ") : "");
  $("#rc-resumen").classList.toggle("aviso", avisos.length > 0);
  $("#rc-resumen-corto").textContent = t("rc_corto", n);
  $("#rc-ejecutar").disabled = est.ejec.ejecutando || (!n.patron && !n.plano && !n.objeto) || (n.patron > 0 && n.patron < 3);
}

function ejecutarRecalibracion() {
  const sel = Object.fromEntries(Object.entries(rc.sel).map(([c, s]) => [c, [...s].sort()]));
  const calibrar = sel.patron.length > 0, reconstruir = sel.plano.length + sel.objeto.length > 0;
  if (calibrar && sel.patron.length < RC_MIN_PATRON && !confirm(t("rc_confirmar_pocas", { n: sel.patron.length }))) return;
  ejecutar({
    etapas: { patrones: false, lightcrafter: false, captura: false, organizar: false, fase_relativa: true,
              fase_absoluta: true, calibracion: calibrar, reconstruccion: reconstruir },
    categorias: ["plano", "objeto"].filter((c) => sel[c].length),
    seleccion: sel,
    calib_poses: sel.patron,
    rehacer: false, fase: $("#a-fase").value, calibracion: $("#a-calib").value, ajustes: ajustesParaEnviar(),
  });
  $("#registro").scrollIntoView({ block: "nearest" });
}

function iniciarRecalibrar() {
  $("#rc").addEventListener("toggle", cargarRecalibrar);
  $("#rc-ejecutar").addEventListener("click", ejecutarRecalibracion);
  $("#rc-limpiar").addEventListener("click", () => { for (const s of Object.values(rc.sel)) s.clear(); pintarRecalibrar(); });
}
