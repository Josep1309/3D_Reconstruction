"""Escaneo 360: une varias vistas (poses) del mismo objeto en una sola nube de puntos.

Cada pose es una vista del objeto (apoyado en otra cara, girado…). Para unirlas:

1. **Por pares, automático por textura:** puntos SIFT en la imagen blanca de cada vista, emparejados
   entre las dos vistas. Cada píxel tiene su X, Y, Z (la reconstrucción), así que cada pareja da dos
   puntos 3D. Con RANSAC se busca el movimiento rígido (giro + traslación) que más parejas explica.
2. **Por pares, manual:** si el objeto no tiene textura o las vistas comparten poca superficie, el
   usuario marca 3 o más puntos en común (pestaña 360°) y de ahí sale el movimiento.
3. **Ajuste fino (ICP punto a plano)** de cada par aceptado: acerca las dos nubes punto a punto.
4. **Global:** se arma un árbol con los mejores pares a partir de la vista de referencia (la
   primera) y luego cada vista se ajusta contra todas las demás ya ubicadas, varias vueltas, para
   repartir el error (al dar la vuelta completa la última vista debe calzar con la primera).
5. **Fusión:** todas las vistas en el sistema de la de referencia, promediadas en una rejilla de
   vóxeles. Se guarda en resultados/escaneos/<nombre>/: nube.ply, nube.npz (xyz, gris, vista) y
   escaneo.json (vistas, pares, transformaciones y calidad).

Uso: `.env/bin/python -m procesamiento.escaneo --nombre cilindro --poses pose_18 pose_19 pose_20`
o la pestaña 360° de la interfaz.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from datos_sistema import configuracion as cfg
from datos_sistema import avance, rutas

DIR_ESCANEOS = cfg.DIR_RESULTADOS / "escaneos"
CAT = "objeto"

# Parámetros (mm salvo indicación)
RANSAC_UMBRAL_MM = 2.5        # distancia para contar una pareja como «explicada» por el movimiento
RANSAC_ITER = 3000
MIN_INLIERS = 12              # parejas de textura mínimas para aceptar un par
ICP_DIST_INI_MM = 6.0         # correspondencias ICP: se empieza tolerante…
ICP_DIST_FIN_MM = 1.5         # …y se termina estricto
ICP_ITER = 40
MIN_SOLAPE = 0.08             # fracción mínima de una vista que debe calzar con la otra
PASO_ICP = 4                  # una de cada 4 filas/columnas para ICP (~1/16 de los puntos)
VOXEL_MM = 0.3                # tamaño de la rejilla de fusión


# ------------------------------------------------------------------ vistas
@dataclass
class Vista:
    pose: str
    mapa: np.ndarray              # (alto, ancho, 3) X, Y, Z en mm; NaN fuera
    m: np.ndarray                 # puntos válidos
    tex: np.ndarray               # imagen blanca (uint8)
    pts: np.ndarray = field(default=None)    # submuestra para ICP (n, 3)
    nor: np.ndarray = field(default=None)    # normales de la submuestra (n, 3)
    nmap: np.ndarray = field(default=None)   # normal de cada píxel (alto, ancho, 3)


def cargar_vista(pose: str, cat: str = CAT) -> Vista:
    from procesamiento import fase, reconstruccion_3d as r3d

    r = r3d.cargar_reconstruccion_pose(rutas.reconstruccion(cat, pose))
    m = r["Mask"].astype(bool) & np.isfinite(r["Z"])
    mapa = np.stack([r["X"], r["Y"], r["Z"]], axis=-1).astype(np.float32)
    mapa[~m] = np.nan
    tex = fase.cargar_fases_pose(rutas.fase_absoluta(cat, pose))["Itex"]
    v = Vista(pose, mapa, m, tex)
    v.pts, v.nor = _submuestra_con_normales(mapa, m, PASO_ICP)
    v.nmap = _mapa_normales(mapa)
    return v


def _mapa_normales(mapa: np.ndarray, s: int = 2) -> np.ndarray:
    """Normal de cada píxel (diferencias centradas a ±s px), orientada hacia la cámara."""
    dx = np.full_like(mapa, np.nan)
    dy = np.full_like(mapa, np.nan)
    dx[:, s:-s] = mapa[:, 2 * s:] - mapa[:, :-2 * s]
    dy[s:-s] = mapa[2 * s:] - mapa[:-2 * s]
    n = np.cross(dx, dy)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
    n[np.einsum("ijk,ijk->ij", np.nan_to_num(mapa), np.nan_to_num(n)) > 0] *= -1
    return n.astype(np.float32)


_CAMARA: dict = {}


def camara() -> tuple[np.ndarray, np.ndarray]:
    """Matriz y distorsión de la cámara (de la calibración en uso), para proyectar puntos."""
    ruta = cfg.DIR_CALIBRACION / "Estereo_TSC_0_2.npz"
    clave = (str(ruta), ruta.stat().st_mtime_ns)
    if _CAMARA.get("clave") != clave:
        with np.load(ruta) as d:
            _CAMARA.update(clave=clave, K=np.asarray(d["Ac"], np.float64), dist=np.asarray(d["dist_cam"], np.float64).ravel())
    return _CAMARA["K"], _CAMARA["dist"]


def _submuestra_con_normales(mapa: np.ndarray, m: np.ndarray, paso: int) -> tuple[np.ndarray, np.ndarray]:
    """Puntos cada `paso` px y su normal, calculada en la rejilla de la cámara (vecinos ±paso)."""
    s = paso
    c = mapa[s:-s:s, s:-s:s]
    dx = mapa[s:-s:s, 2 * s::s][:, : c.shape[1]] - mapa[s:-s:s, : -2 * s : s][:, : c.shape[1]]
    dy = mapa[2 * s::s, s:-s:s][: c.shape[0]] - mapa[: -2 * s : s, s:-s:s][: c.shape[0]]
    n = np.cross(dx, dy)
    largo = np.linalg.norm(n, axis=-1, keepdims=True)
    n = n / np.maximum(largo, 1e-9)
    ok = m[s:-s:s, s:-s:s] & np.all(np.isfinite(n), axis=-1) & (largo[..., 0] > 0)
    # que la normal mire hacia la cámara (origen): -p · n > 0
    pts, nor = c[ok], n[ok]
    nor[np.einsum("ij,ij->i", pts, nor) > 0] *= -1
    return pts.astype(np.float32), nor.astype(np.float32)


# ------------------------------------------------------------------ geometría
def kabsch(a: np.ndarray, b: np.ndarray, w: np.ndarray | None = None) -> np.ndarray:
    """Movimiento rígido T (4x4) que lleva los puntos a sobre b (mínimos cuadrados)."""
    w = np.ones(len(a)) if w is None else w
    ca, cb = np.average(a, axis=0, weights=w), np.average(b, axis=0, weights=w)
    h = ((a - ca) * w[:, None]).T @ (b - cb)
    u, _, vt = np.linalg.svd(h)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    r = vt.T @ np.diag([1, 1, d]) @ u.T
    t = np.eye(4)
    t[:3, :3], t[:3, 3] = r, cb - r @ ca
    return t


def aplicar(t: np.ndarray, p: np.ndarray) -> np.ndarray:
    return p @ t[:3, :3].T + t[:3, 3]


def angulo_grados(t: np.ndarray) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(t[:3, :3]) - 1) / 2))))


def ransac_rigido(a: np.ndarray, b: np.ndarray, umbral: float = RANSAC_UMBRAL_MM, iteraciones: int = RANSAC_ITER,
                  semilla: int = 0) -> tuple[np.ndarray | None, np.ndarray]:
    """Movimiento rígido robusto a parejas equivocadas. Devuelve (T, máscara de inliers)."""
    n = len(a)
    if n < 3:
        return None, np.zeros(n, bool)
    rng = np.random.default_rng(semilla)
    mejor = np.zeros(n, bool)
    for _ in range(iteraciones):
        idx = rng.choice(n, 3, replace=False)
        # tres puntos casi alineados no definen un giro
        if np.linalg.norm(np.cross(a[idx[1]] - a[idx[0]], a[idx[2]] - a[idx[0]])) < 1.0:
            continue
        # un movimiento rígido conserva distancias: descarta tríos inconsistentes sin resolver nada
        da = np.linalg.norm(a[idx] - a[np.roll(idx, 1)], axis=1)
        db = np.linalg.norm(b[idx] - b[np.roll(idx, 1)], axis=1)
        if np.any(np.abs(da - db) > 2 * umbral):
            continue
        t = kabsch(a[idx], b[idx])
        inl = np.linalg.norm(aplicar(t, a) - b, axis=1) < umbral
        if inl.sum() > mejor.sum():
            mejor = inl
    if mejor.sum() < 3:
        return None, mejor
    t = kabsch(a[mejor], b[mejor])
    inl = np.linalg.norm(aplicar(t, a) - b, axis=1) < umbral
    return kabsch(a[inl], b[inl]), inl


def asociar(p: np.ndarray, destinos: list[tuple[np.ndarray, Vista]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Para cada punto p (sistema de referencia), el punto de las vistas destino que la cámara ve
    en esa dirección: se lleva p al sistema de cada vista, se proyecta en su imagen y se lee el
    píxel (asociación proyectiva: mucho más rápida que buscar vecinos en 3D). Si varias vistas lo
    ven, se queda el más cercano. Devuelve (puntos, normales, distancias), en la referencia."""
    k, dist = camara()
    mejor_q = np.full_like(p, np.nan)
    mejor_n = np.full_like(p, np.nan)
    mejor_d = np.full(len(p), np.inf)
    for t, v in destinos:
        r, tr = t[:3, :3], t[:3, 3]
        pq = (p - tr) @ r                       # al sistema de la vista q (inversa de t)
        delante = pq[:, 2] > 1.0
        uv, _ = cv2.projectPoints(pq[delante].reshape(-1, 1, 3), np.zeros(3), np.zeros(3), k, dist)
        uv = np.round(uv.reshape(-1, 2)).astype(np.int64)
        alto, ancho = v.m.shape
        dentro = (uv[:, 0] >= 0) & (uv[:, 0] < ancho) & (uv[:, 1] >= 0) & (uv[:, 1] < alto)
        idx = np.flatnonzero(delante)[dentro]
        f, c = uv[dentro, 1], uv[dentro, 0]
        ok = v.m[f, c] & np.all(np.isfinite(v.nmap[f, c]), axis=1)
        idx, f, c = idx[ok], f[ok], c[ok]
        q = v.mapa[f, c] @ r.T + tr
        n = v.nmap[f, c] @ r.T
        d = np.linalg.norm(q - p[idx], axis=1)
        mejor = d < mejor_d[idx]
        i = idx[mejor]
        mejor_q[i], mejor_n[i], mejor_d[i] = q[mejor], n[mejor], d[mejor]
    return mejor_q, mejor_n, mejor_d


