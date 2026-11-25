// Visor de imágenes a pantalla completa y explorador «carpetas → miniaturas».
// Lo usan la pestaña Imágenes (imágenes organizadas de una pose), Archivos (imágenes crudas de una
// captura) y Calibración (imágenes del patrón de una calibración).
"use strict";

// ============================== visor ==============================
const visorImg = { lista: [], i: 0, foco: null };

// lista: [{url, titulo}] (url de la imagen grande)
function abrirVisor(lista, i = 0) {
  if (!lista.length) return;
  visorImg.lista = lista;
  visorImg.foco = document.activeElement;
  $("#visor-img").hidden = false;
  document.body.classList.add("sin-scroll");
  mostrarEnVisor(i);
  $("#vi-cerrar").focus();
}

function mostrarEnVisor(i) {
  const n = visorImg.lista.length;
  visorImg.i = (i + n) % n;
  const it = visorImg.lista[visorImg.i];
  $("#vi-img").src = it.url;
  $("#vi-img").alt = it.titulo || "";
  $("#vi-titulo").textContent = it.titulo || "";
  $("#vi-contador").textContent = `${visorImg.i + 1} / ${n}`;
  $("#vi-ant").hidden = $("#vi-sig").hidden = n < 2;
  // Precarga de las vecinas: al pasar con las flechas la imagen ya está
  for (const d of [1, -1]) if (n > 1) new Image().src = visorImg.lista[(visorImg.i + d + n) % n].url;
}

function cerrarVisor() {
  if ($("#visor-img").hidden) return false;
  $("#visor-img").hidden = true;
  $("#vi-img").removeAttribute("src");
  document.body.classList.remove("sin-scroll");
  visorImg.foco?.focus?.();
  return true;
}

function iniciarVisor() {
  $("#vi-ant").addEventListener("click", () => mostrarEnVisor(visorImg.i - 1));
  $("#vi-sig").addEventListener("click", () => mostrarEnVisor(visorImg.i + 1));
  $("#vi-cerrar").addEventListener("click", cerrarVisor);
  $("#visor-img").addEventListener("click", (e) => { if (e.target.id === "visor-img") cerrarVisor(); });
  document.addEventListener("keydown", (e) => {
    if ($("#visor-img").hidden) return;
    if (e.key === "Escape") { cerrarVisor(); e.stopImmediatePropagation(); }
    else if (e.key === "ArrowLeft") mostrarEnVisor(visorImg.i - 1);
    else if (e.key === "ArrowRight") mostrarEnVisor(visorImg.i + 1);
  }, true);
}

// ============================== explorador ==============================
// carpetas: [{id, nombre, detalle?, portada (url miniatura), items: [{mini, url, titulo}] | () => Promise<[...]>}]
// La carpeta abierta se recuerda en el contenedor, así que al cambiar de pose se queda dentro.
function pintarExplorador(cont, carpetas, { raiz, vacio } = {}) {
  cont.innerHTML = "";
  if (!carpetas.length) {
    const p = document.createElement("p");
    p.className = "ec-vacio";
    p.textContent = vacio || t("no_disponible");
    cont.appendChild(p);
    return;
  }
  const abierta = carpetas.find((c) => c.id === cont.dataset.abierta);
  if (abierta) return pintarCarpeta(cont, abierta, carpetas, { raiz, vacio });
  delete cont.dataset.abierta;
  const rejilla = document.createElement("div");
  rejilla.className = "carpetas";
  for (const c of carpetas) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "carpeta";
    b.innerHTML = `<span class="carpeta-portada"><img loading="lazy" alt=""><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 3A1.5 1.5 0 0 1 3 1.5h3.2l1.5 1.8H13A1.5 1.5 0 0 1 14.5 4.8v7.7A1.5 1.5 0 0 1 13 14H3a1.5 1.5 0 0 1-1.5-1.5Z"/></svg></span><span class="carpeta-nombre"></span><small></small>`;
    if (c.portada) $("img", b).src = c.portada; else $("img", b).remove();
    $(".carpeta-nombre", b).textContent = c.nombre;
    $("small", b).textContent = c.detalle || "";
    b.addEventListener("click", () => { cont.dataset.abierta = c.id; pintarCarpeta(cont, c, carpetas, { raiz, vacio }); });
    rejilla.appendChild(b);
  }
  cont.appendChild(rejilla);
}

