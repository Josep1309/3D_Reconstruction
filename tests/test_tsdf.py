"""Fusión TSDF y malla por Surface Nets (procesamiento/tsdf.py), con una esfera sintética."""

from __future__ import annotations

import cv2
import numpy as np

from procesamiento import escaneo as e
from procesamiento import tsdf

K = np.array([[900.0, 0, 160], [0, 900.0, 120], [0, 0, 1]])
CENTRO, RADIO = np.array([0, 0, 500.0]), 30.0


def _vista(nombre: str, hueco: bool = False) -> e.Vista:
    alto, ancho = 240, 320
    v, u = np.mgrid[0:alto, 0:ancho].astype(float)
    d = np.stack([(u - 160) / 900, (v - 120) / 900, np.ones_like(u)], -1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    b = d @ CENTRO
    disc = b * b - (CENTRO @ CENTRO - RADIO * RADIO)
    m = disc > 0
    p = d * (b - np.sqrt(np.where(m, disc, 0)))[..., None]
    if hueco:  # una «pinta» de 5x5 px (~7 mm² aquí) sin medida, como las que quita el filtro de manchas
        m[118:123, 158:163] = False
    mapa = np.where(m[..., None], p, np.nan).astype(np.float32)
    vi = e.Vista(nombre, mapa, m, np.full(m.shape, 200, np.uint8))
    vi.nmap = e._mapa_normales(mapa)
    return vi


def _giro(grados: float) -> np.ndarray:
    t = np.eye(4)
    t[:3, :3] = cv2.Rodrigues(np.array([0, np.radians(grados), 0.0]))[0]
    t[:3, 3] = CENTRO - t[:3, :3] @ CENTRO
    return t


def test_esfera_desde_tres_lados():
    vistas = {"a": _vista("a"), "b": _vista("b"), "c": _vista("c")}
    ub = {"a": np.eye(4), "b": _giro(120), "c": _giro(240)}
    pts = np.vstack([e.aplicar(ub[n], vistas[n].mapa[vistas[n].m]) for n in vistas])
    r = tsdf.fusionar_tsdf(vistas, ub, pts, K, np.zeros(5), voxel=0.6)
    d = np.linalg.norm(r["vertices"] - CENTRO, axis=1)
    assert len(r["caras"]) > 10000
    assert abs(d.mean() - RADIO) < 0.05 and d.std() < 0.15            # sobre la esfera
    afuera = np.einsum("ij,ij->i", r["normales"], r["vertices"] - CENTRO) > 0
    assert afuera.mean() > 0.99                                       # normales hacia afuera


def test_rellena_huecos_pequenos():
    v = _vista("a", hueco=True)
    lleno, peso = tsdf.rellenar_vista(v, K, np.zeros(5))
    assert lleno.m[120, 160] and np.isclose(peso[120, 160], tsdf.PESO_RELLENO) and peso[100, 160] == 1.0
    # el relleno queda sobre la esfera (la superficie sigue continua debajo de la pinta)
    assert abs(np.linalg.norm(lleno.mapa[120, 160] - CENTRO) - RADIO) < 0.3
    # un hueco grande (zona no vista) no se inventa
    grande = _vista("b")
    grande.m[105:135, 145:175] = False   # 30x30 px: ~240 mm², dentro de la esfera
    assert not tsdf.rellenar_vista(grande, K, np.zeros(5))[0].m[120, 160]


def test_caja_grande_agranda_la_celda(monkeypatch):
    """Con una caja enorme (p. ej. mesa y fondo), la celda crece en vez de agotar la memoria."""
    monkeypatch.setattr(tsdf, "MAX_CELDAS", 200_000)
    vistas = {"a": _vista("a")}
    pts = vistas["a"].mapa[vistas["a"].m]
    lejos = np.array([[-150, -150, 350], [150, 150, 650.0]])  # puntos sueltos que inflan la caja
    r = tsdf.fusionar_tsdf(vistas, {"a": np.eye(4)}, np.vstack([pts, np.repeat(lejos, 2000, axis=0)]),
                           K, np.zeros(5), voxel=0.5)
    assert r["voxel_mm"] > 0.5 and np.prod(r["grilla"]) <= 200_000   # no se pasa del tope
