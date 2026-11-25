"""Estructura por proceso: rutas.py resuelve las dos estructuras y la migración es reversible."""

from __future__ import annotations

import json
import shutil

import configuracion as cfg
import migrar_por_proceso as mig
import rutas
import sesiones


def _estructura_anterior():
    for d in (cfg.DIR_CAPTURAS, cfg.DIR_ORDENADAS, cfg.DIR_RESULTADOS):
        shutil.rmtree(d, ignore_errors=True)
    sesiones.REGISTRO.unlink(missing_ok=True)
    sesiones.ELEGIDA.unlink(missing_ok=True)
    man = []
    for i, (cat, hora) in enumerate([("patron", "20261125_090000"), ("patron", "20261125_090030"), ("plano", "20261125_090100")]):
        (cfg.DIR_CAPTURAS / cat / hora).mkdir(parents=True)
        (cfg.DIR_CAPTURAS / cat / hora / "f_000.tiff").write_bytes(b"x")
        pose = f"pose_{i:02d}"
        (cfg.DIR_ORDENADAS / cat / pose / "H").mkdir(parents=True)
        (cfg.DIR_ORDENADAS / cat / pose / "H" / "P18_F00.tiff").write_bytes(b"y")
        (cfg.DIR_RESULTADOS / "fases" / cat).mkdir(parents=True, exist_ok=True)
        (cfg.DIR_RESULTADOS / "fases" / cat / f"{pose}.npz").write_bytes(b"z")
        man.append({"categoria": cat, "pose": i, "carpeta": f"capturas_ordenadas/{cat}/{pose}",
                    "fuente": f"capturas/{cat}/{hora}", "firma": f"imagenes|capturas/{cat}/{hora}|1|abc", "segmento": 0})
    (cfg.DIR_ORDENADAS / "manifiesto.json").write_text(json.dumps({"version": 1, "poses": man}))
    sesiones._cache.clear()


def test_rutas_en_la_estructura_anterior():
    _estructura_anterior()
    assert rutas.poses("patron") == ["pose_00", "pose_01"]
    assert rutas.dir_pose_ordenada("patron", "pose_01") == cfg.DIR_ORDENADAS / "patron" / "pose_01"
    assert rutas.fase_absoluta("plano", "pose_02") == cfg.DIR_RESULTADOS / "fases" / "plano" / "pose_02.npz"
    assert rutas.ruta_captura("plano/20261125_090100") == cfg.DIR_CAPTURAS / "plano" / "20261125_090100"


def test_migracion_ida_y_vuelta():
    _estructura_anterior()
    antes = json.loads((cfg.DIR_ORDENADAS / "manifiesto.json").read_text())
    plan = mig.planificar()
    assert len(plan["procesos"]) == 1  # capturas seguidas: un solo proceso
    respaldo = mig.aplicar(plan)
    P = plan["procesos"][0]["proceso"]
    assert rutas.es_proceso(P)
    # todo quedó dentro de la carpeta del proceso y rutas.py lo encuentra
    assert (cfg.DIR_CAPTURAS / P / "patron" / "20261125_090000" / "f_000.tiff").exists()
    assert rutas.dir_pose_ordenada("patron", "pose_01") == cfg.DIR_ORDENADAS / P / "patron" / "pose_01"
    assert rutas.fase_absoluta("plano", "pose_02").exists()
    assert rutas.fase_absoluta("plano", "pose_02").parent == cfg.DIR_RESULTADOS / P / "fases" / "plano"
    assert rutas.ruta_captura("plano/20261125_090100") == cfg.DIR_CAPTURAS / P / "plano" / "20261125_090100"
    assert (cfg.DIR_ORDENADAS / P / "patron" / "pose_00" / "origen.json").exists()
    proceso = json.loads((cfg.DIR_CAPTURAS / P / "proceso.json").read_text())
    assert proceso["poses"] == {"patron": ["pose_00", "pose_01"], "plano": ["pose_02"]}
    e = json.loads((cfg.DIR_ORDENADAS / "manifiesto.json").read_text())["poses"][0]
    assert e["fuente"] == f"capturas/{P}/patron/20261125_090000" and e["fuente"] in e["firma"]
    # el sistema ve los mismos procesos y poses
    assert [len(p["items"]) for p in sesiones.procesos()] == [3]
    assert not (cfg.DIR_CAPTURAS / "patron").exists()
    # deshacer deja todo como estaba
    mig.deshacer(respaldo.name)
    assert json.loads((cfg.DIR_ORDENADAS / "manifiesto.json").read_text()) == antes
    assert (cfg.DIR_CAPTURAS / "patron" / "20261125_090000" / "f_000.tiff").exists()
    assert not (cfg.DIR_CAPTURAS / P).exists()
    assert mig.planificar()["movimientos"]  # se puede volver a migrar


def test_papelera_con_carpetas_de_proceso():
    import archivos

    _estructura_anterior()
    shutil.rmtree(archivos.PAPELERA, ignore_errors=True)
    plan = mig.planificar()
    mig.aplicar(plan)
    P = plan["procesos"][0]["proceso"]
    todas = ["patron/20261125_090000", "patron/20261125_090030", "plano/20261125_090100"]
    archivos.mover_a_papelera(todas)
    assert not (cfg.DIR_CAPTURAS / P).exists() and not (cfg.DIR_ORDENADAS / P).exists()
    lote = archivos.listar_papelera()[0]
    assert lote["restaurable"] and sorted(lote["capturas"]) == todas
    archivos.restaurar(lote["id"])
    assert (cfg.DIR_CAPTURAS / P / "proceso.json").exists()  # el proceso vuelve completo
    assert rutas.fase_absoluta("plano", "pose_02").exists()
    assert rutas.dir_pose_ordenada("patron", "pose_00").parent.parent.name == P


def test_importar_carpeta_externa(tmp_path):
    import importar

    _estructura_anterior()
    externa = tmp_path / "viejas"
    (externa / "patron" / "toma1").mkdir(parents=True)
    (externa / "patron" / "toma1" / "a.tiff").write_bytes(b"1")
    (externa / "objeto").mkdir()
    (externa / "objeto" / "f_00.tiff").write_bytes(b"2")  # imágenes sueltas = una captura
    (externa / "plano" / "20261125_090100").mkdir(parents=True)  # ya está en el sistema
    (externa / "plano" / "20261125_090100" / "b.tiff").write_bytes(b"3")
    (externa / "otra").mkdir()
    plan = importar.analizar(externa)
    assert sorted(plan["capturas"]) == ["objeto", "patron"]
    assert plan["omitidas"] == ["plano/20261125_090100"] and plan["ignoradas"] == ["otra"]
    res = importar.importar(externa)
    P = res["proceso"]
    assert (cfg.DIR_CAPTURAS / P / "patron" / "toma1" / "a.tiff").exists()
    assert (externa / "patron" / "toma1" / "a.tiff").exists()  # el original no se toca
    assert json.loads((cfg.DIR_CAPTURAS / P / "proceso.json").read_text())["origen"] == str(externa)
    sesiones.fijar_solo_proceso(P)
    v = sesiones.configuracion_vigente()
    assert v["carpetas"] == {f"{c}/{x['nombre']}" for c, lista in res["capturas"].items() for x in lista}
    assert importar.analizar(externa)["capturas"] == {}  # volver a importar no duplica
