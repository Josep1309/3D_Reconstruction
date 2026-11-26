"""Medidas rápidas de la nube (procesamiento/medidas.py)."""

from __future__ import annotations

import numpy as np
import pytest

from procesamiento import medidas


def _mapas(P: np.ndarray, ancho: int = 100):
    """Pone los puntos en mapas X, Y, Z «de imagen» (como la reconstrucción) con máscara."""
    n = len(P)
    alto = -(-n // ancho)
    X, Y, Z = (np.full(alto * ancho, np.nan, np.float32) for _ in range(3))
    X[:n], Y[:n], Z[:n] = P.T
    M = np.zeros(alto * ancho, bool)
    M[:n] = True
    return [a.reshape(alto, ancho) for a in (X, Y, Z, M)]


def _esfera(n, radio, centro, rng):
    v = rng.normal(size=(n, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    v = v[v[:, 2] < 0.2]  # el casquete que ve la cámara (z hacia la escena)
    return centro + radio * v


def test_esfera_y_distancia_maxima():
    rng = np.random.default_rng(1)
    P = _esfera(40_000, 36.5, np.array([10.0, -5.0, 450.0]), rng)
    r = medidas.medidas_rapidas(*_mapas(P), recorte=0)
    assert r["esfera"]["diametro_mm"] == pytest.approx(73.0, abs=0.05)
    assert r["esfera"]["rms_mm"] < 0.01
    # el casquete pasa del ecuador: su distancia máxima es el diámetro
    assert r["distancia_maxima"]["distancia_mm"] == pytest.approx(73.0, abs=0.3)
    a, b = r["distancia_maxima"]["a"], r["distancia_maxima"]["b"]
    assert np.hypot(a["X"] - b["X"], np.hypot(a["Y"] - b["Y"], a["Z"] - b["Z"])) == pytest.approx(
        r["distancia_maxima"]["distancia_mm"])
    assert 0 <= a["fx"] <= 1 and 0 <= a["fy"] <= 1


def test_cajas_y_pieza_principal():
    rng = np.random.default_rng(2)
    # placa de 120 × 60 × 4 mm girada 30° alrededor de Z, más un grupo suelto lejano (fondo)
    L = rng.uniform([-60, -30, -2], [60, 30, 2], size=(30_000, 3))
    c, s = np.cos(np.pi / 6), np.sin(np.pi / 6)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    pieza = L @ R.T + [0, 0, 400]
    fondo = rng.uniform([200, 200, 600], [230, 230, 610], size=(500, 3))
    P = np.vstack([pieza, fondo])
    r = medidas.medidas_rapidas(*_mapas(P), recorte=0)
    assert r["puntos"] == len(pieza) and r["puntos_validos"] == len(P)
    assert r["caja_orientada"]["medidas_mm"] == pytest.approx([120, 60, 4], abs=0.5)
    assert abs(abs(np.dot(r["caja_orientada"]["ejes"][0], R[:, 0])) - 1) < 1e-3  # el eje largo es el girado
    ancho_x = 120 * c + 60 * s  # extensión de la placa girada en X de la cámara
    assert r["caja_camara"]["medidas_mm"][0] == pytest.approx(ancho_x, abs=2)  # esquinas poco pobladas
    # sin «solo la pieza principal» el fondo cuenta
    r2 = medidas.medidas_rapidas(*_mapas(P), recorte=0, principal=False)
    assert r2["puntos"] == len(P) and r2["distancia_maxima"]["distancia_mm"] > 300


def test_recorte_invalido_y_pocos_puntos():
    X, Y, Z, M = _mapas(np.random.default_rng(3).normal(size=(100, 3)))
    with pytest.raises(ValueError):
        medidas.medidas_rapidas(X, Y, Z, M, recorte=float("nan"))
    with pytest.raises(ValueError):
        medidas.medidas_rapidas(X, Y, Z, np.zeros_like(M))
