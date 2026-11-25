"""Imágenes de cada paso, nube de puntos y medición sobre la reconstrucción (con caché de mapas)."""

from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path

from comun import DIR_COMPARACIONES, RE_ORDENADA, RE_REF, _archivos_pose, _mtime

import cv2
import numpy as np
import configuracion as cfg


class _CacheMapas:
    """Caché de mapas de los .npz con un límite de memoria.

    Se guarda cada mapa por separado, (ruta, fecha, clave): una imagen necesita 1–3 de los 10–15
    mapas de una pose (~5 MB cada uno). Antes se cacheaban .npz completos, 24 de hasta 52 MB:
    ~1.2 GB de RAM.
    """

    def __init__(self, max_bytes: int = 400_000_000) -> None:
        self.max_bytes = max_bytes
        self.datos: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
        self.claves_npz: dict[tuple, list[str]] = {}
        self.bytes = 0
        self.lock = threading.Lock()

    def claves(self, ruta: str, m: float) -> list[str]:
        with self.lock:
            if (ruta, m) not in self.claves_npz:
                with np.load(ruta) as d:
                    self.claves_npz[(ruta, m)] = list(d.files)
            return self.claves_npz[(ruta, m)]

    def mapa(self, ruta: str, m: float, clave: str) -> np.ndarray:
        k = (ruta, m, clave)
        with self.lock:
            if k in self.datos:
                self.datos.move_to_end(k)
                return self.datos[k]
            with np.load(ruta) as d:
                valor = d[clave]
            self.datos[k] = valor
            self.bytes += valor.nbytes
            while self.bytes > self.max_bytes and len(self.datos) > 1:
                _, viejo = self.datos.popitem(last=False)
                self.bytes -= viejo.nbytes
            return valor

    def limpiar(self) -> None:
        with self.lock:
            self.datos.clear()
            self.claves_npz.clear()
            self.bytes = 0


_cache_mapas = _CacheMapas()
_lock_npz = threading.Lock()  # se toma al mover archivos a la papelera


class _Npz:
    """Vista perezosa de un .npz: cada mapa se lee (y cachea) solo cuando se pide."""

    def __init__(self, ruta: Path, m: float) -> None:
        self.ruta, self.m = str(ruta), m

    def __getitem__(self, clave: str) -> np.ndarray:
        if clave not in self:
            raise KeyError(clave)
        return _cache_mapas.mapa(self.ruta, self.m, clave)

    def __contains__(self, clave: str) -> bool:
        return clave in _cache_mapas.claves(self.ruta, self.m)


def cargar_npz(ruta: Path) -> _Npz:
    m = _mtime(ruta)
    if m is None:
        raise FileNotFoundError(str(ruta))
    return _Npz(ruta, m)


def _leer_ordenada(cat: str, pose: str, orient: str, indice: int) -> np.ndarray:
    import fase

    import rutas

    return fase.leer_gris(fase.buscar_imagen_patron(rutas.dir_pose_ordenada(cat, pose) / orient / cfg.PREFIJO_ORDENADAS, indice))


FONDO = np.array([38, 34, 32], dtype=np.uint8)  # BGR de los píxeles sin dato


def _color(mapa: np.ndarray, mascara: np.ndarray | None, colormap: int,
           rango: tuple[float, float] | None = None, percentiles=(1, 99)) -> tuple[np.ndarray, tuple[float, float]]:
    mapa = mapa.astype(np.float64)
    valido = np.isfinite(mapa) if mascara is None else (mascara.astype(bool) & np.isfinite(mapa))
    if not np.any(valido):
        return np.broadcast_to(FONDO, (*mapa.shape, 3)).copy(), (0.0, 0.0)
    if rango is None:
        lo, hi = np.percentile(mapa[valido], percentiles)
    else:
        lo, hi = rango
    norm = np.clip((np.where(valido, mapa, lo) - lo) / max(hi - lo, 1e-12) * 255, 0, 255).astype(np.uint8)
    img = cv2.applyColorMap(norm, colormap)
    img[~valido] = FONDO
    return img, (float(lo), float(hi))


