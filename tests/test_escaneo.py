"""Escaneo 360 (procesamiento/escaneo.py): movimiento rígido, RANSAC e ICP con asociación proyectiva."""

from __future__ import annotations

import numpy as np

from datos_sistema import configuracion as cfg
from procesamiento import escaneo as e


def _giro(angulo_grados: float, eje=(0.3, 1.0, 0.2), t=(5.0, -3.0, 8.0)) -> np.ndarray:
    import cv2

    eje = np.array(eje, float) / np.linalg.norm(eje)
    m = np.eye(4)
    m[:3, :3] = cv2.Rodrigues(eje * np.radians(angulo_grados))[0]
    m[:3, 3] = t
    return m


def test_kabsch_y_ransac_recuperan_el_movimiento():
    rng = np.random.default_rng(1)
    a = rng.uniform(-50, 50, (200, 3)) + [0, 0, 500]
    t = _giro(35)
    b = e.aplicar(t, a)
    assert np.allclose(e.kabsch(a, b), t, atol=1e-6)
    b[:60] += rng.uniform(-40, 40, (60, 3))          # 30 % de parejas equivocadas
    tr, inl = e.ransac_rigido(a, b)
    assert inl.sum() >= 140 and np.allclose(tr, t, atol=1e-3)


def _vista_sintetica() -> e.Vista:
    """Una superficie ondulada vista por una cámara de prueba (cada píxel con su X, Y, Z)."""
    k = np.array([[1500.0, 0, 320], [0, 1500.0, 240], [0, 0, 1]])
    np.savez(cfg.DIR_CALIBRACION / "Estereo_TSC_0_2.npz", Ac=k, dist_cam=np.zeros(5))
    e._CAMARA.clear()
    alto, ancho = 480, 640
    v, u = np.mgrid[0:alto, 0:ancho].astype(np.float64)
    z = 500 + 15 * np.sin(u / 60) * np.cos(v / 45) + 0.02 * (u - 320)
    mapa = np.stack([(u - 320) / 1500 * z, (v - 240) / 1500 * z, z], axis=-1).astype(np.float32)
    m = np.ones((alto, ancho), bool)
    vista = e.Vista("pose_00", mapa, m, np.zeros((alto, ancho), np.uint8))
    vista.pts, vista.nor = e._submuestra_con_normales(mapa, m, 4)
    vista.nmap = e._mapa_normales(mapa)
    return vista


def test_icp_proyectivo_recupera_un_movimiento_pequeno():
    v = _vista_sintetica()
    t_real = _giro(2.0, t=(1.5, -1.0, 2.0))
    src = e.aplicar(np.linalg.inv(t_real), v.pts)    # la misma superficie, movida
    t, rms, solape = e.icp(src, [(np.eye(4), v)], np.eye(4))
    assert rms < 0.05 and solape > 0.8
    assert np.abs(e.aplicar(t, src) - v.pts).max() < 0.2   # vuelve a su lugar (mm)


def test_ubicar_encadena_pares():
    t01, t12 = _giro(20), _giro(-15, t=(0, 4, 1))
    pares = {"a|b": {"ok": True, "T": t01.tolist(), "solape": 0.5, "rms_mm": 0.3},
             "b|c": {"ok": True, "T": t12.tolist(), "solape": 0.5, "rms_mm": 0.3},
             "a|c": {"ok": False}}
    u = e.ubicar(["a", "b", "c"], pares)
    # b -> a es la inversa de a -> b; c -> a pasa por b
    assert np.allclose(u["b"], np.linalg.inv(t01)) and np.allclose(u["c"], np.linalg.inv(t01) @ np.linalg.inv(t12))
