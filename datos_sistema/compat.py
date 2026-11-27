"""Diferencias entre Linux y Windows, en un solo lugar.

- `PYTHON` / `INSTALADOR`: cómo se llaman el intérprete del entorno y el instalador, para los
  mensajes al usuario.
- `reemplazar`: `os.replace` con reintentos. En Windows falla (PermissionError) si otro proceso
  tiene abierto el destino en ese instante (p. ej. el servidor leyendo `frame.jpg` o un `.npz`).
- `nombre_seguro`: un nombre que llega del navegador no puede salir de su carpeta. En Windows
  también separan `\\` y `:` («C:algo» cambia de unidad).
- `consola_utf8`: la salida redirigida a un archivo o tubería en Windows usa cp1252 y fallaría con
  los acentos y símbolos (✔ ⚠) de los mensajes.
- `dpi_consciente` / `pantallas_windows`: monitores en píxeles reales. Sin declarar el proceso
  «DPI aware», Windows reescala la ventana del proyector (125 %, 150 %…) y difumina las franjas.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ES_WINDOWS = sys.platform == "win32"
PYTHON = r".env\Scripts\python.exe" if ES_WINDOWS else ".env/bin/python"
INSTALADOR = "instalar.bat" if ES_WINDOWS else "./instalar.sh"


def reemplazar(origen: str | Path, destino: str | Path, intentos: int = 50) -> None:
    """Reemplazo atómico; en Windows reintenta ~1 s mientras alguien tenga abierto el destino."""
    for k in range(intentos):
        try:
            os.replace(origen, destino)
            return
        except PermissionError:
            if not ES_WINDOWS or k == intentos - 1:
                raise
            time.sleep(0.02)


def nombre_seguro(nombre: str) -> bool:
    """Un nombre de archivo o carpeta suelto (sin separadores, unidad ni «..»)."""
    return bool(nombre) and not any(c in nombre for c in "/\\:\0") and not nombre.startswith(".")


def consola_utf8() -> None:
    if not ES_WINDOWS:
        return
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_dpi_hecho = False


def dpi_consciente() -> None:
    """Coordenadas y tamaños en píxeles físicos (Windows). Debe llamarse antes de abrir ventanas."""
    global _dpi_hecho
    if not ES_WINDOWS or _dpi_hecho:
        return
    _dpi_hecho = True
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # por monitor (Windows 8.1+)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def pantallas_windows() -> list[dict]:
    """Monitores conectados (como `proyector_hdmi.pantallas` con xrandr): nombre, principal, tamaño
    y posición en el escritorio virtual, en píxeles físicos."""
    if not ES_WINDOWS:
        return []
    import ctypes
    from ctypes import wintypes

    dpi_consciente()

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]

    lista: list[dict] = []
    user32 = ctypes.windll.user32
    Proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cada(hmon, _hdc, _rect, _dato):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcMonitor
            lista.append({"nombre": info.szDevice.lstrip("\\.").strip() or info.szDevice, "principal": bool(info.dwFlags & 1),
                          "ancho": r.right - r.left, "alto": r.bottom - r.top, "x": r.left, "y": r.top})
        return True

    user32.EnumDisplayMonitors(None, None, Proc(cada), 0)
    return lista
