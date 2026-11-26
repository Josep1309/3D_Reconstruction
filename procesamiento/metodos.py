"""Métodos de reconstrucción 3D para comparar (port de los códigos de MATLAB de
recursos/Matlab_Codes/Codes/3DReconstructionCodes y HybridCalibCodes).

**Estéreo (triangulación)** — `StereoReconstruction.m`: cada píxel de la cámara y su coordenada del
proyector (de la fase) definen dos rayos; el punto 3D es su intersección. Variantes según la fase
usada: Fy (la del sistema, por la línea base vertical), Fx, o ambas.

**Híbridos** — `HybridReconstruction.m`, `Eval_PhaseRegression.m`, `Eval_PhaseFrac.m`: en lugar de
triangular, cada píxel de la cámara tiene su propia función que pasa directamente de la fase a
X, Y, Z, ajustada con superficies de calibración:
- *polinomial* (`Polyfit3D.m`): X, Y y Z = polinomio de grado n de la fase;
- *racional* (`Racionalfit3D.m`, `Eval_PhaseFrac.m`): Z = (a0 + a1·φ + a2·φ²) / (1 + b1·φ), y X, Y
  lineales en Z (el píxel ve a lo largo de un rayo). Una cámara y un proyector ideales dan
  exactamente Z = (a0 + a1·φ)/(1 + b1·φ); el término a2 absorbe la distorsión del proyector. (El
  2/2 de `Eval_PhaseFrac.m` tiene infinitas soluciones equivalentes con datos exactos: el ajuste
  queda singular.) La polinomial aproxima esta forma.

y según con qué superficies se ajusta:
- *planos virtuales* (`HybridCalibration_VirtualPlanes_Script.m`, `BackPropagation_Planes2.m`):
  planos perpendiculares a la cámara a varias distancias, generados con la calibración estéreo
  (para cada píxel: su rayo corta el plano, y ese punto se proyecta en el proyector). No mide
  nada nuevo: reproduce la geometría estéreo con funciones por píxel.
- *planos medidos* (`HybridCalibration_Stereo_Script.m`, `XYZ_R3D_Target.m`,
  `PoseEstimation_Hybrid.m`): superficies planas reales capturadas (el tablero del patrón y las
  poses de plano). Se reconstruyen en estéreo, se ajusta su plano y el punto «ideal» de cada píxel
  es donde su rayo corta ese plano; la función se ajusta con la fase **medida**. Así absorbe
  errores sistemáticos de la fase que el modelo estéreo no tiene en cuenta.

Como variable de fase se usa la coordenada del proyector (vp o up, en px): es la fase escalada
(φ·P/2π + c), así que el ajuste es el mismo.

Los modelos híbridos se guardan en resultados/calibracion/modelos/ (dependen de la calibración) y
las reconstrucciones de cada método en resultados/<proceso>/reconstruccion/<cat>/metodos/.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from datos_sistema import configuracion as cfg
from datos_sistema import rutas

DIR_MODELOS = cfg.DIR_RESULTADOS / "calibracion" / "modelos"
PREDETERMINADO = "estereo"

METODOS = {
    "estereo": {"nombre": "Estéreo (Fy)", "tipo": "estereo", "fase": "Fy"},
    "estereo_fx": {"nombre": "Estéreo (Fx)", "tipo": "estereo", "fase": "Fx"},
    "estereo_ambas": {"nombre": "Estéreo (Fx + Fy)", "tipo": "estereo", "fase": "ambas"},
    "hib_pol_virtual": {"nombre": "Híbrido polinomial · planos virtuales", "tipo": "hibrido", "modelo": "pol", "datos": "virtual", "grado": 4},
    "hib_rac_virtual": {"nombre": "Híbrido racional · planos virtuales", "tipo": "hibrido", "modelo": "rac", "datos": "virtual"},
    "hib_pol_medidos": {"nombre": "Híbrido polinomial · planos medidos", "tipo": "hibrido", "modelo": "pol", "datos": "medidos", "grado": 3},
    "hib_rac_medidos": {"nombre": "Híbrido racional · planos medidos", "tipo": "hibrido", "modelo": "rac", "datos": "medidos"},
}
_CANDADOS: dict[str, threading.Lock] = {}  # un ajuste de cada modelo a la vez (la interfaz pide en paralelo)
_CANDADO = threading.Lock()
PLANOS_VIRTUALES = 17          # como HybridCalibration_VirtualPlanes_Script (17 planos)
MARGEN_EXTRAPOLACION = 0.05    # fuera del rango de fase de calibración (±5 %) no se reconstruye


# ------------------------------------------------------------------ utilidades
def _calibracion() -> tuple[dict, Path]:
    ruta = cfg.DIR_CALIBRACION / "Estereo_TSC_0_2.npz"
    with np.load(ruta) as d:
        return {k: d[k] for k in d.files}, ruta


def _rayos(calib: dict, filas: slice, ancho: int) -> tuple[np.ndarray, np.ndarray]:
    """Rayo (xn, yn, 1) sin distorsión de cada píxel de las filas pedidas (comp_distortion_oulu)."""
    v, u = np.mgrid[filas, 0:ancho].astype(np.float64)
    pix = np.stack([u.ravel(), v.ravel()], axis=-1).reshape(-1, 1, 2)
    n = cv2.undistortPoints(pix, np.asarray(calib["Ac"], np.float64), np.asarray(calib["dist_cam"], np.float64).ravel())
    n = n.reshape(-1, 2)
    return n[:, 0], n[:, 1]


def _proyectar(calib: dict, xyz: np.ndarray) -> np.ndarray:
    """Coordenadas (up, vp) del proyector de puntos en el sistema de la cámara (X_p = R·X_c + T)."""
    r, t = np.asarray(calib["R"], np.float64), np.asarray(calib["T"], np.float64).reshape(3)
    xp = xyz @ r.T + t
    uv, _ = cv2.projectPoints(xp.reshape(-1, 1, 3), np.zeros(3), np.zeros(3),
                              np.asarray(calib["Ap"], np.float64), np.asarray(calib["dist_proj"], np.float64).ravel())
    return uv.reshape(-1, 2)


def _resolver(m: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Resuelve muchos sistemas pequeños m·x = b a la vez; los singulares quedan NaN."""
    n = m.shape[-1]
    m = m + np.eye(n) * 1e-9 * np.maximum(np.trace(m, axis1=1, axis2=2), 1e-12)[:, None, None] / n
    ok = np.isfinite(m).all(axis=(1, 2)) & np.isfinite(b).all(axis=1) & (np.abs(np.linalg.det(m)) > 1e-30)
    x = np.full(b.shape, np.nan)
    if ok.any():
        x[ok] = np.linalg.solve(m[ok], b[ok][..., None])[..., 0]
    return x, ok


