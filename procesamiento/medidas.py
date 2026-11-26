"""Medidas rápidas de la nube de una pose (pestaña «Medición»), sin marcar puntos a mano.

Sobre los puntos válidos de la reconstrucción (opcionalmente solo la pieza principal, el mayor
grupo de puntos conectados en 3D, y sin los atípicos de los extremos):

- distancia máxima: los dos puntos más alejados entre sí (con su píxel, para guardarla como
  medición normal);
- caja orientada: largo × ancho × espesor a lo largo de los ejes principales de la nube (no
  depende de cómo esté puesta la pieza frente a la cámara);
- caja de la cámara: extensión en X (derecha), Y (abajo) y Z (profundidad);
- esfera ajustada: diámetro y RMS de los residuos (útil para piezas redondas; si el RMS es grande,
  la pieza no es una esfera).

Todo en mm, en el sistema de la cámara (como la nube).
"""

from __future__ import annotations

import numpy as np

SEPARACION_MM = 3.0     # puntos a menos de esto (en vóxeles de este lado) son de la misma pieza
N_DIRECCIONES = 500     # direcciones (semiesfera) para buscar la distancia máxima

# 13 de los 26 vecinos de un vóxel (la otra mitad es simétrica)
_VECINOS = np.array([(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)
                     if (i, j, k) > (0, 0, 0)], np.int64)


def pieza_principal(P: np.ndarray, separacion_mm: float = SEPARACION_MM) -> np.ndarray:
    """Máscara (por punto) del mayor grupo de puntos conectados en 3D.

    Los puntos se agrupan en vóxeles de `separacion_mm`; dos vóxeles vecinos (26-conectividad)
    son de la misma pieza. Quita el fondo lejano y los grupos sueltos de puntos, pero no separa
    la pieza de un plano sobre el que esté apoyada. Se agrupa en 3D y no en la imagen porque la
    máscara de una pieza puede quedar partida en la imagen (costuras, manchas oscuras)."""
    v = np.floor(P / separacion_mm).astype(np.int64)
    v -= v.min(axis=0) - 1
    base = int(v.max()) + 2
    clave = (v[:, 0] * base + v[:, 1]) * base + v[:, 2]
    claves, de_punto = np.unique(clave, return_inverse=True)
    n = len(claves)
    pares_i, pares_j = [], []
    for d in _VECINOS:
        buscada = claves + (d[0] * base + d[1]) * base + d[2]
        pos = np.minimum(np.searchsorted(claves, buscada), n - 1)
        ok = claves[pos] == buscada
        pares_i.append(np.flatnonzero(ok))
        pares_j.append(pos[ok])
    i, j = np.concatenate(pares_i), np.concatenate(pares_j)
    etiqueta = np.arange(n)
    while True:  # propagación de la menor etiqueta + saltos de puntero
        menor = np.minimum(etiqueta[i], etiqueta[j])
        nueva = etiqueta.copy()
        np.minimum.at(nueva, i, menor)
        np.minimum.at(nueva, j, menor)
        nueva = nueva[nueva]
        if np.array_equal(nueva, etiqueta):
            break
        etiqueta = nueva
    por_punto = etiqueta[de_punto]
    return por_punto == np.argmax(np.bincount(por_punto))


