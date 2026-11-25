"""Configuración común de las pruebas.

Cada prueba que toca datos usa una carpeta temporal como DATOS (TESIS_DIR_DATOS) y otra como
calibración, así nunca se leen ni se modifican las capturas reales. `configuracion` lee esas
variables al importarse, por eso se fijan aquí, antes de importar cualquier módulo del proyecto.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "interfaz"))

_DATOS = Path(tempfile.mkdtemp(prefix="tesis_datos_"))
_CALIB = Path(tempfile.mkdtemp(prefix="tesis_calib_"))
os.environ["TESIS_DIR_DATOS"] = str(_DATOS)
os.environ["TESIS_DIR_CALIBRACION"] = str(_CALIB)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
