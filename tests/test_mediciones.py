"""Mediciones guardadas por pose (mediciones.py)."""

from __future__ import annotations

import math

import pytest

from datos_sistema import mediciones


def _p(fx, x, y, z):
    return {"fx": fx, "fy": 0.5, "X": x, "Y": y, "Z": z, "sigma_mm": 0.03}


def test_guardar_listar_borrar():
    mediciones.RUTA.unlink(missing_ok=True)
    r = mediciones.guardar("objeto", "pose_50", {"nombre": "ancho", "a": _p(0.2, 0, 0, 500), "b": _p(0.8, 30, 40, 500)})
    m = r["mediciones"][0]
    assert m["nombre"] == "ancho" and math.isclose(m["distancia_mm"], 50.0)
    assert mediciones.listar("objeto", "pose_51") == {"mediciones": []}
    assert mediciones.borrar("objeto", "pose_50", m["id"]) == {"mediciones": []}


def test_punto_invalido_rechazado():
    with pytest.raises(ValueError):
        mediciones.guardar("objeto", "pose_50", {"a": _p(1.5, 0, 0, 0), "b": _p(0.2, 1, 1, 1)})
    with pytest.raises(ValueError):
        mediciones.guardar("objeto", "pose_50", {"a": _p(0.1, float("nan"), 0, 0), "b": _p(0.2, 1, 1, 1)})


def test_actualizar_tras_reconstruir(monkeypatch):
    mediciones.RUTA.unlink(missing_ok=True)
    monkeypatch.setattr(mediciones, "firma_reconstruccion", lambda c, p: "v1")
    mediciones.guardar("plano", "pose_60", {"a": _p(0.2, 0, 0, 0), "b": _p(0.8, 10, 0, 0)})
    monkeypatch.setattr(mediciones, "firma_reconstruccion", lambda c, p: "v2")  # se reconstruyó
    assert mediciones.listar("plano", "pose_60")["mediciones"][0]["desactualizada"]
    r = mediciones.actualizar("plano", "pose_60", lambda fx, fy: _p(fx, 20 * fx, 0, 0))
    m = r["mediciones"][0]
    assert not m["desactualizada"] and math.isclose(m["distancia_mm"], 12.0) and r["fallidas"] == []