def icp(src: np.ndarray, destinos: list[tuple[np.ndarray, Vista]], t0: np.ndarray,
        iteraciones: int = ICP_ITER) -> tuple[np.ndarray, float, float]:
    """ICP punto a plano: ajusta T para que `src` calce sobre las vistas destino (cada una con su
    T al sistema de referencia). Devuelve (T, error RMS en mm, fracción de src que calza)."""
    t = t0.copy()
    for k in range(iteraciones):
        lim = ICP_DIST_INI_MM + (ICP_DIST_FIN_MM - ICP_DIST_INI_MM) * min(1.0, k / (iteraciones * 0.6))
        p = aplicar(t, src)
        q, n, d = asociar(p, destinos)
        ok = d < lim
        if ok.sum() < 30:
            return t, float("inf"), 0.0
        q, n, ps = q[ok], n[ok], p[ok]
        r = np.einsum("ij,ij->i", ps - q, n)                   # distancia al plano
        a = np.hstack([np.cross(ps, n), n])                     # linealización (giro pequeño)
        x, *_ = np.linalg.lstsq(a, -r, rcond=None)
        w, v = x[:3], x[3:]
        ang = np.linalg.norm(w)
        paso = np.eye(4)
        paso[:3, :3] = cv2.Rodrigues(w.reshape(3, 1))[0] if ang > 0 else np.eye(3)
        paso[:3, 3] = v
        t = paso @ t
        if ang < 1e-6 and np.linalg.norm(v) < 1e-4 and k > iteraciones * 0.6:
            break
    # medida final con el umbral estricto
    _, _, d = asociar(aplicar(t, src), destinos)
    ok = d < ICP_DIST_FIN_MM
    if not ok.any():
        return t, float("inf"), 0.0
    return t, float(np.sqrt(np.mean(d[ok] ** 2))), float(ok.mean())


