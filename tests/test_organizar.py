"""Organizar: segmentación de ciclos, capturas sin proyección y control rápido de una pose."""

from __future__ import annotations

import numpy as np
import pytest

import configuracion as cfg
import organizar_capturas as oc
import secuencia_patrones as sp

L = cfg.IMAGENES_POR_CICLO


@pytest.fixture(scope="module")
def ciclo() -> list[np.ndarray]:
    """Un ciclo «capturado»: los patrones reducidos y con un fondo gris, como los ve la cámara."""
    pats = [item[2][::8, ::8].astype(np.float32) for item in sp.crear_secuencia_completa()]
    return [np.clip(30 + 0.7 * p, 0, 255).astype(np.uint8) for p in pats]


def test_ciclo_desde_cualquier_patron(ciclo):
    """La cámara empieza en un patrón cualquiera: se reordena desde f_00."""
    rotado = ciclo[17:] + ciclo[:17]
    secs, avisos = oc.segmentar_secuencias(rotado, L)
    assert len(secs) == 1
    assert np.array_equal(secs[0].frames, np.stack(ciclo))


def test_varios_ciclos_se_promedian(ciclo):
    frames = ciclo[5:] + ciclo + ciclo[:5]
    secs, _ = oc.segmentar_secuencias(frames, L)
    assert len(secs) == 1 and secs[0].ciclos_promediados >= 1


def test_frame_perdido_separa_tramos(ciclo):
    frames = ciclo + ciclo[:20] + ciclo[21:] + ciclo  # falta un frame en el segundo ciclo
    secs, avisos = oc.segmentar_secuencias(frames, L)
    assert any("salto inesperado" in a for a in avisos)
    assert all(s.frames.shape[0] == L for s in secs)


def test_captura_sin_proyeccion_se_rechaza_con_motivo():
    constantes = [np.full((64, 80), 29 + (i % 2), np.uint8) for i in range(L)]
    ev = oc.evaluar_captura(constantes)
    assert not ev["ok"]
    assert "brillo casi constante" in ev["motivos"][0]


def test_captura_buena_pasa_el_control(ciclo):
    ev = oc.evaluar_captura(ciclo[9:] + ciclo[:9])
    assert ev["ok"], ev
    assert ev["modulacion_V"] > cfg.GAMMA_TH
    assert ev["saturado"] == 0


def test_saturacion_es_aviso_no_rechazo(ciclo):
    saturado = [np.clip(f.astype(np.int32) * 3, 0, 255).astype(np.uint8) for f in ciclo]
    ev = oc.evaluar_captura(saturado)
    assert any("saturados" in a for a in ev["avisos"])
