"""Calibración Estéreo Tradicional (Cámara - Proyector) en Python.

Adapta los códigos de MATLAB:
- `PhaseRecoveryCodes/CleanPhase.m`, `PhaseRecoveryCodes/Adj2D_5thPol.m`, `HybridCalibCodes/PhaseAdj5.m`
- `StereoCalibCodes/createMaskCB.m`
- `StereoCalibCodes/RegWcordtoImage.m`
- `StereoCalibCodes/Traditional_StereoCalib.m`

La recuperación de fase (relativa y absoluta) está en `fase.py`; esta etapa usa sus resultados.

Flujo:
1. Lee las fases absolutas de cada pose del patrón (`resultados/fases/patron/pose_XX.npz`).
2. Detecta los centros de la grilla de círculos en la imagen blanca de textura.
3. Ajusta una superficie polinomial 2D de 5to orden a `u_p` y `v_p` sobre el tablero (`CleanPhase`),
   con rechazo iterativo de atípicos, para eliminar el ruido de la rejilla del DMD.
4. Evalúa las superficies en los centros: correspondencias cámara (u_c, v_c) <-> proyector (u_p, v_p).
5. Calibra cámara y proyector por separado y estima la línea base estéreo (`Estereo_TSC_0_2.npz`),
   además de la calibración conjunta (`Estereo_TSC_0_2_J.npz`) y un resumen `.json`.

Ejemplo de uso:
    python -m procesamiento.calibracion_estereo
    python -m procesamiento.calibracion_estereo --distancia 15 --cols 9 --rows 12
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from datos_sistema import configuracion as cfg
from procesamiento import fase
from datos_sistema import compat, rutas


# ==============================================================================
# 1. LIMPIEZA DE FASE POR AJUSTE POLINOMIAL (CleanPhase / PhaseAdj5)
# ==============================================================================


def _construir_matriz_polinomio_2d(
    x_norm: np.ndarray, y_norm: np.ndarray, grado: int = 5
) -> np.ndarray:
    """Construye la matriz de Vandermonde 2D de orden `grado` (21 términos para grado 5)."""
    columnas = []
    for n in range(grado, -1, -1):
        for l_exp in range(n, -1, -1):
            columnas.append((x_norm**l_exp) * (y_norm ** (n - l_exp)))
    return np.column_stack(columnas)


def ajustar_polinomio_2d(
    matriz: np.ndarray,
    mascara: np.ndarray,
    grado: int = 5,
    paso_submuestreo: int = 2,
    iteraciones: int = 3,
    k_sigma: float = 3.0,
) -> tuple[np.ndarray, tuple[float, float, float, float], np.ndarray]:
    """Ajusta un polinomio 2D sobre los píxeles de `mascara` con rechazo iterativo de atípicos.

    Retorna los coeficientes, los parámetros de normalización y la máscara de inliers usada.
    """
    sub_mask = np.zeros_like(mascara, dtype=bool)
    sub_mask[::paso_submuestreo, ::paso_submuestreo] = mascara[::paso_submuestreo, ::paso_submuestreo] > 0
    sub_mask &= np.isfinite(matriz)
    y_idx, x_idx = np.nonzero(sub_mask)
    x = x_idx.astype(np.float64)
    y = y_idx.astype(np.float64)
    z = matriz[y_idx, x_idx].astype(np.float64)

    ux, sx = float(np.mean(x)), float(np.std(x)) or 1.0
    uy, sy = float(np.mean(y)), float(np.std(y)) or 1.0
    a_mat = _construir_matriz_polinomio_2d((x - ux) / sx, (y - uy) / sy, grado)

    inliers = np.ones(len(z), dtype=bool)
    coef = np.zeros(a_mat.shape[1])
    for _ in range(max(iteraciones, 1)):
        coef, *_ = np.linalg.lstsq(a_mat[inliers], z[inliers], rcond=None)
        residuo = z - a_mat @ coef
        sigma = 1.4826 * np.median(np.abs(residuo[inliers] - np.median(residuo[inliers])))
        nuevos = np.abs(residuo) < max(k_sigma * sigma, 1e-6)
        if np.array_equal(nuevos, inliers):
            break
        inliers = nuevos

    mascara_inliers = np.zeros_like(sub_mask)
    mascara_inliers[y_idx[inliers], x_idx[inliers]] = True
    return coef, (ux, sx, uy, sy), mascara_inliers


def evaluar_polinomio_2d(
    coef: np.ndarray,
    norm_params: tuple[float, float, float, float],
    x: np.ndarray,
    y: np.ndarray,
    grado: int = 5,
) -> np.ndarray:
    """Evalúa el polinomio 2D en coordenadas arbitrarias `(x, y)`."""
    ux, sx, uy, sy = norm_params
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    a_mat = _construir_matriz_polinomio_2d(((x - ux) / sx).ravel(), ((y - uy) / sy).ravel(), grado)
    return (a_mat @ coef).reshape(x.shape)


def evaluar_polinomio_2d_malla(
    coef: np.ndarray, norm_params: tuple[float, float, float, float], ancho: int, alto: int, grado: int = 5
) -> np.ndarray:
    """Evalúa el polinomio 2D sobre toda la imagen `(alto, ancho)`."""
    x_grid, y_grid = np.meshgrid(np.arange(ancho, dtype=np.float64), np.arange(alto, dtype=np.float64))
    return evaluar_polinomio_2d(coef, norm_params, x_grid, y_grid, grado)


def create_mask_cb(shape_hw: tuple[int, int], puntos_cam: np.ndarray, offset: int = 10) -> np.ndarray:
    """Máscara poligonal alrededor de los puntos detectados del tablero (`createMaskCB.m`)."""
    alto, ancho = shape_hw
    hull = cv2.convexHull(puntos_cam.reshape(-1, 2).astype(np.float32))[:, 0, :]
    centro = np.mean(hull, axis=0, keepdims=True)
    vectores = hull - centro
    normas = np.linalg.norm(vectores, axis=1, keepdims=True)
    normas = np.where(normas > 1e-6, normas, 1.0)
    hull_expandido = (hull + (vectores / normas) * float(offset)).astype(np.int32)
    mascara = np.zeros((alto, ancho), dtype=np.uint8)
    cv2.fillConvexPoly(mascara, hull_expandido, 1)
    return mascara


def reg_wcord_to_image(
    puntos_cam: list[np.ndarray], world_points: np.ndarray, cam_size_hw: tuple[int, int]
) -> np.ndarray:
    """Registra coordenadas del mundo a la imagen con polinomio 2D de 5to orden (`RegWcordtoImage.m`)."""
    alto, ancho = cam_size_hw
    maps = np.zeros((alto, ancho, len(puntos_cam), 2), dtype=np.float32)
    for i, pts in enumerate(puntos_cam):
        u_cam, v_cam = pts[:, 0], pts[:, 1]
        norm_p = (float(u_cam.mean()), float(u_cam.std()), float(v_cam.mean()), float(v_cam.std()))
        a_mat = _construir_matriz_polinomio_2d(
            (u_cam - norm_p[0]) / norm_p[1], (v_cam - norm_p[2]) / norm_p[3]
        )
        for dim in range(2):
            coef, *_ = np.linalg.lstsq(a_mat, world_points[:, dim], rcond=None)
            maps[:, :, i, dim] = evaluar_polinomio_2d_malla(coef, norm_p, ancho, alto)
    return maps


# ==============================================================================
# 2. DETECCIÓN DEL PATRÓN DE CÍRCULOS
# ==============================================================================


def crear_detector_circulos() -> cv2.SimpleBlobDetector:
    """Detector de blobs robusto al patrón de píxeles del DMD."""
    params = cv2.SimpleBlobDetector_Params()
    params.filterByArea = True
    params.minArea = 80
    params.maxArea = 15000
    params.filterByCircularity = True
    params.minCircularity = 0.55
    params.filterByConvexity = True
    params.minConvexity = 0.65
    params.filterByInertia = True
    params.minInertiaRatio = 0.45
    return cv2.SimpleBlobDetector_create(params)


def detectar_puntos_tablero(
    imagen_textura: np.ndarray,
    pattern_size: tuple[int, int],
    pattern_type: str = "symmetric",
    circle_color: str = "white",
) -> np.ndarray:
    """Detecta los centros de la grilla de círculos (`detectCircleGridPoints`)."""
    suavizada = cv2.GaussianBlur(imagen_textura, (5, 5), 1.5)
    img_busqueda = 255 - suavizada if circle_color.lower() == "white" else suavizada

    flags = cv2.CALIB_CB_SYMMETRIC_GRID if pattern_type.lower() == "symmetric" else cv2.CALIB_CB_ASYMMETRIC_GRID
    detector = crear_detector_circulos()
    encontrado, esquinas = cv2.findCirclesGrid(img_busqueda, pattern_size, flags=flags, blobDetector=detector)
    if not encontrado or esquinas is None:
        encontrado, esquinas = cv2.findCirclesGrid(
            img_busqueda, pattern_size, flags=flags | cv2.CALIB_CB_CLUSTERING, blobDetector=detector
        )
    if not encontrado or esquinas is None:
        raise RuntimeError(
            f"No se pudo detectar el patrón de círculos {pattern_size} ({pattern_type}, {circle_color})"
        )
    return esquinas.reshape(-1, 2).astype(np.float64)


def distancia_xy(center_distance: float | tuple[float, float]) -> tuple[float, float]:
    """Normaliza la distancia entre círculos a un par (entre columnas, entre filas) en mm."""
    if np.ndim(center_distance) == 0:
        return float(center_distance), float(center_distance)
    dx, dy = center_distance
    return float(dx), float(dy)


def generar_puntos_mundo_circulos(
    pattern_size: tuple[int, int],
    center_distance: float | tuple[float, float],
    pattern_type: str = "symmetric",
) -> np.ndarray:
    """Coordenadas 3D (Z = 0) de los centros del tablero (`generateCircleGridPoints`).

    `center_distance` puede ser un número o un par (dx, dy): equivale a la corrección
    `worldPoints = (worldPoints/15).*[15.0588 14.9090]` de los scripts de MATLAB.
    El orden de los puntos coincide con el de `cv2.findCirclesGrid` (fila por fila).
    """
    cols, rows = pattern_size
    dx, dy = distancia_xy(center_distance)
    puntos = np.zeros((cols * rows, 3), dtype=np.float32)
    if pattern_type.lower() == "symmetric":
        rejilla = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2).astype(np.float64)
        puntos[:, 0] = rejilla[:, 0] * dx
        puntos[:, 1] = rejilla[:, 1] * dy
    else:
        idx = 0
        for r in range(rows):
            for c in range(cols):
                puntos[idx, 0] = (2 * c + (r % 2)) * dx
                puntos[idx, 1] = r * dy
                idx += 1
    return puntos


# ==============================================================================
# 3. CALIBRACIÓN ESTÉREO (Traditional_StereoCalib.m)
# ==============================================================================


def _mascara_ajuste(mascara_tablero: np.ndarray, calidad: np.ndarray, gamma_th: float, minimo: float = 0.3) -> np.ndarray:
    """Píxeles del tablero con modulación suficiente.

    Si la modulación es baja en casi todo el tablero (franjas horizontales desenfocadas), se baja el
    umbral hasta conservar al menos `minimo` del tablero; el ajuste polinomial con rechazo de
    atípicos compensa el ruido adicional.
    """
    tablero = mascara_tablero > 0
    umbral = gamma_th
    mascara = tablero & (calidad >= umbral)
    total = max(np.count_nonzero(tablero), 1)
    while np.count_nonzero(mascara) < minimo * total and umbral > 0.01:
        umbral *= 0.7
        mascara = tablero & (calidad >= umbral)
    return mascara


# ------------------------------------------------------------------------------
# Sesiones de captura: todas las poses de una calibración deben ser del mismo montaje
# ------------------------------------------------------------------------------


def sesiones_patron(dir_ordenadas: Path | None = None, horas: float | None = None) -> dict[str, dict]:
    """Proceso de captura de cada pose del patrón: {"pose_XX": {"fuente", "hora" (ISO), "sesion"}}.

    «Sesión» = número de orden de los procesos de captura que incluyeron el patrón (`sesiones.py`).
    Es el mismo agrupamiento que usa el resto del sistema: un proceso registrado, o sin registro,
    capturas seguidas (si el patrón sigue después de una pausa, es el mismo proceso). Los
    parámetros se aceptan por compatibilidad y se ignoran.
    """
    from datos_sistema import sesiones

    salida: dict[str, dict] = {}
    k = -1
    for proceso in sesiones.procesos():
        items = [it for it in proceso["items"] if it["cat"] == "patron" and it["poses"]]
        if not items:
            continue
        k += 1
        for it in items:
            for nombre in it["poses"]:
                salida[nombre] = {"fuente": f"capturas/{it['carpeta']}", "hora": it["hora"].isoformat(timespec="seconds"),
                                  "sesion": k}
    return salida


def seleccionar_poses(nombres: list[str], criterio: str | list[str], sesiones: dict[str, dict]) -> list[str]:
    """Poses del patrón que entran a la calibración (`cfg.CALIBRACION_POSES`)."""
    if isinstance(criterio, (list, tuple)):
        faltan = [n for n in criterio if n not in nombres]
        if faltan:
            print(f"  [AVISO] Poses pedidas sin datos (se ignoran): {', '.join(faltan)}")
        return [n for n in nombres if n in criterio]
    if criterio == "todas":
        return list(nombres)
    if criterio != "ultima_sesion":
        raise ValueError(f"CALIBRACION_POSES desconocido: {criterio!r} (usa 'ultima_sesion', 'todas' o una lista)")
    conocidas = [sesiones[n]["sesion"] for n in nombres if n in sesiones]
    if not conocidas:
        return list(nombres)  # sin manifiesto no se sabe: se usan todas
    ultima = max(conocidas)
    return [n for n in nombres if sesiones.get(n, {}).get("sesion") == ultima]


def _rms(residuo: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.sum(residuo ** 2, axis=-1))))


def _pose_estereo(obj, p_cam, p_proj, calib: dict, iteraciones: int = 15):
    """Pose del tablero que mejor explica A LA VEZ cámara y proyector con R, T fijos.

    Es el mismo criterio que minimiza `cv2.stereoCalibrate`, pero para una sola pose: Gauss-Newton
    sobre (rvec, tvec) de la cámara, partiendo de `solvePnP` en la cámara. Devuelve los residuos
    (n, 2) en la cámara y en el proyector.
    """
    ac, dc, ap, dp = calib["Ac"], calib["dist_cam"], calib["Ap"], calib["dist_proj"]
    r_rig, _ = cv2.Rodrigues(np.asarray(calib["R"], np.float64))
    t_rig = np.asarray(calib["T"], np.float64).reshape(3, 1)
    _, rv, tv = cv2.solvePnP(obj, p_cam, ac, dc, flags=cv2.SOLVEPNP_ITERATIVE)
    rv, tv = rv.astype(np.float64), tv.astype(np.float64)
    medido = np.vstack([p_cam.reshape(-1, 2), p_proj.reshape(-1, 2)])
    for _ in range(iteraciones):
        pc, jc = cv2.projectPoints(obj, rv, tv, ac, dc)
        rv_p, tv_p, dr3dr1, dr3dt1, _, _, dt3dr1, dt3dt1, _, _ = cv2.composeRT(rv, tv, r_rig, t_rig)
        pp, jp = cv2.projectPoints(obj, rv_p, tv_p, ap, dp)
        # Regla de la cadena: (rv_p, tv_p) dependen de (rv, tv)
        j_proj = np.hstack([jp[:, :3] @ dr3dr1 + jp[:, 3:6] @ dt3dr1, jp[:, :3] @ dr3dt1 + jp[:, 3:6] @ dt3dt1])
        jac = np.vstack([jc[:, :6], j_proj])
        res = medido - np.vstack([pc.reshape(-1, 2), pp.reshape(-1, 2)])
        paso = np.linalg.lstsq(jac, res.reshape(-1), rcond=None)[0]
        rv += paso[:3].reshape(3, 1)
        tv += paso[3:].reshape(3, 1)
        if np.linalg.norm(paso) < 1e-10:
            break
    pc, _ = cv2.projectPoints(obj, rv, tv, ac, dc)
    rv_p, tv_p = cv2.composeRT(rv, tv, r_rig, t_rig)[:2]
    pp, _ = cv2.projectPoints(obj, rv_p, tv_p, ap, dp)
    return p_cam.reshape(-1, 2) - pc.reshape(-1, 2), p_proj.reshape(-1, 2) - pp.reshape(-1, 2), tv


def errores_reproyeccion(calib: dict, pts_cam: list[np.ndarray], pts_proj: list[np.ndarray],
                         world_points: np.ndarray, residuos: bool = False) -> list[dict]:
    """Errores de reproyección de cada pose con una calibración dada (usada o no al calibrar).

    - `cam_px`, `proj_px`: cámara y proyector por separado (cada uno con su propia pose del
      tablero). Miden la calidad de los intrínsecos y de las correspondencias.
    - `estereo_cam_px`, `estereo_proj_px`, `estereo_px`: con una sola pose del tablero vista por
      los dos y la R, T de la calibración. Es lo que importa para reconstruir: si son mucho
      mayores que los independientes, esa pose no es coherente con la línea base (el montaje se
      movió, o la pose tiene malas correspondencias).
    - `delta_R_grados`, `delta_T_mm`: diferencia entre la R, T de la calibración y la que se
      deduce sólo de esa pose.
    Con `residuos=True` agrega los vectores de error (para graficarlos).
    """
    obj = world_points.astype(np.float64).reshape(-1, 1, 3)
    r_rig = np.asarray(calib["R"], np.float64)
    t_rig = np.asarray(calib["T"], np.float64).reshape(3)
    salida = []
    for pc, pp in zip(pts_cam, pts_proj):
        pc = pc.astype(np.float64).reshape(-1, 1, 2)
        pp = pp.astype(np.float64).reshape(-1, 1, 2)
        _, rvc, tvc = cv2.solvePnP(obj, pc, calib["Ac"], calib["dist_cam"])
        _, rvp, tvp = cv2.solvePnP(obj, pp, calib["Ap"], calib["dist_proj"])
        res_c = pc.reshape(-1, 2) - cv2.projectPoints(obj, rvc, tvc, calib["Ac"], calib["dist_cam"])[0].reshape(-1, 2)
        res_p = pp.reshape(-1, 2) - cv2.projectPoints(obj, rvp, tvp, calib["Ap"], calib["dist_proj"])[0].reshape(-1, 2)
        rc, _ = cv2.Rodrigues(rvc)
        rp, _ = cv2.Rodrigues(rvp)
        r_i = rp @ rc.T
        t_i = tvp.ravel() - r_i @ tvc.ravel()
        est_c, est_p, tv = _pose_estereo(obj, pc, pp, calib)
        info = {
            "cam_px": _rms(res_c), "proj_px": _rms(res_p),
            "estereo_cam_px": _rms(est_c), "estereo_proj_px": _rms(est_p),
            "estereo_px": _rms(np.vstack([est_c, est_p])),
            "delta_R_grados": float(np.degrees(np.linalg.norm(cv2.Rodrigues(r_i @ r_rig.T)[0]))),
            "delta_T_mm": float(np.linalg.norm(t_i - t_rig)),
            "T_pose_mm": t_i.tolist(),
            "distancia_mm": float(np.linalg.norm(tv)),
        }
        if residuos:
            info.update(puntos_cam=pc.reshape(-1, 2).round(2).tolist(), puntos_proj=pp.reshape(-1, 2).round(2).tolist(),
                        res_cam=est_c.round(3).tolist(), res_proj=est_p.round(3).tolist())
        salida.append(info)
    return salida


def correspondencias_pose(
    datos: dict, pattern_size: tuple[int, int], pattern_type: str, circle_color: str,
    gamma_th: float, gamma_th_y: float, offset_mask: int = 10, borde: int = cfg.BORDE_MASCARA,
    mapas_residuo: bool = False,
) -> dict:
    """Correspondencias cámara ↔ proyector de los círculos de una pose del patrón.

    Detecta los círculos en la textura, ajusta el polinomio a u_p y v_p sobre el tablero y lo evalúa
    en los centros. Devuelve {"cam", "proj" (ajustado), "crudo" (sin ajustar), "std" (u, v)} y, con
    `mapas_residuo`, los mapas de residuo del ajuste. Lanza RuntimeError si no detecta el tablero.
    """
    itex = datos["Itex"]
    alto, ancho = itex.shape
    puntos_cam = detectar_puntos_tablero(itex, pattern_size, pattern_type, circle_color)
    tablero = create_mask_cb(itex.shape, puntos_cam, offset=offset_mask)
    if borde > 0:
        tablero[:borde, :] = 0
        tablero[-borde:, :] = 0
        tablero[:, :borde] = 0
        tablero[:, -borde:] = 0
    proyectados = np.zeros_like(puntos_cam)
    crudos = np.zeros_like(puntos_cam)
    std, mapas = [], []
    for dim, (clave, calidad, umbral) in enumerate((("up", "qFx", gamma_th), ("vp", "qFy", gamma_th_y))):
        mapa = datos[clave]
        m_fit = _mascara_ajuste(tablero, datos[calidad], umbral)
        coef, norm_p, inliers = ajustar_polinomio_2d(mapa, m_fit)
        proyectados[:, dim] = evaluar_polinomio_2d(coef, norm_p, puntos_cam[:, 0], puntos_cam[:, 1])
        crudos[:, dim] = cv2.remap(
            mapa.astype(np.float32),
            puntos_cam[:, 0].astype(np.float32).reshape(-1, 1),
            puntos_cam[:, 1].astype(np.float32).reshape(-1, 1),
            cv2.INTER_LINEAR,
        ).ravel()
        # Residuo del ajuste solo en los inliers (no hace falta evaluar toda la imagen)
        yi, xi = np.nonzero(inliers)
        std.append(float(np.std(mapa[yi, xi] - evaluar_polinomio_2d(coef, norm_p, xi, yi))))
        if mapas_residuo:
            ajustado = evaluar_polinomio_2d_malla(coef, norm_p, ancho, alto)
            mapas.append(np.where(inliers, mapa - ajustado, np.nan).astype(np.float32))
    return {"cam": puntos_cam, "proj": proyectados, "crudo": crudos, "std": std, "mapas": mapas}


ARCHIVO_PUNTOS = "Estereo_TSC_0_2_puntos.npz"


def guardar_puntos(ruta: Path, poses: list[str], usadas: list[str], cam: list, proj: list,
                   world_points: np.ndarray) -> None:
    """Correspondencias de las poses de una calibración (las usadas y las detectadas no usadas).
    Viajan con la calibración: con ellas se calculan sus errores por pose en la interfaz."""
    np.savez(ruta, poses=np.array(poses), usadas=np.array(usadas), cam=np.stack(cam).astype(np.float32),
             proj=np.stack(proj).astype(np.float32), worldPoints=world_points)


def puntos_desde_fases(info: dict, dir_fases: Path = cfg.DIR_RESULTADOS / "fases") -> dict:
    """Recalcula las correspondencias de una calibración que no las guardó (anteriores a
    `ARCHIVO_PUNTOS`), desde las fases de sus poses. Las poses sin fase se omiten."""
    size = tuple(info.get("pattern_size") or (cfg.PATRON_COLUMNAS, cfg.PATRON_FILAS))
    distancia = info.get("center_distance_mm") or cfg.PATRON_DISTANCIA_MM
    world = generar_puntos_mundo_circulos(size, tuple(distancia) if np.ndim(distancia) else distancia, cfg.PATRON_TIPO)
    poses, cam, proj, faltan = [], [], [], []
    for nombre in info.get("poses", []):
        ruta = rutas.fase_absoluta("patron", nombre)  # en la carpeta de su proceso
        if not ruta.exists():
            faltan.append(nombre)
            continue
        try:
            c = correspondencias_pose(fase.cargar_fases_pose(ruta), size, cfg.PATRON_TIPO, cfg.PATRON_COLOR_CIRCULOS,
                                      cfg.GAMMA_TH, cfg.GAMMA_TH_Y)
        except RuntimeError:
            faltan.append(nombre)
            continue
        poses.append(nombre)
        cam.append(c["cam"])
        proj.append(c["proj"])
    return {"poses": poses, "usadas": list(poses), "cam": cam, "proj": proj, "worldPoints": world, "faltan": faltan}


def ejecutar_calibracion_estereo(
    dir_fases: Path = cfg.DIR_RESULTADOS / "fases",
    dir_salida: Path = cfg.DIR_CALIBRACION,
    pattern_size: tuple[int, int] = (cfg.PATRON_COLUMNAS, cfg.PATRON_FILAS),
    center_distance: float = cfg.PATRON_DISTANCIA_MM,
    pattern_type: str = cfg.PATRON_TIPO,
    circle_color: str = cfg.PATRON_COLOR_CIRCULOS,
    gamma_th: float = cfg.GAMMA_TH,
    offset_mask: int = 10,
    proj_size_wh: tuple[int, int] = (cfg.PROYECTOR_ANCHO, cfg.PROYECTOR_ALTO),
    borde: int = cfg.BORDE_MASCARA,
    gamma_th_y: float = cfg.GAMMA_TH_Y,
    guardar_mapas: bool = False,
    dir_diagnostico: Path = cfg.DIR_RESULTADOS / "calibracion",
    poses_calibracion: str | list[str] = cfg.CALIBRACION_POSES,
    forzar: bool = False,
    seleccion: dict | None = None,
) -> dict:
    """Ejecuta el flujo de `Traditional_StereoCalib.m` sobre las fases del patrón de calibración.

    Se detectan los círculos en todas las poses, pero sólo calibran las que elige
    `poses_calibracion` (por defecto la última sesión de captura). Los errores de reproyección se
    calculan para todas, así se ve si las poses de otra sesión son coherentes con el montaje actual.
    """
    from datos_sistema import avance

    avance.paso("Cargando las fases del patrón")
    nombres, poses = fase.cargar_fases_categoria(dir_fases, "patron")
    sesiones = sesiones_patron()
    elegidas = set(seleccionar_poses(nombres, poses_calibracion, sesiones))
    n_sesiones = len({v["sesion"] for v in sesiones.values()})
    if n_sesiones > 1:
        for k in sorted({v["sesion"] for v in sesiones.values()}):
            miembros = [n for n in nombres if sesiones.get(n, {}).get("sesion") == k]
            if miembros:
                print(f"  Sesión {k + 1}: {sesiones[miembros[0]]['hora'][:16].replace('T', ' ')} · "
                      f"{', '.join(miembros)}{'  <- se usa' if set(miembros) <= elegidas else ''}")
    alto_cam, ancho_cam = poses[0]["Itex"].shape
    cam_size_wh = (ancho_cam, alto_cam)
    world_points = generar_puntos_mundo_circulos(pattern_size, center_distance, pattern_type)
    dir_salida.mkdir(parents=True, exist_ok=True)
    dir_diagnostico.mkdir(parents=True, exist_ok=True)

    print(f"=== Calibración Estéreo Tradicional ({len(poses)} poses, cámara {ancho_cam}x{alto_cam}) ===")

    usados: list[str] = []
    pts_cam: list[np.ndarray] = []
    pts_proj: list[np.ndarray] = []
    pts_proj_raw: list[np.ndarray] = []
    residuos: list[tuple[np.ndarray, np.ndarray]] = []
    texturas: list[np.ndarray] = []

    detectados: list[str] = []
    det_cam: list[np.ndarray] = []
    det_proj: list[np.ndarray] = []
    for nombre, datos in zip(nombres, poses):
        itex = datos["Itex"]
        try:
            # Mapas de residuo completos solo para la figura de diagnóstico de la primera pose
            c = correspondencias_pose(datos, pattern_size, pattern_type, circle_color, gamma_th, gamma_th_y,
                                      offset_mask, borde, mapas_residuo=not residuos)
        except RuntimeError as exc:
            print(f"  [{nombre}] [AVISO] {exc}; se descarta la pose.")
            continue
        puntos_cam, proyectados, crudos, std_pose, res_pose = c["cam"], c["proj"], c["crudo"], c["std"], c["mapas"]

        detectados.append(nombre)
        det_cam.append(puntos_cam)
        det_proj.append(proyectados)
        if nombre not in elegidas:
            print(f"  [{nombre}] detectada, pero no entra a la calibración (otra sesión o fuera de CALIBRACION_POSES)")
            continue
        usados.append(nombre)
        pts_cam.append(puntos_cam)
        pts_proj.append(proyectados)
        pts_proj_raw.append(crudos)
        if res_pose:
            residuos.append((res_pose[0], res_pose[1]))
        texturas.append(itex)
        print(
            f"  [{nombre}] {len(puntos_cam)} círculos | "
            f"u_p=[{proyectados[:, 0].min():.1f}, {proyectados[:, 0].max():.1f}] "
            f"v_p=[{proyectados[:, 1].min():.1f}, {proyectados[:, 1].max():.1f}] px | "
            f"residuo ajuste u={std_pose[0]:.3f} v={std_pose[1]:.3f} px"
        )

    if len(usados) < 3:
        raise RuntimeError(f"Solo {len(usados)} poses válidas en la selección ({poses_calibracion!r}); "
                           f"se necesitan al menos 3 para calibrar.")

    obj_pts = [world_points.astype(np.float32) for _ in usados]
    cam_pts = [p.reshape(-1, 1, 2).astype(np.float32) for p in pts_cam]
    proj_pts = [p.reshape(-1, 1, 2).astype(np.float32) for p in pts_proj]

    # En MATLAB: NRcoef = 2, SkewFlag = 0, EstimateTangentialDistortion = true -> (k1, k2, p1, p2)
    flags_indep = cv2.CALIB_FIX_K3
    avance.paso("Calibrando la cámara y el proyector")
    rms_cam, k_cam, dist_cam, rvecs_cam, tvecs_cam = cv2.calibrateCamera(
        obj_pts, cam_pts, cam_size_wh, None, None, flags=flags_indep
    )
    rms_proj, k_proj, dist_proj, rvecs_proj, tvecs_proj = cv2.calibrateCamera(
        obj_pts, proj_pts, proj_size_wh, None, None, flags=flags_indep
    )
    err_cam = _errores_por_pose(obj_pts, cam_pts, k_cam, dist_cam, rvecs_cam, tvecs_cam)
    err_proj = _errores_por_pose(obj_pts, proj_pts, k_proj, dist_proj, rvecs_proj, tvecs_proj)

    # 1) Línea base con intrínsecos fijos (estimateStereoBaseline en MATLAB)
    avance.paso("Calibración estéreo (cámara + proyector)")
    rms_st, k_cam_1, dist_cam_1, k_proj_1, dist_proj_1, r_mat, t_vec, e_mat, f_mat = cv2.stereoCalibrate(
        obj_pts, cam_pts, proj_pts, k_cam.copy(), dist_cam.copy(), k_proj.copy(), dist_proj.copy(),
        cam_size_wh, flags=cv2.CALIB_FIX_INTRINSIC,
    )
    # 2) Calibración conjunta (_J en Traditional_StereoCalib.m)
    rms_st_j, k_cam_j, dist_cam_j, k_proj_j, dist_proj_j, r_mat_j, t_vec_j, e_mat_j, f_mat_j = cv2.stereoCalibrate(
        obj_pts, cam_pts, proj_pts, k_cam.copy(), dist_cam.copy(), k_proj.copy(), dist_proj.copy(),
        cam_size_wh, flags=cv2.CALIB_USE_INTRINSIC_GUESS | cv2.CALIB_FIX_K3,
    )

    print("\n================ RESULTADOS DE CALIBRACIÓN ESTÉREO ================")
    print(f"  Poses usadas: {', '.join(usados)}")
    print(f"  Error RMS Cámara (independiente)   : {rms_cam:.4f} px")
    print(f"  Error RMS Proyector (independiente): {rms_proj:.4f} px")
    print(f"  Error RMS Estéreo (fijo, TSC_0_2)  : {rms_st:.4f} px")
    print(f"  Error RMS Estéreo (conjunto, _J)   : {rms_st_j:.4f} px")
    calib_tsc = _parametros(k_cam_1, dist_cam_1, k_proj_1, dist_proj_1, r_mat, t_vec, e_mat, f_mat)
    avance.paso("Errores de reproyección por pose")
    por_pose = dict(zip(detectados, errores_reproyeccion(calib_tsc, det_cam, det_proj, world_points)))
    mediana = float(np.median([por_pose[n]["estereo_px"] for n in usados]))
    print("  Por pose (px)      cámara  proyector  estéreo   ΔR      ΔT")
    for nombre in detectados:
        e = por_pose[nombre]
        marca = "" if nombre in usados else "  (no usada)"
        if e["estereo_px"] > max(3 * mediana, 2.0):
            marca += "  <-- no coherente con la línea base"
        print(f"    {nombre}:        {e['cam_px']:6.3f}  {e['proj_px']:8.3f}  {e['estereo_px']:7.3f}  "
              f"{e['delta_R_grados']:5.2f}°  {e['delta_T_mm']:5.1f} mm{marca}")
    if rms_st > 3 * max(rms_cam, rms_proj, 0.3):
        print(f"  [AVISO] El error estéreo ({rms_st:.2f} px) es muy superior a los independientes: las poses "
              f"no son coherentes entre sí. Casi siempre es porque la cámara o el proyector se movieron entre "
              f"capturas: calibra solo con poses de la misma sesión (CALIBRACION_POSES). MANUAL.md §16.6")
    print("\nMatriz Intrínseca Cámara (Ac):\n", k_cam_1)
    print("Distorsión Cámara [k1, k2, p1, p2, k3]:", dist_cam_1.ravel())
    print("\nMatriz Intrínseca Proyector (Ap):\n", k_proj_1)
    print("Distorsión Proyector [k1, k2, p1, p2, k3]:", dist_proj_1.ravel())
    print("\nRotación Proyector respecto a Cámara (R):\n", r_mat)
    print("Traslación Proyector respecto a Cámara (T en mm):", t_vec.ravel())
    print(f"Línea base: {np.linalg.norm(t_vec):.2f} mm")

    # Zona del proyector cubierta por los círculos: fuera de ella el modelo (sobre todo la
    # distorsión) se extrapola y el error 3D crece. Conviene que cubra casi todo el proyector.
    todos_proj = np.concatenate(pts_proj)
    cobertura_up = np.array([todos_proj[:, 0].min(), todos_proj[:, 0].max()])
    cobertura_vp = np.array([todos_proj[:, 1].min(), todos_proj[:, 1].max()])
    frac_u = (cobertura_up[1] - cobertura_up[0]) / proj_size_wh[0]
    frac_v = (cobertura_vp[1] - cobertura_vp[0]) / proj_size_wh[1]
    print(f"Cobertura del proyector: u_p=[{cobertura_up[0]:.0f}, {cobertura_up[1]:.0f}] ({100 * frac_u:.0f}% "
          f"del ancho) | v_p=[{cobertura_vp[0]:.0f}, {cobertura_vp[1]:.0f}] ({100 * frac_v:.0f}% del alto)")
    if min(frac_u, frac_v) < 0.7:
        print("  [AVISO] Las poses del tablero no cubren bien el proyector. Agrega poses con el tablero "
              "en los bordes del campo (y más inclinadas) para que el modelo no se extrapole.")
    print("===================================================================\n")

    comunes = dict(
        rms_cam=rms_cam, rms_proj=rms_proj, cam_size_wh=np.array(cam_size_wh),
        proj_size_wh=np.array(proj_size_wh), fringe_pitch=cfg.PERIODO,
        cobertura_up=cobertura_up, cobertura_vp=cobertura_vp,
    )
    avance.paso("Control de calidad y guardado")
    # Todo se escribe primero en el historial; se pone en uso solo si pasa el control de calidad
    historial = dir_salida / "historial" / datetime.now().strftime("%Y%m%d_%H%M%S")
    historial.mkdir(parents=True, exist_ok=True)
    ruta_tsc = historial / "Estereo_TSC_0_2.npz"
    np.savez(
        ruta_tsc, **calib_tsc,
        rms_stereo=rms_st, rvecs_cam=np.array(rvecs_cam), tvecs_cam=np.array(tvecs_cam), **comunes,
    )
    ruta_tsc_j = historial / "Estereo_TSC_0_2_J.npz"
    np.savez(
        ruta_tsc_j, **_parametros(k_cam_j, dist_cam_j, k_proj_j, dist_proj_j, r_mat_j, t_vec_j, e_mat_j, f_mat_j),
        rms_stereo=rms_st_j, **comunes,
    )

    # Datos de correspondencias (equivalente a Estereo_PhasesData.mat). M: (n_puntos, 2, P, 2)
    m_corr = np.stack([np.stack(pts_cam, axis=-1), np.stack(pts_proj, axis=-1)], axis=-1)
    m_raw = np.stack([np.stack(pts_cam, axis=-1), np.stack(pts_proj_raw, axis=-1)], axis=-1)
    # Todas las poses detectadas (también las no usadas), para los errores de la interfaz
    m_todas = np.stack([np.stack(det_cam, axis=-1), np.stack(det_proj, axis=-1)], axis=-1)
    # `Maps` (RegWcordtoImage.m) solo lo usan las calibraciones híbridas de MATLAB: es opcional
    # porque son 2 mapas de imagen completa por pose (~10 MB por pose).
    extra_mapas = (
        {"Maps": reg_wcord_to_image(pts_cam, world_points[:, :2], (alto_cam, ancho_cam))}
        if guardar_mapas else {}
    )
    np.savez_compressed(
        dir_diagnostico / "patron_PhasesData.npz",
        poses=np.array(usados), M=m_corr, M_raw=m_raw, worldPoints=world_points,
        poses_detectadas=np.array(detectados), M_detectadas=m_todas,
        Images=np.stack(texturas, axis=-1), **extra_mapas,
    )

    resumen = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "poses": usados,
        "pattern_size": list(pattern_size),
        "center_distance_mm": list(distancia_xy(center_distance)),
        "fringe_pitch": cfg.PERIODO,
        "cam_size_wh": list(cam_size_wh),
        "proj_size_wh": list(proj_size_wh),
        "rms_cam_px": float(rms_cam),
        "rms_proj_px": float(rms_proj),
        "rms_stereo_indep_px": float(rms_st),
        "rms_stereo_joint_px": float(rms_st_j),
        "poses_criterio": poses_calibracion,
        # Si se calibró con una selección manual de poses, se recuerda para volver a ella al activarla
        **({"seleccion": seleccion} if seleccion else {}),
        "error_por_pose_cam_px": dict(zip(usados, map(float, err_cam))),
        "error_por_pose_proj_px": dict(zip(usados, map(float, err_proj))),
        "errores_por_pose": {n: {**por_pose[n], "usada": n in usados, **sesiones.get(n, {})} for n in detectados},
        "Ac": k_cam_1.tolist(),
        "dist_cam": dist_cam_1.ravel().tolist(),
        "Ap": k_proj_1.tolist(),
        "dist_proj": dist_proj_1.ravel().tolist(),
        "R": r_mat.tolist(),
        "T_mm": t_vec.ravel().tolist(),
        "linea_base_mm": float(np.linalg.norm(t_vec)),
        "cobertura_up_px": cobertura_up.tolist(),
        "cobertura_vp_px": cobertura_vp.tolist(),
    }
    motivos = control_calidad(resumen, proj_size_wh)
    hay_anterior = (dir_salida / "Estereo_TSC_0_2.npz").exists()
    en_uso = not motivos or forzar or not hay_anterior
    resumen["control_calidad"] = {"aprobada": not motivos, "motivos": motivos, "forzada": bool(motivos and en_uso)}
    ruta_json = historial / "Estereo_TSC_0_2.json"
    ruta_json.write_text(json.dumps(resumen, indent=2), encoding="utf-8")
    guardar_puntos(historial / ARCHIVO_PUNTOS, detectados, usados, det_cam, det_proj, world_points)
    avance.paso("Figura de diagnóstico")
    _guardar_figura_diagnostico(dir_diagnostico, texturas[0], pts_cam[0], residuos[0], usados[0])

    print(f"[OK] Calibración guardada en {historial} (diagnósticos en {dir_diagnostico})")
    if motivos:
        print("[AVISO] La calibración NO pasa el control de calidad:")
        for m in motivos:
            print(f"        - {m}")
    if en_uso:
        activar_calibracion(historial.name, dir_salida)
        if motivos and not hay_anterior:
            print("[AVISO] Se pone en uso igual porque no había ninguna otra calibración.")
        elif motivos:
            print("[AVISO] Se puso en uso porque se pidió forzarla.")
        print("     Recuerda hacer commit de calibraciones/ para que viaje con el código.")
    else:
        print(f"[AVISO] Calibración RECHAZADA: sigue en uso la anterior. Para usarla igual: pestaña "
              f"Calibración de la interfaz, o calibracion_estereo.py --activar {historial.name}. MANUAL.md §16.6")
    resumen["en_uso"] = en_uso
    resumen["historial"] = historial.name
    return resumen


def control_calidad(resumen: dict, proj_size_wh: tuple[int, int] = (cfg.PROYECTOR_ANCHO, cfg.PROYECTOR_ALTO)) -> list[str]:
    """Motivos por los que una calibración no debería usarse (lista vacía = aprobada)."""
    motivos = []
    rms_st = resumen.get("rms_stereo_indep_px") or float("inf")
    indep = max(resumen.get("rms_cam_px") or 0, resumen.get("rms_proj_px") or 0, 0.3)
    if rms_st > cfg.CALIB_RMS_ESTEREO_MAX_PX:
        motivos.append(f"RMS estéreo {rms_st:.2f} px > {cfg.CALIB_RMS_ESTEREO_MAX_PX} px")
    if rms_st > cfg.CALIB_RAZON_ESTEREO_MAX * indep:
        motivos.append(f"RMS estéreo {rms_st:.2f} px es {rms_st / indep:.0f}× el de cámara/proyector: poses "
                       f"de montajes distintos o con malas correspondencias")
    n = len(resumen.get("poses", []))
    if n < cfg.CALIB_POSES_MIN:
        motivos.append(f"solo {n} poses del patrón (mínimo {cfg.CALIB_POSES_MIN})")
    for clave, total, eje in (("cobertura_up_px", proj_size_wh[0], "ancho"), ("cobertura_vp_px", proj_size_wh[1], "alto")):
        lo, hi = resumen.get(clave) or (0, 0)
        if (hi - lo) / total < cfg.CALIB_COBERTURA_MIN:
            motivos.append(f"las poses cubren solo el {100 * (hi - lo) / total:.0f}% del {eje} del proyector "
                           f"(mínimo {100 * cfg.CALIB_COBERTURA_MIN:.0f}%)")
    return motivos


# ------------------------------------------------------------------------------
# Historial: elegir qué calibración usar
# ------------------------------------------------------------------------------

ARCHIVOS_CALIBRACION = ("Estereo_TSC_0_2.npz", "Estereo_TSC_0_2_J.npz", "Estereo_TSC_0_2.json",
                        "Estereo_TSC_0_2_puntos.npz")


def listar_calibraciones(dir_calibracion: Path = cfg.DIR_CALIBRACION) -> list[dict]:
    """Calibraciones de `historial/` (la más reciente primero), marcando la que está en uso.

    La calibración en uso es la de `dir_calibracion/`; cada recalibración deja además una copia en
    `historial/<fecha>/`, así que la vigente se reconoce comparando el contenido de los archivos.
    """
    activa = dir_calibracion / "Estereo_TSC_0_2.npz"
    # El .npz puede repetirse (misma calibración calculada dos veces); el .json lleva la fecha
    contenido_activo = activa.read_bytes() if activa.exists() else None
    json_activo = (dir_calibracion / "Estereo_TSC_0_2.json").read_bytes() if (dir_calibracion / "Estereo_TSC_0_2.json").exists() else None
    salida = []
    carpetas = sorted((dir_calibracion / "historial").glob("*/"), reverse=True)
    for carpeta in carpetas:
        if not (carpeta / "Estereo_TSC_0_2.npz").exists():
            continue
        try:
            info = json.loads((carpeta / "Estereo_TSC_0_2.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            info = {}
        salida.append({
            "id": carpeta.name,
            "fecha": info.get("fecha"),
            "poses": info.get("poses", []),
            "criterio": info.get("poses_criterio", "todas"),
            "rms_cam_px": info.get("rms_cam_px"),
            "rms_proj_px": info.get("rms_proj_px"),
            "rms_stereo_px": info.get("rms_stereo_indep_px"),
            "linea_base_mm": info.get("linea_base_mm"),
            "poses_info": _origen_poses(info),
            "seleccion": info.get("seleccion"),
            "control": info.get("control_calidad") or {"aprobada": not control_calidad(info), "motivos": control_calidad(info)},
            "activa": contenido_activo is not None and (carpeta / "Estereo_TSC_0_2.npz").read_bytes() == contenido_activo
                      and (json_activo is None or not (carpeta / "Estereo_TSC_0_2.json").exists()
                           or (carpeta / "Estereo_TSC_0_2.json").read_bytes() == json_activo),
        })
    return salida


def exportar_parametros(ident: str | None = None, dir_calibracion: Path = cfg.DIR_CALIBRACION,
                        variante: str | None = None) -> dict:
    """Parámetros de cámara y proyector de una calibración, en el formato `SL_TSC_*.json`:

    - `K` = [[fx, 0, cx], [0, fy, cy], [0, 0, 1]] en píxeles;
    - `radial_distortion` = [k1, k2] (más k3 si no es 0) y `tangential_distortion` = [p1, p2];
    - `image_size` = [alto, ancho];
    - `projector.R`, `projector.t`: X_p = R·X_c + t, en mm (de la cámara al proyector).

    `ident` = carpeta de `historial/`; None = la calibración en uso. `variante` = "independiente"
    (Estereo_TSC_0_2) o "conjunta" (_J); None = la de `cfg.CALIBRACION`.
    """
    if ident:
        if not compat.nombre_seguro(ident):
            raise ValueError(f"calibración inválida: {ident!r}")
        carpeta = dir_calibracion / "historial" / ident
    else:
        carpeta = dir_calibracion
    variante = variante or cfg.CALIBRACION
    ruta = carpeta / ("Estereo_TSC_0_2_J.npz" if variante == "conjunta" else "Estereo_TSC_0_2.npz")
    if not ruta.exists():
        raise FileNotFoundError(f"No existe la calibración {ident or 'en uso'} ({ruta.name}) en {dir_calibracion}")

    def optica(K, dist, tamano_wh) -> dict:
        d = np.zeros(5)
        dist = np.asarray(dist, float).ravel()
        d[:min(len(dist), 5)] = dist[:5]
        k1, k2, p1, p2, k3 = d
        return {"K": np.asarray(K, float).tolist(),
                "radial_distortion": [k1, k2] + ([k3] if k3 != 0 else []),
                "tangential_distortion": [p1, p2],
                "image_size": [int(tamano_wh[1]), int(tamano_wh[0])]}

    with np.load(ruta) as z:
        return {
            "camera": optica(z["Ac"], z["dist_cam"], z["cam_size_wh"]),
            "projector": {**optica(z["Ap"], z["dist_proj"], z["proj_size_wh"]),
                          "R": np.asarray(z["R"], float).tolist(),
                          "t": np.asarray(z["T"], float).ravel().tolist()},
        }


def _origen_poses(info: dict) -> list[dict]:
    """De qué captura sale cada pose del patrón de una calibración (hora y si sigue organizada)."""
    detalle = info.get("errores_por_pose", {})
    salida = []
    for nombre in info.get("poses", []):
        d = detalle.get(nombre, {})
        salida.append({"pose": nombre, "hora": d.get("hora"), "fuente": d.get("fuente"),
                       "estereo_px": d.get("estereo_px"),
                       "existe": rutas.dir_pose_ordenada("patron", nombre).is_dir()})
    return salida


def usar_configuracion_de(calib: dict) -> str:
    """Pone en uso la configuración de la que salió una calibración: su selección manual de poses,
    si se calibró así, o el proceso de captura de sus poses del patrón. Devuelve una descripción."""
    from datos_sistema import sesiones

    if calib.get("seleccion"):
        sesiones.fijar_seleccion(calib["seleccion"])
        return "la selección manual con la que se calibró"
    proceso = sesiones.proceso_de_poses("patron", calib["poses"])
    carpeta = next((p.get("carpeta") for p in sesiones.procesos() if p["id"] == proceso), None)
    if carpeta and rutas.leer_proceso_json(carpeta).get("importado"):
        # Un proceso importado puede tener fecha en medio de otros: solo él, no «desde él en adelante»
        sesiones.fijar_solo_proceso(carpeta)
        return f"solo el proceso importado {carpeta}"
    sesiones.fijar_configuracion(proceso)
    return f"la del proceso {proceso}" if proceso else "la última"


def activar_calibracion(ident: str, dir_calibracion: Path = cfg.DIR_CALIBRACION) -> dict:
    """Pone en uso la calibración `historial/<ident>/` (copia sus 3 archivos a `dir_calibracion/`).

    Si la calibración en uso no está en el historial (p. ej. copiada a mano), antes se respalda en
    `historial/<fecha>_respaldo/` para no perderla. La reconstrucción detecta el cambio (su caché
    depende de la fecha del archivo) y recalcula las poses en la siguiente ejecución.
    """
    origen = dir_calibracion / "historial" / ident
    if not compat.nombre_seguro(ident) or not (origen / "Estereo_TSC_0_2.npz").exists():
        raise FileNotFoundError(f"No existe la calibración '{ident}' en {dir_calibracion / 'historial'}")
    lista = listar_calibraciones(dir_calibracion)
    if (dir_calibracion / "Estereo_TSC_0_2.npz").exists() and not any(c["activa"] for c in lista):
        respaldo = dir_calibracion / "historial" / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_respaldo")
        respaldo.mkdir(parents=True, exist_ok=True)
        for nombre in ARCHIVOS_CALIBRACION:
            if (dir_calibracion / nombre).exists():
                shutil.copy2(dir_calibracion / nombre, respaldo / nombre)
        print(f"[OK] La calibración en uso no estaba en el historial: respaldada en {respaldo}")
    for nombre in ARCHIVOS_CALIBRACION:
        if (origen / nombre).exists():
            # copyfile (no copy2): fecha nueva, para que la caché de la reconstrucción la vea cambiar
            tmp = dir_calibracion / (nombre + ".tmp")
            shutil.copyfile(origen / nombre, tmp)
            compat.reemplazar(tmp, dir_calibracion / nombre)
        else:  # p. ej. los puntos de una calibración anterior: no deben quedar los de otra
            (dir_calibracion / nombre).unlink(missing_ok=True)
    print(f"[OK] Calibración en uso: {ident}")
    return next(c for c in listar_calibraciones(dir_calibracion) if c["id"] == ident)


def _parametros(k_cam, dist_cam, k_proj, dist_proj, r_mat, t_vec, e_mat, f_mat) -> dict:
    dc, dp = dist_cam.ravel(), dist_proj.ravel()
    return dict(
        Ac=k_cam, Ap=k_proj, dist_cam=dc, dist_proj=dp,
        Kr1=np.array([dc[0], dc[1], dc[4]]), Kt1=np.array([dc[2], dc[3]]),
        Kr2=np.array([dp[0], dp[1], dp[4]]), Kt2=np.array([dp[2], dp[3]]),
        R=r_mat, T=t_vec.reshape(3, 1), E=e_mat, F=f_mat,
    )


def _errores_por_pose(obj_pts, img_pts, k_mat, dist, rvecs, tvecs) -> list[float]:
    errores = []
    for obj, img, rv, tv in zip(obj_pts, img_pts, rvecs, tvecs):
        proy, _ = cv2.projectPoints(obj, rv, tv, k_mat, dist)
        errores.append(float(np.sqrt(np.mean(np.sum((proy - img) ** 2, axis=2)))))
    return errores


def normalizar_mapa_color(
    mapa: np.ndarray,
    mask: np.ndarray | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
    colormap: int = cv2.COLORMAP_JET,
) -> np.ndarray:
    """Convierte un arreglo 2D flotante en una imagen BGR con mapa de color de OpenCV."""
    valido = np.isfinite(mapa)
    if mask is not None:
        valido &= mask > 0
    if not np.any(valido):
        return np.zeros((*mapa.shape, 3), dtype=np.uint8)
    vmin = float(np.nanmin(mapa[valido])) if vmin is None else vmin
    vmax = float(np.nanmax(mapa[valido])) if vmax is None else vmax
    escala = (vmax - vmin) if abs(vmax - vmin) > 1e-9 else 1.0
    norm_u8 = np.clip((np.where(valido, mapa, vmin) - vmin) / escala * 255.0, 0, 255).astype(np.uint8)
    color_bgr = cv2.applyColorMap(norm_u8, colormap)
    color_bgr[~valido] = 0
    return color_bgr


def _guardar_figura_diagnostico(
    directorio: Path, itex: np.ndarray, puntos: np.ndarray, residuos: tuple[np.ndarray, np.ndarray], nombre: str
) -> None:
    """Panel: círculos detectados y residuos del ajuste polinomial de u_p y v_p."""
    img = cv2.cvtColor(itex, cv2.COLOR_GRAY2BGR)
    for idx, (ux, uy) in enumerate(puntos):
        cv2.circle(img, (int(round(ux)), int(round(uy))), 8 if idx == 0 else 4,
                   (0, 255, 0) if idx == 0 else (0, 0, 255), -1)
    paneles = [img]
    for res, titulo in zip(residuos, ("residuo u_p", "residuo v_p")):
        lim = max(3 * float(np.nanstd(res)), 1e-3) if np.any(np.isfinite(res)) else 1.0
        col = normalizar_mapa_color(res, vmin=-lim, vmax=lim, colormap=cv2.COLORMAP_TURBO)
        cv2.putText(col, f"{titulo} [+-{lim:.2f} px]", (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
        paneles.append(col)
    cv2.putText(img, f"{nombre}: circulos detectados", (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 255), 2)
    panel = np.hstack(paneles)
    cv2.imwrite(str(directorio / f"diagnostico_calibracion_{nombre}.png"),
                cv2.resize(panel, (0, 0), fx=0.4, fy=0.4, interpolation=cv2.INTER_AREA))


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibración Estéreo Tradicional Cámara-Proyector.")
    parser.add_argument("--fases", type=Path, default=cfg.DIR_RESULTADOS / "fases",
                        help="Carpeta con las fases absolutas (salida de la etapa fase_absoluta)")
    parser.add_argument("--salida", type=Path, default=cfg.DIR_CALIBRACION,
                        help="Carpeta donde se guarda la calibración")
    parser.add_argument("--cols", type=int, default=cfg.PATRON_COLUMNAS, help="Columnas de círculos")
    parser.add_argument("--rows", type=int, default=cfg.PATRON_FILAS, help="Filas de círculos")
    parser.add_argument("--distancia", type=float, nargs="+", default=None,
                        help="Distancia entre centros en mm: un valor, o dos (entre columnas, entre filas)")
    parser.add_argument("--mapas", action="store_true",
                        help="Guarda también los mapas RegWcordtoImage (para las calibraciones híbridas)")
    parser.add_argument("--poses", nargs="+", default=None,
                        help="Poses a usar: 'ultima_sesion' (defecto), 'todas' o nombres como pose_08 pose_09 ...")
    parser.add_argument("--forzar", action="store_true",
                        help="Pone en uso la calibración nueva aunque no pase el control de calidad")
    parser.add_argument("--listar", action="store_true", help="Lista las calibraciones del historial y sale")
    parser.add_argument("--activar", metavar="FECHA",
                        help="Pone en uso la calibración historial/FECHA (p. ej. 20261124_122125) y sale")
    parser.add_argument("--tipo-patron", default=cfg.PATRON_TIPO, choices=["symmetric", "asymmetric"])
    args = parser.parse_args()
    if args.listar:
        for c in listar_calibraciones(args.salida):
            print(f"  {'*' if c['activa'] else ' '} {c['id']}  {len(c['poses']):2d} poses  "
                  f"estéreo {c['rms_stereo_px'] or float('nan'):6.3f} px  ({c['criterio']})")
        print("  (* = en uso; para cambiarla: --activar FECHA)")
        return
    if args.activar:
        elegida = activar_calibracion(args.activar, args.salida)
        print(f"[OK] Configuración vigente: {usar_configuracion_de(elegida)}")
        return

    ejecutar_calibracion_estereo(
        dir_fases=args.fases,
        dir_salida=args.salida,
        pattern_size=(args.cols, args.rows),
        center_distance=(cfg.PATRON_DISTANCIA_MM if args.distancia is None
                         else args.distancia[0] if len(args.distancia) == 1 else tuple(args.distancia[:2])),
        pattern_type=args.tipo_patron,
        guardar_mapas=args.mapas,
        forzar=args.forzar,
        poses_calibracion=(cfg.CALIBRACION_POSES if not args.poses
                           else args.poses[0] if len(args.poses) == 1 and not args.poses[0].startswith("pose_")
                           else args.poses),
    )


if __name__ == "__main__":
    main()