# ------------------------------------------------------------------ ajuste por píxel
def ajustar(v: np.ndarray, x: np.ndarray, y: np.ndarray, z: np.ndarray, modelo: str, grado: int = 3) -> dict:
    """Ajusta, píxel por píxel, la función fase -> X, Y, Z. Entradas (n_píxeles, n_superficies) con NaN
    donde no hay dato. Devuelve los coeficientes y el rango de fase usado (para no extrapolar).

    Los píxeles sin datos (p. ej. bordes que ninguna superficie medida cubrió) quedan sin modelo; sus
    avisos de numpy («Mean of empty slice»…) son esperables y se silencian."""
    import warnings

    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)
        return _ajustar(v, x, y, z, modelo, grado)


def _ajustar(v: np.ndarray, x: np.ndarray, y: np.ndarray, z: np.ndarray, modelo: str, grado: int) -> dict:
    w = np.isfinite(v) & np.isfinite(z) & np.isfinite(x) & np.isfinite(y)
    cuenta = w.sum(axis=1)
    vv = np.where(w, v, np.nan)
    with np.errstate(all="ignore"):
        mu, sd = np.nanmean(vv, axis=1), np.nanstd(vv, axis=1)
    sd = np.where(sd > 1e-6, sd, np.nan)
    t = np.where(w, (v - mu[:, None]) / sd[:, None], 0.0)
    # Z también normalizada por píxel: Z (~500 mm) multiplica a la fase en el ajuste racional
    with np.errstate(all="ignore"):
        mz, sz = np.nanmean(np.where(w, z, np.nan), axis=1), np.nanstd(np.where(w, z, np.nan), axis=1)
    sz = np.where(sz > 1e-9, sz, 1.0)
    zn = np.where(w, (z - mz[:, None]) / sz[:, None], 0.0)
    xx, yy = (np.where(w, a, 0.0) for a in (x, y))
    salida = {"modelo": modelo, "mu": mu, "sd": sd, "mz": mz, "sz": sz,
              "vmin": np.nanmin(np.where(w, v, np.inf), axis=1), "vmax": np.nanmax(np.where(w, v, -np.inf), axis=1)}
    if modelo == "pol":
        base = np.stack([t ** j for j in range(grado + 1)], axis=-1) * w[..., None]      # (n, k, g+1)
        m = np.einsum("nki,nkj->nij", base, base)
        cz, ok = _resolver(m, np.einsum("nki,nk->ni", base, zn))
        cx, _ = _resolver(m, np.einsum("nki,nk->ni", base, xx))
        cy, _ = _resolver(m, np.einsum("nki,nk->ni", base, yy))
        ok &= cuenta >= grado + 2
        salida.update(cz=cz, cx=cx, cy=cy)
    else:
        # zn·(1 + b1·t) = a0 + a1·t + a2·t²  ->  lineal en (a0, a1, a2, b1)
        fila = np.stack([np.ones_like(t), t, t * t, -t * zn], axis=-1) * w[..., None]
        m = np.einsum("nki,nkj->nij", fila, fila)
        cz, ok = _resolver(m, np.einsum("nki,nk->ni", fila, zn))
        # X, Y lineales en Z (a lo largo del rayo del píxel), con Z normalizada
        bz = np.stack([zn, np.ones_like(zn)], axis=-1) * w[..., None]
        mz = np.einsum("nki,nkj->nij", bz, bz)
        cx, _ = _resolver(mz, np.einsum("nki,nk->ni", bz, xx))
        cy, _ = _resolver(mz, np.einsum("nki,nk->ni", bz, yy))
        ok &= cuenta >= 5
        salida.update(cz=cz, cx=cx, cy=cy)
    salida["ok"] = ok & np.isfinite(sd)
    return salida