# ------------------------------------------------------------------ pares
def _rasgos(v: Vista, maximo: int = 6000):
    sift = cv2.SIFT_create(nfeatures=maximo)
    from procesamiento import mascara

    tex = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(v.tex)
    # la silueta con sus agujeritos rellenos (si no, erosionar la máscara la deja casi vacía)
    dentro = cv2.erode(mascara._rellenar_huecos(v.m).astype(np.uint8), np.ones((7, 7), np.uint8))
    kp, desc = sift.detectAndCompute(tex, dentro)
    if desc is None:
        return np.zeros((0, 3), np.float32), None
    xy = np.array([k.pt for k in kp])
    alto, ancho = v.m.shape
    f = np.clip(np.round(xy[:, 1]).astype(int), 0, alto - 1)
    c = np.clip(np.round(xy[:, 0]).astype(int), 0, ancho - 1)
    p3 = v.mapa[f, c].copy()
    # si cae en un agujerito, la mediana de los puntos válidos de su entorno 5x5
    for i in np.flatnonzero(~np.all(np.isfinite(p3), axis=1)):
        ventana = v.mapa[max(f[i] - 2, 0):f[i] + 3, max(c[i] - 2, 0):c[i] + 3].reshape(-1, 3)
        ventana = ventana[np.all(np.isfinite(ventana), axis=1)]
        if len(ventana) >= 3:
            p3[i] = np.median(ventana, axis=0)
    ok = np.all(np.isfinite(p3), axis=1)
    return p3[ok], desc[ok]


