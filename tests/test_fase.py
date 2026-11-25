"""Recuperación de fase: decodificar los patrones del proyector debe dar su columna/fila exacta."""

from __future__ import annotations

import numpy as np
import pytest

from datos_sistema import configuracion as cfg
from procesamiento import fase
from captura import secuencia_patrones as sp

P, N, B = cfg.PERIODO, cfg.N_PASOS, cfg.N_BITS_GRAY


@pytest.fixture(scope="module")
def secuencia() -> np.ndarray:
    """Los 50 patrones tal como se cargan en el proyector (alto × ancho del proyector)."""
    return np.stack([item[2] for item in sp.crear_secuencia_completa()]).astype(np.float64)


def test_secuencia_tiene_50_patrones(secuencia):
    assert len(secuencia) == cfg.IMAGENES_POR_CICLO
    assert secuencia.shape[1:] == (cfg.PROYECTOR_ALTO, cfg.PROYECTOR_ANCHO)
    assert secuencia[-2].max() == 0 and secuencia[-1].min() == 255  # negro y blanco al final


@pytest.mark.parametrize("orientacion, eje", [("V", 1), ("H", 0)])
def test_decodificacion_exacta(secuencia, orientacion, eje):
    """u_p (franjas V) y v_p (franjas H) decodificados = coordenada real: error 0.000 px."""
    inicio = 0 if orientacion == "H" else cfg.IMAGENES_POR_ORIENTACION
    rel = fase.fase_relativa(secuencia[inicio:inicio + N], gamma_th=0.0, suavizado=0.0)
    bits = fase.bits_gray(secuencia[inicio + N:inicio + N + B], rel["A"], med_filt_size=0)
    k = fase.decodificar_gray(bits, "msb")  # los .bmp van con el bit más significativo primero
    coord = fase.coordenada_proyector(fase.fase_absoluta(rel["phi"], k, P, med_filt_size=0), P)
    real = np.indices(coord.shape)[eje].astype(np.float64)
    assert np.max(np.abs(coord - real)) < 1e-6


def test_detecta_orden_de_bits(secuencia):
    """Con los bits invertidos (como llegan con la secuencia cargada), «auto» detecta LSB."""
    inicio = cfg.IMAGENES_POR_ORIENTACION
    rel = fase.fase_relativa(secuencia[inicio:inicio + N, :200, :400], gamma_th=0.0)
    bits = fase.bits_gray(secuencia[inicio + N:inicio + N + B, :200, :400][::-1], rel["A"], med_filt_size=0)
    orden, _ = fase.detectar_orden_bits(rel["phi"], bits, P, np.ones(rel["phi"].shape, bool), 0)
    assert orden == "lsb"


def test_firma_cambia_con_los_parametros():
    a = fase.firma_absoluta(18, 6, 0.15, 0.03, 5, "auto", 25, 15)
    assert a == fase.firma_absoluta(18, 6, 0.15, 0.03, 5, "auto", 25, 15)
    assert a != fase.firma_absoluta(18, 6, 0.0, 0.03, 5, "auto", 25, 15)
    assert fase.firma_relativa(18, 1.5) != fase.firma_relativa(18, 0.0)


def test_actualizado_respeta_la_firma(tmp_path):
    entrada = tmp_path / "entrada.txt"
    entrada.write_text("x")
    salida = tmp_path / "salida.npz"
    fase.guardar_npz_atomico(salida, firma=np.array("rel|18|1.5"), dato=np.zeros(3))
    assert fase._actualizado(salida, [entrada], "rel|18|1.5")
    assert not fase._actualizado(salida, [entrada], "rel|18|0")
    assert not list(tmp_path.glob("*.tmp"))  # la escritura atómica no deja temporales
