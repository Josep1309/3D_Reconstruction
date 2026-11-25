"""Procesos de captura y configuración vigente del montaje.

Un **proceso** es una ejecución de la captura: por ejemplo, patrón × 8, plano × 3 y objeto × 1.
- Desde ahora, `pipeline.etapa_captura` registra cada proceso en `<DATOS>/procesos_captura.json`
  con sus carpetas de `capturas/`. Ese archivo no está versionado, igual que los datos.
- Las capturas anteriores al registro se agrupan por tiempo: una pausa de más de
  `cfg.MINUTOS_ENTRE_PROCESOS` sin capturar empieza un proceso nuevo. La hora de cada pose sale
  del nombre de su carpeta en `capturas/` (AAAAMMDD_HHMMSS), que registra el manifiesto de
  `capturas_ordenadas/`.

La **configuración vigente** empieza en el último proceso que capturó el patrón (la calibración
del montaje actual) e incluye lo capturado después, como los objetos medidos más tarde sin
recalibrar. Si nunca se capturó el patrón, es el último proceso. Con
`cfg.SOLO_CONFIGURACION_ACTUAL = True`, las etapas de proceso y la interfaz solo usan y muestran
esas poses. Lo anterior sigue en disco, pero no se procesa ni se ve.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import configuracion as cfg

REGISTRO = cfg.DATOS / "procesos_captura.json"
_cache: dict = {}


def hora_de_carpeta(ruta: str | Path) -> datetime | None:
    """Hora de captura a partir de un nombre de carpeta AAAAMMDD_HHMMSS (en cualquier nivel de la ruta)."""
    for parte in reversed(Path(ruta).parts):
        try:
            return datetime.strptime(parte[:15], "%Y%m%d_%H%M%S")
        except ValueError:
            continue
    return None


def _clave_carpeta(ruta: str | Path) -> str:
    """'capturas/patron/20261124_130228' -> 'patron/20261124_130228'."""
    partes = Path(ruta).parts
    return "/".join(partes[-2:])


# ------------------------------------------------------------------ registro de procesos
def leer_registro(ruta: Path = REGISTRO) -> list[dict]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def registrar_proceso(carpetas: list[Path], plan: list[tuple[str, int]], ruta: Path = REGISTRO) -> None:
    """Agrega al registro un proceso de captura con sus carpetas (lo llama pipeline.etapa_captura)."""
    if not carpetas:
        return
    registro = leer_registro(ruta)
    horas = [h for h in (hora_de_carpeta(c) for c in carpetas) if h is not None]
    registro.append({
        "inicio": min(horas).isoformat(timespec="seconds") if horas else datetime.now().isoformat(timespec="seconds"),
        "fin": datetime.now().isoformat(timespec="seconds"),
        "plan": {c: n for c, n in plan},
        "carpetas": [_clave_carpeta(c) for c in carpetas],
    })
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(json.dumps(registro, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(ruta)


# ------------------------------------------------------------------ procesos y configuración vigente
def horas_poses(dir_ordenadas: Path = cfg.DIR_ORDENADAS) -> dict[tuple[str, str], tuple[datetime, str]]:
    """{(categoria, "pose_XX"): (hora de captura, carpeta fuente)} según el manifiesto."""
    try:
        manifiesto = json.loads((dir_ordenadas / "manifiesto.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    salida = {}
    for e in manifiesto.get("poses", []):
        hora = hora_de_carpeta(str(e.get("fuente", "")))
        if hora is not None:
            salida[(e["categoria"], f"pose_{int(e['pose']):02d}")] = (hora, str(e.get("fuente", "")))
    return salida


def procesos(dir_ordenadas: Path = cfg.DIR_ORDENADAS, registro: Path = REGISTRO) -> list[dict]:
    """Procesos en orden cronológico: [{"inicio", "fin", "poses": {(cat, pose), ...}, "patron": bool,
    "registrado": bool}]."""
    proceso_de_carpeta = {}
    for i, entrada in enumerate(leer_registro(registro)):
        for carpeta in entrada.get("carpetas", []):
            proceso_de_carpeta[carpeta] = i
    registrados: dict[int, dict] = {}
    sueltas = []
    for clave, (hora, fuente) in horas_poses(dir_ordenadas).items():
        i = proceso_de_carpeta.get(_clave_carpeta(fuente))
        if i is None:
            sueltas.append((hora, clave))
            continue
        p = registrados.setdefault(i, {"inicio": hora, "fin": hora, "poses": set(), "patron": False, "registrado": True})
        p["inicio"], p["fin"] = min(p["inicio"], hora), max(p["fin"], hora)
        p["poses"].add(clave)
        p["patron"] |= clave[0] == "patron"
    # Capturas sin registro (anteriores a él): una pausa larga separa procesos
    agrupados: list[dict] = []
    for hora, clave in sorted(sueltas):
        if not agrupados or (hora - agrupados[-1]["fin"]).total_seconds() > cfg.MINUTOS_ENTRE_PROCESOS * 60:
            agrupados.append({"inicio": hora, "fin": hora, "poses": set(), "patron": False, "registrado": False})
        p = agrupados[-1]
        p["fin"] = hora
        p["poses"].add(clave)
        p["patron"] |= clave[0] == "patron"
    return sorted([*registrados.values(), *agrupados], key=lambda p: p["inicio"])


def configuracion_vigente(dir_ordenadas: Path = cfg.DIR_ORDENADAS) -> dict | None:
    """Poses del montaje actual: {"desde": datetime, "poses": {cat: {pose, ...}}, "procesos_ocultos"},
    o None si no hay manifiesto (entonces no se filtra nada). Se recalcula solo si cambian el
    manifiesto o el registro."""
    ruta = dir_ordenadas / "manifiesto.json"
    try:
        m_reg = REGISTRO.stat().st_mtime if REGISTRO.exists() else 0
        clave = (str(ruta), ruta.stat().st_mtime, m_reg, cfg.MINUTOS_ENTRE_PROCESOS)
    except OSError:
        return None
    if clave in _cache:
        return _cache[clave]
    lista = procesos(dir_ordenadas)
    resultado = None
    if lista:
        con_patron = [i for i, p in enumerate(lista) if p["patron"]]
        primero = con_patron[-1] if con_patron else len(lista) - 1
        poses: dict[str, set[str]] = {c: set() for c in cfg.CATEGORIAS}
        for p in lista[primero:]:
            for cat, pose in p["poses"]:
                poses.setdefault(cat, set()).add(pose)
        resultado = {"desde": lista[primero]["inicio"], "poses": poses, "procesos_ocultos": primero}
    _cache.clear()
    _cache[clave] = resultado
    return resultado


def poses_vigentes(categoria: str, dir_ordenadas: Path = cfg.DIR_ORDENADAS) -> set[str] | None:
    """Nombres de las poses de `categoria` en la configuración vigente; None = no filtrar."""
    if not cfg.SOLO_CONFIGURACION_ACTUAL:
        return None
    conf = configuracion_vigente(dir_ordenadas)
    return None if conf is None else conf["poses"].get(categoria, set())


def captura_vigente(carpeta: str | Path, dir_ordenadas: Path = cfg.DIR_ORDENADAS) -> bool:
    """Si una carpeta de `capturas/` (por su hora) pertenece a la configuración vigente."""
    if not cfg.SOLO_CONFIGURACION_ACTUAL:
        return True
    conf = configuracion_vigente(dir_ordenadas)
    hora = hora_de_carpeta(carpeta)
    return conf is None or hora is None or hora >= conf["desde"]


def resumen_texto(dir_ordenadas: Path = cfg.DIR_ORDENADAS) -> str:
    conf = configuracion_vigente(dir_ordenadas) if cfg.SOLO_CONFIGURACION_ACTUAL else None
    if conf is None:
        return ""
    cuenta = ", ".join(f"{c} {len(p)}" for c, p in conf["poses"].items() if p)
    oculto = f"; se ignoran {conf['procesos_ocultos']} proceso(s) anteriores" if conf["procesos_ocultos"] else ""
    return f"Configuración vigente desde {conf['desde']:%Y-%m-%d %H:%M} ({cuenta}{oculto})"


def info_vigente(dir_ordenadas: Path = cfg.DIR_ORDENADAS) -> dict | None:
    """Resumen para la interfaz: desde cuándo, cuántas poses por categoría y procesos ocultos."""
    conf = configuracion_vigente(dir_ordenadas) if cfg.SOLO_CONFIGURACION_ACTUAL else None
    if conf is None:
        return None
    return {"desde": conf["desde"].isoformat(timespec="seconds"),
            "poses": {c: len(p) for c, p in conf["poses"].items()},
            "procesos_ocultos": conf["procesos_ocultos"]}
