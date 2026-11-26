"""Fusión volumétrica TSDF (Truncated Signed Distance Function) y malla por Surface Nets.

Alternativa a la fusión por vóxeles de puntos de `escaneo.py` (como KinectFusion, Curless y Levoy
1996). Cada vista del escaneo es un mapa de profundidad de una cámara calibrada con su posición
conocida (tras el ICP). En una grilla 3D alrededor del objeto, cada celda acumula, de cada vista
que la ve, la distancia con signo a la superficie medida a lo largo del eje de la cámara:

    d = Z_medida(píxel donde se proyecta la celda) − Z_celda      (> 0: delante de la superficie)

truncada a ±μ y promediada con un peso que favorece las vistas que miran la superficie de frente
(cos del ángulo entre la normal y el rayo). Al promediar distancias —y no puntos— el ruido se
cancela a lo largo de la normal, que es donde está el error de la proyección de franjas, y las
vistas rasantes o de borde pesan menos.

La superficie es el cero de esa función. Se extrae con **Surface Nets** (Gibson 1998): un vértice
por celda que cruza el cero (promedio de los cruces en sus aristas) y un cuadrilátero por cada
arista de la grilla que cruza el cero, uniendo los vértices de las 4 celdas que la comparten. Da una
malla más regular que marching cubes y no necesita tablas de casos.
"""

from __future__ import annotations

import time

import cv2
import numpy as np


PESO_RELLENO = 0.3   # los píxeles rellenados (huecos pequeños) pesan menos que los medidos
BLOQUE = 2_000_000   # celdas por bloque al integrar (acota la memoria)
MAX_CELDAS = 40_000_000  # tope de la grilla (~0.5 GB): si la caja es enorme, la celda se agranda


def rellenar_vista(v, k: np.ndarray, dist: np.ndarray, max_mm2: float = 10.0):
    """Copia de la vista con los huecos PEQUEÑOS de su mapa de profundidad rellenos (inpainting de
    Z desde su contorno): las pintas oscuras que quita el filtro de manchas, píxeles sueltos sin
    fase. Supone que la superficie sigue continua debajo. Los huecos grandes (zonas no vistas) no se
    tocan. Devuelve (vista, peso por píxel: 1 medido, PESO_RELLENO relleno)."""
    from procesamiento import escaneo as esc
    from procesamiento import mascara

    m = v.m
    huecos = mascara._rellenar_huecos(m) & ~m
    n, lab, st, _ = cv2.connectedComponentsWithStats(huecos.astype(np.uint8), connectivity=8)
    # área máxima en píxeles: ~max_mm2 de superficie a la distancia típica de la vista
    z_med = float(np.nanmedian(v.mapa[..., 2][m])) if m.any() else 500.0
    mm_por_px = z_med / float(k[0, 0])
    max_px = max_mm2 / (mm_por_px * mm_por_px)
    chicos = np.zeros(n, bool)
    chicos[1:] = st[1:, cv2.CC_STAT_AREA] <= max_px
    rellenar = chicos[lab]
    if not rellenar.any():
        return v, np.where(m, 1.0, 0.0).astype(np.float32)
    # convolución normalizada: promedia SOLO píxeles medidos (cv2.inpaint mezcla los ceros de fuera
    # del objeto y tira la superficie hacia la cámara); si falta, con un entorno más grande
    z = np.where(m, v.mapa[..., 2], 0).astype(np.float32)
    mf = m.astype(np.float32)
    zi = np.zeros_like(z)
    falta = rellenar.copy()
    for sigma in (2, 4, 8, 16):
        num = cv2.GaussianBlur(z, (0, 0), sigma)
        den = cv2.GaussianBlur(mf, (0, 0), sigma)
        ok = falta & (den > 0.05)
        zi[ok] = num[ok] / den[ok]
        falta &= ~ok
    rellenar &= ~falta
    nueva_m = m | rellenar
    # X, Y a lo largo del rayo de cada píxel rellenado (sin distorsión)
    alto, ancho = m.shape
    fila, col = np.nonzero(rellenar)
    rayo = cv2.undistortPoints(np.stack([col, fila], -1).astype(np.float64).reshape(-1, 1, 2), k, dist).reshape(-1, 2)
    mapa = v.mapa.copy()
    mapa[fila, col, 0] = rayo[:, 0] * zi[fila, col]
    mapa[fila, col, 1] = rayo[:, 1] * zi[fila, col]
    mapa[fila, col, 2] = zi[fila, col]
    nv = esc.Vista(v.pose, mapa, nueva_m, v.tex)
    nv.nmap = esc._mapa_normales(mapa)
    peso = np.where(m, 1.0, np.where(rellenar, PESO_RELLENO, 0.0)).astype(np.float32)
    return nv, peso


