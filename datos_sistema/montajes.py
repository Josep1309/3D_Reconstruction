"""Elegir el montaje (proyector y forma de disparo) y guardar sus datos medidos.

El montaje en uso se guarda en <DATOS>/montaje.json; `configuracion.py` lo lee al importarse (cada
etapa del pipeline corre en un proceso nuevo, y el servidor web se reinicia al cambiarlo). Ver
MONTAJES en configuracion.py.
"""

from __future__ import annotations

import json

from datos_sistema import configuracion as cfg

RUTA = cfg.DATOS / "montaje.json"


def leer() -> dict:
    try:
        datos = json.loads(RUTA.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def listar() -> list[dict]:
    return [{"id": k, "nombre": v["nombre"], "proyeccion": v["proyeccion"], "disparo": v["disparo"]}
            for k, v in cfg.MONTAJES.items()]


def info() -> dict:
    """El montaje en uso, para la interfaz."""
    return {"id": cfg.MONTAJE, **{k: cfg.MONTAJE_INFO[k] for k in ("nombre", "proyeccion", "disparo")},
            "proyector": [cfg.PROYECTOR_ANCHO, cfg.PROYECTOR_ALTO], "bits_gray": cfg.N_BITS_GRAY,
            "imagenes_por_ciclo": cfg.IMAGENES_POR_CICLO, "latencia_cuadros": cfg.HDMI_LATENCIA_CUADROS,
            "medido": leer().get("medido", {}).get(cfg.MONTAJE)}


def fijar(montaje: str) -> None:
    from datos_sistema import sesiones

    if montaje not in cfg.MONTAJES:
        raise ValueError(f"montaje desconocido: {montaje}")
    sesiones.escribir_json(RUTA, {**leer(), "montaje": montaje})


def guardar_latencia(resultado: dict) -> None:
    """Guarda la latencia medida del proyector del montaje en uso (la usa la captura)."""
    from datos_sistema import sesiones

    datos = leer()
    datos.setdefault("latencia_cuadros", {})[cfg.MONTAJE] = int(resultado["recomendada"])
    datos.setdefault("medido", {})[cfg.MONTAJE] = resultado
    sesiones.escribir_json(RUTA, datos)
