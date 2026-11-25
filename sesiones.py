"""Procesos de captura y configuración vigente del montaje.

Un **proceso** es una ejecución de la captura: por ejemplo, patrón × 8, plano × 3 y objeto × 1.
- `pipeline.etapa_captura` registra cada proceso en `<DATOS>/procesos_captura.json` con sus
  carpetas de `capturas/`. Ese archivo no está versionado, igual que los datos.
- Las capturas sin registro (anteriores a él) se agrupan por tiempo: una pausa de más de
  `cfg.MINUTOS_ENTRE_PROCESOS` sin capturar empieza un proceso nuevo. La hora de cada captura sale
  del nombre de su carpeta (AAAAMMDD_HHMMSS).

Una **configuración** empieza en un proceso que capturó el patrón (una calibración del montaje) e
incluye los procesos siguientes hasta el próximo patrón, como los objetos medidos más tarde sin
recalibrar.
- La **configuración vigente** es por defecto la última. También se puede elegir otra
  (`fijar_configuracion`, que guarda `<DATOS>/configuracion_elegida.json`). Al capturar un patrón
  nuevo se vuelve a la última.
- Con `cfg.SOLO_CONFIGURACION_ACTUAL = True`, las etapas de proceso y la interfaz solo usan y
  muestran sus poses. Lo demás sigue en disco y se ve en la pestaña *Archivos* de la interfaz.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

import configuracion as cfg

REGISTRO = cfg.DATOS / "procesos_captura.json"
ELEGIDA = cfg.DATOS / "configuracion_elegida.json"
_cache: dict = {}
_lock = threading.Lock()


def hora_de_carpeta(ruta: str | Path) -> datetime | None:
    """Hora de captura a partir de un nombre AAAAMMDD_HHMMSS (en cualquier nivel de la ruta)."""
    for parte in reversed(Path(ruta).parts):
        try:
            return datetime.strptime(parte[:15], "%Y%m%d_%H%M%S")
        except ValueError:
            continue
    return None


def clave_carpeta(ruta: str | Path) -> str:
    """'capturas/patron/20261124_130228' -> 'patron/20261124_130228'."""
    return "/".join(Path(ruta).parts[-2:])


def _leer_json(ruta: Path, defecto):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defecto


# Candado de los archivos JSON de datos (registro, notas, manifiesto, ajustes): el servidor atiende
# peticiones en varios hilos, y dos «leer, cambiar y escribir» simultáneos perderían o mezclarían datos
ESCRITURA = threading.RLock()


def escribir_json(ruta: Path, datos, indent: int = 1) -> None:
    """Escritura atómica: a un temporal único (proceso e hilo) y luego renombrado."""
    tmp = ruta.with_name(f".{ruta.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    with ESCRITURA:
        tmp.write_text(json.dumps(datos, indent=indent, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ruta)


_escribir_json = escribir_json


# ------------------------------------------------------------------ registro de procesos
def leer_registro(ruta: Path = REGISTRO) -> list[dict]:
    datos = _leer_json(ruta, [])
    return datos if isinstance(datos, list) else []


def registrar_proceso(carpetas: list[Path], plan: list[tuple[str, int]], ruta: Path = REGISTRO) -> None:
    """Agrega al registro un proceso de captura con sus carpetas (lo llama pipeline.etapa_captura).

    Si el proceso capturó el patrón, empieza una configuración nueva y la vigente vuelve a ser la
    última (se olvida una configuración elegida a mano).
    """
    if not carpetas:
        return
    with ESCRITURA:
        _registrar(carpetas, plan, ruta)
    if any(clave_carpeta(c).startswith("patron/") for c in carpetas):
        fijar_configuracion(None)


def _registrar(carpetas: list[Path], plan: list[tuple[str, int]], ruta: Path) -> None:
    registro = leer_registro(ruta)
    horas = [h for h in (hora_de_carpeta(c) for c in carpetas) if h is not None]
    registro.append({
        "inicio": min(horas).isoformat(timespec="seconds") if horas else datetime.now().isoformat(timespec="seconds"),
        "fin": datetime.now().isoformat(timespec="seconds"),
        "plan": {c: n for c, n in plan},
        "carpetas": [clave_carpeta(c) for c in carpetas],
    })
    _escribir_json(ruta, registro)


def quitar_del_registro(carpetas: set[str], ruta: Path = REGISTRO) -> None:
    with ESCRITURA:
        _quitar(carpetas, ruta)


def _quitar(carpetas: set[str], ruta: Path) -> None:
    registro = leer_registro(ruta)
    if not registro:
        return
    for entrada in registro:
        entrada["carpetas"] = [c for c in entrada.get("carpetas", []) if c not in carpetas]
    _escribir_json(ruta, [e for e in registro if e["carpetas"]])


# ------------------------------------------------------------------ capturas y procesos
def capturas(dir_capturas: Path | None = None, dir_ordenadas: Path | None = None) -> list[dict]:
    """Todas las capturas: carpetas (o videos) de `capturas/<cat>/`, más las poses organizadas
    cuya captura ya no está. [{"cat", "carpeta": "cat/nombre", "hora", "existe", "poses": [...]}]"""
    dir_capturas = dir_capturas or cfg.DIR_CAPTURAS
    dir_ordenadas = dir_ordenadas or cfg.DIR_ORDENADAS
    manifiesto = _leer_json(dir_ordenadas / "manifiesto.json", {})
    rechazo_de = {clave_carpeta(r.get("fuente", "")): r.get("motivo", "") for r in manifiesto.get("rechazadas", {}).values()}
    poses_de: dict[str, list[str]] = {}
    pureza_de: dict[str, float] = {}  # la peor pureza de las secuencias de cada captura (organizar)
    for e in manifiesto.get("poses", []):
        clave = clave_carpeta(str(e.get("fuente", "")))
        nombre = f"pose_{int(e['pose']):02d}"
        if e.get("categoria") and not clave.startswith(e["categoria"] + "/"):
            clave = f"{e['categoria']}/{Path(clave).name}"
        poses_de.setdefault(clave, []).append(nombre)
        cal = e.get("calidad") or {}
        if "pureza_H" in cal:
            pureza_de[clave] = min(pureza_de.get(clave, 1.0), cal["pureza_H"], cal["pureza_V"])
    import rutas

    items: dict[str, dict] = {}
    # capturas/<proceso>/<cat>/<captura> (estructura actual) y capturas/<cat>/<captura> (anterior)
    for cat, nombre, p, proceso_dir in rutas.capturas_en_disco():
        clave = f"{cat}/{nombre}"
        hora = hora_de_carpeta(nombre) or datetime.fromtimestamp(p.stat().st_mtime)
        items[clave] = {"cat": cat, "carpeta": clave, "hora": hora, "existe": True,
                        "poses": sorted(poses_de.get(clave, [])), "rechazo": rechazo_de.get(clave),
                        "pureza": pureza_de.get(clave), "proceso_dir": proceso_dir}
    for clave, poses in poses_de.items():
        if clave not in items:
            cat = clave.split("/")[0]
            hora = hora_de_carpeta(clave)
            if hora is not None and cat in cfg.CATEGORIAS:
                items[clave] = {"cat": cat, "carpeta": clave, "hora": hora, "existe": False, "poses": sorted(poses),
                                "proceso_dir": rutas.proceso_de_pose(cat, sorted(poses)[0])}
    return sorted(items.values(), key=lambda i: (i["hora"], i["carpeta"]))


def procesos(dir_capturas: Path | None = None, dir_ordenadas: Path | None = None,
             registro: Path = REGISTRO) -> list[dict]:
    """Procesos en orden cronológico:
    [{"id" (inicio ISO), "inicio", "fin", "items": [...], "patron": bool, "registrado": bool}]."""
    proceso_de = {}
    for i, entrada in enumerate(leer_registro(registro)):
        for carpeta in entrada.get("carpetas", []):
            proceso_de[carpeta] = i
    registrados: dict[int, list[dict]] = {}
    por_carpeta: dict[str, list[dict]] = {}
    sueltos: list[dict] = []
    for item in capturas(dir_capturas, dir_ordenadas):
        if item.get("proceso_dir"):  # estructura actual: la carpeta del proceso manda
            por_carpeta.setdefault(item["proceso_dir"], []).append(item)
            continue
        i = proceso_de.get(item["carpeta"])
        (registrados.setdefault(i, []) if i is not None else sueltos).append(item)
    grupos = [(items, True) for items in registrados.values()]
    grupos += [(items, True) for items in por_carpeta.values()]
    actual: list[dict] = []
    for item in sueltos:  # sin registro: una pausa larga separa procesos...
        if actual:
            pausa = (item["hora"] - actual[-1]["hora"]).total_seconds()
            # ...salvo que siga capturándose el patrón: el orden de un proceso es patrón → plano → objeto
            sigue_patron = actual[-1]["cat"] == item["cat"] == "patron" and pausa < cfg.MINUTOS_CONTINUACION_PATRON * 60
            if pausa > cfg.MINUTOS_ENTRE_PROCESOS * 60 and not sigue_patron:
                grupos.append((actual, False))
                actual = []
        actual.append(item)
    if actual:
        grupos.append((actual, False))
    salida = []
    for items, registrado in grupos:
        items = sorted(items, key=lambda x: (x["hora"], x["carpeta"]))
        inicio = items[0]["hora"]
        salida.append({"id": inicio.isoformat(timespec="seconds"), "inicio": inicio, "fin": items[-1]["hora"],
                       "items": items, "patron": any(x["cat"] == "patron" for x in items),
                       "registrado": registrado, "carpeta": items[0].get("proceso_dir"),
                       "nombre": _rutas().nombre_legible(items[0].get("proceso_dir"))})
    return sorted(salida, key=lambda p: p["inicio"])


def fijar_configuracion(proceso_id: str | None) -> None:
    """Elige la configuración que empieza en `proceso_id` (None = la última, automática)."""
    if proceso_id is None:
        ELEGIDA.unlink(missing_ok=True)
    else:
        _escribir_json(ELEGIDA, {"proceso": proceso_id, "fijada": _ahora()})
    _cache.clear()


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fijada() -> datetime | None:
    """Cuándo se eligió la configuración en uso (las capturas posteriores de plano/objeto se le
    suman solas). Archivos anteriores sin la marca: la fecha del archivo."""
    datos = _leer_json(ELEGIDA, {})
    try:
        return datetime.fromisoformat(datos["fijada"])
    except (KeyError, TypeError, ValueError):
        try:
            return datetime.fromtimestamp(ELEGIDA.stat().st_mtime)
        except OSError:
            return None


def _capturas_nuevas(lista: list[dict], desde: datetime | None) -> list[dict]:
    """Capturas de plano y objeto de procesos sin patrón hechos después de `desde`: con una
    configuración elegida (selección manual, un proceso o una importación) se suman solas, para
    no tener que agregar cada objeto nuevo a mano. Un proceso con patrón es otro montaje: ese
    caso ya lo cubre registrar_proceso (vuelve a la última configuración)."""
    if desde is None:
        return []
    return [it for p in lista if not p["patron"] for it in p["items"]
            if it["cat"] != "patron" and it["hora"] > desde]


def _sumar_nuevas(resultado: dict, nuevas: list[dict]) -> dict:
    for it in nuevas:
        resultado["poses"].setdefault(it["cat"], set()).update(it["poses"])
        resultado["carpetas"].add(it["carpeta"])
        resultado["hasta"] = max(resultado["hasta"], it["hora"])
    resultado["nuevas"] = len(nuevas)
    return resultado


def fijar_seleccion(seleccion: dict[str, list[str]]) -> None:
    """Configuración elegida a mano: exactamente estas poses ({cat: ["pose_XX", ...]}), de
    cualquier proceso. Sirve para recalibrar y reconstruir con capturas tomadas antes, sin
    depender de cómo se agrupan los procesos. «Volver a la última» o capturar un patrón nuevo la quitan."""
    limpia = {c: sorted({str(p) for p in seleccion.get(c, []) if str(p).startswith("pose_")}) for c in cfg.CATEGORIAS}
    if not any(limpia.values()):
        raise ValueError("la selección está vacía")
    _escribir_json(ELEGIDA, {"seleccion": limpia, "fijada": _ahora()})
    _cache.clear()


def fijar_solo_proceso(carpeta: str) -> None:
    """Configuración = exactamente las capturas de una carpeta de proceso (p. ej. una importación),
    sin sumar los procesos siguientes. Sus poses se toman del manifiesto al momento de usarlas, así
    que sirve antes de organizar."""
    _escribir_json(ELEGIDA, {"solo_proceso": carpeta, "fijada": _ahora()})
    _cache.clear()


def seleccion_manual() -> dict[str, list[str]] | None:
    """La selección manual en uso, o None si la configuración es por procesos."""
    return _leer_json(ELEGIDA, {}).get("seleccion")


def configuraciones(lista: list[dict] | None = None) -> list[tuple[int, int]]:
    """Rangos [desde, hasta) de índices de `procesos()` que forman cada configuración."""
    lista = procesos() if lista is None else lista
    inicios = [i for i, p in enumerate(lista) if p["patron"]]
    if not inicios or inicios[0] != 0:
        inicios = [0, *inicios]  # lo anterior al primer patrón forma su propia configuración
    return [(a, b) for a, b in zip(inicios, [*inicios[1:], len(lista)]) if a < b]


def _clave_cache() -> tuple:
    marcas = []
    carpetas = [cfg.DIR_CAPTURAS, *(cfg.DIR_CAPTURAS / c for c in cfg.CATEGORIAS)]
    if cfg.DIR_CAPTURAS.is_dir():  # carpetas de proceso y sus categorías
        for p in cfg.DIR_CAPTURAS.iterdir():
            if p.is_dir() and p.name[:1].isdigit():
                carpetas += [p, *(p / c for c in cfg.CATEGORIAS)]
    for ruta in (cfg.DIR_ORDENADAS / "manifiesto.json", REGISTRO, ELEGIDA, *carpetas):
        try:
            marcas.append(ruta.stat().st_mtime_ns)
        except OSError:
            marcas.append(0)
    return (str(cfg.DATOS), cfg.MINUTOS_ENTRE_PROCESOS, *marcas)


def configuracion_vigente() -> dict | None:
    """{"desde", "hasta", "proceso", "auto", "poses": {cat: {...}}, "carpetas": {...},
    "procesos_ocultos"} de la configuración vigente, o None si no hay capturas."""
    clave = _clave_cache()
    with _lock:
        if clave in _cache:
            return _cache[clave]
        lista = procesos()
        resultado = None
        rangos = configuraciones(lista)
        manual = seleccion_manual()
        solo = _leer_json(ELEGIDA, {}).get("solo_proceso")
        if solo and lista:
            items = [it for p in lista if p.get("carpeta") == solo for it in p["items"]]
            manual = {c: [pose for it in items if it["cat"] == c for pose in it["poses"]] for c in cfg.CATEGORIAS}
            resultado = _vigente_manual(lista, manual)
            resultado["carpetas"] |= {it["carpeta"] for it in items}
            resultado["proceso"] = next((p["id"] for p in lista if p.get("carpeta") == solo), "solo_proceso")
            resultado["manual"] = False
        elif manual and lista:
            resultado = _vigente_manual(lista, manual)
        elif rangos:
            elegida = _leer_json(ELEGIDA, {}).get("proceso")
            rango = next((r for r in rangos if lista[r[0]]["id"] == elegida), None)
            auto = rango is None
            rango = rango or rangos[-1]
            poses: dict[str, set[str]] = {c: set() for c in cfg.CATEGORIAS}
            carpetas: set[str] = set()
            for p in lista[rango[0]:rango[1]]:
                for item in p["items"]:
                    carpetas.add(item["carpeta"])
                    poses.setdefault(item["cat"], set()).update(item["poses"])
            resultado = {"desde": lista[rango[0]]["inicio"], "hasta": lista[rango[1] - 1]["fin"],
                         "proceso": lista[rango[0]]["id"], "auto": auto, "poses": poses,
                         "carpetas": carpetas, "procesos_ocultos": len(lista) - (rango[1] - rango[0]),
                         "es_ultima": rango == rangos[-1]}
            if not auto and rango != rangos[-1]:  # las capturas posteriores quedarían en otra configuración
                ya = {it["carpeta"] for p in lista[rango[0]:rango[1]] for it in p["items"]}
                _sumar_nuevas(resultado, [it for it in _capturas_nuevas(lista, _fijada()) if it["carpeta"] not in ya])
        if resultado and (solo or manual) and lista:
            ya = resultado["carpetas"]
            _sumar_nuevas(resultado, [it for it in _capturas_nuevas(lista, _fijada()) if it["carpeta"] not in ya])
        _cache.clear()
        _cache[clave] = resultado
        return resultado


def _vigente_manual(lista: list[dict], seleccion: dict[str, list[str]]) -> dict:
    poses = {c: set(seleccion.get(c, [])) for c in cfg.CATEGORIAS}
    carpetas, horas, usados = set(), [], set()
    for i, p in enumerate(lista):
        for item in p["items"]:
            if poses.get(item["cat"], set()) & set(item["poses"]):
                carpetas.add(item["carpeta"])
                horas.append(item["hora"])
                usados.add(i)
    desde = min(horas) if horas else lista[-1]["inicio"]
    return {"desde": desde, "hasta": max(horas) if horas else desde, "proceso": "seleccion", "auto": False,
            "manual": True, "poses": poses, "carpetas": carpetas,
            "procesos_ocultos": len(lista) - len(usados), "es_ultima": False}


def poses_vigentes(categoria: str) -> set[str] | None:
    """Nombres de las poses de `categoria` en la configuración vigente; None = no filtrar."""
    if not cfg.SOLO_CONFIGURACION_ACTUAL:
        return None
    conf = configuracion_vigente()
    return None if conf is None else conf["poses"].get(categoria, set())


def captura_vigente(carpeta: str | Path) -> bool:
    """Si una carpeta de `capturas/` pertenece a la configuración vigente."""
    if not cfg.SOLO_CONFIGURACION_ACTUAL:
        return True
    conf = configuracion_vigente()
    return conf is None or clave_carpeta(carpeta) in conf["carpetas"]


def resumen_texto() -> str:
    conf = configuracion_vigente() if cfg.SOLO_CONFIGURACION_ACTUAL else None
    if conf is None:
        return ""
    cuenta = ", ".join(f"{c} {len(p)}" for c, p in conf["poses"].items() if p)
    tipo = "selección manual" if conf.get("manual") else "elegida" if not conf["auto"] else "la última"
    oculto = f"; se ignoran {conf['procesos_ocultos']} proceso(s)" if conf["procesos_ocultos"] else ""
    return f"Configuración vigente ({tipo}) desde {conf['desde']:%Y-%m-%d %H:%M} ({cuenta}{oculto})"


def info_vigente() -> dict | None:
    """Resumen para la interfaz."""
    conf = configuracion_vigente() if cfg.SOLO_CONFIGURACION_ACTUAL else None
    if conf is None:
        return None
    return {"desde": conf["desde"].isoformat(timespec="seconds"), "proceso": conf["proceso"],
            "auto": conf["auto"], "es_ultima": conf["es_ultima"], "manual": bool(conf.get("manual")),
            "poses": {c: len(p) for c, p in conf["poses"].items()},
            "procesos_ocultos": conf["procesos_ocultos"], "nuevas": conf.get("nuevas", 0)}


def proceso_de_poses(categoria: str, poses: list[str]) -> str | None:
    """Id del proceso (el más reciente) que contiene alguna de esas poses."""
    buscadas = set(poses)
    elegido = None
    for p in procesos():
        if any(i["cat"] == categoria and buscadas & set(i["poses"]) for i in p["items"]):
            elegido = p["id"]
    return elegido


def _rutas():
    import rutas  # rutas no depende de sesiones, pero se importa tarde por orden de carga

    return rutas
