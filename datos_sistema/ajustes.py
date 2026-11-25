"""Ajustes de procesamiento elegidos en la interfaz (⚙), guardados en `<DATOS>/ajustes.json`.

Los usan la interfaz web, `pipeline.py` por terminal y cualquier navegador. Sin el archivo valen
los de `configuracion.py`.

Formato:
- `efectivos`: {VARIABLE: número | texto | null}. null = paso desactivado.
- `valores`: el estado de los controles de la interfaz.
- `selects`: triangulación, calibración y poses del patrón.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from datos_sistema import configuracion as cfg

RUTA = cfg.DATOS / "ajustes.json"

# Variables que puede cambiar la interfaz, y el valor que las «desactiva»
NEUTROS = {
    "CAM_EXPOSICION_US": 12000.0,    # (siempre activo: el valor lo pone la interfaz)
    "SUAVIZADO_FASE_PX": 0.0,        # sin suavizado de S y C
    "GAMMA_TH": 0.0,                 # sin máscara de modulación X
    "GAMMA_TH_Y": 0.0,               # sin máscara de modulación Y
    "UMBRAL_INTENSIDAD": -1.0,       # sin máscara de intensidad
    "BORDE_MASCARA": 0,              # sin recorte de bordes
    "MED_FILT": 0,                   # sin filtro de mediana del orden de franja
    "SALTO_MAX_MM": float("inf"),    # sin filtro de saltos
    "Z_MIN_MM": float("-inf"),       # sin límite de Z (se envía junto con Z_MAX_MM)
    "Z_MAX_MM": float("inf"),
    "PLANO_UMBRAL_MM": 3.0,
    "FILTRO_VECINOS_SIGMA": 0.0,     # sin filtro de puntos aislados
    "REFLECTANCIA_REL_MIN": 0.0,     # sin filtro de manchas
    "SATURACION_NIVEL": 256,         # sin descartar saturados
}
ENTEROS = {"BORDE_MASCARA", "MED_FILT", "SATURACION_NIVEL"}


def leer(ruta: Path = RUTA) -> dict:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def guardar(datos: dict, ruta: Path = RUTA) -> None:
    from datos_sistema import sesiones

    sesiones.escribir_json(ruta, datos)


def valores(efectivos: dict, base: dict | None = None) -> dict:
    """{VARIABLE: valor} que resultan de aplicar `efectivos` sobre `base` (por defecto, los
    valores de configuracion.py), sin tocar `configuracion`."""
    base = dict(cfg.VALORES_ORIGINALES if base is None else base)
    salida = {}
    efectivos = dict(efectivos)
    dx, dy = efectivos.pop("PATRON_DX_MM", None), efectivos.pop("PATRON_DY_MM", None)
    if dx and dy:
        salida["PATRON_DISTANCIA_MM"] = (float(dx), float(dy)) if float(dx) != float(dy) else float(dx)
    for clave, valor in efectivos.items():
        if clave == "ORDEN_BITS_GRAY":
            if valor in ("auto", "lsb", "msb"):
                salida[clave] = valor
        elif clave in NEUTROS:
            nuevo = NEUTROS[clave] if valor is None else float(valor)
            if clave in ENTEROS and math.isfinite(nuevo):
                nuevo = int(nuevo)
            salida[clave] = nuevo
    return {**{k: base[k] for k in salida if k in base}, **salida}


def aplicar(efectivos: dict) -> list[str]:
    """Aplica los ajustes a `configuracion`. Devuelve los cambios respecto a configuracion.py,
    para el registro."""
    cambios = []
    for clave, nuevo in valores(efectivos).items():
        if getattr(cfg, clave) != nuevo:
            desactivado = clave in NEUTROS and efectivos.get(clave, 0) is None
            cambios.append(f"{clave}={'desactivado' if desactivado else nuevo}")
        setattr(cfg, clave, nuevo)
    return cambios


def aplicar_guardados() -> list[str]:
    """Para `pipeline.py` por terminal: los mismos ajustes que la interfaz."""
    return aplicar(leer().get("efectivos", {}))


def firmas_esperadas(efectivos: dict | None = None) -> tuple[str, str]:
    """Firmas (fase relativa, fase absoluta) que tendrían las poses calculadas con estos ajustes."""
    from procesamiento import fase

    v = {**cfg.VALORES_ORIGINALES, **valores(leer().get("efectivos", {}) if efectivos is None else efectivos)}
    return (fase.firma_relativa(v["N_PASOS"], v["SUAVIZADO_FASE_PX"]),
            fase.firma_absoluta(v["PERIODO"], v["N_BITS_GRAY"], v["GAMMA_TH"], v["GAMMA_TH_Y"], v["MED_FILT"],
                                v["ORDEN_BITS_GRAY"], v["UMBRAL_INTENSIDAD"], v["BORDE_MASCARA"]))


def describir_firma(firma: str) -> str:
    """'abs|18|6|0.15|0.03|5|auto|25|15' -> texto legible de los parámetros."""
    partes = firma.split("|")
    if partes[0] == "rel" and len(partes) >= 3:
        return f"suavizado σ={partes[2]}"
    if partes[0] == "abs" and len(partes) >= 9:
        return (f"γX≥{partes[3]} · γY≥{partes[4]} · mediana {partes[5]} · bits {partes[6]} · "
                f"intensidad>{partes[7]} · borde {partes[8]} px")
    return firma
