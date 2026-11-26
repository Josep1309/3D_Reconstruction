// Visor de nubes de puntos en WebGL, sin dependencias (funciona sin internet).
// Coordenadas de entrada: sistema de la cámara en mm (X derecha, Y abajo, Z hacia la escena).
// Controles: arrastrar = girar, clic derecho / Shift + arrastrar = desplazar, rueda = acercar,
// doble clic = vista inicial. En pantallas táctiles: un dedo gira, dos dedos acercan.
"use strict";

class VisorNube {
  constructor(canvas) {
    this.canvas = canvas;
    const gl = canvas.getContext("webgl", { antialias: false, preserveDrawingBuffer: false });
    if (!gl) throw new Error(window.t ? t("webgl_no") : "WebGL no disponible");
    this.gl = gl;
    this.n = 0;
    this.tamano = 2;
    this.modoColor = "profundidad";
    this._programa();
    this.bPos = gl.createBuffer();
    this.bCol = gl.createBuffer();
    this._eventos();
    new ResizeObserver(() => this.dibujar()).observe(canvas);
  }

  _programa() {
    const gl = this.gl;
    const vs = `
      attribute vec3 pos; attribute vec3 col;
      uniform mat4 mvp; uniform float tam;
      varying vec3 vCol;
      void main() { gl_Position = mvp * vec4(pos, 1.0); gl_PointSize = tam; vCol = col; }`;
    const fs = `
      precision mediump float; varying vec3 vCol;
      void main() { gl_FragColor = vec4(vCol, 1.0); }`;
    const compilar = (tipo, fuente) => {
      const s = gl.createShader(tipo);
      gl.shaderSource(s, fuente);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    };
    const p = gl.createProgram();
    gl.attachShader(p, compilar(gl.VERTEX_SHADER, vs));
    gl.attachShader(p, compilar(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    this.prog = p;
    this.aPos = gl.getAttribLocation(p, "pos");
    this.aCol = gl.getAttribLocation(p, "col");
    this.uMvp = gl.getUniformLocation(p, "mvp");
    this.uTam = gl.getUniformLocation(p, "tam");
  }

  // datos: ArrayBuffer con uint32 N | float32 xyz*N | uint8 gris*N [| uint32 alto, ancho, índice*N]
  // centro: [x, y, z] común a varios visores (comparar métodos); si no, la mediana de esta nube
  cargar(buffer, conIndices = false, centro = null) {
    const n = new DataView(buffer).getUint32(0, true);
    const xyz = new Float32Array(buffer, 4, n * 3);
    this.gris = new Uint8Array(buffer, 4 + n * 12, n);
    this.n = n;
    this.xyz = xyz;  // coordenadas originales (mm), para medir
    this.indices = null;
    if (conIndices) {  // el bloque no queda alineado a 4 bytes: se copia
      const ini = 4 + n * 13;
      const cab = new Uint32Array(buffer.slice(ini, ini + 8));
      this.forma = [cab[0], cab[1]];
      this.indices = new Uint32Array(buffer.slice(ini + 8, ini + 8 + n * 4));
    }
    // Centro y escala robustos (percentiles) para no depender de puntos atípicos
    const muestra = (eje) => {
      const v = [];
      const paso = Math.max(1, Math.floor(n / 20000));
      for (let i = 0; i < n; i += paso) v.push(xyz[i * 3 + eje]);
      v.sort((a, b) => a - b);
      return [v[Math.floor(v.length * 0.01)], v[Math.floor(v.length * 0.5)], v[Math.floor(v.length * 0.99)]];
    };
    const [x1, xm, x9] = muestra(0), [y1, ym, y9] = muestra(1), [z1, zm, z9] = muestra(2);
    this.centro = centro || [xm, ym, zm];
    const [cx0, cy0, cz0] = this.centro;
    this.zRango = [z1, z9];
    this.radio = Math.max(x9 - x1, y9 - y1, z9 - z1, 1) * 0.6;
    // Posiciones centradas (mejor precisión en float32 de la GPU)
    const pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      pos[i * 3] = xyz[i * 3] - cx0;
      pos[i * 3 + 1] = xyz[i * 3 + 1] - cy0;
      pos[i * 3 + 2] = xyz[i * 3 + 2] - cz0;
    }
    this.z = new Float32Array(n);
    for (let i = 0; i < n; i++) this.z[i] = xyz[i * 3 + 2];
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.bPos);
    gl.bufferData(gl.ARRAY_BUFFER, pos, gl.STATIC_DRAW);
    this._colores();
    this.reiniciar();
  }

