"""Máscara por pose (mascara.py): pasos de limpieza, guardado y filtro de puntos aislados."""

from __future__ import annotations

import numpy as np

from procesamiento import mascara


def _objeto_con_agujeros():
    valido = np.zeros((200, 300), bool)
    valido[50:150, 80:220] = True          # el objeto
    valido[60:140:10, 90:210:10] = False   # agujeritos dentro (píxeles sin fase)
    valido[10:14, 10:14] = True            # isla suelta de 16 px
    gamma = np.where(valido, 0.5, 0.0).astype(np.float32)
    gamma[50:150, 80:100] = 0.05           # franja con poca modulación
    return valido, gamma


def test_sin_parametros_respeta_la_fase():
    valido, gamma = _objeto_con_agujeros()
    assert np.array_equal(mascara.calcular(valido, gamma, {}), valido)


def test_umbral_islas_y_region_mayor():
    valido, gamma = _objeto_con_agujeros()
    assert not mascara.calcular(valido, gamma, {"umbral": 0.1})[50:150, 80:100].any()
    assert not mascara.calcular(valido, gamma, {"min_isla": 100})[10:14, 10:14].any()
    m = mascara.calcular(valido, gamma, {"mayor": True})
    assert not m[10:14, 10:14].any() and m[105, 155]


def test_erosion_solo_recorta_el_contorno():
    """Los agujeritos de dentro no crecen: solo se pierde el borde exterior."""
    valido, gamma = _objeto_con_agujeros()
    m = mascara.calcular(valido, gamma, {"erosion": 3})
    assert not m[50:53].any() and not m[:, 80:83].any()      # contorno recortado
    assert m[64, 95] and m[65, 150]                          # vecinos de los agujeritos intactos
    assert (valido.sum() - m.sum()) < 0.15 * valido.sum()


def test_poligonos_recorte_y_exclusion():
    valido, gamma = _objeto_con_agujeros()
    recorte = [[0.5, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]]  # mitad derecha
    m = mascara.calcular(valido, gamma, {"recortes": [recorte]})
    assert not m[:, :140].any() and m[105, 205]
    m = mascara.calcular(valido, gamma, {"exclusiones": [recorte]})
    assert not m[:, 160:].any() and m[105, 125]


def test_guardar_cargar_y_firma():
    valido, gamma = _objeto_con_agujeros()
    assert mascara.cargar("objeto", "pose_99") is None and mascara.firma("objeto", "pose_99") is None
    m = mascara.calcular(valido, gamma, {"mayor": True})
    mascara.guardar("objeto", "pose_99", m, {"mayor": True})
    assert np.array_equal(mascara.cargar("objeto", "pose_99"), m)
    assert mascara.leer_parametros("objeto", "pose_99")["mayor"] is True
    assert mascara.firma("objeto", "pose_99")
    assert mascara.borrar("objeto", "pose_99") and mascara.cargar("objeto", "pose_99") is None


def test_filtro_de_vecinos_quita_un_punto_volando():
    yy, xx = np.mgrid[0:100, 0:100].astype(np.float32)
    z = 500 + 0.01 * xx
    z[50, 50] = 560.0  # punto volando
    m = np.ones_like(z, bool)
    r = mascara.filtrar_vecinos(xx * 0.2, yy * 0.2, z, m, 3.0)
    assert not r[50, 50] and r.sum() >= m.sum() - 9  # quita el volando (y como mucho sus vecinos)
    assert np.array_equal(mascara.filtrar_vecinos(xx, yy, z, m, 0.0), m)  # 0 = desactivado
