"""Extracción de fase de objetos/planos y Reconstrucción 3D Estéreo en Python.

Adapta los códigos de MATLAB:
- `PhaseRecoveryCodes/RecoveryPhases_objects.m`
- `StereoCalibCodes/StereoReconstruction.m`
- `StereoCalibCodes/comp_distortion_oulu.m`
- `3DReconstructionCodes/Plane_fitting.m`
- `3DReconstructionCodes/XYZtoPC.m`
- `3DReconstructionCodes/R3D_ComplexShape.m`
- `3DReconstructionCodes/R3D_mirrorPositions.m`

Flujo:
1. Lee las secuencias organizadas en `capturas_ordenadas/objeto` y/o `capturas_ordenadas/plano`.
2. Recupera las fases desenvueltas `Fx` (de `V/`) y `Fy` (de `H/`), mapas de calidad
   `qFx`, `qFy`, imagen de textura `Itex` y máscara válida `MaskC`, guardándolos en
   `<categoria>_PhasesData.npz` (`RecoveryPhases_objects.m`).
3. Carga los parámetros estéreo (`Estereo_TSC_0_2.npz`) y ejecuta la triangulación
   estéreo compensando distorsiones radiales y tangenciales con el modelo iterativo
   de Oulu (`comp_distortion_oulu.m` + `StereoReconstruction.m`).
4. Si se procesa `plano`, ajusta un plano por mínimos cuadrados a cada pose
   (`Plane_fitting.m`) y reporta el error RMS de planicidad en milímetros.
5. Exporta las nubes de puntos 3D con textura a archivos `.ply` binarios (`XYZtoPC.m`
   + `pcwrite`) y genera figuras de visualización 3D y mapas de profundidad/error.

Ejemplo de uso:
    python reconstruccion_3d.py --calibracion capturas_ordenadas/patron/Estereo_TSC_0_2.npz
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from calibracion_estereo import (
    _normalizar_mapa_color,
    buscar_imagen_patron,
    unwrap_phase_gray_code,
)


# ==============================================================================
# 1. COMPENSACIÓN DE DISTORSIÓN Y TRIANGULACIÓN ESTÉREO (StereoReconstruction.m)
# ==============================================================================


def comp_distortion_oulu(xd: np.ndarray, k: np.ndarray) -> np.ndarray:
    """Compensa la distorsión radial y tangencial iterativamente (`comp_distortion_oulu.m`).

    Parámetros:
    - xd: Coordenadas normalizadas distorsionadas de dimensión (2, N).
    - k: Vector de 5 coeficientes de distorsión `[k1, k2, p1, p2, k3]`.

    Retorna:
    - x: Coordenadas normalizadas corregidas de dimensión (2, N).
    """
    k_flat = np.asarray(k, dtype=np.float64).ravel()
    if k_flat.size < 5:
        k_pad = np.zeros(5, dtype=np.float64)
        k_pad[: k_flat.size] = k_flat
        k_flat = k_pad

    if np.allclose(k_flat, 0.0):
        return xd.copy()

    k1, k2, p1, p2, k3 = k_flat[0], k_flat[1], k_flat[2], k_flat[3], k_flat[4]
    x = xd.copy()

    for _ in range(18):
        r_2 = np.sum(x * x, axis=0)
        k_radial = 1.0 + k1 * r_2 + k2 * (r_2**2) + k3 * (r_2**3)
        delta_x = np.vstack(
            [
                2.0 * p1 * x[0, :] * x[1, :] + p2 * (r_2 + 2.0 * (x[0, :] ** 2)),
                p1 * (r_2 + 2.0 * (x[1, :] ** 2)) + 2.0 * p2 * x[0, :] * x[1, :],
            ]
        )
        x = (xd - delta_x) / k_radial[np.newaxis, :]

    return x


def stereo_reconstruction(
    fx: np.ndarray,
    fy: np.ndarray,
    mask: np.ndarray,
    fringe_pitch: int,
    stereo_params: dict[str, np.ndarray],
    fd: str = "Fy",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Triangulación 3D cámara-proyector (réplica exacta de `StereoReconstruction.m`).

    Parámetros:
    - fx, fy: Mapas de fase desenvuelta (H, W) o (H, W, P).
    - mask: Máscara booleana/binaria de píxeles válidos con igual forma que `fx`.
    - fringe_pitch: Paso de las franjas proyectadas en píxeles (ej. 18).
    - stereo_params: Diccionario o archivo `.npz` con `Ac`, `Ap`, `R`, `T`, `dist_cam`, `dist_proj`.
    - fd: Dirección de fase usada para triangular (`'Fy'` o `'Fx'`).

    Retorna:
    - x_cm, y_cm, z_cm: Coordenadas 3D en el sistema de la cámara (en mm), con `NaN` fuera de `mask`.
    - t_elapsed: Tiempo de cómputo en segundos.
    """
    es_2d = fx.ndim == 2
    if es_2d:
        fx = fx[:, :, np.newaxis]
        fy = fy[:, :, np.newaxis]
        mask = mask[:, :, np.newaxis]

    ac = np.asarray(stereo_params["Ac"], dtype=np.float64)
    ap = np.asarray(stereo_params["Ap"], dtype=np.float64)
    r_mat = np.asarray(stereo_params["R"], dtype=np.float64)
    t_vec = np.asarray(stereo_params["T"], dtype=np.float64).reshape(3, 1)
    w_mat = np.hstack([r_mat, t_vec])  # Matriz 3x4 [R, T]

    if "dist_cam" in stereo_params:
        k_cam = np.asarray(stereo_params["dist_cam"], dtype=np.float64).ravel()
    else:
        kr1 = np.asarray(stereo_params["Kr1"], dtype=np.float64).ravel()
        kt1 = np.asarray(stereo_params["Kt1"], dtype=np.float64).ravel()
        k_cam = np.array([kr1[0], kr1[1], kt1[0], kt1[1], kr1[2]])

    if "dist_proj" in stereo_params:
        k_proj = np.asarray(stereo_params["dist_proj"], dtype=np.float64).ravel()
    else:
        kr2 = np.asarray(stereo_params["Kr2"], dtype=np.float64).ravel()
        kt2 = np.asarray(stereo_params["Kt2"], dtype=np.float64).ravel()
        k_proj = np.array([kr2[0], kr2[1], kt2[0], kt2[1], kr2[2]])

    alto, ancho, n_poses = fx.shape
    mask_bool = (mask > 0) & np.isfinite(fx) & np.isfinite(fy)
    mask_union = np.any(mask_bool, axis=2)

    # Coordenadas de píxel en cámara (0-based, consistentes con la calibración OpenCV)
    uc_grid, vc_grid = np.meshgrid(
        np.arange(ancho, dtype=np.float64), np.arange(alto, dtype=np.float64)
    )
    uc_valid = uc_grid[mask_union]
    vc_valid = vc_grid[mask_union]

    homog_cam = np.vstack([uc_valid, vc_valid, np.ones_like(uc_valid)])
    rc = np.linalg.solve(ac, homog_cam)

    t0 = time.perf_counter()
    rc_undist = comp_distortion_oulu(rc[:2, :], k_cam)

    ud_img = np.zeros((alto, ancho), dtype=np.float64)
    vd_img = np.zeros((alto, ancho), dtype=np.float64)
    ud_img[mask_union] = rc_undist[0, :]
    vd_img[mask_union] = rc_undist[1, :]

    ud_vol = np.repeat(ud_img[:, :, np.newaxis], n_poses, axis=2)
    vd_vol = np.repeat(vd_img[:, :, np.newaxis], n_poses, axis=2)

    ud_pts = ud_vol[mask_bool]
    vd_pts = vd_vol[mask_bool]
    rui = np.vstack([ud_pts, vd_pts, np.ones_like(ud_pts)])

    # Conversión de fase desenvuelta a coordenadas del proyector
    fx_pts = fx[mask_bool]
    fy_pts = fy[mask_bool]
    up = float(fringe_pitch) * fx_pts / (2.0 * np.pi)
    vp = float(fringe_pitch) * fy_pts / (2.0 * np.pi)

    homog_proj = np.vstack([up, vp, np.ones_like(up)])
    x_proj = np.linalg.solve(ap, homog_proj)
    x_proj_undist = comp_distortion_oulu(x_proj[:2, :], k_proj)

    # Selección de coeficientes de triangulación según la dirección de fase ('Fx' o 'Fy')
    if fd.lower() == "fx":
        a_coef = w_mat[0, 0] - w_mat[2, 0] * x_proj_undist[0, :]
        b_coef = w_mat[0, 1] - w_mat[2, 1] * x_proj_undist[0, :]
        c_coef = w_mat[0, 2] - w_mat[2, 2] * x_proj_undist[0, :]
        d_coef = -w_mat[0, 3] + w_mat[2, 3] * x_proj_undist[0, :]
    elif fd.lower() == "fy":
        a_coef = w_mat[1, 0] - w_mat[2, 0] * x_proj_undist[1, :]
        b_coef = w_mat[1, 1] - w_mat[2, 1] * x_proj_undist[1, :]
        c_coef = w_mat[1, 2] - w_mat[2, 2] * x_proj_undist[1, :]
        d_coef = -w_mat[1, 3] + w_mat[2, 3] * x_proj_undist[1, :]
    else:
        raise ValueError("El parámetro fd debe ser 'Fx' o 'Fy'")

    zc = d_coef / (a_coef * rui[0, :] + b_coef * rui[1, :] + c_coef)
    xc = zc * rui[0, :]
    yc = zc * rui[1, :]
    t_elapsed = time.perf_counter() - t0

    x_cm = np.full(fx.shape, np.nan, dtype=np.float64)
    y_cm = np.full(fx.shape, np.nan, dtype=np.float64)
    z_cm = np.full(fx.shape, np.nan, dtype=np.float64)

    x_cm[mask_bool] = xc
    y_cm[mask_bool] = yc
    z_cm[mask_bool] = zc

    if es_2d:
        return x_cm[:, :, 0], y_cm[:, :, 0], z_cm[:, :, 0], t_elapsed
    return x_cm, y_cm, z_cm, t_elapsed


