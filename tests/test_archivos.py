"""Papelera: mover una captura con todo lo derivado y restaurarla tal cual (mismos nombres)."""

from __future__ import annotations

import json
import shutil

import archivos
import configuracion as cfg
import sesiones


def _preparar():
    for d in (cfg.DIR_CAPTURAS, cfg.DIR_ORDENADAS, cfg.DIR_RESULTADOS, archivos.PAPELERA):
        shutil.rmtree(d, ignore_errors=True)
    sesiones.REGISTRO.unlink(missing_ok=True)
    nombre = "20261125_090000"
    (cfg.DIR_CAPTURAS / "objeto" / nombre).mkdir(parents=True)
    (cfg.DIR_CAPTURAS / "objeto" / nombre / "objeto_frame_000.tiff").write_bytes(b"x")
    (cfg.DIR_ORDENADAS / "objeto" / "pose_04" / "H").mkdir(parents=True)
    (cfg.DIR_ORDENADAS / "objeto" / "pose_04" / "H" / "P18_F00.tiff").write_bytes(b"y")
    fases = cfg.DIR_RESULTADOS / "fases" / "objeto"
    fases.mkdir(parents=True)
    for f in ("pose_04.npz", "pose_04_relativa.npz", "pose_40.npz"):
        (fases / f).write_bytes(b"z")
    (cfg.DIR_ORDENADAS / "manifiesto.json").write_text(json.dumps({"version": 1, "poses": [
        {"categoria": "objeto", "pose": 4, "fuente": f"capturas/objeto/{nombre}", "firma": "f", "segmento": 0}]}))
    sesiones.registrar_proceso([cfg.DIR_CAPTURAS / "objeto" / nombre], [("objeto", 1)])
    return f"objeto/{nombre}"


def test_papelera_ida_y_vuelta():
    clave = _preparar()
    r = archivos.mover_a_papelera([clave])
    assert r["elementos"] == 4  # captura, pose organizada y sus 2 fases (no pose_40)
    assert not (cfg.DIR_CAPTURAS / clave).exists()
    assert (cfg.DIR_RESULTADOS / "fases" / "objeto" / "pose_40.npz").exists()
    manifiesto = json.loads((cfg.DIR_ORDENADAS / "manifiesto.json").read_text())
    assert manifiesto["poses"] == [] and manifiesto["ultimo_indice"]["objeto"] == 4
    lotes = archivos.listar_papelera()
    assert len(lotes) == 1 and lotes[0]["restaurable"] and lotes[0]["capturas"] == [clave]

    res = archivos.restaurar(lotes[0]["id"])
    assert res["conflictos"] == [] and res["devueltos"] >= 3
    assert (cfg.DIR_CAPTURAS / clave / "objeto_frame_000.tiff").exists()
    assert (cfg.DIR_ORDENADAS / "objeto" / "pose_04" / "H" / "P18_F00.tiff").exists()
    assert (cfg.DIR_RESULTADOS / "fases" / "objeto" / "pose_04_relativa.npz").exists()
    manifiesto = json.loads((cfg.DIR_ORDENADAS / "manifiesto.json").read_text())
    assert [(e["categoria"], e["pose"]) for e in manifiesto["poses"]] == [("objeto", 4)]  # mismo nombre
    assert any(clave in e["carpetas"] for e in sesiones.leer_registro())
    assert archivos.listar_papelera() == []


def test_rutas_fuera_de_capturas_rechazadas():
    import pytest

    for mala in ("../etc", "objeto/../../x", "otra/20261125_090000", "objeto/.oculto"):
        with pytest.raises(ValueError):
            archivos.ruta_captura(mala)


def test_notas_simultaneas_no_se_pierden_ni_se_corrompen():
    import threading

    archivos.NOTAS.unlink(missing_ok=True)
    hilos = [threading.Thread(target=archivos.guardar_nota, args=(f"pose:objeto/pose_{i:02d}", f"pieza {i}"))
             for i in range(40)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    notas = archivos.leer_notas()
    assert len(notas) == 40 and notas["pose:objeto/pose_07"] == "pieza 7"
