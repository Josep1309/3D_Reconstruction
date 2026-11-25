"""Mediciones de distancia guardadas por pose (pestaña «Medición» de la interfaz).

Se guardan en `<DATOS>/mediciones.json`: {"cat/pose_XX": [medición, …]}. Cada medición guarda los
dos puntos (posición en la imagen, normalizada a [0, 1], y X, Y, Z en mm), la distancia y la firma
de la reconstrucción con la que se midió. Si la pose se reconstruye de nuevo (otra máscara, otra
calibración…), la medición queda marcada como «desactualizada» y se puede volver a medir en los
mismos lugares de la imagen.
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime

import configuracion as cfg
import rutas

RUTA = cfg.DATOS / "mediciones.json"


def _leer() -> dict:
    try:
        datos = json.loads(RUTA.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _escribir(datos: dict) -> None:
    import sesiones

    sesiones.escribir_json(RUTA, datos)


def firma_reconstruccion(cat: str, pose: str) -> str | None:
    try:
        return str(rutas.reconstruccion(cat, pose).stat().st_mtime_ns)
    except OSError:
        return None


def _punto(p: dict) -> dict:
    salida = {k: float(p[k]) for k in ("fx", "fy", "X", "Y", "Z")}
    if not all(math.isfinite(v) for v in salida.values()) or not (0 <= salida["fx"] <= 1 and 0 <= salida["fy"] <= 1):
        raise ValueError("punto inválido")
    if p.get("sigma_mm") is not None:
        salida["sigma_mm"] = float(p["sigma_mm"])
    return salida


def distancia(a: dict, b: dict) -> float:
    return math.dist((a["X"], a["Y"], a["Z"]), (b["X"], b["Y"], b["Z"]))


def listar(cat: str, pose: str) -> dict:
    firma = firma_reconstruccion(cat, pose)
    lista = _leer().get(f"{cat}/{pose}", [])
    return {"mediciones": [{**m, "desactualizada": m.get("firma") != firma} for m in lista]}


def guardar(cat: str, pose: str, medicion: dict) -> dict:
    import sesiones

    a, b = _punto(medicion["a"]), _punto(medicion["b"])
    nueva = {"id": uuid.uuid4().hex[:10], "nombre": str(medicion.get("nombre") or "").strip()[:80],
             "a": a, "b": b, "distancia_mm": distancia(a, b), "fecha": datetime.now().isoformat(timespec="seconds"),
             "firma": firma_reconstruccion(cat, pose)}
    with sesiones.ESCRITURA:
        datos = _leer()
        datos.setdefault(f"{cat}/{pose}", []).append(nueva)
        _escribir(datos)
    return listar(cat, pose)


def borrar(cat: str, pose: str, ident: str) -> dict:
    import sesiones

    with sesiones.ESCRITURA:
        datos = _leer()
        clave = f"{cat}/{pose}"
        datos[clave] = [m for m in datos.get(clave, []) if m.get("id") != ident]
        if not datos[clave]:
            del datos[clave]
        _escribir(datos)
    return listar(cat, pose)


def actualizar(cat: str, pose: str, medir) -> dict:
    """Vuelve a medir las mediciones desactualizadas en los mismos lugares de la imagen, con la
    reconstrucción actual. `medir(fx, fy)` devuelve el punto 3D más cercano."""
    import sesiones

    firma = firma_reconstruccion(cat, pose)
    fallidas = []
    with sesiones.ESCRITURA:
        datos = _leer()
        for m in datos.get(f"{cat}/{pose}", []):
            if m.get("firma") == firma:
                continue
            try:
                m["a"], m["b"] = (_punto(medir(m[k]["fx"], m[k]["fy"])) for k in ("a", "b"))
            except (ValueError, KeyError):
                fallidas.append(m.get("nombre") or m["id"])
                continue
            m["distancia_mm"], m["firma"] = distancia(m["a"], m["b"]), firma
        _escribir(datos)
    return {**listar(cat, pose), "fallidas": fallidas}
