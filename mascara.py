"""Máscara por pose para quitar puntos que no son del objeto (fondo, bordes, puntos volando).

Se arma en la interfaz (pestaña «Máscara») a partir de la modulación γ de la fase con la que se
triangula, y se guarda junto a las fases de la pose:

    resultados/<proceso>/fases/<cat>/pose_XX_mascara.png    255 = se conserva (se puede editar fuera)
    resultados/<proceso>/fases/<cat>/pose_XX_mascara.json   parámetros con los que se calculó

La reconstrucción (`reconstruccion_3d.py`) la aplica si existe y recalcula la pose cuando cambia.
Sin máscara todo funciona como antes.

Pasos, en orden (todos opcionales salvo la máscara de fase, que siempre se respeta):
  1. píxeles válidos de la fase (umbrales de ⚙ Ajustes) y γ ≥ `umbral`;
  2. `recortes`: si hay, solo se conserva lo que está dentro de alguno (polígonos);
  3. `exclusiones`: se quita lo que está dentro (polígonos);
  4. `erosion` px: recorta el contorno (los bordes del objeto suelen dar puntos volando);
  5. `min_isla` px: quita regiones sueltas más pequeñas;
  6. `mayor`: conserva solo la región conectada más grande (el objeto).
Los polígonos van en coordenadas de imagen normalizadas a [0, 1].
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import cv2
import numpy as np

import configuracion as cfg
import rutas

DEFECTO = {"umbral": None, "recortes": [], "exclusiones": [], "erosion": 0, "min_isla": 0, "mayor": False}


def ruta_png(cat: str, pose: str) -> Path:
    return rutas.dir_fases(cat, pose) / f"{pose}_mascara.png"


def ruta_json(cat: str, pose: str) -> Path:
    return rutas.dir_fases(cat, pose) / f"{pose}_mascara.json"


def fase_triangulacion() -> str:
    """'Fx', 'Fy' o 'ambas': la fase con la que se triangula (decide qué modulación γ se usa)."""
    import reconstruccion_3d as r3d

    ruta = cfg.DIR_CALIBRACION / "Estereo_TSC_0_2.npz"
    try:
        params = dict(np.load(ruta)) if ruta.exists() else {}
    except (OSError, ValueError):
        params = {}
    try:
        fd = r3d.elegir_fase(cfg.FASE_TRIANGULACION, params)
    except Exception:  # noqa: BLE001 - sin calibración: la fase que el sistema usa casi siempre
        fd = "Fy"
    return {"fx": "Fx", "fy": "Fy"}.get(str(fd).lower(), "ambas")


def base(fases: dict, fd: str | None = None) -> tuple[np.ndarray, np.ndarray, float]:
    """(válidos, γ, umbral actual): máscara de la fase y modulación de la fase de triangulación."""
    fd = fd or fase_triangulacion()
    if fd == "Fx":
        valido, gamma, umbral = fases["MaskX"], fases["qFx"], cfg.GAMMA_TH
    elif fd == "Fy":
        valido, gamma, umbral = fases["MaskY"], fases["qFy"], cfg.GAMMA_TH_Y
    else:
        valido = fases["MaskX"] & fases["MaskY"]
        gamma, umbral = np.minimum(fases["qFx"], fases["qFy"]), min(cfg.GAMMA_TH, cfg.GAMMA_TH_Y)
    return np.asarray(valido, bool), np.nan_to_num(np.asarray(gamma, np.float32)), float(umbral)


def normalizar(params: dict | None) -> dict:
    """Parámetros completos y saneados (vienen de la interfaz)."""
    p = {**DEFECTO, **(params or {})}

    def poligonos(lista):
        salida = []
        for pol in lista or []:
            pts = [[min(max(float(x), 0.0), 1.0), min(max(float(y), 0.0), 1.0)] for x, y in pol][:500]
            if len(pts) >= 3:
                salida.append(pts)
        return salida[:50]

    return {
        "umbral": None if p["umbral"] in (None, "") else min(max(float(p["umbral"]), 0.0), 1.0),
        "recortes": poligonos(p["recortes"]), "exclusiones": poligonos(p["exclusiones"]),
        "erosion": int(min(max(int(p["erosion"] or 0), 0), 50)),
        "min_isla": int(min(max(int(p["min_isla"] or 0), 0), 10_000_000)),
        "mayor": bool(p["mayor"]),
    }


def _rellenar(poligonos: list, forma: tuple[int, int]) -> np.ndarray:
    alto, ancho = forma
    capa = np.zeros(forma, np.uint8)
    for pol in poligonos:
        pts = np.round(np.array(pol) * [ancho - 1, alto - 1]).astype(np.int32)
        cv2.fillPoly(capa, [pts], 1)
    return capa.astype(bool)


def _rellenar_huecos(m: np.ndarray) -> np.ndarray:
    """La máscara con sus huecos interiores rellenos (lo que no se alcanza desde el borde de la imagen)."""
    fondo = np.pad(~m, 1, constant_values=True).astype(np.uint8)
    cv2.floodFill(fondo, None, (0, 0), 2)
    return (fondo[1:-1, 1:-1] != 2)


def calcular(valido: np.ndarray, gamma: np.ndarray, params: dict) -> np.ndarray:
    """Máscara final (bool) a partir de los píxeles válidos de la fase y la modulación γ."""
    p = normalizar(params)
    m = valido.copy()
    if p["umbral"] is not None:
        m &= gamma >= p["umbral"]
    if p["recortes"]:
        m &= _rellenar(p["recortes"], m.shape)
    if p["exclusiones"]:
        m &= ~_rellenar(p["exclusiones"], m.shape)
    if p["erosion"]:  # solo el contorno exterior: los agujeritos de dentro no crecen
        k = 2 * p["erosion"] + 1
        silueta = _rellenar_huecos(m)
        m &= cv2.erode(silueta.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))).astype(bool)
    if p["min_isla"] or p["mayor"]:
        n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
        areas = stats[1:, cv2.CC_STAT_AREA]
        if n > 1:
            conservar = areas >= p["min_isla"] if p["min_isla"] else np.ones(n - 1, bool)
            if p["mayor"]:
                conservar = np.zeros(n - 1, bool)
                conservar[int(np.argmax(areas))] = True
            m = np.concatenate([[False], conservar])[etiquetas]
    return m


def guardar(cat: str, pose: str, mascara: np.ndarray, params: dict) -> Path:
    """Escribe el PNG y sus parámetros (de forma atómica: la reconstrucción puede estar leyendo)."""
    destino = ruta_png(cat, pose)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(f".{destino.stem}.{os.getpid()}.png")
    if not cv2.imwrite(str(tmp), mascara.astype(np.uint8) * 255):
        raise OSError(f"No se pudo escribir {destino}")
    os.replace(tmp, destino)
    import sesiones

    sesiones.escribir_json(ruta_json(cat, pose), {**normalizar(params), "fase": fase_triangulacion(),
                                                  "conservados": int(mascara.sum()), "total": int(mascara.size)})
    return destino


def borrar(cat: str, pose: str) -> bool:
    hubo = ruta_png(cat, pose).exists()
    ruta_png(cat, pose).unlink(missing_ok=True)
    ruta_json(cat, pose).unlink(missing_ok=True)
    return hubo


def cargar(cat: str, pose: str, forma: tuple[int, int] | None = None) -> np.ndarray | None:
    """Máscara guardada (bool), o None si la pose no tiene."""
    ruta = ruta_png(cat, pose)
    if not ruta.exists():
        return None
    img = cv2.imread(str(ruta), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise OSError(f"No se pudo leer la máscara {ruta}")
    if forma and img.shape != tuple(forma):
        img = cv2.resize(img, (forma[1], forma[0]), interpolation=cv2.INTER_NEAREST)
    return img > 127


def leer_parametros(cat: str, pose: str) -> dict | None:
    try:
        return json.loads(ruta_json(cat, pose).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {} if ruta_png(cat, pose).exists() else None  # PNG editado a mano, sin parámetros


def firma(cat: str, pose: str) -> str | None:
    """Identifica la máscara guardada (para la caché de la reconstrucción); None = sin máscara."""
    try:
        st = ruta_png(cat, pose).stat()
    except OSError:
        return None
    return f"{st.st_mtime_ns}|{st.st_size}"


def zonas_dificiles(fases: dict, dir_pose: Path, fd: str, rel_min: float = cfg.REFLECTANCIA_REL_MIN,
                    borde: int = cfg.REFLECTANCIA_BORDE_PX, saturacion: float = cfg.SATURACION_NIVEL) -> np.ndarray:
    """Píxeles donde la fase no es fiable aunque pasen los umbrales: bordes de manchas oscuras
    (modulación mucho menor que la de su entorno) y píxeles saturados. Devuelve True = descartar.

    La modulación se suaviza (σ 1.5 px) antes de compararla: tiene un patrón fino píxel a píxel
    (rejilla del DMD) que, si no, se confunde con manchas."""
    alto, ancho = fases["Itex"].shape
    malo = np.zeros((alto, ancho), bool)
    orient = {"fx": ["V"], "fy": ["H"]}.get(str(fd).lower(), ["H", "V"])
    if rel_min and rel_min > 0:
        for o in orient:
            b = cv2.GaussianBlur(np.nan_to_num(fases["BY" if o == "H" else "BX"]).astype(np.float32), (0, 0), 1.5)
            entorno = cv2.medianBlur(np.clip(b, 0, 255).astype(np.uint8), 31).astype(np.float32)
            malo |= b < rel_min * np.maximum(entorno, 1.0)
        if borde > 0:
            k = 2 * borde + 1
            malo = cv2.dilate(malo.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))).astype(bool)
    if saturacion is not None and saturacion <= 255:
        for o in orient:
            malo |= imagenes_saturadas(dir_pose, o, saturacion) >= cfg.N_PASOS / 2
    return malo


def imagenes_saturadas(dir_pose: Path, orient: str = "H", nivel: float = 250) -> np.ndarray:
    """En cuántos de los corrimientos de fase llega cada píxel a `nivel` (0 si faltan imágenes)."""
    cuenta = None
    for i in range(cfg.N_PASOS):
        img = cv2.imread(str(dir_pose / orient / f"{cfg.PREFIJO_ORDENADAS}{i:02d}.tiff"), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        cuenta = (img >= nivel).astype(np.int16) if cuenta is None else cuenta + (img >= nivel)
    return cuenta if cuenta is not None else np.zeros((1, 1), np.int16)


def filtrar_vecinos(x: np.ndarray, y: np.ndarray, z: np.ndarray, m: np.ndarray, sigma: float) -> np.ndarray:
    """Quita puntos aislados en 3D (como `pcdenoise`, pero sobre la rejilla de la cámara).

    Para cada punto, distancia media 3D a sus vecinos válidos (8 alrededor); se descartan los que
    superan la mediana en más de `sigma` desviaciones robustas (MAD), y los que no tienen vecinos."""
    if not sigma or sigma <= 0 or not np.any(m):
        return m
    pts = np.stack([x, y, z], axis=-1).astype(np.float32)
    pts[~m] = np.nan
    pad = np.pad(pts, ((1, 1), (1, 1), (0, 0)), constant_values=np.nan)
    suma = np.zeros(m.shape, np.float32)
    n = np.zeros(m.shape, np.int16)
    alto, ancho = m.shape
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == dx == 0:
                continue
            vecino = pad[1 + dy:1 + dy + alto, 1 + dx:1 + dx + ancho]
            d = np.linalg.norm(pts - vecino, axis=-1)
            ok = np.isfinite(d)
            suma[ok] += d[ok]
            n += ok
    media = np.where(n > 0, suma / np.maximum(n, 1), np.inf)
    valores = media[m & (n > 0)]
    if valores.size < 10:
        return m
    med = float(np.median(valores))
    # piso: en una superficie muy regular la MAD tiende a 0 y se quitarían puntos sanos
    mad = max(1.4826 * float(np.median(np.abs(valores - med))), 0.05 * med, 1e-6)
    return m & (n > 0) & (media <= med + sigma * mad)
