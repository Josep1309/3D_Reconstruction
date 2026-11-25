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


def test_ajustes_de_la_interfaz(monkeypatch):
    import ejecutor

    for clave in ("PATRON_DISTANCIA_MM", "GAMMA_TH", "SALTO_MAX_MM", "MED_FILT"):
        monkeypatch.setattr(cfg, clave, getattr(cfg, clave))  # se restauran al terminar
    cambios = ejecutor.aplicar_ajustes({"PATRON_DX_MM": 15.0588, "PATRON_DY_MM": 14.909, "GAMMA_TH": None,
                                        "SALTO_MAX_MM": 7, "MED_FILT": 3.0})
    assert cfg.PATRON_DISTANCIA_MM == (15.0588, 14.909)
    assert cfg.GAMMA_TH == 0.0 and cfg.SALTO_MAX_MM == 7.0 and cfg.MED_FILT == 3 and isinstance(cfg.MED_FILT, int)
    assert any("GAMMA_TH=desactivado" in c for c in cambios)


def test_ajustes_guardados_y_firmas(tmp_path):
    import ajustes

    ruta = tmp_path / "ajustes.json"
    ajustes.guardar({"efectivos": {"SUAVIZADO_FASE_PX": None, "GAMMA_TH": 0.2, "MED_FILT": 3}}, ruta)
    efectivos = ajustes.leer(ruta)["efectivos"]
    v = ajustes.valores(efectivos)
    assert v["SUAVIZADO_FASE_PX"] == 0.0 and v["GAMMA_TH"] == 0.2 and v["MED_FILT"] == 3
    rel, absoluta = ajustes.firmas_esperadas(efectivos)
    por_defecto = ajustes.firmas_esperadas({})
    assert rel != por_defecto[0] and absoluta != por_defecto[1]
    assert "γX≥0.2" in ajustes.describir_firma(absoluta)


def test_seleccion_manual_de_poses(datos):
    # Patrón de la primera sesión + objeto medido mucho después: no forman una configuración por procesos
    sesiones.fijar_seleccion({"patron": ["pose_00", "pose_02"], "objeto": ["pose_01"]})
    conf = sesiones.configuracion_vigente()
    assert conf["manual"] and conf["poses"]["patron"] == {"pose_00", "pose_02"}
    assert conf["poses"]["objeto"] == {"pose_01"} and conf["poses"]["plano"] == set()
    assert sesiones.poses_vigentes("patron") == {"pose_00", "pose_02"}
    assert "selección manual" in sesiones.resumen_texto()
    sesiones.fijar_configuracion(None)
    assert not sesiones.configuracion_vigente().get("manual")
    with pytest.raises(ValueError):
        sesiones.fijar_seleccion({"patron": []})


def _fijar_en(minutos: float) -> None:
    """Simula que la configuración se eligió en T0 + minutos."""
    datos = json.loads(sesiones.ELEGIDA.read_text())
    datos["fijada"] = (T0 + timedelta(minutes=minutos)).isoformat()
    sesiones.ELEGIDA.write_text(json.dumps(datos))
    sesiones._cache.clear()


def test_capturas_nuevas_se_suman_a_la_seleccion(datos):
    """Con una selección manual, un objeto capturado después aparece solo (sin recalibrar)."""
    sesiones.fijar_seleccion({"patron": ["pose_00", "pose_01"], "plano": ["pose_00"]})
    _fijar_en(200)  # se eligió entre el objeto de las 12:01 y el de las 15:00
    v = sesiones.configuracion_vigente()
    assert v["poses"]["objeto"] == {"pose_01"}           # el posterior, sí; el anterior, no
    assert v["poses"]["patron"] == {"pose_00", "pose_01"}  # la calibración no cambia
    assert v["nuevas"] == 1


def test_capturas_nuevas_se_suman_al_proceso_elegido(datos):
    primera = sesiones.procesos()[0]["id"]
    sesiones.fijar_configuracion(primera)
    _fijar_en(200)
    v = sesiones.configuracion_vigente()
    assert "pose_01" in v["poses"]["objeto"] and "pose_00" not in v["poses"]["objeto"]
    assert v["poses"]["patron"] == {"pose_00", "pose_01", "pose_02"}