def integrar(vistas: dict, ubicadas: dict, caja: tuple[np.ndarray, np.ndarray], voxel: float,
             trunc: float, k: np.ndarray, dist: np.ndarray, cerca: np.ndarray | None = None, avisar=None):
    """Grillas TSDF (F), pesos (W) y gris (C) en la caja [mín, máx] (sistema de referencia).
    `cerca`: máscara de las celdas a calcular (las próximas a la superficie); si no, todas."""
    lo, hi = caja
    forma = tuple(np.ceil((hi - lo) / voxel).astype(int) + 1)
    f = np.zeros(forma, np.float32)
    w = np.zeros(forma, np.float32)
    c = np.zeros(forma, np.float32)
    idx_todas = np.flatnonzero(cerca) if cerca is not None else np.arange(int(np.prod(forma)))
    fv, wv, cv = f.reshape(-1), w.reshape(-1), c.reshape(-1)
    for n_vista, (pose, t) in enumerate(ubicadas.items()):
        v, peso_px = rellenar_vista(vistas[pose], k, dist)
        r, tr = t[:3, :3].astype(np.float32), t[:3, 3].astype(np.float32)
        alto, ancho = v.m.shape
        # por bloques: la memoria no depende del tamaño de la grilla
        for b0 in range(0, len(idx_todas), BLOQUE):
            idx = idx_todas[b0:b0 + BLOQUE]
            ijk = np.stack(np.unravel_index(idx, forma), axis=-1).astype(np.float32)
            pc = (lo.astype(np.float32) + ijk * np.float32(voxel) - tr) @ r   # al sistema de la cámara de la vista
            sel = np.flatnonzero(pc[:, 2] > 1.0)
            if not len(sel):
                continue
            uv, _ = cv2.projectPoints(pc[sel].astype(np.float64).reshape(-1, 1, 3), np.zeros(3), np.zeros(3), k, dist)
            uv = np.round(uv.reshape(-1, 2)).astype(np.int64)
            dentro = (uv[:, 0] >= 0) & (uv[:, 0] < ancho) & (uv[:, 1] >= 0) & (uv[:, 1] < alto)
            sel, uv = sel[dentro], uv[dentro]
            fila, col = uv[:, 1], uv[:, 0]
            ok = v.m[fila, col]
            sel, fila, col = sel[ok], fila[ok], col[ok]
            p = pc[sel]
            sdf = v.mapa[fila, col, 2] - p[:, 2]
            n = v.nmap[fila, col]
            coseno = -np.einsum("ij,ij->i", n, p) / np.linalg.norm(p, axis=1)   # normal hacia la cámara
            util = (sdf > -trunc) & np.isfinite(sdf) & np.isfinite(coseno) & (coseno > 0.15)
            if not util.any():
                continue
            sel, sdf, coseno = sel[util], sdf[util], coseno[util]
            gris = v.tex[fila[util], col[util]].astype(np.float32)
            tsdf = np.clip(sdf / trunc, -1.0, 1.0)
            peso = (coseno * peso_px[fila[util], col[util]]).astype(np.float32)
            celdas = idx[sel]
            wn = wv[celdas] + peso
            fv[celdas] = (fv[celdas] * wv[celdas] + tsdf * peso) / wn
            cv[celdas] = (cv[celdas] * wv[celdas] + gris * peso) / wn
            wv[celdas] = wn
        if avisar:
            avisar(n_vista + 1, len(ubicadas), f"TSDF: vista {pose}")
    return f, w, c


def cerca_de_puntos(puntos: np.ndarray, lo: np.ndarray, forma: tuple, voxel: float, radio: float) -> np.ndarray:
    """Máscara de las celdas a menos de `radio` de algún punto (para no calcular la grilla entera)."""
    m = np.zeros(forma, bool)
    ijk = np.round((puntos - lo) / voxel).astype(np.int64)
    ok = np.all((ijk >= 0) & (ijk < np.array(forma)), axis=1)
    m[tuple(ijk[ok].T)] = True
    r = int(np.ceil(radio / voxel))
    for eje in range(3):                                   # dilatación separable, eje por eje
        acc = m.copy()
        for s in range(1, r + 1):
            acc[tuple(slice(s, None) if a == eje else slice(None) for a in range(3))] |= \
                m[tuple(slice(None, -s) if a == eje else slice(None) for a in range(3))]
            acc[tuple(slice(None, -s) if a == eje else slice(None) for a in range(3))] |= \
                m[tuple(slice(s, None) if a == eje else slice(None) for a in range(3))]
        m = acc
    return m


