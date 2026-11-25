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
META = "papelera.json"  # qué se quitó del manifiesto y del registro (para restaurar)
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
    with sesiones.ESCRITURA:
        return _mover_a_papelera(carpetas)


def _mover_a_papelera(carpetas: list[str]) -> dict:
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
    quitadas = _actualizar_indices(poses_borradas, set(carpetas))
    registro = [e for e in sesiones.leer_registro() if set(e.get("carpetas", [])) & set(carpetas)]
    sesiones.quitar_del_registro(set(carpetas))
    sesiones._cache.clear()
    # Lo necesario para restaurar el lote tal como estaba (mismos nombres de pose)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / META).write_text(json.dumps({
        "fecha": datetime.now().isoformat(timespec="seconds"), "carpetas": carpetas,
        "manifiesto_poses": quitadas["poses"], "rechazadas": quitadas["rechazadas"],
        "registro": [{**e, "carpetas": [c for c in e["carpetas"] if c in carpetas]} for e in registro],
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"carpetas": len(carpetas), "elementos": movidos, "papelera": str(destino)}


def listar_papelera() -> list[dict]:
    """Lotes de la papelera (el más reciente primero) con lo que contiene cada uno."""
    lotes = []
    for lote in sorted((p for p in PAPELERA.glob("*") if p.is_dir()), reverse=True) if PAPELERA.is_dir() else []:
        try:
            meta = json.loads((lote / META).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
        capturas = meta.get("carpetas") or sorted(
            f"{c.parent.name}/{c.name}" for c in (lote / "capturas").glob("*/*")) if (lote / "capturas").is_dir() else meta.get("carpetas", [])
        raices = {q.name for q in lote.iterdir() if q.name != META}
        lotes.append({"id": lote.name, "fecha": meta.get("fecha"), "capturas": capturas,
                      # sin metadatos (p. ej. una pose repetida) se devuelven solo los archivos
                      "restaurable": raices <= {"capturas", "capturas_ordenadas", "resultados"},
                      "con_datos": bool(meta),
                      "bytes": sum(f.stat().st_size for f in lote.rglob("*") if f.is_file())})
    return lotes


def restaurar(lote_id: str) -> dict:
    """Devuelve un lote de la papelera a su lugar, con sus entradas del manifiesto y del registro.

    No pisa nada: si algo ya existe en el destino, ese elemento queda en la papelera."""
    with sesiones.ESCRITURA:
        return _restaurar(lote_id)


def _restaurar(lote_id: str) -> dict:
    lote = PAPELERA / lote_id
    if "/" in lote_id or lote_id.startswith(".") or not lote.is_dir():
        raise FileNotFoundError(f"no existe el lote {lote_id} en la papelera")
    try:
        meta = json.loads((lote / META).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        meta = {}
    raices = {p.name for p in lote.iterdir() if p.name != META}
    if not raices <= {"capturas", "capturas_ordenadas", "resultados"}:
        raise ValueError(f"el lote {lote_id} no tiene la estructura de la papelera (p. ej. viene de reorganizar): "
                         f"restáuralo a mano")
    devueltos, conflictos = 0, []
    for origen in sorted(p for p in lote.iterdir() if p.name != META):
        for elemento in ([origen] if origen.is_file() else _elementos(origen)):
            destino = cfg.DATOS / elemento.relative_to(lote)
            if destino.exists():
                conflictos.append(str(elemento.relative_to(lote)))
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(elemento), str(destino))
            devueltos += 1
    ruta_man = cfg.DIR_ORDENADAS / "manifiesto.json"
    if meta.get("manifiesto_poses") or meta.get("rechazadas"):
        try:
            manifiesto = json.loads(ruta_man.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifiesto = {"version": 1, "poses": []}
        existentes = {(e["categoria"], int(e["pose"])) for e in manifiesto.get("poses", [])}
        manifiesto.setdefault("poses", []).extend(
            e for e in meta.get("manifiesto_poses", []) if (e["categoria"], int(e["pose"])) not in existentes)
        manifiesto.setdefault("rechazadas", {}).update(meta.get("rechazadas", {}))
        sesiones.escribir_json(ruta_man, manifiesto, indent=2)
    if meta.get("registro"):
        registro = sesiones.leer_registro() + meta["registro"]
        sesiones._escribir_json(sesiones.REGISTRO, sorted(registro, key=lambda e: e.get("inicio", "")))
    if not conflictos:
        shutil.rmtree(lote, ignore_errors=True)
    sesiones._cache.clear()
    return {"devueltos": devueltos, "conflictos": conflictos, "sin_datos_manifiesto": not meta}


def _elementos(carpeta: Path) -> list[Path]:
    """Hojas a mover: las carpetas de captura/pose completas y los archivos sueltos."""
    salida = []
    for p in sorted(carpeta.rglob("*")):
        rel = p.relative_to(carpeta)
        # capturas/<cat>/<captura> y capturas_ordenadas/<cat>/pose_XX se mueven enteras
        if p.is_dir() and carpeta.name in ("capturas", "capturas_ordenadas") and len(rel.parts) == 2:
            salida.append(p)
        elif p.is_file() and not any(q in salida for q in p.parents):
            if carpeta.name in ("capturas", "capturas_ordenadas") and len(rel.parts) > 2:
                continue  # ya va dentro de su carpeta
            salida.append(p)
    return salida


def _actualizar_indices(poses_borradas: dict[str, set[str]], carpetas: set[str]) -> dict:
    ruta = cfg.DIR_ORDENADAS / "manifiesto.json"
    try:
        manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifiesto = None
    quitadas = {"poses": [], "rechazadas": {}}
    if manifiesto is not None:
        quitadas["poses"] = [e for e in manifiesto.get("poses", [])
                             if f"pose_{int(e['pose']):02d}" in poses_borradas.get(e["categoria"], set())]
        quitadas["rechazadas"] = {f: r for f, r in manifiesto.get("rechazadas", {}).items()
                                  if sesiones.clave_carpeta(r.get("fuente", "")) in carpetas}
        ultimo = manifiesto.setdefault("ultimo_indice", {})
        for e in manifiesto.get("poses", []):
            ultimo[e["categoria"]] = max(int(ultimo.get(e["categoria"], -1)), int(e["pose"]))
        manifiesto["poses"] = [
            e for e in manifiesto.get("poses", [])
            if f"pose_{int(e['pose']):02d}" not in poses_borradas.get(e["categoria"], set())
        ]
        manifiesto["rechazadas"] = {f: r for f, r in manifiesto.get("rechazadas", {}).items()
                                    if sesiones.clave_carpeta(r.get("fuente", "")) not in carpetas}
        sesiones.escribir_json(ruta, manifiesto, indent=2)
    for cat, poses in poses_borradas.items():
        ruta_res = cfg.DIR_RESULTADOS / "reconstruccion" / cat / f"{cat}_resumen.json"
        try:
            resumen = json.loads(ruta_res.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ruta_res.write_text(json.dumps({k: v for k, v in resumen.items() if k not in poses}, indent=2),
                            encoding="utf-8")
    return quitadas


# ------------------------------------------------------------------ notas
NOTAS = cfg.DATOS / "notas.json"


def leer_notas() -> dict[str, str]:
    """{"proceso:<id>": texto, "pose:<cat>/<pose>": texto} (p. ej. «pieza A, cara superior»)."""
    try:
        datos = json.loads(NOTAS.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def guardar_nota(clave: str, texto: str) -> None:
    if not re.fullmatch(r"(proceso:[\dT:-]+|pose:(patron|plano|objeto)/pose_\d+)", clave):
        raise ValueError(f"clave de nota inválida: {clave}")
    with sesiones.ESCRITURA:  # leer, cambiar y escribir sin que otra petición se meta en medio
        notas = leer_notas()
        texto = texto.strip()[:200]
        if texto:
            notas[clave] = texto
        else:
            notas.pop(clave, None)
        sesiones.escribir_json(NOTAS, notas)


def tamano(ruta: Path) -> int:
    if ruta.is_file():
        return ruta.stat().st_size
    return sum(f.stat().st_size for f in ruta.rglob("*") if f.is_file()) if ruta.is_dir() else 0


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
