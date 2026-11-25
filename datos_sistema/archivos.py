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

from datos_sistema import configuracion as cfg
from datos_sistema import rutas
from datos_sistema import sesiones

PAPELERA = cfg.DATOS / "papelera"
META = "papelera.json"  # qué se quitó del manifiesto y del registro (para restaurar)
EXT_IMAGEN = {".png", ".tif", ".tiff", ".bmp", ".jpg", ".jpeg"}


def ruta_captura(clave: str) -> Path:
    """'patron/20261124_130228' -> su carpeta en capturas/ (en la carpeta de su proceso o en la
    estructura anterior), sin permitir salir de capturas/."""
    return rutas.ruta_captura(clave)


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


def _limpiar_vacias(carpeta: Path, destino: Path) -> None:
    """Quita las carpetas que quedan vacías al mover algo (categoría o proceso), sin salir de las
    carpetas de datos. Un proceso al que solo le queda su proceso.json también se vacía: el
    proceso.json va a la papelera con lo demás (para poder restaurarlo)."""
    raices = {cfg.DIR_CAPTURAS.resolve(), cfg.DIR_ORDENADAS.resolve(), cfg.DIR_RESULTADOS.resolve(), cfg.DATOS.resolve()}
    actual = carpeta
    while actual.is_dir() and actual.resolve() not in raices:
        if any(p.name != "proceso.json" for p in actual.iterdir()):
            break
        for resto in list(actual.iterdir()):
            _mover(resto, destino)
        actual.rmdir()
        actual = actual.parent


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
        _limpiar_vacias(ruta.parent, destino)
        for pose in poses:
            # Organizada, fases y reconstrucción, donde estén (carpeta de su proceso o estructura anterior)
            for elemento in rutas.archivos_de_pose(cat, pose):
                movidos += _mover(elemento, destino)
                _limpiar_vacias(elemento.parent, destino)
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


def capturas_de_poses(cat: str, poses: list[str]) -> dict:
    """Qué hay que mover para borrar estas poses: las capturas de las que salieron (con lo derivado
    de ellas). Si una captura dio varias poses, se van todas. {"capturas", "poses"}"""
    pedidas = set(poses)
    capturas, todas = [], set()
    for it in sesiones.capturas():
        if it["cat"] == cat and pedidas & set(it["poses"]):
            capturas.append(it["carpeta"])
            todas.update(it["poses"])
    faltan = pedidas - todas
    if faltan:
        raise ValueError(f"no se encontró la captura de: {', '.join(sorted(faltan))}")
    return {"capturas": capturas, "poses": sorted(todas, key=lambda p: int(p[5:]))}


def borrar_poses(cat: str, poses: list[str]) -> dict:
    """Mueve a la papelera las poses (sus capturas y todo lo derivado). Se restauran desde Archivos."""
    plan = capturas_de_poses(cat, poses)
    return {**mover_a_papelera(plan["capturas"]), "poses": plan["poses"]}


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
    """Lo que se devuelve de un lote: las carpetas de captura y de pose completas (las que cuelgan
    de una carpeta de categoría, con o sin carpeta de proceso) y los archivos sueltos."""
    unidades: list[Path] = []
    if carpeta.name in ("capturas", "capturas_ordenadas"):
        for p in sorted(carpeta.rglob("*")):
            if p.is_dir() and p.parent.name in cfg.CATEGORIAS and not any(u in p.parents for u in unidades):
                unidades.append(p)
    sueltos = [p for p in sorted(carpeta.rglob("*"))
               if p.is_file() and not any(u in p.parents for u in unidades)]
    return unidades + sueltos


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


# ------------------------------------------------------------------ nombre de un proceso
def renombrar_proceso(carpeta: str, nombre: str) -> str:
    """Le pone (o cambia, o quita con "") el nombre a un proceso: renombra su carpeta en
    capturas/, capturas_ordenadas/ y resultados/ (AAAA-MM-DD_HHMM_<nombre>) y actualiza el
    manifiesto, su proceso.json y la configuración elegida. Las poses no cambian de nombre, así que
    calibraciones, notas, máscaras y mediciones siguen valiendo. Devuelve el nombre nuevo de la carpeta."""
    import os

    if not rutas.es_proceso(carpeta) or not (cfg.DIR_CAPTURAS / carpeta).is_dir():
        raise ValueError(f"no existe el proceso '{carpeta}'")
    prefijo = rutas.RE_PREFIJO_PROCESO.match(carpeta)[0]
    etiqueta = rutas.etiqueta_carpeta(nombre)
    nueva = f"{prefijo}_{etiqueta}" if etiqueta else prefijo
    raices = [r for r in (cfg.DIR_CAPTURAS, cfg.DIR_ORDENADAS, cfg.DIR_RESULTADOS) if (r / carpeta).is_dir()]
    with sesiones.ESCRITURA:
        if nueva != carpeta:
            if any((r / nueva).exists() for r in (cfg.DIR_CAPTURAS, cfg.DIR_ORDENADAS, cfg.DIR_RESULTADOS)):
                raise ValueError(f"ya existe un proceso '{nueva}'")
            hechos = []
            try:
                for r in raices:
                    os.rename(r / carpeta, r / nueva)
                    hechos.append(r)
            except OSError:
                for r in hechos:  # deja todo como estaba
                    os.rename(r / nueva, r / carpeta)
                raise
            _cambiar_proceso_en_manifiesto(carpeta, nueva)
            elegida = sesiones._leer_json(sesiones.ELEGIDA, {})
            if elegida.get("solo_proceso") == carpeta:
                sesiones._escribir_json(sesiones.ELEGIDA, {**elegida, "solo_proceso": nueva})
        ruta_json = cfg.DIR_CAPTURAS / nueva / "proceso.json"
        datos = sesiones._leer_json(ruta_json, {})
        datos["proceso"] = nueva
        if nombre.strip():
            datos["nombre"] = nombre.strip()[:80]
        else:
            datos.pop("nombre", None)
        sesiones._escribir_json(ruta_json, datos)
    sesiones._cache.clear()
    return nueva


def _cambiar_proceso_en_manifiesto(viejo: str, nuevo: str) -> None:
    ruta = cfg.DIR_ORDENADAS / "manifiesto.json"
    man = sesiones._leer_json(ruta, None)
    if not man:
        return

    def cambiar(texto: str) -> str:
        partes = Path(texto).parts
        return str(Path(*[nuevo if p == viejo else p for p in partes])) if viejo in partes else texto

    def firma(f: str) -> str:
        partes = f.split("|")
        if len(partes) >= 2:
            partes[1] = cambiar(partes[1])
        return "|".join(partes)

    for e in man.get("poses", []):
        e["fuente"], e["carpeta"], e["firma"] = cambiar(e.get("fuente", "")), cambiar(e.get("carpeta", "")), firma(e.get("firma", ""))
    man["rechazadas"] = {firma(k): {**r, "fuente": cambiar(r.get("fuente", ""))} for k, r in man.get("rechazadas", {}).items()}
    sesiones._escribir_json(ruta, man)
