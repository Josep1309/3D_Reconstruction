"""Montajes (LightCrafter / proyector HDMI): perfiles, captura sincronizada y separación de datos."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np

from conftest import RAIZ
from datos_sistema import configuracion as cfg
from datos_sistema import sesiones


def _cfg_con(montaje: str) -> dict:
    """Valores de configuración en un proceso nuevo con ese montaje (se fijan al importar)."""
    codigo = ("import json; from datos_sistema import configuracion as c; print(json.dumps({k: getattr(c, k) for k in "
              "('MONTAJE','PROYECTOR_ANCHO','PROYECTOR_ALTO','N_BITS_GRAY','IMAGENES_POR_CICLO','CAM_TRIGGER_OVERLAP','CAM_ALTO','CAM_DEBOUNCE_US')}"
              " | {'patrones': c.DIR_PATRONES.name, 'calib': c.DIR_CALIBRACION.name}))")
    env = {**os.environ, "TESIS_MONTAJE": montaje}
    env.pop("TESIS_DIR_CALIBRACION", None)
    salida = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, env=env, capture_output=True, text=True, check=True)
    return json.loads(salida.stdout)


def test_perfiles_de_montaje():
    lc = _cfg_con("lightcrafter")
    assert (lc["PROYECTOR_ANCHO"], lc["PROYECTOR_ALTO"], lc["N_BITS_GRAY"], lc["IMAGENES_POR_CICLO"]) == (912, 1140, 6, 50)
    assert lc["calib"] == "calibraciones" and lc["CAM_TRIGGER_OVERLAP"] == "Off"
    assert lc["CAM_ALTO"] == 1024                                                  # la ROI de siempre
    hd = _cfg_con("hdmi_dell")
    assert (hd["PROYECTOR_ANCHO"], hd["PROYECTOR_ALTO"], hd["N_BITS_GRAY"], hd["IMAGENES_POR_CICLO"]) == (1280, 800, 7, 52)
    assert 2 ** hd["N_BITS_GRAY"] * cfg.PERIODO >= hd["PROYECTOR_ANCHO"]          # los bits cubren todo el ancho
    assert hd["calib"] == "hdmi_dell" and hd["patrones"] == "hdmi_dell_1280x800" and hd["CAM_TRIGGER_OVERLAP"] == "ReadOut"
    # a 60 Hz la cámara solo alcanza con 960 filas, y el pulso de VSYNC (~0.1 ms) pasa el antirrebote
    assert hd["CAM_ALTO"] == 960 and hd["CAM_DEBOUNCE_US"] < 100
    assert _cfg_con("no_existe")["MONTAJE"] == "lightcrafter"                    # uno desconocido no rompe nada


def test_captura_sincronizada_en_orden():
    """Cada imagen guardada corresponde a su patrón (el búfer se vacía y se espera la latencia)."""
    from captura import capturar_patrones as cp
    from captura import proyector_hdmi as ph

    patrones = [np.full((cfg.PROYECTOR_ALTO, cfg.PROYECTOR_ANCHO), v, np.uint8) for v in (0, 60, 120, 180, 240)]
    cam = cp.CamaraSimuladaHDMI(periodo_s=0)
    with cam, ph.ProyectorSimulado() as proy:
        frames = cam.capturar_sincronizado(proy, patrones, latencia=2)
    medias = [float(f.mean()) for f in frames]
    assert len(frames) == 5 and all(a < b for a, b in zip(medias, medias[1:]))     # siguen el orden de los patrones


def test_la_configuracion_no_mezcla_montajes(monkeypatch):
    lista = [{"id": "a", "inicio": None, "fin": None, "items": [], "patron": True, "montaje": "lightcrafter"},
             {"id": "b", "inicio": None, "fin": None, "items": [], "patron": True, "montaje": "hdmi_dell"}]
    monkeypatch.setattr(sesiones, "procesos", lambda *a, **k: lista)
    sesiones._cache.clear()
    monkeypatch.setattr(cfg, "MONTAJE", "hdmi_dell")
    sesiones._cache.clear()
    v = sesiones.configuracion_vigente()
    assert v["proceso"] == "b"
    monkeypatch.setattr(sesiones, "procesos", lambda *a, **k: lista[:1])       # el montaje en uso aún sin capturas
    sesiones._cache.clear()
    v = sesiones.configuracion_vigente()
    assert v is not None and not any(v["poses"].values())                       # no muestra las del otro
    sesiones._cache.clear()