def generar_imagen(cat: str, pose: str, tipo: str) -> tuple[np.ndarray, str]:
    """Devuelve (imagen BGR o gris, texto de escala) para un paso del proceso."""
    archivos = _archivos_pose(cat, pose)
    n, b = cfg.N_PASOS, cfg.N_BITS_GRAY
    if tipo.startswith("dif:"):  # diferencia de Z contra una referencia (comparar)
        dif, _, solo_actual, solo_ref = diferencia_z(cat, pose, tipo[4:], mascaras=True)
        validos = np.isfinite(dif)
        lim = float(np.percentile(np.abs(dif[validos]), 98)) if np.any(validos) else 0.0
        if lim < 1e-3:  # sin diferencias en los puntos comunes: gris neutro
            img = np.broadcast_to(FONDO, (*dif.shape, 3)).copy()
            img[validos] = (150, 150, 150)
        else:
            img, _ = _color(dif, None, cv2.COLORMAP_TURBO, (-lim, lim))
        # Puntos que solo tiene una de las dos (p. ej. los que quita un filtro): rojo / azul
        img[solo_ref] = (60, 60, 230)
        img[solo_actual] = (230, 140, 60)
        escala = f"ΔZ ±{lim:.2f} mm" if lim >= 1e-3 else "ΔZ = 0 (gris)"
        return img, f"{escala} · rojo: solo en la referencia · azul: solo en la actual"
    m = RE_ORDENADA.match(tipo)
    if m:  # cualquier imagen organizada: img_V_03 = franja vertical, paso 3
        indice = int(m.group(2))
        if not 0 <= indice < cfg.IMAGENES_POR_ORIENTACION + 2:
            raise ValueError("índice de imagen fuera de rango")
        return _leer_ordenada(cat, pose, m.group(1), indice), "intensidad"
    if tipo in ("franja_V", "franja_H"):
        return _leer_ordenada(cat, pose, tipo[-1], 0), "intensidad"
    if tipo == "gray_V":
        return _leer_ordenada(cat, pose, "V", n), "bit Gray"
    if tipo == "textura":
        if archivos["absoluta"].exists():
            return cargar_npz(archivos["absoluta"])["Itex"], "intensidad"
        return _leer_ordenada(cat, pose, "H", n + b + 1), "intensidad"
    if tipo in ("phiX", "phiY", "qX", "qY"):
        rel = cargar_npz(archivos["relativa"])
        if tipo.startswith("phi"):
            img, r = _color(rel[tipo], None, cv2.COLORMAP_TWILIGHT_SHIFTED, (-np.pi, np.pi))
            return img, "−π … π rad"
        img, r = _color(rel[tipo], None, cv2.COLORMAP_VIRIDIS, (0.0, 1.0))
        return img, "γ 0 … 1"
    if tipo in ("Fx", "Fy", "kX", "kY", "mascara"):
        absl = cargar_npz(archivos["absoluta"])
        if tipo == "mascara":
            nivel = absl["MaskX"].astype(np.uint8) + 2 * absl["MaskY"].astype(np.uint8)
            paleta = np.array([FONDO, [70, 130, 230], [80, 200, 120], [240, 240, 240]], dtype=np.uint8)
            return paleta[nivel], "gris: nada · azul: solo X · verde: solo Y · blanco: ambas"
        mascara = absl["MaskX"] if tipo in ("Fx", "kX") else absl["MaskY"]
        if tipo.startswith("k"):
            img, r = _color(absl[tipo], mascara, cv2.COLORMAP_JET, percentiles=(0, 100))
            return img, f"orden {r[0]:.0f} … {r[1]:.0f}"
        img, r = _color(absl[tipo], mascara, cv2.COLORMAP_TURBO, percentiles=(0.5, 99.5))
        return img, f"{r[0]:.0f} … {r[1]:.0f} rad"
    if tipo in ("Z", "error"):
        xyz = cargar_npz(archivos["reconstruida"])
        if tipo == "Z":
            img, r = _color(xyz["Z"], xyz["Mask"], cv2.COLORMAP_VIRIDIS)
            return img, f"Z {r[0]:.1f} … {r[1]:.1f} mm"
        if "E" not in xyz:
            raise FileNotFoundError("sin mapa de error (solo categoría plano)")
        e = xyz["E"]
        lim = float(np.nanpercentile(np.abs(e), 98)) if np.any(np.isfinite(e)) else 1.0
        img, r = _color(e, None, cv2.COLORMAP_TURBO, (-lim, lim))
        return img, f"error ±{lim:.2f} mm"
    raise ValueError(f"tipo de imagen desconocido: {tipo}")


