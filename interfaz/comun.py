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
    return {
        "organizada": cfg.DIR_ORDENADAS / cat / pose / "H" / f"{cfg.PREFIJO_ORDENADAS}{cfg.IMAGENES_POR_ORIENTACION + 1:02d}.tiff",
        "relativa": DIR_FASES / cat / f"{pose}_relativa.npz",
        "absoluta": DIR_FASES / cat / f"{pose}.npz",
        "reconstruida": DIR_RECONSTRUCCION / cat / f"{cat}_{pose}.npz",
    }


def listar_poses(cat: str) -> list[str]:
    """Poses de la categoría en la configuración vigente del montaje (sesiones.py)."""
    import sesiones

    vigentes = sesiones.poses_vigentes(cat)
    nombres = set()
    for carpeta in (cfg.DIR_ORDENADAS / cat, DIR_FASES / cat):
        if carpeta.is_dir():
            for p in carpeta.iterdir():
                nombre = p.name.split("_relativa")[0].removesuffix(".npz").removesuffix(".png")
                if RE_POSE.match(nombre) and (vigentes is None or nombre in vigentes):
                    nombres.add(nombre)
    return sorted(nombres, key=lambda n: int(n[5:]))


# ------------------------------------------------------------------ comparar resultados
DIR_COMPARACIONES = cfg.DIR_RESULTADOS / "comparaciones"
RE_REF = re.compile(r"^(copia:\d{8}_\d{6}_\w+|pose:pose_\d+)$")
