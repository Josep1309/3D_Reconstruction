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
    python calibracion_estereo.py
    python calibracion_estereo.py --distancia 15 --cols 9 --rows 12
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import configuracion as cfg
import fase


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


def sesiones_patron(dir_ordenadas: Path = cfg.DIR_ORDENADAS,
                    horas: float = cfg.HORAS_ENTRE_SESIONES) -> dict[str, dict]:
    """Agrupa las poses del patrón en sesiones según la hora de su captura original.

    La hora sale del nombre de la carpeta de `capturas/` (AAAAMMDD_HHMMSS) que registra el
    manifiesto. Dos capturas separadas por más de `horas` son sesiones distintas: entre ellas el
    montaje pudo moverse. Devuelve {"pose_XX": {"fuente", "hora" (ISO), "sesion" (0, 1, ...)}}.
    """
    try:
        manifiesto = json.loads((dir_ordenadas / "manifiesto.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    horas_pose: dict[str, datetime] = {}
    fuentes: dict[str, str] = {}
    for entrada in manifiesto.get("poses", []):
        if entrada.get("categoria") != "patron":
            continue
        nombre = f"pose_{int(entrada['pose']):02d}"
        fuente = str(entrada.get("fuente", ""))
        fuentes[nombre] = fuente
        for parte in reversed(Path(fuente).parts):
            try:
                horas_pose[nombre] = datetime.strptime(parte[:15], "%Y%m%d_%H%M%S")
                break
            except ValueError:
                continue
    salida: dict[str, dict] = {}
    sesion, anterior = -1, None
    for nombre, hora in sorted(horas_pose.items(), key=lambda kv: kv[1]):
        if anterior is None or (hora - anterior).total_seconds() > horas * 3600:
            sesion += 1
        anterior = hora
        salida[nombre] = {"fuente": fuentes[nombre], "hora": hora.isoformat(timespec="seconds"), "sesion": sesion}
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
) -> dict:
    """Ejecuta el flujo de `Traditional_StereoCalib.m` sobre las fases del patrón de calibración.

    Se detectan los círculos en todas las poses, pero sólo calibran las que elige
    `poses_calibracion` (por defecto la última sesión de captura). Los errores de reproyección se
    calculan para todas, así se ve si las poses de otra sesión son coherentes con el montaje actual.
    """
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
            puntos_cam = detectar_puntos_tablero(itex, pattern_size, pattern_type, circle_color)
        except RuntimeError as exc:
            print(f"  [{nombre}] [AVISO] {exc}; se descarta la pose.")
            continue

        tablero = create_mask_cb(itex.shape, puntos_cam, offset=offset_mask)
        if borde > 0:
            tablero[:borde, :] = 0
            tablero[-borde:, :] = 0
            tablero[:, :borde] = 0
            tablero[:, -borde:] = 0

        proyectados = np.zeros_like(puntos_cam)
        crudos = np.zeros_like(puntos_cam)
        res_pose = []
        std_pose = []
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
            residuo = mapa[yi, xi] - evaluar_polinomio_2d(coef, norm_p, xi, yi)
            std_pose.append(float(np.std(residuo)))
            if not residuos:  # mapa completo solo para la figura de diagnóstico de la primera pose
                ajustado = evaluar_polinomio_2d_malla(coef, norm_p, ancho_cam, alto_cam)
                res_pose.append(np.where(inliers, mapa - ajustado, np.nan).astype(np.float32))

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
    rms_cam, k_cam, dist_cam, rvecs_cam, tvecs_cam = cv2.calibrateCamera(
        obj_pts, cam_pts, cam_size_wh, None, None, flags=flags_indep
    )
    rms_proj, k_proj, dist_proj, rvecs_proj, tvecs_proj = cv2.calibrateCamera(
        obj_pts, proj_pts, proj_size_wh, None, None, flags=flags_indep
    )
    err_cam = _errores_por_pose(obj_pts, cam_pts, k_cam, dist_cam, rvecs_cam, tvecs_cam)
    err_proj = _errores_por_pose(obj_pts, proj_pts, k_proj, dist_proj, rvecs_proj, tvecs_proj)

    # 1) Línea base con intrínsecos fijos (estimateStereoBaseline en MATLAB)
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
    ruta_tsc = dir_salida / "Estereo_TSC_0_2.npz"
    np.savez(
        ruta_tsc, **calib_tsc,
        rms_stereo=rms_st, rvecs_cam=np.array(rvecs_cam), tvecs_cam=np.array(tvecs_cam), **comunes,
    )
    ruta_tsc_j = dir_salida / "Estereo_TSC_0_2_J.npz"
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
    ruta_json = dir_salida / "Estereo_TSC_0_2.json"
    ruta_json.write_text(json.dumps(resumen, indent=2), encoding="utf-8")

    _guardar_figura_diagnostico(dir_diagnostico, texturas[0], pts_cam[0], residuos[0], usados[0])

    # Copia en el historial: recalibrar no hace perder la calibración anterior
    historial = dir_salida / "historial" / datetime.now().strftime("%Y%m%d_%H%M%S")
    historial.mkdir(parents=True, exist_ok=True)
    for ruta in (ruta_tsc, ruta_tsc_j, ruta_json):
        shutil.copy2(ruta, historial / ruta.name)
    print(f"[OK] Calibración guardada en:\n  - {ruta_tsc}\n  - {ruta_tsc_j}\n  - {ruta_json}\n"
          f"  (copia en {historial}; diagnósticos en {dir_diagnostico})")
    print("     Para volver a una calibración anterior, copia sus 3 archivos desde historial/ a "
          f"'{dir_salida}'. Recuerda hacer commit de calibraciones/ para que viaje con el código.")
    return resumen


# ------------------------------------------------------------------------------
# Historial: elegir qué calibración usar
# ------------------------------------------------------------------------------

ARCHIVOS_CALIBRACION = ("Estereo_TSC_0_2.npz", "Estereo_TSC_0_2_J.npz", "Estereo_TSC_0_2.json")


def listar_calibraciones(dir_calibracion: Path = cfg.DIR_CALIBRACION) -> list[dict]:
    """Calibraciones de `historial/` (la más reciente primero), marcando la que está en uso.

    La calibración en uso es la de `dir_calibracion/`; cada recalibración deja además una copia en
    `historial/<fecha>/`, así que la vigente se reconoce comparando el contenido de los archivos.
    """
    activa = dir_calibracion / "Estereo_TSC_0_2.npz"
    contenido_activo = activa.read_bytes() if activa.exists() else None
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
            "activa": contenido_activo is not None and (carpeta / "Estereo_TSC_0_2.npz").read_bytes() == contenido_activo,
        })
    return salida