# ==============================================================================
# 2. EXTRACCIÓN DE FASES DE OBJETOS / PLANOS (RecoveryPhases_objects.m)
# ==============================================================================


def recuperar_fases_directorio(
    directorio_categoria: Path,
    fringe_pitch: int = 18,
    n_step: int = 18,
    n_bits: int = 7,
    gamma_th: float = 0.15,
    umbral_intensidad: int = 25,
) -> dict[str, np.ndarray]:
    """Extrae y guarda las fases `Fx`, `Fy`, calidad `qFx`, `qFy` y máscara `MaskC` (`RecoveryPhases_objects.m`)."""
    carpetas_poses = sorted(
        p
        for p in directorio_categoria.iterdir()
        if p.is_dir() and p.name.startswith("pose_")
    )
    if not carpetas_poses:
        raise FileNotFoundError(
            f"No se encontraron carpetas 'pose_XX' en {directorio_categoria}."
        )

    n_poses = len(carpetas_poses)
    nitext = n_step + n_bits

    # Leer primera imagen para conocer dimensiones
    primera_tex = buscar_imagen_patron(
        carpetas_poses[0] / "H" / f"P{fringe_pitch}_F", nitext
    )
    img0 = cv2.imread(str(primera_tex), cv2.IMREAD_UNCHANGED)
    if img0 is None:
        raise OSError(f"No se pudo leer {primera_tex}")
    alto, ancho = img0.shape[:2]

    fx = np.zeros((alto, ancho, n_poses), dtype=np.float64)
    fy = np.zeros((alto, ancho, n_poses), dtype=np.float64)
    qfx = np.zeros((alto, ancho, n_poses), dtype=np.float64)
    qfy = np.zeros((alto, ancho, n_poses), dtype=np.float64)
    images = np.zeros((alto, ancho, n_poses), dtype=np.uint8)
    mask_c = np.zeros((alto, ancho, n_poses), dtype=np.uint8)

    for i, dir_pose in enumerate(carpetas_poses):
        prefijo_h = dir_pose / "H" / f"P{fringe_pitch}_F"
        prefijo_v = dir_pose / "V" / f"P{fringe_pitch}_F"

        ruta_tex = buscar_imagen_patron(prefijo_h, nitext)
        itex = cv2.imread(str(ruta_tex), cv2.IMREAD_UNCHANGED)
        if itex.ndim == 3:
            itex = itex[:, :, 0]
        images[:, :, i] = itex

        fx_aux, mask_h, _, _, _, gmx = unwrap_phase_gray_code(
            prefijo_v, fringe_pitch, n_step, n_bits, med_filt_size=5, gamma_th=gamma_th
        )
        fy_aux, mask_v, _, _, _, gmy = unwrap_phase_gray_code(
            prefijo_h, fringe_pitch, n_step, n_bits, med_filt_size=5, gamma_th=gamma_th
        )

        fx[:, :, i] = fx_aux
        fy[:, :, i] = fy_aux
        qfx[:, :, i] = gmx
        qfy[:, :, i] = gmy

        # Máscara automática igual a RecoveryPhases_objects.m (línea 70):
        # MaskC(:,:,i) = mask_v .* mask_h .* (Itex > 25)
        m_pose = (mask_v > 0) & (mask_h > 0) & (itex > umbral_intensidad)
        # Eliminar bordes de 15 px para evitar artefactos del filtro de mediana
        m_pose[:15, :] = False
        m_pose[-15:, :] = False
        m_pose[:, :15] = False
        m_pose[:, -15:] = False
        mask_c[:, :, i] = m_pose.astype(np.uint8)

        print(
            f"  [{dir_pose.name}] Píxeles válidos en máscara: "
            f"{int(np.count_nonzero(m_pose))} ({100.0 * np.mean(m_pose):.1f}%)"
        )

    nombre_cat = directorio_categoria.name
    ruta_phases = directorio_categoria / f"{nombre_cat}_PhasesData.npz"
    np.savez_compressed(
        ruta_phases,
        Fx=fx,
        Fy=fy,
        qFx=qfx,
        qFy=qfy,
        images=images,
        MaskC=mask_c,
    )
    print(f"[OK] Fases guardadas en: '{ruta_phases}'")

    return {
        "Fx": fx,
        "Fy": fy,
        "qFx": qfx,
        "qFy": qfy,
        "images": images,
        "MaskC": mask_c,
    }