  vaciar() { this.n = 0; this.dibujar(); }

  _colores() {
    if (!this.n) return;
    const n = this.n, col = new Float32Array(n * 3);
    if (this.modoColor === "vista" && this.etiquetas) {  // escaneo 360: un color por vista
      for (let i = 0; i < n; i++) {
        const c = COLORES_VISTA[this.etiquetas[i] % COLORES_VISTA.length];
        col[i * 3] = c[0]; col[i * 3 + 1] = c[1]; col[i * 3 + 2] = c[2];
      }
    } else if (this.modoColor === "textura") {
      for (let i = 0; i < n; i++) { const g = this.gris[i] / 255; col[i * 3] = col[i * 3 + 1] = col[i * 3 + 2] = g; }
    } else {
      const [lo, hi] = this.zRango, esc = 1 / Math.max(hi - lo, 1e-6);
      for (let i = 0; i < n; i++) {
        // Más cerca de la cámara = amarillo, más lejos = violeta (como en las figuras de profundidad)
        const t = 1 - Math.min(1, Math.max(0, (this.z[i] - lo) * esc));
        const c = viridis(t);
        col[i * 3] = c[0]; col[i * 3 + 1] = c[1]; col[i * 3 + 2] = c[2];
      }
    }
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.bCol);
    gl.bufferData(gl.ARRAY_BUFFER, col, gl.STATIC_DRAW);
  }

  setColor(modo) { this.modoColor = modo; this._colores(); this.dibujar(); }
  setEtiquetas(etiquetas) { this.etiquetas = etiquetas; this._colores(); this.dibujar(); }
  setTamano(t) { this.tamano = t; this.dibujar(); }

  // Vista inicial: desde la cámara (mirando +Z, con Y hacia abajo), algo inclinada
  reiniciar() {
    this.yaw = 0.35; this.pitch = -0.35; this.dist = this.radio ? this.radio * 2.6 : 500;
    this.pan = [0, 0, 0];
    this.dibujar();
    this.alMover?.();
  }

  // Vista (cámara virtual) para copiarla a otro visor
  get vista() { return { yaw: this.yaw, pitch: this.pitch, dist: this.dist, pan: [...this.pan] }; }
  set vista(v) { Object.assign(this, { yaw: v.yaw, pitch: v.pitch, dist: v.dist, pan: [...v.pan] }); this.dibujar(); }

  _matriz() {
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    const persp = perspectiva(45 * Math.PI / 180, w / Math.max(h, 1), this.dist * 0.01, this.dist * 10);
    // Órbita alrededor del objetivo. La "cámara virtual" empieza detrás de la cámara real
    // (en −Z) con el vector arriba = −Y, como la imagen original.
    const cy = Math.cos(this.yaw), sy = Math.sin(this.yaw), cp = Math.cos(this.pitch), sp = Math.sin(this.pitch);
    const dir = [sy * cp, sp, -cy * cp];  // del objetivo hacia el ojo
    const obj = this.pan;
    const ojo = [obj[0] + dir[0] * this.dist, obj[1] + dir[1] * this.dist, obj[2] + dir[2] * this.dist];
    return multiplicar(persp, mirarA(ojo, obj, [0, -1, 0]));
  }

  dibujar() {
    if (this._pendiente) return;
    this._pendiente = true;
    requestAnimationFrame(() => {
      this._pendiente = false;
      const gl = this.gl, c = this.canvas, dpr = window.devicePixelRatio || 1;
      const w = Math.round(c.clientWidth * dpr), h = Math.round(c.clientHeight * dpr);
      if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
      gl.viewport(0, 0, w, h);
      gl.clearColor(0.07, 0.067, 0.063, 1);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      if (!this.n) return;
      gl.enable(gl.DEPTH_TEST);
      gl.useProgram(this.prog);
      gl.uniformMatrix4fv(this.uMvp, false, this._matriz());
      gl.uniform1f(this.uTam, this.tamano * dpr);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.bPos);
      gl.enableVertexAttribArray(this.aPos);
      gl.vertexAttribPointer(this.aPos, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.bCol);
      gl.enableVertexAttribArray(this.aCol);
      gl.vertexAttribPointer(this.aCol, 3, gl.FLOAT, false, 0, 0);
      gl.drawArrays(gl.POINTS, 0, this.n);
      this.alDibujar?.();
    });
  }

  // Posición en pantalla (px CSS dentro del lienzo) de un punto en mm; null si queda detrás
  proyectar(p, mvp = this._matriz()) {
    const x = p[0] - this.centro[0], y = p[1] - this.centro[1], z = p[2] - this.centro[2];
    const cw = mvp[3] * x + mvp[7] * y + mvp[11] * z + mvp[15];
    if (cw <= 0) return null;
    const cx = (mvp[0] * x + mvp[4] * y + mvp[8] * z + mvp[12]) / cw;
    const cy = (mvp[1] * x + mvp[5] * y + mvp[9] * z + mvp[13]) / cw;
    return [(cx + 1) / 2 * this.canvas.clientWidth, (1 - cy) / 2 * this.canvas.clientHeight];
  }

  // Punto de la nube bajo el cursor: entre los que caen a menos de `radio` px, el más cercano a
  // la cámara virtual (el que se ve delante). Devuelve su índice en la nube o -1.
  elegir(clientX, clientY, radio = 7) {
    if (!this.n) return -1;
    const r = this.canvas.getBoundingClientRect();
    const px = clientX - r.left, py = clientY - r.top, w = r.width, h = r.height;
    const m = this._matriz(), [c0, c1, c2] = this.centro, xyz = this.xyz;
    const r2 = radio * radio, tol = this.dist * 0.01;
    let mejor = -1, mejorProf = Infinity, mejorD = Infinity;
    for (let i = 0; i < this.n; i++) {
      const x = xyz[i * 3] - c0, y = xyz[i * 3 + 1] - c1, z = xyz[i * 3 + 2] - c2;
      const cw = m[3] * x + m[7] * y + m[11] * z + m[15];
      if (cw <= 0) continue;
      const sx = ((m[0] * x + m[4] * y + m[8] * z + m[12]) / cw + 1) / 2 * w;
      const sy = (1 - (m[1] * x + m[5] * y + m[9] * z + m[13]) / cw) / 2 * h;
      const d2 = (sx - px) ** 2 + (sy - py) ** 2;
      if (d2 > r2) continue;
      // el de delante gana; a igual profundidad (±1 % de la distancia), el más cercano al cursor
      if (cw < mejorProf - tol || (Math.abs(cw - mejorProf) <= tol && d2 < mejorD)) {
        mejor = i; mejorProf = Math.min(cw, mejorProf); mejorD = d2;
      }
    }
    return mejor;
  }

  punto(i) { return [this.xyz[i * 3], this.xyz[i * 3 + 1], this.xyz[i * 3 + 2]]; }

  _desplazar(dx, dy) {
    // Desplaza el objetivo en el plano de la pantalla
    const cy = Math.cos(this.yaw), sy = Math.sin(this.yaw), cp = Math.cos(this.pitch), sp = Math.sin(this.pitch);
    const dir = [sy * cp, sp, -cy * cp];
    const der = normalizar(cruz([0, -1, 0], dir));
    const arr = cruz(dir, der);
    const k = this.dist * 0.0015;
    for (let i = 0; i < 3; i++) this.pan[i] += (-dx * der[i] + dy * arr[i]) * k;
  }

  _eventos() {
    const c = this.canvas;
    let previo = null, modo = null;
    const toques = new Map();
    c.addEventListener("contextmenu", (e) => e.preventDefault());
    let inicio = null;
    c.addEventListener("pointerdown", (e) => {
      c.setPointerCapture(e.pointerId);
      inicio = [e.clientX, e.clientY, e.button, e.shiftKey];
      toques.set(e.pointerId, [e.clientX, e.clientY]);
      previo = [e.clientX, e.clientY];
      modo = (e.button === 2 || e.shiftKey) ? "pan" : "girar";
    });
    c.addEventListener("pointermove", (e) => {
      if (!toques.has(e.pointerId)) return;
      if (toques.size === 2) {  // pellizco
        const [a, b] = [...toques.values()];
        const d0 = Math.hypot(a[0] - b[0], a[1] - b[1]);
        toques.set(e.pointerId, [e.clientX, e.clientY]);
        const [a2, b2] = [...toques.values()];
        const d1 = Math.hypot(a2[0] - b2[0], a2[1] - b2[1]);
        if (d0 > 0 && d1 > 0) { this.dist *= d0 / d1; this.dibujar(); }
        return;
      }
      toques.set(e.pointerId, [e.clientX, e.clientY]);
      const dx = e.clientX - previo[0], dy = e.clientY - previo[1];
      previo = [e.clientX, e.clientY];
      if (modo === "pan") this._desplazar(dx, dy);
      else {
        this.yaw += dx * 0.008;
        this.pitch = Math.max(-1.5, Math.min(1.5, this.pitch + dy * 0.008));
      }
      this.dibujar();
      this.alMover?.();
    });
    const soltar = (e) => { toques.delete(e.pointerId); if (!toques.size) previo = null; };
    c.addEventListener("pointerup", (e) => {
      // clic sin arrastrar (botón izquierdo): la pestaña Medición lo usa para elegir puntos
      if (inicio && inicio[2] === 0 && !inicio[3] && Math.hypot(e.clientX - inicio[0], e.clientY - inicio[1]) < 4) this.alClic?.(e);
      inicio = null;
      soltar(e);
    });
    c.addEventListener("pointercancel", soltar);
    c.addEventListener("wheel", (e) => {
      e.preventDefault();
      this.dist *= Math.exp(e.deltaY * 0.0012);
      this.dibujar();
      this.alMover?.();
    }, { passive: false });
    c.addEventListener("dblclick", () => { if (!this.sinDobleClic) this.reiniciar(); });
  }
}