async function pintarCarpeta(cont, c, carpetas, opciones) {
  cont.innerHTML = "";
  const miga = document.createElement("nav");
  miga.className = "miga";
  const volver = document.createElement("button");
  volver.type = "button";
  volver.textContent = `← ${opciones.raiz || t("volver")}`;
  volver.addEventListener("click", () => { delete cont.dataset.abierta; pintarExplorador(cont, carpetas, opciones); });
  const titulo = document.createElement("b");
  titulo.textContent = c.nombre;
  miga.append(volver, titulo);
  cont.appendChild(miga);
  const rejilla = document.createElement("div");
  rejilla.className = "miniaturas";
  rejilla.textContent = t("cargando");
  cont.appendChild(rejilla);
  let items;
  try { items = typeof c.items === "function" ? await c.items() : c.items; }
  catch (err) { rejilla.textContent = t("error_x", { m: err.message }); return; }
  if (cont.dataset.abierta !== c.id) return;  // se cambió de carpeta mientras cargaba
  rejilla.textContent = "";
  if (!items.length) { rejilla.textContent = opciones.vacio || t("no_disponible"); return; }
  items.forEach((it, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "mini";
    b.innerHTML = `<img loading="lazy" alt=""><span></span>`;
    $("img", b).src = it.mini;
    $("img", b).alt = it.titulo;
    $("span", b).textContent = it.titulo;
    b.addEventListener("click", () => abrirVisor(items, i));
    rejilla.appendChild(b);
  });
}

// ============================== Imágenes de una pose organizada ==============================
// Cada orientación tiene 18 corrimientos, 6 bits Gray, negro y blanco (P18_F00 … F25)
function carpetasDePose(cat, pose, v) {
  const n = est.config?.parametros?.PERIODO ?? 18, b = est.config?.parametros?.N_BITS_GRAY ?? 6;
  const url = (o, i, ancho) => `/api/imagen?cat=${cat}&pose=${pose}&tipo=img_${o}_${String(i).padStart(2, "0")}&ancho=${ancho}&v=${v}`;
  const item = (o, i, titulo) => ({ mini: url(o, i, 360), url: url(o, i, 1600), titulo });
  const rango = (a, k) => Array.from({ length: k }, (_, j) => a + j);
  const desfase = (k) => Math.round(360 * k / n);
  return [
    { id: "franjas_V", nombre: t("car_franjas_V"), portada: url("V", 0, 360), detalle: t("car_n_imagenes", { n }),
      items: rango(0, n).map((k) => item("V", k, t("car_paso", { k, g: desfase(k) }))) },
    { id: "franjas_H", nombre: t("car_franjas_H"), portada: url("H", 0, 360), detalle: t("car_n_imagenes", { n }),
      items: rango(0, n).map((k) => item("H", k, t("car_paso", { k, g: desfase(k) }))) },
    { id: "gray_V", nombre: t("car_gray_V"), portada: url("V", n + 2, 360), detalle: t("car_n_imagenes", { n: b }),
      items: rango(0, b).map((k) => item("V", n + k, t("car_bit", { k: k + 1, n: b }))) },
    { id: "gray_H", nombre: t("car_gray_H"), portada: url("H", n + 2, 360), detalle: t("car_n_imagenes", { n: b }),
      items: rango(0, b).map((k) => item("H", n + k, t("car_bit", { k: k + 1, n: b }))) },
    // Un solo negro y un solo blanco por ciclo: organizar los copia en H/ y en V/ (son idénticos)
    { id: "referencia", nombre: t("car_referencia"), portada: url("H", n + b + 1, 360), detalle: t("car_n_imagenes", { n: 2 }),
      items: [item("H", n + b, t("car_negro")), item("H", n + b + 1, t("car_blanco"))] },
  ];
}

function cargarCarpetasPose() {
  const cont = $("#carpetas-pose");
  const p = infoPose();
  const carpetas = est.pose && p?.organizada ? carpetasDePose(est.cat, est.pose, version("organizada")) : [];
  const clave = `${est.cat}/${est.pose}/${version("organizada")}/${IDIOMA}/${!!p?.organizada}`;
  if (cont.dataset.clave === clave && cont.childElementCount) return;
  cont.dataset.clave = clave;
  pintarExplorador(cont, carpetas, { raiz: t("paso_captura"), vacio: est.pose ? t("falta_organizada") : t("sin_poses_cat") });
}

// Imágenes crudas de una captura (pestaña Archivos)
async function itemsDeCaptura(carpeta) {
  const nombres = await api(`/api/captura/lista?carpeta=${encodeURIComponent(carpeta)}`);
  const url = (i, ancho) => `/api/captura/imagen?carpeta=${encodeURIComponent(carpeta)}&i=${i}&ancho=${ancho}`;
  return nombres.map((nombre, i) => ({ mini: url(i, 320), url: url(i, 1600), titulo: nombre }));
}