# ==============================================================================
# 3. AJUSTE DE PLANOS Y EXPORTACIÓN A NUBE DE PUNTOS PLY (Plane_fitting.m / XYZtoPC.m)
# ==============================================================================


def plane_fitting(
    xx: np.ndarray, yy: np.ndarray, zz: np.ndarray, mask: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Ajusta un plano Z = A*X + B*Y + C por mínimos cuadrados a cada pose (`Plane_fitting.m`).

    Retorna:
    - e: Mapa de distancia perpendicular al plano ideal en mm `(H, W, P)`.
    - erms: Vector con el error RMS de planicidad por pose en mm `(P,)`.
    - ze: Plano Z evaluado `(H, W, P)`.
    - tts: Coeficientes `[A, B, C]` de cada plano `(P, 3)`.
    """
    alto, ancho, n_poses = xx.shape
    e_map = np.full_like(xx, np.nan, dtype=np.float64)
    ze_map = np.full_like(xx, np.nan, dtype=np.float64)
    tts = np.zeros((n_poses, 3), dtype=np.float64)
    erms = np.zeros(n_poses, dtype=np.float64)

    for i in range(n_poses):
        x = xx[:, :, i]
        y = yy[:, :, i]
        z = zz[:, :, i]

        valido = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
        if mask is not None:
            valido &= mask[:, :, i] > 0

        # Recorte de valores atípicos extremos (percentil 1..99 en Z) para ajuste robusto
        if np.count_nonzero(valido) > 100:
            z_vals = z[valido]
            z_med = np.median(z_vals)
            mad = np.median(np.abs(z_vals - z_med))
            if mad > 1e-6:
                valido &= np.abs(z - z_med) < 4.0 * 1.4826 * mad

        a_mat = np.column_stack([x[valido], y[valido], np.ones(np.count_nonzero(valido))])
        b_vec = z[valido]
        tt, _, _, _ = np.linalg.lstsq(a_mat, b_vec, rcond=None)
        tts[i, :] = tt

        ze = tt[0] * x + tt[1] * y + tt[2]
        ze_map[:, :, i] = ze

        # Distancia perpendicular punto-plano: (A*x + B*y - z + C) / sqrt(A^2 + B^2 + 1)
        dist_perp = (tt[0] * x + tt[1] * y - z + tt[2]) / np.sqrt(
            tt[0] ** 2 + tt[1] ** 2 + 1.0
        )
        e_pose = np.where(valido, dist_perp, np.nan)
        e_map[:, :, i] = e_pose

        err_vals = e_pose[valido]
        erms[i] = float(np.sqrt(np.mean((err_vals - np.mean(err_vals)) ** 2)))

    return e_map, erms, ze_map, tts


def _filtrar_outliers_3d(
    x: np.ndarray, y: np.ndarray, z: np.ndarray, mask: np.ndarray
) -> np.ndarray:
    """Filtra saltos abruptos locales en Z (equivalente rápido en rejilla 2D a `pcdenoise`)."""
    mask_out = (mask > 0) & np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    if np.count_nonzero(mask_out) == 0:
        return mask_out

    z_clean = np.where(mask_out, z, np.nanmedian(z[mask_out])).astype(np.float32)
    z_med_local = cv2.medianBlur(z_clean, 5).astype(np.float64)
    # Descartar píxeles cuyo salto local respecto a su vecindad 5x5 supere 5 mm
    salto_local = np.abs(z - z_med_local) < 5.0
    # Además acotar al rango físico razonable frente a la cámara (100 mm a 1500 mm)
    rango_z = (z > 100.0) & (z < 1500.0)
    return mask_out & salto_local & rango_z


def escribir_ply_binario(
    ruta_ply: Path, puntos_xyz: np.ndarray, colores_rgb: np.ndarray
) -> None:
    """Escribe una nube de puntos con color en formato PLY binario little-endian (`pcwrite`)."""
    n_pts = puntos_xyz.shape[0]
    encabezado = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {n_pts}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property uchar red\n"
        "property uchar green\n"
        "property uchar blue\n"
        "end_header\n"
    ).encode("ascii")

    dtype_vertice = np.dtype(
        [
            ("x", "<f4"),
            ("y", "<f4"),
            ("z", "<f4"),
            ("r", "u1"),
            ("g", "u1"),
            ("b", "u1"),
        ]
    )
    datos = np.empty(n_pts, dtype=dtype_vertice)
    datos["x"] = puntos_xyz[:, 0].astype(np.float32)
    datos["y"] = puntos_xyz[:, 1].astype(np.float32)
    datos["z"] = puntos_xyz[:, 2].astype(np.float32)
    datos["r"] = colores_rgb[:, 0].astype(np.uint8)
    datos["g"] = colores_rgb[:, 1].astype(np.uint8)
    datos["b"] = colores_rgb[:, 2].astype(np.uint8)

    with ruta_ply.open("wb") as f:
        f.write(encabezado)
        f.write(datos.tobytes())


def xyz_to_pc_and_save_ply(
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    images: np.ndarray,
    mask: np.ndarray,
    directorio_salida: Path,
    prefijo_ply: str,
) -> tuple[list[Path], np.ndarray]:
    """Convierte las matrices `(Xs, Ys, Zs)` en nubes de puntos filtradas y guarda `.ply` (`XYZtoPC.m`)."""
    n_poses = xs.shape[2]
    new_mask = np.zeros_like(mask, dtype=np.uint8)
    rutas_ply: list[Path] = []

    for i in range(n_poses):
        indi = _filtrar_outliers_3d(
            xs[:, :, i], ys[:, :, i], zs[:, :, i], mask[:, :, i]
        )
        new_mask[:, :, i] = indi.astype(np.uint8)

        pts = np.column_stack(
            [xs[:, :, i][indi], ys[:, :, i][indi], zs[:, :, i][indi]]
        )
        intensidad = images[:, :, i][indi].astype(np.uint8)
        colores = np.column_stack([intensidad, intensidad, intensidad])

        ruta_ply = directorio_salida / f"{prefijo_ply}_Stereo_pose_{i:02d}.ply"
        escribir_ply_binario(ruta_ply, pts, colores)
        rutas_ply.append(ruta_ply)
        print(
            f"  [PLY] '{ruta_ply.name}' guardado con {len(pts):,} puntos 3D."
        )

    return rutas_ply, new_mask


def _guardar_visualizacion_reconstruccion(
    directorio_salida: Path,
    nombre_cat: str,
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    images: np.ndarray,
    mask: np.ndarray,
    e_map: np.ndarray | None = None,
    erms: np.ndarray | None = None,
) -> None:
    """Genera un panel visual con imagen de textura, mapa de profundidad Z y mapa de error usando OpenCV."""
    indi = (mask[:, :, 0] > 0) & np.isfinite(zs[:, :, 0])
    tex_bgr = cv2.cvtColor(images[:, :, 0], cv2.COLOR_GRAY2BGR)
    cv2.putText(
        tex_bgr,
        f"{nombre_cat} (pose_00): Textura",
        (25, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (0, 255, 255),
        2,
    )

    if np.any(indi):
        vmin_z, vmax_z = np.nanpercentile(zs[:, :, 0][indi], [2, 98])
    else:
        vmin_z, vmax_z = 300.0, 900.0

    z_bgr = _normalizar_mapa_color(
        zs[:, :, 0],
        indi.astype(np.uint8),
        vmin=float(vmin_z),
        vmax=float(vmax_z),
        colormap=cv2.COLORMAP_VIRIDIS,
    )
    cv2.putText(
        z_bgr,
        f"Profundidad Z [{vmin_z:.1f}, {vmax_z:.1f}] mm",
        (25, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (255, 255, 255),
        2,
    )

    if e_map is not None and erms is not None:
        err_bgr = _normalizar_mapa_color(
            e_map[:, :, 0],
            indi.astype(np.uint8),
            vmin=-0.6,
            vmax=0.6,
            colormap=cv2.COLORMAP_TURBO,
        )
        cv2.putText(
            err_bgr,
            f"Error Plano RMS = {erms[0]:.4f} mm [-0.6, +0.6 mm]",
            (25, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2,
        )
        panel = np.hstack([tex_bgr, z_bgr, err_bgr])
    else:
        panel = np.hstack([tex_bgr, z_bgr])

    panel_redim = cv2.resize(panel, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    ruta_fig = directorio_salida / f"reconstruccion_{nombre_cat}_pose00.png"
    cv2.imwrite(str(ruta_fig), panel_redim)


def procesar_reconstruccion(
    directorio_base: Path,
    ruta_calibracion: Path,
    categorias: Sequence[str] = ("objeto", "plano"),
    fringe_pitch: int = 18,
    n_step: int = 18,
    n_bits: int = 7,
    fd: str = "Fy",
    gamma_th: float = 0.15,
    umbral_intensidad: int = 25,
) -> None:
    """Ejecuta la extracción de fase y reconstrucción 3D para las categorías indicadas."""
    if not ruta_calibracion.exists():
        raise FileNotFoundError(
            f"No existe el archivo de calibración '{ruta_calibracion}'. "
            f"Ejecuta primero calibracion_estereo.py."
        )

    stereo_params = dict(np.load(ruta_calibracion))

    for categoria in categorias:
        dir_cat = directorio_base / categoria
        if not dir_cat.is_dir():
            print(f"[AVISO] No existe '{dir_cat}', se omite.")
            continue

        print(f"\n================ RECONSTRUCCIÓN 3D: '{categoria.upper()}' ================")
        datos_fases = recuperar_fases_directorio(
            directorio_categoria=dir_cat,
            fringe_pitch=fringe_pitch,
            n_step=n_step,
            n_bits=n_bits,
            gamma_th=gamma_th,
            umbral_intensidad=umbral_intensidad,
        )

        fx = datos_fases["Fx"]
        fy = datos_fases["Fy"]
        qfx = datos_fases["qFx"]
        qfy = datos_fases["qFy"]
        images = datos_fases["images"]
        mask_c = datos_fases["MaskC"]

        # Refinar máscara por calidad de fase en la dirección seleccionada (como en R3D_ComplexShape.m)
        qf_sel = qfy if fd.lower() == "fy" else qfx
        indi_mask = (mask_c > 0) & (qf_sel > gamma_th) & (images > umbral_intensidad)

        xs, ys, zs, t_rec = stereo_reconstruction(
            fx=fx,
            fy=fy,
            mask=indi_mask,
            fringe_pitch=fringe_pitch,
            stereo_params=stereo_params,
            fd=fd,
        )
        print(f"[OK] Triangulación estéreo ({fd}) completada en {t_rec:.3f} s.")

        rutas_ply, new_mask = xyz_to_pc_and_save_ply(
            xs=xs,
            ys=ys,
            zs=zs,
            images=images,
            mask=indi_mask,
            directorio_salida=dir_cat,
            prefijo_ply=categoria,
        )

        e_map = None
        erms = None
        if categoria.lower() == "plano":
            e_map, erms, ze_map, tts = plane_fitting(xs, ys, zs, new_mask)
            print("\n--- Evaluación de Planicidad (Plane_fitting) ---")
            for idx_p, err_val in enumerate(erms):
                z_mean = float(np.nanmean(zs[:, :, idx_p][new_mask[:, :, idx_p] > 0]))
                print(
                    f"  pose_{idx_p:02d}: Z_medio = {z_mean:6.2f} mm | Error RMS Plano = {err_val:.4f} mm"
                )
            print(f"  -> Error RMS Promedio en Planos: {float(np.mean(erms)):.4f} mm")

            ruta_r3d = dir_cat / f"{categoria}_R3D.npz"
            np.savez_compressed(
                ruta_r3d,
                Xs=xs,
                Ys=ys,
                Zs=zs,
                Mask=new_mask,
                e_s=e_map,
                erms_s=erms,
                Ze=ze_map,
                TTs=tts,
            )
        else:
            for idx_p in range(xs.shape[2]):
                m_p = new_mask[:, :, idx_p] > 0
                if np.any(m_p):
                    print(
                        f"  pose_{idx_p:02d}: X=[{np.nanmin(xs[:, :, idx_p][m_p]):.1f}, {np.nanmax(xs[:, :, idx_p][m_p]):.1f}] mm | "
                        f"Y=[{np.nanmin(ys[:, :, idx_p][m_p]):.1f}, {np.nanmax(ys[:, :, idx_p][m_p]):.1f}] mm | "
                        f"Z=[{np.nanmin(zs[:, :, idx_p][m_p]):.1f}, {np.nanmax(zs[:, :, idx_p][m_p]):.1f}] mm"
                    )
            ruta_r3d = dir_cat / f"{categoria}_R3D.npz"
            np.savez_compressed(
                ruta_r3d,
                Xs=xs,
                Ys=ys,
                Zs=zs,
                Mask=new_mask,
            )

        _guardar_visualizacion_reconstruccion(
            directorio_salida=dir_cat,
            nombre_cat=categoria,
            xs=xs,
            ys=ys,
            zs=zs,
            images=images,
            mask=new_mask,
            e_map=e_map,
            erms=erms,
        )
        print(f"[OK] Resultados 3D guardados en '{ruta_r3d}'")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extracción de fase y Reconstrucción 3D Estéreo (adaptado de MATLAB)."
    )
    parser.add_argument(
        "--directorio-base",
        type=Path,
        default=Path("capturas_ordenadas"),
        help="Carpeta raíz con las capturas organizadas (por defecto: capturas_ordenadas)",
    )
    parser.add_argument(
        "--calibracion",
        type=Path,
        default=Path("capturas_ordenadas/patron/Estereo_TSC_0_2.npz"),
        help="Ruta al archivo de calibración estéreo .npz",
    )
    parser.add_argument(
        "--categorias",
        nargs="+",
        default=["objeto", "plano"],
        help="Categorías a reconstruir (por defecto: objeto plano)",
    )
    parser.add_argument(
        "--fase",
        type=str,
        default="Fy",
        choices=["Fy", "Fx"],
        help="Dirección de fase para la triangulación (por defecto: Fy, igual que en MATLAB)",
    )
    parser.add_argument(
        "--pitch",
        type=int,
        default=18,
        help="Período de las franjas en píxeles (por defecto: 18)",
    )
    parser.add_argument(
        "--nstep",
        type=int,
        default=18,
        help="Número de pasos de corrimiento de fase (por defecto: 18)",
    )
    parser.add_argument(
        "--nbits",
        type=int,
        default=7,
        help="Número de bits de código Gray (por defecto: 7)",
    )
    parser.add_argument(
        "--gamma-th",
        type=float,
        default=0.05,
        help="Umbral de modulación gamma (por defecto: 0.05 para incluir objetos oscuros)",
    )
    args = parser.parse_args()

    procesar_reconstruccion(
        directorio_base=args.directorio_base,
        ruta_calibracion=args.calibracion,
        categorias=args.categorias,
        fringe_pitch=args.pitch,
        n_step=args.nstep,
        n_bits=args.nbits,
        fd=args.fase,
        gamma_th=args.gamma_th,
    )


if __name__ == "__main__":
    main()
