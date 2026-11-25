"""Rutas, expresiones y utilidades compartidas por los módulos del servidor web."""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import configuracion as cfg  # noqa: E402


DIR_ESTATICO = Path(__file__).resolve().parent / "estatico"
DIR_FASES = cfg.DIR_RESULTADOS / "fases"
DIR_RECONSTRUCCION = cfg.DIR_RESULTADOS / "reconstruccion"
DIR_CALIBRACION = cfg.DIR_CALIBRACION
ARCHIVO_VIVO = cfg.DIR_RESULTADOS / ".vivo" / "frame.jpg"
RE_POSE = re.compile(r"^pose_\d+$")
RE_ORDENADA = re.compile(r"^img_([HV])_(\d{1,2})$")


def _mtime(ruta: Path) -> float | None:
    try:
        return ruta.stat().st_mtime
    except OSError:
        return None


def _archivos_pose(cat: str, pose: str) -> dict[str, Path]:
    """Archivos de cada paso de una pose, en la carpeta de su proceso (rutas.py)."""
    import rutas

    return {
        "organizada": rutas.dir_pose_ordenada(cat, pose) / "H" / f"{cfg.PREFIJO_ORDENADAS}{cfg.IMAGENES_POR_ORIENTACION + 1:02d}.tiff",
        "relativa": rutas.fase_relativa(cat, pose),
        "absoluta": rutas.fase_absoluta(cat, pose),
        "reconstruida": rutas.reconstruccion(cat, pose),
    }


def listar_poses(cat: str) -> list[str]:
    """Poses de la categoría en la configuración vigente del montaje (sesiones.py)."""
    import rutas
    import sesiones

    vigentes = sesiones.poses_vigentes(cat)
    return [p for p in rutas.poses(cat) if vigentes is None or p in vigentes]


# ------------------------------------------------------------------ comparar resultados
DIR_COMPARACIONES = cfg.DIR_RESULTADOS / "comparaciones"
RE_REF = re.compile(r"^(copia:\d{8}_\d{6}_\w+|pose:pose_\d+)$")