def emparejar_textura(a: Vista, b: Vista, rasgos: dict) -> dict:
    """Movimiento de a hacia b por puntos de textura (SIFT + RANSAC). {"T", "inliers", "parejas"}"""
    pa, da = rasgos[a.pose]
    pb, db = rasgos[b.pose]
    if da is None or db is None or len(pa) < 3 or len(pb) < 3:
        return {"T": None, "inliers": 0, "parejas": 0}
    m = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=64))
    ida = m.knnMatch(da, db, k=2)
    idb = {x[0].queryIdx: x[0].trainIdx for x in m.knnMatch(db, da, k=2) if len(x) == 2 and x[0].distance < 0.8 * x[1].distance}
    parejas = [(x[0].queryIdx, x[0].trainIdx) for x in ida
               if len(x) == 2 and x[0].distance < 0.8 * x[1].distance and idb.get(x[0].trainIdx) == x[0].queryIdx]
    if len(parejas) < 3:
        return {"T": None, "inliers": 0, "parejas": len(parejas)}
    ia, ib = np.array(parejas).T
    t, inl = ransac_rigido(pa[ia], pb[ib])
    return {"T": t, "inliers": int(inl.sum()), "parejas": len(parejas)}


def par(a: Vista, b: Vista, rasgos: dict, manual: list | None = None) -> dict:
    """Une la vista a con la b: textura o puntos manuales, y luego ICP. T lleva a hacia b."""
    if manual and len(manual) >= 3:
        pa = np.array([x[0] for x in manual], float)
        pb = np.array([x[1] for x in manual], float)
        t0, metodo, n = kabsch(pa, pb), "manual", len(manual)
    else:
        r = emparejar_textura(a, b, rasgos)
        if r["T"] is None or r["inliers"] < MIN_INLIERS:
            return {"ok": False, "metodo": "textura", "inliers": r["inliers"], "parejas": r["parejas"],
                    "motivo": f"pocos puntos de textura en común ({r['inliers']})"}
        t0, metodo, n = r["T"], "textura", r["inliers"]
    t, rms, solape = icp(a.pts, [(np.eye(4), b)], t0)
    ok = math.isfinite(rms) and solape >= MIN_SOLAPE
    salida = {"ok": ok, "metodo": metodo, "inliers": n, "T": t.tolist(), "rms_mm": rms, "solape": solape,
              "giro_grados": angulo_grados(t)}
    if not ok:
        salida["motivo"] = f"calzan pocas zonas ({100 * solape:.0f} % de la vista)"
    return salida


# ------------------------------------------------------------------ global
def ubicar(poses: list[str], pares: dict[str, dict]) -> dict[str, np.ndarray]:
    """Transformación de cada vista al sistema de la primera, por el árbol de mejores pares (Prim).
    Las vistas que no quedan conectadas no aparecen."""
    ref = poses[0]
    ubicadas = {ref: np.eye(4)}
    aristas = []
    for clave, r in pares.items():
        if r.get("ok"):
            a, b = clave.split("|")
            peso = r["solape"] / max(r["rms_mm"], 0.05)
            t = np.array(r["T"])
            aristas += [(peso, a, b, t), (peso, b, a, np.linalg.inv(t))]  # (de, hacia, T de→hacia)
    while True:
        candidatas = [(p, a, b, t) for p, a, b, t in aristas if a not in ubicadas and b in ubicadas]
        if not candidatas:
            return ubicadas
        _, a, b, t = max(candidatas, key=lambda x: x[0])
        ubicadas[a] = ubicadas[b] @ t  # a -> b -> referencia