// ---------- álgebra mínima (matrices 4x4 en orden de columnas, como WebGL) ----------
function perspectiva(fovy, aspecto, cerca, lejos) {
  const f = 1 / Math.tan(fovy / 2), nf = 1 / (cerca - lejos);
  return new Float32Array([f / aspecto, 0, 0, 0, 0, f, 0, 0, 0, 0, (lejos + cerca) * nf, -1, 0, 0, 2 * lejos * cerca * nf, 0]);
}
function cruz(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function normalizar(v) { const l = Math.hypot(...v) || 1; return v.map((x) => x / l); }
function mirarA(ojo, obj, arriba) {
  const z = normalizar([ojo[0] - obj[0], ojo[1] - obj[1], ojo[2] - obj[2]]);
  const x = normalizar(cruz(arriba, z));
  const y = cruz(z, x);
  const t = (v) => -(v[0] * ojo[0] + v[1] * ojo[1] + v[2] * ojo[2]);
  return new Float32Array([x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, t(x), t(y), t(z), 1]);
}
function multiplicar(a, b) {
  const r = new Float32Array(16);
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) {
    let s = 0;
    for (let k = 0; k < 4; k++) s += a[k * 4 + j] * b[i * 4 + k];
    r[i * 4 + j] = s;
  }
  return r;
}
// Colores de las vistas de un escaneo 360 (distinguibles entre sí, en claro y oscuro)
const COLORES_VISTA = [[0.31, 0.6, 0.98], [0.98, 0.55, 0.16], [0.3, 0.8, 0.4], [0.93, 0.3, 0.35], [0.7, 0.5, 0.95],
  [0.95, 0.85, 0.25], [0.3, 0.85, 0.85], [0.95, 0.5, 0.8], [0.6, 0.6, 0.6], [0.6, 0.85, 0.2], [0.55, 0.35, 0.2], [0.2, 0.4, 0.75]];
window.COLORES_VISTA = COLORES_VISTA;
// Mapa de color viridis aproximado por tramos (t en [0, 1])
const VIRIDIS = [[0.267, 0.005, 0.329], [0.229, 0.322, 0.546], [0.128, 0.567, 0.551], [0.369, 0.789, 0.383], [0.993, 0.906, 0.144]];
function viridis(t) {
  const x = t * (VIRIDIS.length - 1), i = Math.min(Math.floor(x), VIRIDIS.length - 2), f = x - i;
  const a = VIRIDIS[i], b = VIRIDIS[i + 1];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

window.VisorNube = VisorNube;