def surface_nets(f: np.ndarray, w: np.ndarray, c: np.ndarray, lo: np.ndarray, voxel: float, peso_min: float = 0.3):
    """Malla del cero de F (solo donde hay peso suficiente). Devuelve (vértices, caras, gris)."""
    valido = w >= peso_min
    pos = f > 0
    nx, ny, nz = f.shape
    # celdas (i, j, k) con sus 8 esquinas válidas y con cambio de signo
    esquinas = [(a, b, d) for a in (0, 1) for b in (0, 1) for d in (0, 1)]
    def corte(a, b, d):
        return (slice(a, nx - 1 + a), slice(b, ny - 1 + b), slice(d, nz - 1 + d))
    todas_validas = np.ones((nx - 1, ny - 1, nz - 1), bool)
    alguna_pos = np.zeros_like(todas_validas)
    todas_pos = np.ones_like(todas_validas)
    for e in esquinas:
        todas_validas &= valido[corte(*e)]
        alguna_pos |= pos[corte(*e)]
        todas_pos &= pos[corte(*e)]
    activa = todas_validas & alguna_pos & ~todas_pos
    celdas = np.flatnonzero(activa)
    if not len(celdas):
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int64), np.zeros(0, np.uint8)
    ci, cj, ck = np.unravel_index(celdas, activa.shape)
    # vértice: promedio de los cruces por cero en las 12 aristas de la celda
    aristas = [((0, 0, 0), (1, 0, 0)), ((0, 1, 0), (1, 1, 0)), ((0, 0, 1), (1, 0, 1)), ((0, 1, 1), (1, 1, 1)),
               ((0, 0, 0), (0, 1, 0)), ((1, 0, 0), (1, 1, 0)), ((0, 0, 1), (0, 1, 1)), ((1, 0, 1), (1, 1, 1)),
               ((0, 0, 0), (0, 0, 1)), ((1, 0, 0), (1, 0, 1)), ((0, 1, 0), (0, 1, 1)), ((1, 1, 0), (1, 1, 1))]
    suma = np.zeros((len(celdas), 3))
    cuenta = np.zeros(len(celdas))
    for a, b in aristas:
        fa = f[ci + a[0], cj + a[1], ck + a[2]]
        fb = f[ci + b[0], cj + b[1], ck + b[2]]
        cruza = (fa > 0) != (fb > 0)
        tt = np.where(cruza, fa / np.where(fa - fb == 0, 1, fa - fb), 0)
        p = np.stack([ci + a[0] + tt * (b[0] - a[0]), cj + a[1] + tt * (b[1] - a[1]), ck + a[2] + tt * (b[2] - a[2])], axis=-1)
        suma += p * cruza[:, None]
        cuenta += cruza
    vert = (lo + voxel * suma / cuenta[:, None]).astype(np.float32)
    gris = np.clip(c[ci, cj, ck], 0, 255).astype(np.uint8)
    # caras: por cada arista de la grilla con cambio de signo, el cuadrilátero de las 4 celdas vecinas
    caras = []
    def vertice(i, j, k):
        lin = np.ravel_multi_index((i, j, k), activa.shape)
        pos_ = np.searchsorted(celdas, lin)
        pos_ = np.minimum(pos_, len(celdas) - 1)
        return pos_, celdas[pos_] == lin
    for eje in range(3):
        sh = [0, 0, 0]
        sh[eje] = 1
        a_ = (slice(0, nx - sh[0]), slice(0, ny - sh[1]), slice(0, nz - sh[2]))
        b_ = (slice(sh[0], nx), slice(sh[1], ny), slice(sh[2], nz))
        cruza = valido[a_] & valido[b_] & (pos[a_] != pos[b_])
        i, j, k = np.nonzero(cruza)
        signo = pos[a_][i, j, k]
        # las 4 celdas que comparten la arista (en los dos ejes perpendiculares)
        o1, o2 = [e for e in range(3) if e != eje]
        def desplazar(d1, d2):
            q = [i.copy(), j.copy(), k.copy()]
            q[o1] = q[o1] - d1
            q[o2] = q[o2] - d2
            return q
        quad = [desplazar(1, 1), desplazar(0, 1), desplazar(0, 0), desplazar(1, 0)]
        dentro = np.ones(len(i), bool)
        for q in quad:
            for e in range(3):
                dentro &= (q[e] >= 0) & (q[e] < activa.shape[e])
        idxs, oks = [], dentro.copy()
        for q in quad:
            qq = [np.clip(q[e], 0, activa.shape[e] - 1) for e in range(3)]
            v, ok = vertice(*qq)
            idxs.append(v)
            oks &= ok
        v0, v1, v2, v3 = (x[oks] for x in idxs)
        s = signo[oks]
        # orientación: que la normal apunte hacia F > 0 (afuera, hacia las cámaras)
        t1 = np.where(s[:, None], np.stack([v0, v1, v2], -1), np.stack([v0, v2, v1], -1))
        t2 = np.where(s[:, None], np.stack([v0, v2, v3], -1), np.stack([v0, v3, v2], -1))
        caras += [t1, t2]
    caras = np.vstack(caras) if caras else np.zeros((0, 3), np.int64)
    return vert, caras, gris