def _ejes_principales(P: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    c = P.mean(axis=0)
    _, _, vt = np.linalg.svd(P - c, full_matrices=False)
    return c, vt  # filas = ejes, de mayor a menor varianza


def _recortar(P: np.ndarray, recorte: float) -> np.ndarray:
    """Quita los puntos fuera de los percentiles [recorte, 100 − recorte] en cada eje principal."""
    if recorte <= 0 or len(P) < 20:
        return np.ones(len(P), bool)
    c, ejes = _ejes_principales(P)
    q = (P - c) @ ejes.T
    lo, hi = np.percentile(q, [recorte, 100 - recorte], axis=0)
    return np.all((q >= lo) & (q <= hi), axis=1)


def _direcciones(n: int) -> np.ndarray:
    """n direcciones casi uniformes en la semiesfera z ≥ 0 (espiral de Fibonacci)."""
    i = np.arange(n) + 0.5
    z = i / n
    r = np.sqrt(1 - z * z)
    t = np.pi * (1 + 5 ** 0.5) * i
    return np.column_stack([r * np.cos(t), r * np.sin(t), z])


def distancia_maxima(P: np.ndarray) -> tuple[int, int, float]:
    """Índices de los dos puntos más alejados y su distancia.

    Candidatos: los extremos de la nube en N_DIRECCIONES direcciones (la distancia entre ellos no
    baja de diámetro·cos 3°); luego se afina buscando, alternadamente, el punto más lejano a cada
    extremo, que solo puede alargarla."""
    c = P.mean(axis=0)
    Q = (P - c).astype(np.float32)
    D = _direcciones(N_DIRECCIONES).astype(np.float32)
    cand = set()
    for k in range(0, len(D), 64):
        proy = D[k:k + 64] @ Q.T          # (direcciones, puntos): argmax por filas contiguas
        cand.update(np.argmax(proy, axis=1).tolist())
        cand.update(np.argmin(proy, axis=1).tolist())
    idx = np.fromiter(cand, int)
    C = P[idx]
    d2 = ((C[:, None, :] - C[None, :, :]) ** 2).sum(-1)
    i, j = np.unravel_index(int(np.argmax(d2)), d2.shape)
    a, b, mejor = int(idx[i]), int(idx[j]), float(np.sqrt(d2[i, j]))
    for _ in range(4):
        cambio = False
        for fijo in (a, b):
            dist = np.linalg.norm(P - P[fijo], axis=1)
            k = int(np.argmax(dist))
            if dist[k] > mejor + 1e-9:
                a, b, mejor, cambio = fijo, k, float(dist[k]), True
        if not cambio:
            break
    return a, b, mejor


def esfera(P: np.ndarray) -> dict | None:
    """Esfera por mínimos cuadrados (algebraica, con una pasada sin los residuos > 3·RMS)."""
    if len(P) < 10:
        return None
    usar = np.ones(len(P), bool)
    for _ in range(2):
        Q = P[usar]
        A = np.column_stack([2 * Q, np.ones(len(Q))])
        sol, *_ = np.linalg.lstsq(A, (Q * Q).sum(1), rcond=None)
        centro = sol[:3]
        r2 = sol[3] + centro @ centro
        if r2 <= 0:
            return None
        radio = float(np.sqrt(r2))
        res = np.linalg.norm(P - centro, axis=1) - radio
        rms = float(np.sqrt(np.mean(res[usar] ** 2)))
        usar = np.abs(res) <= 3 * rms if rms > 0 else usar
    return {"centro": centro.tolist(), "diametro_mm": 2 * radio, "rms_mm": rms}


def _caja(P: np.ndarray, centro: np.ndarray, ejes: np.ndarray, ordenar: bool = False) -> dict:
    q = (P - centro) @ ejes.T
    lo, hi = q.min(axis=0), q.max(axis=0)
    medio = centro + ((lo + hi) / 2) @ ejes
    medidas = hi - lo
    if ordenar:  # largo ≥ ancho ≥ espesor
        orden = np.argsort(-medidas)
        ejes, medidas = ejes[orden], medidas[orden]
    return {"centro": medio.tolist(), "ejes": ejes.tolist(), "medidas_mm": medidas.tolist()}


def medidas_rapidas(X: np.ndarray, Y: np.ndarray, Z: np.ndarray, mascara: np.ndarray,
                    recorte: float = 0.1, principal: bool = True) -> dict:
    """Medidas de la nube organizada (mapas X, Y, Z de la imagen). `recorte` en % por lado."""
    if not 0 <= recorte <= 5:
        raise ValueError("recorte de atípicos fuera de rango (0–5 %)")
    m = mascara.astype(bool) & np.isfinite(X) & np.isfinite(Y) & np.isfinite(Z)
    idx = np.flatnonzero(m)
    total = len(idx)
    P = np.column_stack([X.ravel()[idx], Y.ravel()[idx], Z.ravel()[idx]]).astype(np.float64)
    if principal and total:
        pieza = pieza_principal(P)
        P, idx = P[pieza], idx[pieza]
    if len(P) >= 20:
        dentro = _recortar(P, recorte)
        P, idx = P[dentro], idx[dentro]
    if len(P) < 20:
        raise ValueError("muy pocos puntos para medir (revisa la máscara o desactiva «solo la pieza principal»)")
    alto, ancho = m.shape

    def punto(k: int) -> dict:
        f, c = divmod(int(idx[k]), ancho)
        return {"fx": c / (ancho - 1), "fy": f / (alto - 1), "X": float(P[k, 0]), "Y": float(P[k, 1]), "Z": float(P[k, 2])}

    a, b, dmax = distancia_maxima(P)
    centro, ejes = _ejes_principales(P)
    orientada = _caja(P, centro, ejes, ordenar=True)
    camara = _caja(P, centro, np.eye(3))
    return {
        "puntos": len(P), "puntos_validos": total, "recorte": recorte, "principal": principal,
        "distancia_maxima": {"a": punto(a), "b": punto(b), "distancia_mm": dmax},
        "caja_orientada": orientada,
        "caja_camara": camara,
        "esfera": esfera(P),
    }