def activar_calibracion(ident: str, dir_calibracion: Path = cfg.DIR_CALIBRACION) -> dict:
    """Pone en uso la calibración `historial/<ident>/` (copia sus 3 archivos a `dir_calibracion/`).

    Si la calibración en uso no está en el historial (p. ej. copiada a mano), antes se respalda en
    `historial/<fecha>_respaldo/` para no perderla. La reconstrucción detecta el cambio (su caché
    depende de la fecha del archivo) y recalcula las poses en la siguiente ejecución.
    """
    origen = dir_calibracion / "historial" / ident
    if "/" in ident or ident.startswith(".") or not (origen / "Estereo_TSC_0_2.npz").exists():
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
            tmp.replace(dir_calibracion / nombre)
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
        activar_calibracion(args.activar, args.salida)
        return

    ejecutar_calibracion_estereo(
        dir_fases=args.fases,
        dir_salida=args.salida,
        pattern_size=(args.cols, args.rows),
        center_distance=(cfg.PATRON_DISTANCIA_MM if args.distancia is None
                         else args.distancia[0] if len(args.distancia) == 1 else tuple(args.distancia[:2])),
        pattern_type=args.tipo_patron,
        guardar_mapas=args.mapas,
        poses_calibracion=(cfg.CALIBRACION_POSES if not args.poses
                           else args.poses[0] if len(args.poses) == 1 and not args.poses[0].startswith("pose_")
                           else args.poses),
    )


if __name__ == "__main__":
    main()
