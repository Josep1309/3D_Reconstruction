"""Dónde está cada cosa en la carpeta de datos.

Las tres carpetas de datos se ordenan igual, **por proceso de captura**:

    capturas/2026-11-24_1302/            proceso.json + patron/ plano/ objeto/ (capturas crudas)
    capturas_ordenadas/2026-11-24_1302/  patron/pose_23/{H,V} … (+ origen.json en cada pose)
    resultados/2026-11-24_1302/          fases/<cat>/pose_23*.npz · reconstruccion/<cat>/<cat>_pose_23.*

El nombre de la pose (`pose_23`) sigue siendo único dentro de su categoría en todo el sistema: es
su identidad (calibraciones, notas, selecciones). La carpeta del proceso solo es la ubicación, y
se lee del manifiesto (`carpeta` de cada pose). También se entiende la estructura anterior, sin
carpeta de proceso (`capturas/<cat>/…`, `capturas_ordenadas/<cat>/pose_XX`, `resultados/fases/<cat>`),
para lo que aún no se migró (`migrar_por_proceso.py`).

Lo que no es de una pose queda donde estaba: `resultados/calibracion/`, `resultados/comparaciones/`,
`resultados/reconstruccion/<cat>/<cat>_resumen.json` (resumen de todas las poses), etc.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path

import configuracion as cfg

RE_PROCESO = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}(_\d{2}(_\d+)?)?$")
FORMATO_PROCESO = "%Y-%m-%d_%H%M"

_cache: dict = {}
_lock = threading.Lock()


def es_proceso(nombre: str) -> bool:
    return bool(RE_PROCESO.match(nombre))


def nombre_proceso(hora: datetime, ocupados: set[str] | None = None) -> str:
    """Nombre de la carpeta de un proceso que empieza a esa hora (único entre los ya usados)."""
    ocupados = set(ocupados or ()) | {p.name for p in cfg.DIR_CAPTURAS.glob("*") if p.is_dir()}
    nombre = hora.strftime(FORMATO_PROCESO)
    if nombre in ocupados:
        nombre = hora.strftime(FORMATO_PROCESO + "_%S")
    k = 2
    base = nombre
    while nombre in ocupados:
        nombre, k = f"{base}_{k}", k + 1
    return nombre


def proceso_en_ruta(ruta: str | Path) -> str | None:
    """Carpeta de proceso que aparece en una ruta (capturas/<P>/<cat>/…), o None."""
    return next((p for p in Path(ruta).parts if es_proceso(p)), None)


# ------------------------------------------------------------------ poses organizadas (manifiesto)
def _manifiesto() -> dict:
    ruta = cfg.DIR_ORDENADAS / "manifiesto.json"
    try:
        m = ruta.stat().st_mtime_ns
    except OSError:
        return {}
    clave = (str(ruta), m)
    with _lock:
        if _cache.get("clave") != clave:
            try:
                datos = json.loads(ruta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                datos = {}
            proceso = {}
            for e in datos.get("poses", []):
                proceso[(e["categoria"], f"pose_{int(e['pose']):02d}")] = proceso_en_ruta(e.get("carpeta", ""))
            _cache.update(clave=clave, proceso=proceso)
        return _cache


def proceso_de_pose(cat: str, pose: str) -> str | None:
    """Carpeta del proceso de una pose organizada (None = estructura anterior, sin proceso)."""
    return _manifiesto().get("proceso", {}).get((cat, pose))


def poses(cat: str) -> list[str]:
    """Todas las poses organizadas de una categoría (manifiesto + carpetas existentes), en orden."""
    nombres = {p for (c, p) in _manifiesto().get("proceso", {}) if c == cat}
    for base in (cfg.DIR_ORDENADAS / cat, *(d / cat for d in _carpetas_proceso(cfg.DIR_ORDENADAS))):
        if base.is_dir():
            nombres.update(p.name for p in base.iterdir() if p.is_dir() and re.fullmatch(r"pose_\d+", p.name))
    return sorted(nombres, key=lambda n: int(n[5:]))


def _carpetas_proceso(base: Path) -> list[Path]:
    return sorted(p for p in base.glob("*") if p.is_dir() and es_proceso(p.name)) if base.is_dir() else []


def _base(raiz: Path, proceso: str | None) -> Path:
    return raiz / proceso if proceso else raiz


def dir_pose_ordenada(cat: str, pose: str) -> Path:
    proceso = proceso_de_pose(cat, pose)
    if proceso is None:  # sin manifiesto: buscar en las dos estructuras
        for d in [cfg.DIR_ORDENADAS / cat / pose, *(p / cat / pose for p in _carpetas_proceso(cfg.DIR_ORDENADAS))]:
            if d.is_dir():
                return d
    return _base(cfg.DIR_ORDENADAS, proceso) / cat / pose


def dir_fases(cat: str, pose: str) -> Path:
    """Carpeta con pose_XX.npz, pose_XX_relativa.npz y sus figuras."""
    proceso = proceso_de_pose(cat, pose)
    return (cfg.DIR_RESULTADOS / proceso / "fases" / cat) if proceso else (cfg.DIR_RESULTADOS / "fases" / cat)


def dir_reconstruccion(cat: str, pose: str) -> Path:
    """Carpeta con <cat>_pose_XX.npz / .ply y la figura reconstruccion_<cat>_pose_XX.png."""
    proceso = proceso_de_pose(cat, pose)
    return (cfg.DIR_RESULTADOS / proceso / "reconstruccion" / cat) if proceso else (cfg.DIR_RESULTADOS / "reconstruccion" / cat)


def dir_resumen(cat: str) -> Path:
    """Resumen de la reconstrucción de todas las poses de la categoría (no depende del proceso)."""
    return cfg.DIR_RESULTADOS / "reconstruccion" / cat


def fase_relativa(cat: str, pose: str) -> Path:
    return dir_fases(cat, pose) / f"{pose}_relativa.npz"


def fase_absoluta(cat: str, pose: str) -> Path:
    return dir_fases(cat, pose) / f"{pose}.npz"


def reconstruccion(cat: str, pose: str, ext: str = "npz") -> Path:
    return dir_reconstruccion(cat, pose) / f"{cat}_{pose}.{ext}"


def archivos_de_pose(cat: str, pose: str) -> list[Path]:
    """Todo lo derivado de una pose: carpeta organizada, fases y reconstrucción (lo que exista)."""
    salida = [dir_pose_ordenada(cat, pose)]
    df, dr = dir_fases(cat, pose), dir_reconstruccion(cat, pose)
    salida += sorted(df.glob(f"{pose}[._]*")) if df.is_dir() else []
    salida += sorted([*dr.glob(f"{cat}_{pose}.*"), *dr.glob(f"reconstruccion_{cat}_{pose}.*")]) if dr.is_dir() else []
    return [p for p in salida if p.exists()]


# ------------------------------------------------------------------ capturas crudas
def ruta_captura(clave: str) -> Path:
    """'patron/20261124_130228' -> su carpeta en capturas/ (en un proceso o en la estructura anterior).

    La clave «categoría/nombre» identifica una captura: el nombre (fecha y hora) es único."""
    cat, _, nombre = clave.partition("/")
    if cat not in cfg.CATEGORIAS or not nombre or "/" in nombre or nombre.startswith(".") or ".." in nombre:
        raise ValueError(f"captura inválida: {clave}")
    for p in _carpetas_proceso(cfg.DIR_CAPTURAS):
        if (p / cat / nombre).exists():
            return p / cat / nombre
    return cfg.DIR_CAPTURAS / cat / nombre


def capturas_en_disco() -> list[tuple[str, str, Path, str | None]]:
    """[(categoría, nombre, ruta, carpeta de proceso o None)] de todo capturas/."""
    salida = []
    for proceso, base in [(None, cfg.DIR_CAPTURAS), *((p.name, p) for p in _carpetas_proceso(cfg.DIR_CAPTURAS))]:
        for cat in cfg.CATEGORIAS:
            if (base / cat).is_dir():
                salida += [(cat, p.name, p, proceso) for p in sorted((base / cat).iterdir()) if not p.name.startswith(".")]
    return salida


def leer_proceso_json(proceso: str) -> dict:
    try:
        return json.loads((cfg.DIR_CAPTURAS / proceso / "proceso.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