def refinar_global(vistas: dict[str, Vista], ubicadas: dict[str, np.ndarray], vueltas: int = 3) -> dict[str, dict]:
    """Ajusta cada vista contra todas las demás ya ubicadas (reparte el error del lazo)."""
    calidad = {}
    poses = list(ubicadas)
    for vuelta in range(vueltas):
        for i, p in enumerate(poses[1:], 1):
            destinos = [(ubicadas[q], vistas[q]) for q in poses if q != p]
            t, rms, solape = icp(vistas[p].pts, destinos, ubicadas[p], iteraciones=15)
            if math.isfinite(rms) and solape >= MIN_SOLAPE:
                ubicadas[p] = t
            calidad[p] = {"rms_mm": rms, "solape": solape}
            avance.contador(vuelta * len(poses) + i, vueltas * len(poses), f"Ajuste global: vuelta {vuelta + 1} de {vueltas}, {p}")
    return calidad


def fusionar(vistas: dict[str, Vista], ubicadas: dict[str, np.ndarray], voxel: float = VOXEL_MM):
    """Todas las vistas en el sistema de la referencia, promediadas por vóxel."""
    xyz, gris, vista = [], [], []
    for k, (p, t) in enumerate(ubicadas.items()):
        v = vistas[p]
        pts = aplicar(t, v.mapa[v.m].astype(np.float64)).astype(np.float32)
        xyz.append(pts)
        gris.append(v.tex[v.m])
        vista.append(np.full(len(pts), k, np.uint8))
    xyz, gris, vista = np.vstack(xyz), np.concatenate(gris), np.concatenate(vista)
    celda = np.floor((xyz - xyz.min(axis=0)) / voxel).astype(np.int64)
    clave = (celda[:, 0] * 73856093) ^ (celda[:, 1] * 19349663) ^ (celda[:, 2] * 83492791)
    _, inv, cuenta = np.unique(clave, return_inverse=True, return_counts=True)
    suma = np.zeros((len(cuenta), 3))
    np.add.at(suma, inv, xyz)
    sg = np.zeros(len(cuenta))
    np.add.at(sg, inv, gris)
    primera = np.zeros(len(cuenta), np.int64)
    primera[inv[::-1]] = np.arange(len(inv))[::-1]  # la vista del primer punto de cada vóxel
    return ((suma / cuenta[:, None]).astype(np.float32), (sg / cuenta).astype(np.uint8), vista[primera])


# ------------------------------------------------------------------ escaneo completo
def carpeta(nombre: str) -> Path:
    slug = rutas.etiqueta_carpeta(nombre)
    if not slug:
        raise ValueError("el escaneo necesita un nombre")
    return DIR_ESCANEOS / slug