def orientar(vert: np.ndarray, caras: np.ndarray, f: np.ndarray, lo: np.ndarray, voxel: float) -> np.ndarray:
    """Asegura que las normales de las caras apunten hacia F > 0 (si el criterio de signo quedó al
    revés para un eje, se corrige comparando con el gradiente de F)."""
    if not len(caras):
        return caras
    a, b, c = vert[caras[:, 0]], vert[caras[:, 1]], vert[caras[:, 2]]
    n = np.cross(b - a, c - a)
    centro = (a + b + c) / 3
    ijk = np.clip(np.round((centro - lo) / voxel).astype(int), 1, np.array(f.shape) - 2)
    grad = np.stack([f[ijk[:, 0] + 1, ijk[:, 1], ijk[:, 2]] - f[ijk[:, 0] - 1, ijk[:, 1], ijk[:, 2]],
                     f[ijk[:, 0], ijk[:, 1] + 1, ijk[:, 2]] - f[ijk[:, 0], ijk[:, 1] - 1, ijk[:, 2]],
                     f[ijk[:, 0], ijk[:, 1], ijk[:, 2] + 1] - f[ijk[:, 0], ijk[:, 1], ijk[:, 2] - 1]], axis=-1)
    al_reves = np.einsum("ij,ij->i", n, grad) < 0
    caras = caras.copy()
    caras[al_reves] = caras[al_reves][:, [0, 2, 1]]
    return caras


def normales_vertices(vert: np.ndarray, caras: np.ndarray) -> np.ndarray:
    n = np.zeros_like(vert, dtype=np.float64)
    if len(caras):
        a, b, c = vert[caras[:, 0]], vert[caras[:, 1]], vert[caras[:, 2]]
        fn = np.cross(b - a, c - a)
        for e in range(3):
            np.add.at(n, caras[:, e], fn)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    return n.astype(np.float32)


def limpiar(vert: np.ndarray, caras: np.ndarray, gris: np.ndarray, min_caras: int = 200):
    """Quita los pedazos sueltos de malla (componentes con pocas caras) y los vértices sin usar."""
    if not len(caras):
        return vert, caras, gris
    # componentes conexas: propagación de la etiqueta mínima por las aristas (vectorizada), con
    # saltos de puntero para que converja en pocas vueltas
    e0 = np.concatenate([caras[:, 0], caras[:, 1], caras[:, 2]])
    e1 = np.concatenate([caras[:, 1], caras[:, 2], caras[:, 0]])
    raices = np.arange(len(vert))
    for _ in range(200):
        m = np.minimum(raices[e0], raices[e1])
        nuevo = raices.copy()
        np.minimum.at(nuevo, e0, m)
        np.minimum.at(nuevo, e1, m)
        for _ in range(4):
            nuevo = nuevo[nuevo]
        if np.array_equal(nuevo, raices):
            break
        raices = nuevo
    comp = raices[caras[:, 0]]
    ids, cuentas = np.unique(comp, return_counts=True)
    grandes = set(ids[cuentas >= min_caras])
    caras = caras[np.isin(comp, list(grandes))]
    usados = np.unique(caras)
    nuevo = -np.ones(len(vert), np.int64)
    nuevo[usados] = np.arange(len(usados))
    return vert[usados], nuevo[caras], gris[usados]


