"""Métodos de reconstrucción (procesamiento/metodos.py): ajuste por píxel y modelos híbridos."""

from __future__ import annotations

import numpy as np

from datos_sistema import configuracion as cfg
from procesamiento import metodos as mt


def test_ajuste_racional_recupera_la_funcion():
    """Z = (a0 + a1 t + a4 t²)/(1 + a2 t + a3 t²) por píxel, y X, Y lineales en Z."""
    rng = np.random.default_rng(0)
    n, k = 200, 12
    v = np.sort(rng.uniform(300, 700, (n, k)), axis=1)
    z = (5000 + 3 * v) / (10 + 0.004 * v)            # forma de un sistema ideal (1/1)
    x, y = 0.2 * z + 3, -0.1 * z + 1
    mod = mt.ajustar(v, x, y, z, "rac")
    v_nuevo = (v[:, 3] + v[:, 4]) / 2                # dentro del rango de cada píxel
    xe, ye, ze, ok = mt.evaluar({**mod, "modelo": np.array("rac")}, v_nuevo)
    z_real = (5000 + 3 * v_nuevo) / (10 + 0.004 * v_nuevo)
    assert ok.all() and np.allclose(ze, z_real, atol=1e-3) and np.allclose(xe, 0.2 * z_real + 3, atol=1e-3)


def test_ajuste_polinomial_y_fuera_de_rango():
    rng = np.random.default_rng(1)
    v = np.sort(rng.uniform(100, 200, (50, 10)), axis=1)
    z = 400 + 0.5 * v + 1e-3 * v ** 2
    mod = {**mt.ajustar(v, v * 0.1, v * 0.2, z, "pol", grado=3), "modelo": np.array("pol")}
    _, _, ze, ok = mt.evaluar(mod, np.full(50, 150.0))
    assert ok.all() and np.allclose(ze, 400 + 75 + 22.5, atol=1e-3)
    _, _, _, ok = mt.evaluar(mod, np.full(50, 260.0))  # muy fuera del rango calibrado: no extrapola
    assert not ok.any()


def test_planos_virtuales_reproducen_la_geometria():
    """Con una cámara y un proyector ideales, el modelo racional de planos virtuales da el mismo
    punto que la geometría exacta (el rayo del píxel cortado a la distancia que indica la fase)."""
    k = np.array([[800.0, 0, 32], [0, 800.0, 24], [0, 0, 1]])
    calib = {"Ac": k, "dist_cam": np.zeros(5), "Ap": np.array([[900.0, 0, 456], [0, 900.0, 570], [0, 0, 1]]),
             "dist_proj": np.zeros(5), "R": np.eye(3), "T": np.array([[20.0], [-90.0], [5.0]]),
             "tvecs_cam": np.array([[[0.0], [0.0], [480.0]], [[0.0], [0.0], [560.0]]])}
    forma = (48, 64)
    filas = slice(0, 48)
    vv, xx, yy, zz = mt._muestras_virtuales(calib, forma, "Fy", filas)
    mod = {**mt.ajustar(vv, xx, yy, zz, "rac"), "modelo": np.array("rac")}
    # un punto de prueba por píxel a 517 mm (no es ninguno de los planos de ajuste)
    xn, yn = mt._rayos(calib, filas, 64)
    p = np.stack([xn * 517, yn * 517, np.full(len(xn), 517.0)], axis=-1)
    vp = mt._proyectar(calib, p)[:, 1]
    x, y, z, ok = mt.evaluar(mod, vp)
    assert ok.all() and np.abs(z - 517).max() < 0.01 and np.abs(x - p[:, 0]).max() < 0.01
    # el polinomial (grado 4) aproxima: error pequeño pero no nulo
    mp = {**mt.ajustar(vv, xx, yy, zz, "pol", 4), "modelo": np.array("pol")}
    assert np.abs(mt.evaluar(mp, vp)[2] - 517).max() < 0.1
    assert cfg.Z_MIN_MM < zz.min() < zz.max() < cfg.Z_MAX_MM
