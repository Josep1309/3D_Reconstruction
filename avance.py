"""Avisos de avance para la barra de progreso de la interfaz.

Con la interfaz (`TESIS_MARCAS_AVANCE=1`, lo pone interfaz/ejecutor.py) se imprime una marca
`@@avance {json}` que el servidor convierte en la barra; en la terminal, `paso()` imprime una línea
normal y `contador()` no imprime nada (las etapas ya escriben una línea por pose o captura).
"""

from __future__ import annotations

import json
import os


def _interfaz() -> bool:
    return os.environ.get("TESIS_MARCAS_AVANCE") == "1"


def paso(texto: str) -> None:
    """Qué se está haciendo ahora, sin contador (la barra de la etapa queda «en curso»)."""
    if _interfaz():
        print("@@avance " + json.dumps({"paso": texto}, ensure_ascii=False), flush=True)
    else:
        print(f"  → {texto}…", flush=True)


def partes(n: int) -> None:
    """La etapa que empieza recorre `n` partes (p. ej. categorías), cada una con su contador."""
    if _interfaz():
        print("@@avance " + json.dumps({"partes": n}), flush=True)


def contador(i: int, n: int, texto: str | None = None) -> None:
    """Va por el elemento `i` de `n` (0 = empezando)."""
    if _interfaz():
        print("@@avance " + json.dumps({"i": i, "n": n, **({"paso": texto} if texto else {})}, ensure_ascii=False), flush=True)
