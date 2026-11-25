"""Análisis estático: nombres sin definir, imports rotos (lo que un error de tipeo deja pasar)."""

from __future__ import annotations

import shutil
import subprocess
import sys

import pytest

from conftest import RAIZ


@pytest.mark.skipif(shutil.which("ruff") is None and subprocess.run(
    [sys.executable, "-m", "ruff", "--version"], capture_output=True).returncode != 0, reason="ruff no instalado")
def test_sin_nombres_indefinidos():
    r = subprocess.run([sys.executable, "-m", "ruff", "check", "--select", "F,E9", "--quiet", str(RAIZ)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_modulos_importan():
    import importlib

    for modulo in ("pipeline", "fase", "calibracion_estereo", "reconstruccion_3d", "organizar_capturas",
                   "capturar_patrones", "sesiones", "archivos", "verificar", "servidor", "ejecutor"):
        importlib.import_module(modulo)