def leer(nombre: str) -> dict:
    try:
        return json.loads((carpeta(nombre) / "escaneo.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def listar() -> list[dict]:
    salida = []
    if DIR_ESCANEOS.is_dir():
        for d in sorted(DIR_ESCANEOS.iterdir()):
            try:
                e = json.loads((d / "escaneo.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            salida.append({k: e.get(k) for k in ("nombre", "poses", "fecha", "puntos", "unidas", "rms_mm")} | {"id": d.name})
    return salida


def nube_binaria(nombre: str, maximo: int = 1_500_000) -> bytes:
    """Para el visor: uint32 N | float32 xyz·N | uint8 gris·N | uint8 vista·N (como /api/nube, más la vista)."""
    with np.load(carpeta(nombre) / "nube.npz") as d:
        xyz, gris, vista = d["xyz"], d["gris"], d["vista"]
    if len(xyz) > maximo:
        idx = np.sort(np.random.default_rng(0).choice(len(xyz), maximo, replace=False))
        xyz, gris, vista = xyz[idx], gris[idx], vista[idx]
    return (np.uint32(len(xyz)).tobytes() + xyz.astype("<f4").tobytes() + gris.astype(np.uint8).tobytes()
            + vista.astype(np.uint8).tobytes())


def unir(nombre: str, poses: list[str], manual: dict[str, list] | None = None, voxel: float = VOXEL_MM) -> dict:
    """Une las poses (la primera es la referencia). `manual`: {"pose_a|pose_b": [[pa, pb], …]}."""
    from procesamiento import reconstruccion_3d as r3d
    from datos_sistema import sesiones

    if len(poses) < 2:
        raise ValueError("hacen falta al menos 2 vistas")
    t0 = time.perf_counter()
    manual = manual or {}
    print(f"=== Escaneo 360 «{nombre}»: {len(poses)} vistas ({', '.join(poses)}) ===", flush=True)
    avance.partes(1)
    vistas = {}
    for i, p in enumerate(poses):
        avance.contador(i, len(poses), f"Cargando la vista {p}")
        vistas[p] = cargar_vista(p)
    rasgos = {}
    for i, p in enumerate(poses):
        avance.contador(i, len(poses), f"Puntos de textura de {p}")
        rasgos[p] = _rasgos(vistas[p])
    # pares: todos contra todos (son pocos), en ambos sentidos se usa el mismo
    claves = [(a, b) for i, a in enumerate(poses) for b in poses[i + 1:]]
    pares = {}
    for k, (a, b) in enumerate(claves):
        avance.contador(k, len(claves), f"Uniendo {a} con {b}")
        man = manual.get(f"{a}|{b}") or [[q, p] for p, q in manual.get(f"{b}|{a}", [])]
        r = par(vistas[a], vistas[b], rasgos, man)
        pares[f"{a}|{b}"] = r
        estado = (f"{r['metodo']}: {r['inliers']} puntos, ICP {r['rms_mm']:.3f} mm, calza {100 * r['solape']:.0f} %, giro {r['giro_grados']:.0f}°"
                  if r.get("T") else "")
        print(f"  [{a} + {b}] {'OK' if r['ok'] else 'no se unen'}: {estado or r.get('motivo', '')}"
              + ("" if r["ok"] or not estado else f" — {r.get('motivo', '')}"), flush=True)
    ubicadas = ubicar(poses, pares)
    sueltas = [p for p in poses if p not in ubicadas]
    if sueltas:
        print(f"[AVISO] No se pudieron unir: {', '.join(sueltas)}. Marca puntos en común con otra vista (pestaña 360°).", flush=True)
    calidad = refinar_global(vistas, ubicadas) if len(ubicadas) > 2 else {}
    avance.paso("Fusionando las vistas")
    xyz, gris, vista = fusionar(vistas, ubicadas, voxel)
    destino = carpeta(nombre)
    destino.mkdir(parents=True, exist_ok=True)
    r3d.escribir_ply_binario(destino / "nube.ply", xyz, np.column_stack([gris, gris, gris]))
    from procesamiento import fase

    orden = list(ubicadas)
    fase.guardar_npz_atomico(destino / "nube.npz", xyz=xyz, gris=gris, vista=vista, vistas=np.array(orden))
    rms = [c["rms_mm"] for c in calidad.values() if math.isfinite(c["rms_mm"])]
    info = {
        "nombre": nombre, "poses": poses, "fecha": datetime.now().isoformat(timespec="seconds"),
        "manual": manual, "voxel_mm": voxel, "puntos": int(len(xyz)), "unidas": orden, "sueltas": sueltas,
        "pares": {k: {kk: vv for kk, vv in r.items()} for k, r in pares.items()},
        "transformaciones": {p: t.tolist() for p, t in ubicadas.items()},
        "calidad": calidad, "rms_mm": float(np.median(rms)) if rms else None,
        "calibracion": str(cfg.DIR_CALIBRACION / "Estereo_TSC_0_2.npz"),
    }
    sesiones.escribir_json(destino / "escaneo.json", info)
    print(f"[OK] Escaneo «{nombre}»: {len(orden)} de {len(poses)} vistas unidas, {len(xyz):,} puntos"
          + (f", ajuste {info['rms_mm']:.3f} mm" if info["rms_mm"] else "")
          + f" ({time.perf_counter() - t0:.0f} s) -> {destino / 'nube.ply'}", flush=True)
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--nombre", required=True)
    parser.add_argument("--poses", nargs="+", required=True, help="poses de objeto; la primera es la referencia")
    parser.add_argument("--voxel", type=float, default=VOXEL_MM)
    args = parser.parse_args()
    previo = leer(args.nombre)
    unir(args.nombre, args.poses, previo.get("manual"), args.voxel)


if __name__ == "__main__":
    main()
