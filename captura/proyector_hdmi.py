"""Proyección de los patrones por HDMI (montaje «hdmi_dell»).

El PC muestra cada patrón a pantalla completa en el proyector (una segunda pantalla del
escritorio) con una ventana de OpenCV (Qt, ya incluida: no hace falta instalar nada). La cámara se
dispara con el VSYNC del HDMI en cada cuadro (60 Hz), así que recibe cuadros continuamente aunque el
patrón no cambie. Para cada patrón (`CamaraFLIR.capturar_sincronizado`):

1. se muestra el patrón;
2. se vacía el búfer de la cámara: esos cuadros se expusieron con el patrón anterior;
3. se descartan `HDMI_LATENCIA_CUADROS` cuadros (el proyector tarda en mostrar la imagen nueva);
4. se guarda el siguiente.

Resultado: las mismas imágenes ordenadas de siempre (un ciclo de IMAGENES_POR_CICLO), así que
organizar, fases, calibración y reconstrucción no cambian. La latencia se mide con `medir_latencia`
(⚙ Ajustes → Proyector → «Medir latencia»).

Requisitos: el proyector configurado en el sistema a su resolución nativa (1280×800, 60 Hz) como
pantalla extendida (no duplicada), sin «keystone» ni modos de imagen que alteren el brillo.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

from datos_sistema import configuracion as cfg

VENTANA = "Patrones (proyector)"


def pantallas() -> list[dict]:
    """Pantallas conectadas según xrandr (también funciona en Wayland vía XWayland)."""
    try:
        salida = subprocess.run(["xrandr", "--query"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    lista = []
    for linea in salida.splitlines():
        m = re.match(r"^(\S+) connected (primary )?(\d+)x(\d+)\+(\d+)\+(\d+)", linea)
        if m:
            lista.append({"nombre": m.group(1), "principal": bool(m.group(2)), "ancho": int(m.group(3)),
                          "alto": int(m.group(4)), "x": int(m.group(5)), "y": int(m.group(6))})
    return lista


def ubicar_pantalla(ancho: int = cfg.PROYECTOR_ANCHO, alto: int = cfg.PROYECTOR_ALTO,
                    pantalla: str = cfg.HDMI_PANTALLA) -> dict:
    """La pantalla del proyector: «x,y» explícito, o «auto» (la de su resolución, si no la que no es
    la principal)."""
    if pantalla and pantalla != "auto":
        x, y = (int(v) for v in str(pantalla).split(","))
        return {"nombre": "manual", "x": x, "y": y, "ancho": ancho, "alto": alto, "principal": False}
    lista = pantallas()
    exacta = [p for p in lista if (p["ancho"], p["alto"]) == (ancho, alto)]
    otras = [p for p in lista if not p["principal"]]
    if exacta:
        return exacta[0]
    if otras:
        return otras[0]
    detectadas = ", ".join(f"{p['nombre']} {p['ancho']}×{p['alto']}" for p in lista) or "ninguna"
    raise RuntimeError(f"No se encontró la pantalla del proyector ({ancho}×{alto}). Pantallas detectadas: {detectadas}. "
                       "Conecta el proyector por HDMI como pantalla EXTENDIDA a su resolución nativa, o indica su "
                       "posición en HDMI_PANTALLA (\"x,y\").")


def cargar_patrones(directorio: Path = cfg.DIR_PATRONES) -> list[np.ndarray]:
    """Las imágenes f_00 … f_NN de la secuencia, en orden (una por patrón del ciclo)."""
    rutas = sorted(Path(directorio).glob("f_*.bmp"))
    if len(rutas) != cfg.IMAGENES_POR_CICLO:
        raise FileNotFoundError(f"Hay {len(rutas)} patrones en {directorio} y se necesitan {cfg.IMAGENES_POR_CICLO}: "
                                "genéralos (⚙ Ajustes → Proyector → «Generar los patrones»)")
    imgs = [cv2.imread(str(r), cv2.IMREAD_GRAYSCALE) for r in rutas]
    if any(i is None or i.shape != (cfg.PROYECTOR_ALTO, cfg.PROYECTOR_ANCHO) for i in imgs):
        raise ValueError(f"Los patrones de {directorio} no son de {cfg.PROYECTOR_ANCHO}×{cfg.PROYECTOR_ALTO}: genéralos de nuevo")
    return imgs


class ProyectorHDMI:
    """Ventana a pantalla completa en el proyector (se usa con `with`)."""

    simulado = False

    def __init__(self, ancho: int = cfg.PROYECTOR_ANCHO, alto: int = cfg.PROYECTOR_ALTO) -> None:
        self.ancho, self.alto = ancho, alto
        self.actual: np.ndarray | None = None

    def __enter__(self) -> ProyectorHDMI:
        p = ubicar_pantalla(self.ancho, self.alto)
        cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
        cv2.moveWindow(VENTANA, p["x"], p["y"])
        cv2.resizeWindow(VENTANA, self.ancho, self.alto)
        cv2.setWindowProperty(VENTANA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        self.mostrar(np.zeros((self.alto, self.ancho), np.uint8))
        cv2.waitKey(300)  # que el gestor de ventanas termine de ubicarla
        print(f"[OK] Proyector HDMI: pantalla {p['nombre']} {p.get('ancho')}×{p.get('alto')} en +{p['x']}+{p['y']}", flush=True)
        return self

    def mostrar(self, imagen: np.ndarray) -> None:
        self.actual = imagen
        cv2.imshow(VENTANA, imagen)
        cv2.waitKey(1)  # procesa los eventos: sin esto la ventana no se repinta

    def blanco(self) -> None:
        self.mostrar(np.full((self.alto, self.ancho), 255, np.uint8))

    def __exit__(self, *_exc) -> None:
        try:
            cv2.destroyWindow(VENTANA)
            cv2.waitKey(1)
        except cv2.error:
            pass


class ProyectorSimulado(ProyectorHDMI):
    """Para el modo demo: no abre ventanas; la cámara simulada «ve» el último patrón mostrado."""

    simulado = True

    def __enter__(self) -> ProyectorSimulado:
        print(f"[OK] Proyector HDMI SIMULADO ({self.ancho}×{self.alto})", flush=True)
        return self

    def mostrar(self, imagen: np.ndarray) -> None:
        self.actual = imagen

    def __exit__(self, *_exc) -> None:
        pass


def medir_latencia(camara, proyector, repeticiones: int = 5, maximo: int = 12) -> dict:
    """Cuántos cuadros tarda el proyector en mostrar un patrón nuevo, y a qué ritmo llegan los
    disparos. Alterna negro y blanco y cuenta los cuadros hasta que el brillo cambia."""
    negro = np.zeros((proyector.alto, proyector.ancho), np.uint8)
    blanco = np.full_like(negro, 255)
    cuadros, tiempos = [], []
    with camara.adquisicion() as leer:
        for rep in range(repeticiones):
            for patron, sube in ((negro, False), (blanco, True)):
                # referencia: un cuadro con el patrón ANTERIOR todavía en pantalla
                leer.vaciar()
                img, t = leer.siguiente()
                ref = float(np.mean(img))
                proyector.mostrar(patron)
                leer.vaciar()
                for k in range(maximo):
                    img, t = leer.siguiente()
                    tiempos.append(t)
                    brillo = float(np.mean(img))
                    if (brillo - ref > 30) if sube else (ref - brillo > 30):
                        if sube:
                            cuadros.append(k)
                        break
    if len(tiempos) > 3:
        dt = np.diff(np.array(tiempos))
        hz = float(1.0 / np.median(dt[dt > 0])) if np.any(dt > 0) else None
    else:
        hz = None
    if not cuadros:
        raise RuntimeError("La cámara no vio cambiar el brillo al alternar negro y blanco: ¿apunta al área "
                           "proyectada? ¿llega el VSYNC a Line0?")
    recomendada = int(max(cuadros)) + 1  # un cuadro de margen
    return {"cuadros": cuadros, "recomendada": recomendada, "disparos_hz": hz}