# ------------------------------------------------------------------ medición sobre la reconstrucción
def _xyz(cat: str, pose: str) -> _Npz:
    return cargar_npz(_archivos_pose(cat, pose)["reconstruida"])


def punto_3d(cat: str, pose: str, fx: float, fy: float, radio: int = 6) -> dict:
    """X, Y, Z del píxel válido más cercano a (fx, fy) ∈ [0, 1]² de la imagen (radio en px)."""
    xyz = _xyz(cat, pose)
    m = xyz["Mask"].astype(bool) & np.isfinite(xyz["Z"])
    alto, ancho = m.shape
    c, f = int(round(fx * (ancho - 1))), int(round(fy * (alto - 1)))
    f0, f1, c0, c1 = max(f - radio, 0), min(f + radio + 1, alto), max(c - radio, 0), min(c + radio + 1, ancho)
    ys, xs = np.nonzero(m[f0:f1, c0:c1])
    if not len(ys):
        raise ValueError("sin punto 3D válido cerca de ahí")
    k = int(np.argmin((ys + f0 - f) ** 2 + (xs + c0 - c) ** 2))
    fi, ci = int(ys[k] + f0), int(xs[k] + c0)
    return {"fila": fi, "col": ci, "fx": ci / (ancho - 1), "fy": fi / (alto - 1),
            **{k2: float(xyz[k2][fi, ci]) for k2 in ("X", "Y", "Z")}}


def perfil_3d(cat: str, pose: str, a: tuple[float, float], b: tuple[float, float], n: int = 400) -> dict:
    """Z (y la distancia recorrida en mm) a lo largo del segmento a→b de la imagen."""
    xyz = _xyz(cat, pose)
    m = xyz["Mask"].astype(bool) & np.isfinite(xyz["Z"])
    alto, ancho = m.shape
    t = np.linspace(0, 1, n)
    cols = np.clip(np.round((a[0] + (b[0] - a[0]) * t) * (ancho - 1)).astype(int), 0, ancho - 1)
    filas = np.clip(np.round((a[1] + (b[1] - a[1]) * t) * (alto - 1)).astype(int), 0, alto - 1)
    # Cada muestra: mediana de los píxeles válidos en una ventana 5×5 (el mapa tiene píxeles sueltos
    # sin dato por la rejilla del DMD; leer solo el píxel exacto deja la curva entrecortada)
    mapas = {k: np.where(m, xyz[k], np.nan) for k in ("X", "Y", "Z")}
    X, Y, Z = (np.full(n, np.nan) for _ in range(3))
    for i, (f, c) in enumerate(zip(filas, cols)):
        ventana = (slice(max(f - 2, 0), f + 3), slice(max(c - 2, 0), c + 3))
        if np.any(m[ventana]):
            X[i], Y[i], Z[i] = (float(np.nanmedian(mapas[k][ventana])) for k in ("X", "Y", "Z"))
    # Distancia recorrida en el plano X-Y (mm), interpolando sobre los huecos
    pasos = np.hypot(np.diff(X), np.diff(Y))
    pasos = np.where(np.isfinite(pasos), pasos, np.nanmedian(pasos) if np.any(np.isfinite(pasos)) else 0)
    s = np.concatenate([[0], np.cumsum(pasos)])
    return {"s_mm": np.round(s, 3).tolist(), "z_mm": [None if not np.isfinite(z) else round(float(z), 3) for z in Z]}


