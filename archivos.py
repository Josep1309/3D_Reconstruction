"""Navegador de archivos de la interfaz: imágenes de una captura y limpieza a la papelera.

Borrar una captura mueve a `<DATOS>/papelera/<fecha>/` todo lo que depende de ella, conservando
sus rutas relativas para poder restaurarlo a mano:
- la carpeta cruda de `capturas/<cat>/`;
- sus poses organizadas de `capturas_ordenadas/<cat>/pose_XX/`;
- las fases de `resultados/fases/<cat>/pose_XX*`;
- la reconstrucción de `resultados/reconstruccion/<cat>/<cat>_pose_XX.*`.

También se quitan sus entradas del manifiesto, del resumen de la reconstrucción y del registro de
procesos. Los índices de pose borrados no se reutilizan (`manifiesto["ultimo_indice"]`). Nada se
elimina de verdad hasta vaciar la papelera.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import configuracion as cfg
import sesiones

PAPELERA = cfg.DATOS / "papelera"
EXT_IMAGEN = {".png", ".tif", ".tiff", ".bmp", ".jpg", ".jpeg"}


def ruta_captura(clave: str) -> Path:
    """'patron/20261124_130228' -> ruta dentro de capturas/ (sin permitir salir de ella)."""
    cat, _, nombre = clave.partition("/")
    if cat not in cfg.CATEGORIAS or not nombre or "/" in nombre or nombre.startswith("."):
        raise ValueError(f"captura inválida: {clave}")
    return cfg.DIR_CAPTURAS / cat / nombre


def frames_captura(clave: str) -> list[Path]:
    """Imágenes de una captura cruda, en orden natural."""
    ruta = ruta_captura(clave)
    if not ruta.is_dir():
        raise FileNotFoundError(f"no existe la captura {clave}")
    return sorted((p for p in ruta.rglob("*") if p.suffix.lower() in EXT_IMAGEN),
                  key=lambda p: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p.name)])


def leer_frame(clave: str, indice: int) -> np.ndarray:
    frames = frames_captura(clave)
    if not 0 <= indice < len(frames):
        raise FileNotFoundError(f"la captura {clave} tiene {len(frames)} imágenes")
    img = cv2.imread(str(frames[indice]), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise OSError(f"no se pudo leer {frames[indice].name}")
    if img.dtype != np.uint8:
        img = (img >> 8).astype(np.uint8) if img.dtype == np.uint16 else np.clip(img, 0, 255).astype(np.uint8)
    return img


def _mover(origen: Path, destino_raiz: Path) -> bool:
    if not origen.exists():
        return False
    try:
        relativa = origen.resolve().relative_to(cfg.DATOS.resolve())
    except ValueError:
        relativa = Path(origen.name)
    destino = destino_raiz / relativa
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(origen), str(destino))
    return True


def mover_a_papelera(carpetas: list[str]) -> dict:
    """Mueve a la papelera las capturas indicadas ('cat/nombre') y todo lo derivado de ellas."""
    items = {i["carpeta"]: i for i in sesiones.capturas()}
    destino = PAPELERA / datetime.now().strftime("%Y%m%d_%H%M%S")
    movidos = 0
    poses_borradas: dict[str, set[str]] = {}
    for clave in carpetas:
        ruta = ruta_captura(clave)  # valida el nombre
        cat = clave.split("/")[0]
        poses = items.get(clave, {}).get("poses", [])
        poses_borradas.setdefault(cat, set()).update(poses)
        movidos += _mover(ruta, destino)
        for pose in poses:
            movidos += _mover(cfg.DIR_ORDENADAS / cat / pose, destino)
            for archivo in (cfg.DIR_RESULTADOS / "fases" / cat).glob(f"{pose}[._]*"):
                movidos += _mover(archivo, destino)
            dir_rec = cfg.DIR_RESULTADOS / "reconstruccion" / cat
            for archivo in [*dir_rec.glob(f"{cat}_{pose}.*"), *dir_rec.glob(f"reconstruccion_{cat}_{pose}.*")]:
                movidos += _mover(archivo, destino)
    _actualizar_indices(poses_borradas, set(carpetas))
    sesiones.quitar_del_registro(set(carpetas))
    sesiones._cache.clear()
    return {"carpetas": len(carpetas), "elementos": movidos, "papelera": str(destino)}


def _actualizar_indices(poses_borradas: dict[str, set[str]], carpetas: set[str]) -> None:
    ruta = cfg.DIR_ORDENADAS / "manifiesto.json"
    try:
        manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifiesto = None
    if manifiesto is not None:
        ultimo = manifiesto.setdefault("ultimo_indice", {})
        for e in manifiesto.get("poses", []):
            ultimo[e["categoria"]] = max(int(ultimo.get(e["categoria"], -1)), int(e["pose"]))
        manifiesto["poses"] = [
            e for e in manifiesto.get("poses", [])
            if f"pose_{int(e['pose']):02d}" not in poses_borradas.get(e["categoria"], set())
        ]
        manifiesto["rechazadas"] = {f: r for f, r in manifiesto.get("rechazadas", {}).items()
                                    if sesiones.clave_carpeta(r.get("fuente", "")) not in carpetas}
        tmp = ruta.with_name(ruta.name + ".tmp")
        tmp.write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ruta)
    for cat, poses in poses_borradas.items():
        ruta_res = cfg.DIR_RESULTADOS / "reconstruccion" / cat / f"{cat}_resumen.json"
        try:
            resumen = json.loads(ruta_res.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ruta_res.write_text(json.dumps({k: v for k, v in resumen.items() if k not in poses}, indent=2),
                            encoding="utf-8")


def info_papelera() -> dict:
    if not PAPELERA.is_dir():
        return {"lotes": 0, "bytes": 0}
    total = sum(p.stat().st_size for p in PAPELERA.rglob("*") if p.is_file())
    return {"lotes": sum(1 for p in PAPELERA.iterdir() if p.is_dir()), "bytes": total}


def vaciar_papelera() -> dict:
    info = info_papelera()
    if PAPELERA.is_dir():
        shutil.rmtree(PAPELERA)
    return info
