// Manual dentro de la interfaz: muestra MANUAL.md (GET /api/manual) con un índice, y abre la
// sección pedida (p. ej. abrirManual("16.5") desde el aviso de error). Incluye los atajos de teclado.
// Markdown mínimo propio (sin dependencias): títulos, párrafos, listas anidadas, tablas, código,
// citas, negrita, cursiva, código en línea y enlaces.
"use strict";

const manual = { html: null, cargando: null };

const escMd = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function enLinea(texto) {
  const codigos = [];
  let s = escMd(texto).replace(/`([^`]+)`/g, (_, c) => { codigos.push(c); return `\u0000${codigos.length - 1}\u0000`; });
  s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\w)/g, "$1<i>$2</i>")
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, t, u) => (u.startsWith("http") ? `<a href="${u}" target="_blank" rel="noopener">${t}</a>` : t));
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codigos[+i]}</code>`);
}

const idSeccion = (titulo) => "man-" + titulo.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
  .replace(/[^a-z0-9.]+/g, "-").replace(/^-|-$/g, "");

function markdownAHtml(md) {
  const lineas = md.replace(/\r/g, "").split("\n");
  const out = [];
  const indice = [];
  let i = 0;
  const listas = [];  // pila de {tipo, sangria}
  const cerrarListas = (hasta = -1) => { while (listas.length && listas.at(-1).sangria > hasta) out.push(`</li></${listas.pop().tipo}>`); };
  while (i < lineas.length) {
    const l = lineas[i];
    if (/^```/.test(l)) {  // bloque de código
      cerrarListas();
      const buf = [];
      for (i++; i < lineas.length && !/^```/.test(lineas[i]); i++) buf.push(escMd(lineas[i]));
      out.push(`<pre><code>${buf.join("\n")}</code></pre>`); i++; continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(l);
    if (h) {
      cerrarListas();
      const nivel = h[1].length, id = idSeccion(h[2]);
      if (nivel <= 3) indice.push({ nivel, id, texto: h[2] });
      out.push(`<h${nivel + 1} id="${id}">${enLinea(h[2])}</h${nivel + 1}>`); i++; continue;
    }
    if (/^\s*\|.*\|\s*$/.test(l)) {  // tabla
      cerrarListas();
      const filas = [];
      for (; i < lineas.length && /^\s*\|.*\|\s*$/.test(lineas[i]); i++) filas.push(lineas[i]);
      const celdas = (f) => f.trim().slice(1, -1).split(/(?<!\\)\|/).map((c) => enLinea(c.trim().replace(/\\\|/g, "|")));
      const cuerpo = filas.filter((f, k) => !(k === 1 && /^[\s|:-]+$/.test(f)));
      out.push("<div class='man-tabla'><table><thead><tr>" + celdas(cuerpo[0]).map((c) => `<th>${c}</th>`).join("") + "</tr></thead><tbody>" +
        cuerpo.slice(1).map((f) => "<tr>" + celdas(f).map((c) => `<td>${c}</td>`).join("") + "</tr>").join("") + "</tbody></table></div>");
      continue;
    }
    const item = /^(\s*)([-*]|\d+\.)\s+(.*)$/.exec(l);
    if (item) {
      const sangria = item[1].length, tipo = /\d/.test(item[2]) ? "ol" : "ul";
      if (!listas.length || sangria > listas.at(-1).sangria) { out.push(`<${tipo}><li>`); listas.push({ tipo, sangria }); }
      else { cerrarListas(sangria); out.push("</li><li>"); }
      out.push(enLinea(item[3])); i++; continue;
    }
    if (/^\s*$/.test(l)) { i++; if (!listas.length) out.push(""); continue; }
    if (listas.length && /^\s+\S/.test(l)) { out.push(" " + enLinea(l.trim())); i++; continue; }  // continuación de un ítem
    cerrarListas();
    if (/^>/.test(l)) {
      const buf = [];
      for (; i < lineas.length && /^>/.test(lineas[i]); i++) buf.push(lineas[i].replace(/^>\s?/, ""));
      out.push(`<blockquote>${enLinea(buf.join(" "))}</blockquote>`); continue;
    }
    if (/^---+\s*$/.test(l)) { out.push("<hr>"); i++; continue; }
    const buf = [];
    for (; i < lineas.length && lineas[i].trim() && !/^(#{1,4}\s|```|\s*\||\s*([-*]|\d+\.)\s|>)/.test(lineas[i]); i++) buf.push(lineas[i].trim());
    out.push(`<p>${enLinea(buf.join(" "))}</p>`);
  }
  cerrarListas();
  return { html: out.join("\n"), indice };
}

async function cargarManual() {
  if (manual.html) return;
  manual.cargando ??= (async () => {
    const r = await fetch("/api/manual");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const { html, indice } = markdownAHtml(await r.text());
    $("#man-contenido").innerHTML = html;
    $("#man-indice").innerHTML = indice.filter((x) => x.nivel <= 2 || /^\d+\.\d+/.test(x.texto))
      .map((x) => `<a href="#${x.id}" class="n${x.nivel}">${enLinea(x.texto)}</a>`).join("");
    for (const a of $$("#man-indice a")) a.addEventListener("click", (e) => { e.preventDefault(); irASeccion(a.getAttribute("href").slice(1)); });
    manual.html = html;
  })();
  await manual.cargando;
}

function irASeccion(id) {
  const destino = document.getElementById(id);
  if (!destino) return;
  destino.scrollIntoView({ block: "start" });
  destino.classList.add("resaltado");
  setTimeout(() => destino.classList.remove("resaltado"), 1600);
}

// abrirManual("16.5") abre la sección cuyo título empieza por ese número
async function abrirManual(seccion) {
  $("#manual").showModal();
  try { await cargarManual(); }
  catch (err) { $("#man-contenido").textContent = t("error_x", { m: err.message }); return; }
  if (seccion) {
    const h = [...$$("#man-contenido h2, #man-contenido h3, #man-contenido h4")]
      .find((x) => x.textContent.trim().startsWith(seccion + " ") || x.textContent.trim().startsWith(seccion + "."));
    if (h) irASeccion(h.id);
  }
}
window.abrirManual = abrirManual;

function buscarEnManual(texto) {
  const q = texto.trim().toLowerCase();
  for (const el of $$("#man-contenido .encontrado")) el.classList.remove("encontrado");
  if (q.length < 3) return;
  const bloques = [...$$("#man-contenido p, #man-contenido li, #man-contenido td, #man-contenido h2, #man-contenido h3, #man-contenido h4")];
  const hallados = bloques.filter((b) => b.textContent.toLowerCase().includes(q));
  hallados.forEach((b) => b.classList.add("encontrado"));
  $("#man-resultados").textContent = hallados.length ? t("man_resultados", { n: hallados.length }) : t("man_sin_resultados");
  hallados[0]?.scrollIntoView({ block: "center" });
}

function iniciarManual() {
  $("#b-manual").addEventListener("click", () => abrirManual());
  let temporizador = null;
  $("#man-buscar").addEventListener("input", (e) => { clearTimeout(temporizador); temporizador = setTimeout(() => buscarEnManual(e.target.value), 250); });
  // «?» (fuera de un campo de texto) abre el manual en los atajos de teclado
  document.addEventListener("keydown", (e) => {
    if (e.key === "?" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName) && !$("#manual").open) {
      e.preventDefault(); abrirManual(); setTimeout(() => irASeccion("man-atajos"), 50);
    }
  });
}