def histograma_plano(cat: str, pose: str, bins: int = 60) -> dict:
    """Histograma del error respecto al plano ajustado (solo plano) y sus estadísticas."""
    xyz = _xyz(cat, pose)
    if "E" not in xyz:
        raise FileNotFoundError("sin mapa de error (solo categoría plano)")
    e = xyz["E"][np.isfinite(xyz["E"])].astype(np.float64)
    lim = float(np.percentile(np.abs(e), 99.5)) or 1.0
    cuentas, bordes = np.histogram(np.clip(e, -lim, lim), bins=bins, range=(-lim, lim))
    return {"cuentas": cuentas.tolist(), "bordes": np.round(bordes, 4).tolist(), "n": int(e.size),
            "rms": float(np.sqrt(np.mean((e - e.mean()) ** 2))), "p95": float(np.percentile(np.abs(e), 95)),
            "max": float(np.max(np.abs(e)))}


def _ruta_referencia(cat: str, ref: str) -> Path:
    if not RE_REF.match(ref):
        raise ValueError("referencia inválida")
    tipo, valor = ref.split(":", 1)
    ruta = DIR_COMPARACIONES / f"{valor}.npz" if tipo == "copia" else _archivos_pose(cat, valor)["reconstruida"]
    if not ruta.exists():
        raise FileNotFoundError("la referencia no existe")
    return ruta


def diferencia_z(cat: str, pose: str, ref: str, mascaras: bool = False):
    """Z(actual) − Z(referencia) en los píxeles válidos en ambos, y estadísticas de la comparación."""
    a, b = _xyz(cat, pose), cargar_npz(_ruta_referencia(cat, ref))
    ma = a["Mask"].astype(bool) & np.isfinite(a["Z"])
    mb = b["Mask"].astype(bool) & np.isfinite(b["Z"])
    comun = ma & mb
    dif = np.where(comun, a["Z"].astype(np.float64) - b["Z"].astype(np.float64), np.nan)
    d = dif[comun]
    stats = {"puntos_actual": int(ma.sum()), "puntos_ref": int(mb.sum()), "comunes": int(comun.sum()),
             "solo_actual": int((ma & ~mb).sum()), "solo_ref": int((mb & ~ma).sum())}
    if d.size:
        stats.update(media=float(d.mean()), rms=float(np.sqrt(np.mean(d ** 2))), p95=float(np.percentile(np.abs(d), 95)),
                     max=float(np.max(np.abs(d))))
    if mascaras:
        return dif, stats, ma & ~mb, mb & ~ma
    return dif, stats


def generar_nube(cat: str, pose: str, maximo: int) -> bytes:
    archivos = _archivos_pose(cat, pose)
    xyz = cargar_npz(archivos["reconstruida"])
    m = xyz["Mask"].astype(bool) & np.isfinite(xyz["Z"])
    idx = np.flatnonzero(m)
    if len(idx) > maximo:
        idx = np.sort(np.random.default_rng(0).choice(idx, maximo, replace=False))
    pts = np.column_stack([xyz[k].ravel()[idx] for k in ("X", "Y", "Z")]).astype("<f4")
    if archivos["absoluta"].exists():
        gris = cargar_npz(archivos["absoluta"])["Itex"].ravel()[idx].astype(np.uint8)
    else:
        gris = np.full(len(idx), 200, np.uint8)
    return np.uint32(len(idx)).tobytes() + pts.tobytes() + gris.tobytes()