def fusionar_tsdf(vistas: dict, ubicadas: dict, puntos: np.ndarray, k: np.ndarray, dist: np.ndarray,
                  voxel: float = 0.5, trunc: float | None = None, avisar=None) -> dict:
    """Escaneo completo: grilla alrededor de `puntos` (la nube ya unida), integración y malla."""
    t0 = time.perf_counter()
    # caja robusta: sin el 0.2 % de puntos más extremos (un punto suelto no infla la grilla)
    lo0, hi0 = np.percentile(puntos, 0.2, axis=0), np.percentile(puntos, 99.8, axis=0)
    pedido = voxel
    def celdas(vx: float) -> float:  # la grilla tiene 3·trunc (= 12 celdas) de margen por lado
        return float(np.prod(np.ceil((hi0 - lo0) / vx) + 25))
    if celdas(voxel) > MAX_CELDAS:  # caja muy grande (p. ej. con mesa y fondo): celda más grande, no sin memoria
        while celdas(voxel) > MAX_CELDAS:
            voxel = round(voxel * 1.05 + 0.005, 2)
        print(f"  [AVISO] La caja del escaneo mide {np.round(hi0 - lo0).astype(int).tolist()} mm: la malla TSDF usa "
              f"celdas de {voxel} mm (en vez de {pedido}) para no agotar la memoria. Quita el fondo con la "
              f"máscara de cada pose para más detalle.", flush=True)
    trunc = trunc or 4 * voxel
    lo = (lo0 - 3 * trunc).astype(np.float64)
    hi = (hi0 + 3 * trunc).astype(np.float64)
    dentro = np.all((puntos >= lo) & (puntos <= hi), axis=1)
    puntos = puntos[dentro]
    forma = tuple(np.ceil((hi - lo) / voxel).astype(int) + 1)
    cerca = cerca_de_puntos(puntos, lo, forma, voxel, 2 * trunc)
    f, w, c = integrar(vistas, ubicadas, (lo, hi), voxel, trunc, k, dist, cerca, avisar)
    vert, caras, gris = surface_nets(f, w, c, lo, voxel)
    caras = orientar(vert, caras, f, lo, voxel)
    vert, caras, gris = limpiar(vert, caras, gris)
    return {"vertices": vert, "caras": caras.astype(np.int64), "gris": gris,
            "normales": normales_vertices(vert, caras), "voxel_mm": voxel, "trunc_mm": trunc,
            "grilla": list(forma), "segundos": time.perf_counter() - t0}


def escribir_ply_malla(ruta, vert: np.ndarray, caras: np.ndarray, gris: np.ndarray) -> None:
    cab = ("ply\nformat binary_little_endian 1.0\n"
           f"element vertex {len(vert)}\nproperty float x\nproperty float y\nproperty float z\n"
           "property uchar red\nproperty uchar green\nproperty uchar blue\n"
           f"element face {len(caras)}\nproperty list uchar int vertex_indices\nend_header\n").encode("ascii")
    v = np.empty(len(vert), dtype=[("p", "<f4", 3), ("c", "u1", 3)])
    v["p"], v["c"] = vert, np.repeat(gris[:, None], 3, axis=1)
    fc = np.empty(len(caras), dtype=[("n", "u1"), ("i", "<i4", 3)])
    fc["n"], fc["i"] = 3, caras
    with open(ruta, "wb") as fh:
        fh.write(cab)
        fh.write(v.tobytes())
        fh.write(fc.tobytes())


def escribir_stl(ruta, vert: np.ndarray, caras: np.ndarray) -> None:
    a, b, c = vert[caras[:, 0]], vert[caras[:, 1]], vert[caras[:, 2]]
    n = np.cross(b - a, c - a)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    reg = np.zeros(len(caras), dtype=[("n", "<f4", 3), ("a", "<f4", 3), ("b", "<f4", 3), ("c", "<f4", 3), ("x", "<u2")])
    reg["n"], reg["a"], reg["b"], reg["c"] = n, a, b, c
    with open(ruta, "wb") as fh:
        fh.write(b"Escaneo 360 - malla TSDF".ljust(80, b" "))
        fh.write(np.uint32(len(caras)).tobytes())
        fh.write(reg.tobytes())
