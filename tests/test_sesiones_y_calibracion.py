"""Procesos de captura, configuración vigente y control de calidad de la calibración."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

import calibracion_estereo as ce
import configuracion as cfg
import sesiones

T0 = datetime(2026, 11, 24, 10, 0, 0)


def _crear(cat: str, minutos: float, pose: int | None, manifiesto: list) -> str:
    nombre = (T0 + timedelta(minutes=minutos)).strftime("%Y%m%d_%H%M%S")
    (cfg.DIR_CAPTURAS / cat / nombre).mkdir(parents=True, exist_ok=True)
    if pose is not None:
        manifiesto.append({"categoria": cat, "pose": pose, "fuente": f"capturas/{cat}/{nombre}", "firma": nombre,
                           "segmento": 0})
    return f"{cat}/{nombre}"


@pytest.fixture()
def datos():
    """Dos montajes: patrón+plano (10:00) y, 2 h después, patrón+objeto (12:00) + objeto suelto."""
    import shutil

    for d in (cfg.DIR_CAPTURAS, cfg.DIR_ORDENADAS):
        shutil.rmtree(d, ignore_errors=True)
    sesiones.REGISTRO.unlink(missing_ok=True)
    sesiones.ELEGIDA.unlink(missing_ok=True)
    man: list = []
    _crear("patron", 0, 0, man)
    _crear("patron", 1, 1, man)
    _crear("patron", 6, 2, man)    # pausa de 5 min, pero sigue el patrón: mismo proceso
    _crear("plano", 7, 0, man)
    _crear("patron", 120, 3, man)
    _crear("objeto", 121, 0, man)
    _crear("objeto", 300, 1, man)  # medido mucho después, sin recalibrar
    _crear("plano", 122, None, man)  # captura que no se organizó
    cfg.DIR_ORDENADAS.mkdir(parents=True, exist_ok=True)
    (cfg.DIR_ORDENADAS / "manifiesto.json").write_text(json.dumps({"version": 1, "poses": man}))
    sesiones._cache.clear()
    yield
    sesiones.ELEGIDA.unlink(missing_ok=True)


def test_procesos_y_configuraciones(datos):
    lista = sesiones.procesos()
    assert [p["patron"] for p in lista] == [True, True, False]
    assert len(lista[0]["items"]) == 4  # la pausa de 5 min en el patrón no parte el proceso
    assert sesiones.configuraciones(lista) == [(0, 1), (1, 3)]


def test_vigente_es_la_ultima_y_se_puede_elegir(datos):
    conf = sesiones.configuracion_vigente()
    assert conf["auto"] and conf["poses"]["patron"] == {"pose_03"}
    assert conf["poses"]["objeto"] == {"pose_00", "pose_01"}
    primera = sesiones.procesos()[0]["id"]
    sesiones.fijar_configuracion(primera)
    conf = sesiones.configuracion_vigente()
    assert not conf["auto"] and conf["poses"]["patron"] == {"pose_00", "pose_01", "pose_02"}
    assert conf["poses"]["objeto"] == set()
    sesiones.fijar_configuracion(None)
    assert sesiones.configuracion_vigente()["auto"]


def test_registrar_proceso_con_patron_vuelve_a_la_ultima(datos):
    sesiones.fijar_configuracion(sesiones.procesos()[0]["id"])
    nueva = _crear("patron", 400, None, [])
    sesiones.registrar_proceso([cfg.DIR_CAPTURAS / nueva], [("patron", 1)])
    assert not sesiones.ELEGIDA.exists()
    assert sesiones.leer_registro()[-1]["carpetas"] == [nueva]


def _resumen(**cambios) -> dict:
    base = {"rms_stereo_indep_px": 0.6, "rms_cam_px": 0.55, "rms_proj_px": 0.5, "poses": [f"pose_{i:02d}" for i in range(7)],
            "cobertura_up_px": [200, 760], "cobertura_vp_px": [170, 1070]}
    return {**base, **cambios}


def test_control_calidad_aprueba_una_buena():
    assert ce.control_calidad(_resumen()) == []


@pytest.mark.parametrize("cambios, texto", [
    ({"rms_stereo_indep_px": 12.8}, "RMS estéreo"),          # poses de dos montajes (caso real)
    ({"poses": ["pose_00", "pose_01", "pose_02"]}, "poses"),
    ({"cobertura_up_px": [400, 600]}, "ancho"),
])
def test_control_calidad_rechaza(cambios, texto):
    motivos = ce.control_calidad(_resumen(**cambios))
    assert motivos and any(texto in m for m in motivos)


def test_pipeline_no_reconstruye_con_calibracion_rechazada(monkeypatch):
    import pipeline

    monkeypatch.setattr(ce, "ejecutar_calibracion_estereo", lambda *a, **k: {"en_uso": False})
    monkeypatch.setitem(pipeline.ETAPAS, "reconstruccion", True)
    with pytest.raises(RuntimeError, match="control de calidad"):
        pipeline.etapa_calibracion()
    monkeypatch.setattr(ce, "ejecutar_calibracion_estereo", lambda *a, **k: {"en_uso": True})
    pipeline.etapa_calibracion()  # aprobada: sigue sin error