def evaluar(mod: dict, v: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """X, Y, Z del modelo para la fase medida v (mismo tamaño que la imagen). También la máscara de
    píxeles dentro del rango calibrado."""
    forma = v.shape
    v = v.reshape(-1).astype(np.float64)
    rango = mod["vmax"] - mod["vmin"]
    dentro = (mod["ok"] & np.isfinite(v) & (v >= mod["vmin"] - MARGEN_EXTRAPOLACION * rango)
              & (v <= mod["vmax"] + MARGEN_EXTRAPOLACION * rango))
    t = np.where(dentro, (v - mod["mu"]) / mod["sd"], 0.0)
    if str(mod["modelo"]) == "pol":
        def horner(c):
            r = np.zeros_like(t)
            for j in range(c.shape[1] - 1, -1, -1):
                r = r * t + c[:, j]
            return r
        z, x, y = horner(mod["cz"]) * mod["sz"] + mod["mz"], horner(mod["cx"]), horner(mod["cy"])
    else:
        a = mod["cz"]
        with np.errstate(all="ignore"):
            zn = (a[:, 0] + a[:, 1] * t + a[:, 2] * t * t) / (1 + a[:, 3] * t)
        z = zn * mod["sz"] + mod["mz"]
        x = mod["cx"][:, 0] * zn + mod["cx"][:, 1]
        y = mod["cy"][:, 0] * zn + mod["cy"][:, 1]
    dentro &= np.isfinite(z)
    sal = [np.where(dentro, a, np.nan).reshape(forma).astype(np.float32) for a in (x, y, z)]
    return sal[0], sal[1], sal[2], dentro.reshape(forma)


# ------------------------------------------------------------------ datos de calibración híbrida
def _muestras_virtuales(calib: dict, forma: tuple[int, int], fase: str, filas: slice):
    """Planos perpendiculares a la cámara a varias distancias (BackPropagation_Planes2)."""
    alto, ancho = forma
    tz = np.asarray(calib.get("tvecs_cam", np.zeros((1, 3, 1))), np.float64).reshape(-1, 3)[:, 2]
    z0 = max(cfg.Z_MIN_MM, float(tz.min()) - 120 if tz.size else 400)
    z1 = min(cfg.Z_MAX_MM, float(tz.max()) + 120 if tz.size else 800)
    zs = np.linspace(z0, z1, PLANOS_VIRTUALES)
    xn, yn = _rayos(calib, filas, ancho)
    n = len(xn)
    vv, xx, yy, zz = (np.empty((n, len(zs))) for _ in range(4))
    for k, z in enumerate(zs):
        p = np.stack([xn * z, yn * z, np.full(n, z)], axis=-1)
        uv = _proyectar(calib, p)
        vv[:, k] = uv[:, 1] if fase == "Fy" else uv[:, 0]
        xx[:, k], yy[:, k], zz[:, k] = p[:, 0], p[:, 1], z
    return vv, xx, yy, zz


def _poses_medidas() -> list[tuple[str, str, Path]]:
    """Poses de plano y del patrón de la configuración en uso que tienen fase (las superficies de los
    modelos de planos medidos)."""
    from datos_sistema import sesiones

    salida = []
    for cat in ("plano", "patron"):
        for pose in sorted(sesiones.poses_vigentes(cat) or []):
            ruta = rutas.fase_absoluta(cat, pose)
            if ruta.exists():
                salida.append((cat, pose, ruta))
    return salida


def _superficies_medidas(calib: dict, fase: str) -> list[dict]:
    """Planos reales: las poses de plano y del patrón de la configuración en uso, reconstruidas en
    estéreo; de cada una, su plano ajustado (RANSAC) y la fase medida en sus píxeles."""
    from procesamiento import fase as fase_mod
    from procesamiento import reconstruccion_3d as r3d

    sup = []
    for cat, pose, ruta in _poses_medidas():
        if True:
            d = fase_mod.cargar_fases_pose(ruta)
            x, y, z, m = r3d.triangular(d["up"], d["vp"], d["MaskX"], d["MaskY"], calib, "Fy",
                                        peso_x=d.get("BX"), peso_y=d.get("BY"))
            m = r3d.filtrar_outliers_3d(z, m, cfg.SALTO_MAX_MM, cfg.Z_MIN_MM, cfg.Z_MAX_MM)
            if m.sum() < 5000:
                continue
            e_map, erms, tt = r3d.plane_fitting(x, y, z, m, umbral_mm=1.0)
            inl = np.isfinite(e_map)
            if inl.sum() < 5000:
                continue
            sup.append({"pose": f"{cat}/{pose}", "plano": [float(c) for c in tt], "erms": erms,
                        "m": inl, "v": (d["vp"] if fase == "Fy" else d["up"]).astype(np.float32),
                        "firma": ruta.stat().st_mtime_ns})
    return sup


def _id_modelo(metodo: str, ruta_calib: Path, extra: str = "") -> str:
    st = ruta_calib.stat()
    base = f"v2|{metodo}|{ruta_calib.resolve()}|{st.st_mtime_ns}|{cfg.Z_MIN_MM}|{cfg.Z_MAX_MM}|{extra}"
    return hashlib.sha1(base.encode()).hexdigest()[:12]


def modelo_hibrido(metodo: str, forma: tuple[int, int] = (1024, 1280), avisar=print) -> dict:
    """El modelo híbrido del método (lo ajusta y lo guarda la primera vez)."""
    with _CANDADO:
        candado = _CANDADOS.setdefault(metodo, threading.Lock())
    with candado:
        return _modelo_hibrido(metodo, forma, avisar)


def id_modelo(metodo: str) -> str:
    """Identifica el modelo vigente del método: calibración y, en los de planos medidos, las poses
    usadas y la fecha de su fase (sin reconstruir nada: es barato)."""
    _, ruta_calib = _calibracion()
    extra = ""
    if METODOS[metodo].get("datos") == "medidos":
        extra = json.dumps([(f"{c}/{p}", r.stat().st_mtime_ns) for c, p, r in _poses_medidas()])
    return _id_modelo(metodo, ruta_calib, extra)


def _modelo_hibrido(metodo: str, forma: tuple[int, int], avisar) -> dict:
    from procesamiento import fase as fase_mod

    info = METODOS[metodo]
    calib, _ = _calibracion()
    fase = "Fy"  # como en los códigos de MATLAB (la línea base es vertical)
    ident = id_modelo(metodo)
    ruta = DIR_MODELOS / f"{metodo}_{ident}.npz"
    if ruta.exists():
        with np.load(ruta) as d:
            return {k: d[k] for k in d.files}
    superficies = _superficies_medidas(calib, fase) if info["datos"] == "medidos" else None
    if superficies is not None and len(superficies) < (5 if info["modelo"] == "rac" else info["grado"] + 2):
        raise ValueError(f"hacen falta más superficies planas medidas (hay {len(superficies)}): captura poses de plano")
    t0 = time.perf_counter()
    avisar(f"[INFO] Ajustando el modelo «{info['nombre']}» (una sola vez por calibración)…")
    alto, ancho = forma
    partes = {k: [] for k in ("mu", "sd", "mz", "sz", "vmin", "vmax", "cz", "cx", "cy", "ok")}
    paso = 64
    for f0 in range(0, alto, paso):
        filas = slice(f0, min(f0 + paso, alto))
        if superficies is None:
            vv, xx, yy, zz = _muestras_virtuales(calib, forma, fase, filas)
        else:
            xn, yn = _rayos(calib, filas, ancho)
            k = len(superficies)
            vv = np.full((len(xn), k), np.nan); xx, yy, zz = vv.copy(), vv.copy(), vv.copy()
            for i, s in enumerate(superficies):
                a, b, c = s["plano"]                       # z = a·x + b·y + c
                with np.errstate(all="ignore"):
                    esc = c / (1 - a * xn - b * yn)        # el rayo (xn, yn, 1)·esc corta el plano
                m = s["m"][filas].ravel()
                vv[m, i] = s["v"][filas].ravel()[m]
                xx[m, i], yy[m, i], zz[m, i] = (xn * esc)[m], (yn * esc)[m], esc[m]
        r = ajustar(vv, xx, yy, zz, info["modelo"], info.get("grado", 3))
        for kk in partes:
            partes[kk].append(r[kk])
    mod = {k: np.concatenate(v) for k, v in partes.items()}
    mod["modelo"] = np.array(info["modelo"])
    mod["forma"] = np.array(forma)
    if superficies is not None:
        mod["superficies"] = np.array([s["pose"] for s in superficies])
    DIR_MODELOS.mkdir(parents=True, exist_ok=True)
    fase_mod.guardar_npz_atomico(ruta, **mod)
    avisar(f"[INFO] Modelo listo en {time.perf_counter() - t0:.0f} s ({100 * mod['ok'].mean():.0f} % de los píxeles con modelo)"
           + (f"; superficies: {len(superficies)}" if superficies is not None else ""))
    return mod


# ------------------------------------------------------------------ reconstrucción de una pose
def ruta_resultado(cat: str, pose: str, metodo: str) -> Path:
    if metodo == PREDETERMINADO:
        return rutas.reconstruccion(cat, pose)
    return rutas.dir_reconstruccion(cat, pose) / "metodos" / f"{cat}_{pose}_{metodo}.npz"


def reconstruir(cat: str, pose: str, metodo: str, avisar=print) -> Path:
    """Reconstruye la pose con el método (si no está ya) y devuelve el .npz (X, Y, Z, Mask, E).
    Aplica los mismos filtros que la reconstrucción normal, para comparar en igualdad. Si otro
    pedido ya la está calculando (la tabla y los visores piden a la vez), espera a ese."""
    with _CANDADO:
        candado = _CANDADOS.setdefault(f"{cat}/{pose}/{metodo}", threading.Lock())
    with candado:
        return _reconstruir(cat, pose, metodo, avisar)


def _reconstruir(cat: str, pose: str, metodo: str, avisar=print) -> Path:
    from procesamiento import fase as fase_mod
    from procesamiento import mascara
    from procesamiento import reconstruccion_3d as r3d

    if metodo not in METODOS:
        raise ValueError(f"método desconocido: {metodo}")
    if metodo == PREDETERMINADO:
        ruta = rutas.reconstruccion(cat, pose)
        if not ruta.exists():
            raise FileNotFoundError(f"{cat}/{pose} no está reconstruida")
        return ruta
    info = METODOS[metodo]
    ruta_fase = rutas.fase_absoluta(cat, pose)
    calib, ruta_calib = _calibracion()
    destino = ruta_resultado(cat, pose, metodo)
    ident = _id_modelo(metodo, ruta_calib) if info["tipo"] == "estereo" else id_modelo(metodo)
    firma = (f"{ruta_fase.stat().st_mtime_ns}|{ident}|{cfg.SALTO_MAX_MM}|{cfg.Z_MIN_MM}|{cfg.Z_MAX_MM}|"
             f"{mascara.reflectancia_de(cat, pose)}|{cfg.FILTRO_VECINOS_SIGMA}|{mascara.firma(cat, pose)}")
    if destino.exists():
        try:
            with np.load(destino) as d:
                if str(d["firma"]) == firma:
                    return destino
        except (OSError, KeyError, ValueError):
            pass
    t0 = time.perf_counter()
    d = fase_mod.cargar_fases_pose(ruta_fase)
    if info["tipo"] == "estereo":
        x, y, z, m = r3d.triangular(d["up"], d["vp"], d["MaskX"], d["MaskY"], calib, info["fase"],
                                    peso_x=d.get("BX"), peso_y=d.get("BY"))
        modelo_id = ""
    else:
        mod = modelo_hibrido(metodo, d["vp"].shape, avisar)
        x, y, z, dentro = evaluar(mod, d["vp"])
        m = dentro & d["MaskY"]
        modelo_id = str(mod.get("superficies", ""))
    # mismos filtros que la reconstrucción normal
    m = r3d.filtrar_outliers_3d(z, m, cfg.SALTO_MAX_MM, cfg.Z_MIN_MM, cfg.Z_MAX_MM)
    m &= ~mascara.zonas_dificiles(d, rutas.dir_pose_ordenada(cat, pose), "Fy", rel_min=mascara.reflectancia_de(cat, pose))
    propia = mascara.cargar(cat, pose, m.shape)
    if propia is not None:
        m &= propia
    m = mascara.filtrar_vecinos(x, y, z, m, cfg.FILTRO_VECINOS_SIGMA)
    extra = {}
    if cat == "plano" and m.sum() > 100:
        e_map, erms, _ = r3d.plane_fitting(x, y, z, m, umbral_mm=cfg.PLANO_UMBRAL_MM)
        extra = {"E": e_map.astype(np.float32), "erms": np.array(erms)}
    destino.parent.mkdir(parents=True, exist_ok=True)
    fase_mod.guardar_npz_atomico(destino, X=x.astype(np.float32), Y=y.astype(np.float32), Z=z.astype(np.float32),
                                 Mask=m, firma=np.array(firma), modelo_id=np.array(modelo_id or "estereo"),
                                 segundos=np.array(time.perf_counter() - t0), **extra)
    return destino


def comparar(cat: str, pose: str, metodos: list[str] | None = None, avisar=print) -> dict:
    """Estadísticas de cada método para una pose: puntos, rango de Z, planitud (planos) y diferencia
    con el estéreo (Fy) en los píxeles que tienen los dos."""
    from procesamiento import reconstruccion_3d as r3d

    metodos = metodos or list(METODOS)
    base = r3d.cargar_reconstruccion_pose(reconstruir(cat, pose, PREDETERMINADO))
    mb = base["Mask"].astype(bool) & np.isfinite(base["Z"])
    salida = {}
    for met in metodos:
        try:
            r = r3d.cargar_reconstruccion_pose(reconstruir(cat, pose, met, avisar))
        except (ValueError, FileNotFoundError) as exc:
            salida[met] = {"error": str(exc)}
            continue
        m = r["Mask"].astype(bool) & np.isfinite(r["Z"])
        com = m & mb
        dz = (r["Z"] - base["Z"])[com]
        info = {"puntos": int(m.sum()), "z": [float(np.percentile(r["Z"][m], 1)), float(np.percentile(r["Z"][m], 99))] if m.any() else None,
                "dif_mediana_mm": float(np.median(np.abs(dz))) if dz.size else None,
                "dif_rms_mm": float(np.sqrt(np.mean(dz ** 2))) if dz.size else None,
                "dif_p95_mm": float(np.percentile(np.abs(dz), 95)) if dz.size else None,
                "segundos": float(r.get("segundos", 0.0))}
        if METODOS[met].get("datos") == "medidos":
            # esta pose fue una de las superficies con las que se ajustó el modelo: su resultado es optimista
            info["en_ajuste"] = f"{cat}/{pose}" in str(r.get("modelo_id", ""))
        if cat == "plano":
            if "E" in r and met != PREDETERMINADO:
                info["planitud_mm"] = float(r["erms"])
            elif "E" in r:
                e = r["E"][np.isfinite(r["E"])]
                info["planitud_mm"] = float(np.sqrt(np.mean((e - e.mean()) ** 2))) if e.size else None
        salida[met] = info
    return salida


def listar() -> list[dict]:
    return [{"id": k, "nombre": v["nombre"], "tipo": v["tipo"]} for k, v in METODOS.items()]
