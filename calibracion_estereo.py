"""Calibración Estéreo Tradicional (Cámara - Proyector) en Python.

Adapta los códigos de MATLAB:
- `PhaseRecoveryCodes/GenGrayCode.m`
- `PhaseRecoveryCodes/GenInverseGrayCodeLUT.m`
- `PhaseRecoveryCodes/ComputeNStepPhase.m`
- `PhaseRecoveryCodes/UnwrapPhaseGrayCode.m`
- `PhaseRecoveryCodes/CleanPhase.m`
- `PhaseRecoveryCodes/Adj2D_5thPol.m`
- `HybridCalibCodes/PhaseAdj5.m`
- `StereoCalibCodes/createMaskCB.m`
- `StereoCalibCodes/RegWcordtoImage.m`
- `StereoCalibCodes/Traditional_StereoCalib.m`

Flujo:
1. Lee las poses organizadas en `capturas_ordenadas/patron/pose_XX/` (`H/` y `V/`).
2. Detecta los centros del patrón de círculos en la imagen de textura blanca (`P18_F25.tiff`).
3. Recupera las fases desenvueltas `Fx` (franjas verticales en `V/`) y `Fy` (franjas
   horizontales en `H/`) mediante N-Step Phase Shifting con filtrado FFT + Código Gray.
4. Ajusta una superficie polinomial 2D de 5to orden (`CleanPhase` / `PhaseAdj5`) sobre
   la máscara del tablero para limpiar el ruido de alta frecuencia de la rejilla DMD.
5. Calcula las coordenadas correspondientes en el proyector:
       u_p = Fx * FringePitch / (2 * pi)
       v_p = Fy * FringePitch / (2 * pi)
6. Calibra intrínsecamente cámara y proyector por separado y estima la línea base
   estéreo (`Estereo_TSC_0_2.npz` y `.json`), además de la calibración conjunta (`_J`).

Ejemplo de uso:
    python calibracion_estereo.py --directorio capturas_ordenadas/patron
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


# ==============================================================================
# 1. FUNCIONES DE RECUPERACIÓN Y LIMPIEZA DE FASE (PhaseRecoveryCodes)
# ==============================================================================


def gen_gray_code(n_bits: int) -> np.ndarray:
    """Genera la tabla de código Gray de `n_bits` bits (réplica de `GenGrayCode.m`)."""
    if n_bits < 1:
        raise ValueError("n_bits debe ser >= 1")

    data = np.zeros((1 << n_bits, n_bits), dtype=np.int32)
    for i in range(1, n_bits + 1):
        if i == 1:
            data[0, 0] = 0
            data[1, 0] = 1
        else:
            half = 1 << (i - 1)
            full = 1 << i
            data[0:half, i - 1] = 0
            data[half:full, 0 : i - 1] = data[half - 1 :: -1, 0 : i - 1]
            data[half:full, i - 1] = 1
    return data


def gen_inverse_gray_code_lut(n_bits: int) -> np.ndarray:
    """Genera la LUT inversa de código Gray (réplica exacta de `GenInverseGrayCodeLUT.m`).

    Nota: En MATLAB `codeLUT(code + 1) = K` devuelve valores 1-based (1 .. 2^NBits).
    """
    g_code = gen_gray_code(n_bits)
    code_lut = np.zeros(1 << n_bits, dtype=np.int32)

    for k in range(1 << n_bits):
        code = 0
        for n in range(n_bits):
            code = code * 2 + int(g_code[k, n])
        code_lut[code] = k + 1  # 1-based igual que en MATLAB
    return code_lut


def compute_n_step_phase(
    images_stack: np.ndarray, gamma_th: float, n_step: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Calcula la fase envuelta filtrando en frecuencia con ventana Hanning (`ComputeNStepPhase.m`).

    Parámetros:
    - images_stack: Arreglo (H, W, n_step) en float64.
    - gamma_th: Umbral de modulación `gm = Idp / Ip`.
    - n_step: Número de pasos de corrimiento de fase.

    Retorna:
    - ph: Fase envuelta en [-pi, pi].
    - mask: Máscara binaria (255 donde gm >= gamma_th, 0 en caso contrario).
    - texture: Imagen de textura promedio + amplitud (`uint8(Idp + Ip)`).
    - gm: Mapa de modulación/calidad `Idp / Ip`.
    """
    l_steps = n_step
    t = np.arange(l_steps, dtype=np.float64) / float(l_steps)
    # En MATLAB: hanning(L) simétrica = 0.5 * (1 - cos(2*pi*(1:L)/(L+1)))
    han = 0.5 * (
        1.0 - np.cos(2.0 * np.pi * np.arange(1, l_steps + 1) / (l_steps + 1))
    )
    senial = 255.0 * np.cos(t * 2.0 * np.pi) * np.fft.fftshift(han)

    y_fft = np.fft.fft(images_stack, axis=2) * np.fft.fft(senial).reshape(
        1, 1, l_steps
    )
    i_filt = np.fft.ifft(y_fft, axis=2).real

    angles = (2.0 * np.pi / l_steps) * np.arange(l_steps, dtype=np.float64).reshape(
        1, 1, l_steps
    )
    s_sum = np.sum(i_filt * np.sin(angles), axis=2)
    c_sum = np.sum(i_filt * np.cos(angles), axis=2)
    ip = np.mean(i_filt, axis=2)

    idp = 2.0 * np.sqrt(c_sum**2 + s_sum**2) / float(l_steps)
    ph = -np.arctan2(s_sum, c_sum)

    gm = np.divide(idp, ip, out=np.zeros_like(idp), where=ip > 1e-6)
    mask = np.where(gm >= gamma_th, 255.0, 0.0)
    texture = np.clip(idp + ip, 0, 255).astype(np.uint8)

    return ph, mask, texture, gm


def buscar_imagen_patron(prefijo_ruta: Path, indice: int) -> Path:
    """Busca el archivo `<prefijo><indice:02d>` con extensión `.tiff`, `.tif` o `.png`."""
    for ext in (".tiff", ".tif", ".png", ".bmp"):
        candidato = prefijo_ruta.parent / f"{prefijo_ruta.name}{indice:02d}{ext}"
        if candidato.exists():
            return candidato
    raise FileNotFoundError(
        f"No se encontró imagen para {prefijo_ruta}{indice:02d}.[tiff|png|bmp]"
    )


def unwrap_phase_gray_code(
    file_prefix: Path,
    fringe_pitch: int = 18,
    n_step: int = 18,
    n_bits: int = 7,
    med_filt_size: int = 5,
    gamma_th: float = 0.15,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Desenvuelve la fase combinando N-Step Phase Shifting y Código Gray (`UnwrapPhaseGrayCode.m`)."""
    lista_pasos: list[np.ndarray] = []
    for step in range(n_step):
        ruta = buscar_imagen_patron(file_prefix, step)
        img = cv2.imread(str(ruta), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise OSError(f"No se pudo leer {ruta}")
        if img.ndim == 3:
            img = img[:, :, 0]
        lista_pasos.append(img.astype(np.float64))

    i_stack = np.stack(lista_pasos, axis=-1)
    i_avg = np.mean(i_stack, axis=-1)

    ph, mask, texture, gm = compute_n_step_phase(i_stack, gamma_th, n_step)

    bcode = np.zeros(i_avg.shape, dtype=np.int32)
    for n_bin in range(n_bits):
        ruta_bin = buscar_imagen_patron(file_prefix, n_step + n_bin)
        i0 = cv2.imread(str(ruta_bin), cv2.IMREAD_UNCHANGED)
        if i0 is None:
            raise OSError(f"No se pudo leer {ruta_bin}")
        if i0.ndim == 3:
            i0 = i0[:, :, 0]
        icode = (i0.astype(np.float64) > i_avg).astype(np.int32)
        bcode = bcode * 2 + icode

    code_lut = gen_inverse_gray_code_lut(n_bits)
    code_word = code_lut[bcode]

    # Alineación de fase entre el patrón binario de onda cuadrada y los bordes del código Gray:
    # Las transiciones de codeWord ocurren en ph ≈ -pi/2, por lo que desplazamos el corte de rama
    # de atan2 a -pi/2 + pi/fringe_pitch para evitar saltos de 2*pi dentro de cada período.
    shift = -np.pi / 2.0 + np.pi / float(fringe_pitch)
    ph_shifted = np.arctan2(np.sin(ph + shift), np.cos(ph + shift))

    uph = ph_shifted + code_word.astype(np.float64) * (2.0 * np.pi)
    uph = uph - shift

    if med_filt_size > 1:
        ksize = med_filt_size if med_filt_size % 2 == 1 else med_filt_size + 1
        suph = cv2.medianBlur(uph.astype(np.float32), ksize).astype(np.float64)
        unwr_phase = uph - np.round((uph - suph) / (2.0 * np.pi)) * (2.0 * np.pi)
    else:
        unwr_phase = uph

    return unwr_phase, (mask > 0).astype(np.uint8), texture, code_word, ph, gm


def _construir_matriz_polinomio_2d(
    x_norm: np.ndarray, y_norm: np.ndarray, grado: int = 5
) -> np.ndarray:
    """Construye la matriz de Vandermonde 2D de orden `grado` (21 términos para grado 5)."""
    columnas = []
    for n in range(grado, -1, -1):
        for l_exp in range(n, -1, -1):
            columnas.append((x_norm**l_exp) * (y_norm ** (n - l_exp)))
    return np.column_stack(columnas)


def ajustar_polinomio_2d_5to(
    matriz: np.ndarray, mascara: np.ndarray, paso_submuestreo: int = 1
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Ajusta un polinomio 2D de 5to orden sobre los píxeles activos de `mascara` (`polyfit2D_1_5`)."""
    sub_mask = mascara[::paso_submuestreo, ::paso_submuestreo] > 0
    sub_mat = matriz[::paso_submuestreo, ::paso_submuestreo]

    y_idx, x_idx = np.nonzero(sub_mask)
    x = (x_idx * paso_submuestreo).astype(np.float64)
    y = (y_idx * paso_submuestreo).astype(np.float64)
    z = sub_mat[y_idx, x_idx].astype(np.float64)

    ux, sx = float(np.mean(x)), float(np.std(x))
    uy, sy = float(np.mean(y)), float(np.std(y))
    sx = sx if sx > 1e-9 else 1.0
    sy = sy if sy > 1e-9 else 1.0

    x_norm = (x - ux) / sx
    y_norm = (y - uy) / sy

    a_mat = _construir_matriz_polinomio_2d(x_norm, y_norm, grado=5)
    coef, _, _, _ = np.linalg.lstsq(a_mat, z, rcond=None)
    return coef, (ux, sx, uy, sy)


def evaluar_polinomio_2d_5to_puntos(
    coef: np.ndarray,
    norm_params: tuple[float, float, float, float],
    x: np.ndarray,
    y: np.ndarray,
) -> np.ndarray:
    """Evalúa el polinomio 2D de 5to orden en coordenadas arbitrarias `(x, y)`."""
    ux, sx, uy, sy = norm_params
    x_norm = (np.asarray(x, dtype=np.float64) - ux) / sx
    y_norm = (np.asarray(y, dtype=np.float64) - uy) / sy
    a_mat = _construir_matriz_polinomio_2d(x_norm.ravel(), y_norm.ravel(), grado=5)
    return (a_mat @ coef).reshape(np.asarray(x).shape)


def evaluar_polinomio_2d_5to_malla(
    coef: np.ndarray,
    norm_params: tuple[float, float, float, float],
    ancho: int,
    alto: int,
) -> np.ndarray:
    """Evalúa el polinomio 2D de 5to orden sobre toda la imagen `(alto, ancho)`."""
    x_grid, y_grid = np.meshgrid(
        np.arange(ancho, dtype=np.float64), np.arange(alto, dtype=np.float64)
    )
    return evaluar_polinomio_2d_5to_puntos(coef, norm_params, x_grid, y_grid)


def clean_phase(
    fases_x: np.ndarray, fases_y: np.ndarray, mask: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Limpia los mapas de fase ajustando polinomios 2D de 5to grado (`CleanPhase.m` + `PhaseAdj5.m`).

    Retorna:
    - fases_xa, fases_ya: Mapas de fase ajustados polinomialmente (H, W, N).
    - mask_x2, mask_y2: Máscaras depuradas donde el error residual está en (-0.3, 0.3) rad.
    - res_x, res_y: Mapas de error residual `Fases - Fases_ajustadas`.
    """
    alto, ancho, n_poses = fases_x.shape
    fases_xa = np.zeros_like(fases_x)
    fases_ya = np.zeros_like(fases_y)
    res_x = np.full_like(fases_x, np.nan)
    res_y = np.full_like(fases_y, np.nan)

    for i in range(n_poses):
        m_i = (mask[:, :, i] > 0) & np.isfinite(fases_x[:, :, i]) & np.isfinite(
            fases_y[:, :, i]
        )
        if np.count_nonzero(m_i) < 30:
            raise ValueError(f"Pose {i}: muy pocos píxeles válidos en la máscara.")

        coef_x, norm_x = ajustar_polinomio_2d_5to(fases_x[:, :, i], m_i, paso_submuestreo=2)
        fases_xa[:, :, i] = evaluar_polinomio_2d_5to_malla(coef_x, norm_x, ancho, alto)

        coef_y, norm_y = ajustar_polinomio_2d_5to(fases_y[:, :, i], m_i, paso_submuestreo=2)
        fases_ya[:, :, i] = evaluar_polinomio_2d_5to_malla(coef_y, norm_y, ancho, alto)

        rx = fases_x[:, :, i] - fases_xa[:, :, i]
        ry = fases_y[:, :, i] - fases_ya[:, :, i]
        res_x[:, :, i] = np.where(m_i, rx, np.nan)
        res_y[:, :, i] = np.where(m_i, ry, np.nan)

    mask_x2 = (mask > 0) & (res_x > -0.3) & (res_x < 0.3)
    mask_y2 = (mask > 0) & (res_y > -0.3) & (res_y < 0.3)
    return fases_xa, fases_ya, mask_x2, mask_y2, res_x, res_y


def create_mask_cb(
    shape_hw: tuple[int, int], puntos_cam: np.ndarray, offset: int = 10
) -> np.ndarray:
    """Crea una máscara poligonal alrededor de los puntos detectados del tablero (`createMaskCB.m`)."""
    alto, ancho = shape_hw
    hull = cv2.convexHull(puntos_cam.reshape(-1, 2).astype(np.float32))
    centro = np.mean(hull[:, 0, :], axis=0, keepdims=True)
    vectores = hull[:, 0, :] - centro
    normas = np.linalg.norm(vectores, axis=1, keepdims=True)
    normas = np.where(normas > 1e-6, normas, 1.0)
    hull_expandido = (hull[:, 0, :] + (vectores / normas) * float(offset)).astype(
        np.int32
    )

    mascara = np.zeros((alto, ancho), dtype=np.uint8)
    cv2.fillConvexPoly(mascara, hull_expandido, 1)
    return mascara


def reg_wcord_to_image(
    m_points: np.ndarray, world_points: np.ndarray, cam_size_hw: tuple[int, int]
) -> np.ndarray:
    """Registra coordenadas del mundo a la imagen mediante polinomio 2D de 5to orden (`RegWcordtoImage.m`)."""
    alto, ancho = cam_size_hw
    n_poses = m_points.shape[2]
    maps = np.zeros((alto, ancho, n_poses, 2), dtype=np.float64)

    for i in range(n_poses):
        u_cam = m_points[:, 0, i, 0]
        v_cam = m_points[:, 1, i, 0]
        ux, sx = float(np.mean(u_cam)), float(np.std(u_cam))
        uy, sy = float(np.mean(v_cam)), float(np.std(v_cam))
        norm_p = (ux, sx, uy, sy)
        a_mat = _construir_matriz_polinomio_2d(
            (u_cam - ux) / sx, (v_cam - uy) / sy, grado=5
        )
        for dim in range(2):
            coef, _, _, _ = np.linalg.lstsq(a_mat, world_points[:, dim], rcond=None)
            maps[:, :, i, dim] = evaluar_polinomio_2d_5to_malla(
                coef, norm_p, ancho, alto
            )
    return maps


# ==============================================================================
# 2. DETECCIÓN DEL PATRÓN DE CÍRCULOS Y CALIBRACIÓN ESTÉREO
# ==============================================================================


def crear_detector_circulos() -> cv2.SimpleBlobDetector:
    """Configura un detector de blobs robusto al patrón de píxeles DMD del proyector."""
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
    # Suavizado ligero para eliminar la rejilla de alta frecuencia del DMD
    suavizada = cv2.GaussianBlur(imagen_textura, (5, 5), 1.5)
    if circle_color.lower() == "white":
        img_busqueda = 255 - suavizada
    else:
        img_busqueda = suavizada

    flags = (
        cv2.CALIB_CB_SYMMETRIC_GRID
        if pattern_type.lower() == "symmetric"
        else cv2.CALIB_CB_ASYMMETRIC_GRID
    )
    detector = crear_detector_circulos()
    encontrado, esquinas = cv2.findCirclesGrid(
        img_busqueda,
        pattern_size,
        flags=flags,
        blobDetector=detector,
    )
    if not encontrado or esquinas is None:
        # Intento adicional con clustering si la perspectiva es fuerte
        encontrado, esquinas = cv2.findCirclesGrid(
            img_busqueda,
            pattern_size,
            flags=flags | cv2.CALIB_CB_CLUSTERING,
            blobDetector=detector,
        )
    if not encontrado or esquinas is None:
        raise RuntimeError(
            f"No se pudo detectar el patrón de círculos {pattern_size} ({pattern_type}, {circle_color})"
        )
    return esquinas.reshape(-1, 2).astype(np.float64)


def generar_puntos_mundo_circulos(
    pattern_size: tuple[int, int],
    center_distance: float,
    pattern_type: str = "symmetric",
) -> np.ndarray:
    """Genera las coordenadas 2D/3D del tablero (`generateCircleGridPoints`)."""
    cols, rows = pattern_size
    puntos = np.zeros((cols * rows, 3), dtype=np.float32)
    if pattern_type.lower() == "symmetric":
        grid = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
        puntos[:, :2] = grid * float(center_distance)
    else:
        idx = 0
        for r in range(rows):
            for c in range(cols):
                puntos[idx, 0] = (2 * c + (r % 2)) * float(center_distance)
                puntos[idx, 1] = r * float(center_distance)
                idx += 1
    return puntos


def ejecutar_calibracion_estereo(
    directorio_patron: Path,
    fringe_pitch: int = 18,
    n_step: int = 18,
    n_bits: int = 7,
    texture_img_num: int = 25,
    pattern_size: tuple[int, int] = (9, 12),
    center_distance: float = 15.0,
    pattern_type: str = "symmetric",
    circle_color: str = "white",
    gamma_th: float = 0.15,
    offset_mask: int = 10,
    cam_size_wh: tuple[int, int] = (1280, 1024),
    proj_size_wh: tuple[int, int] = (912, 1140),
) -> dict:
    """Ejecuta el flujo completo de `Traditional_StereoCalib.m` sobre las poses en `directorio_patron`."""
    carpetas_poses = sorted(
        p for p in directorio_patron.iterdir() if p.is_dir() and p.name.startswith("pose_")
    )
    if not carpetas_poses:
        raise FileNotFoundError(
            f"No se encontraron carpetas 'pose_XX' en {directorio_patron}. "
            f"Ejecuta primero organizar_capturas.py."
        )

    n_poses = len(carpetas_poses)
    ancho_cam, alto_cam = cam_size_wh
    n_puntos = pattern_size[0] * pattern_size[1]
    world_points = generar_puntos_mundo_circulos(
        pattern_size, center_distance, pattern_type
    )

    fx_vol = np.zeros((alto_cam, ancho_cam, n_poses), dtype=np.float64)
    fy_vol = np.zeros((alto_cam, ancho_cam, n_poses), dtype=np.float64)
    mask_vol = np.zeros((alto_cam, ancho_cam, n_poses), dtype=np.uint8)
    mask_p_vol = np.zeros((alto_cam, ancho_cam, n_poses), dtype=np.uint8)
    images_vol = np.zeros((alto_cam, ancho_cam, n_poses), dtype=np.uint8)

    # M tiene dimensiones (n_puntos, 2, n_poses, 2) igual que en MATLAB:
    # M(:, :, i, 0) -> puntos cámara (u_c, v_c)
    # M(:, :, i, 1) -> puntos proyector (u_p, v_p)
    m_correspondencias = np.zeros((n_puntos, 2, n_poses, 2), dtype=np.float64)
    m_correspondencias_raw = np.zeros((n_puntos, 2, n_poses, 2), dtype=np.float64)

    print(
        f"=== Iniciando Calibración Estéreo Tradicional ({n_poses} poses en '{directorio_patron}') ==="
    )

    for i, dir_pose in enumerate(carpetas_poses):
        prefijo_h = dir_pose / "H" / f"P{fringe_pitch}_F"
        prefijo_v = dir_pose / "V" / f"P{fringe_pitch}_F"

        ruta_tex = buscar_imagen_patron(prefijo_h, texture_img_num)
        itex = cv2.imread(str(ruta_tex), cv2.IMREAD_UNCHANGED)
        if itex is None:
            raise OSError(f"No se pudo leer la imagen de textura {ruta_tex}")
        if itex.ndim == 3:
            itex = itex[:, :, 0]

        puntos_cam = detectar_puntos_tablero(
            itex, pattern_size, pattern_type, circle_color
        )
        m_correspondencias[:, :, i, 0] = puntos_cam
        m_correspondencias_raw[:, :, i, 0] = puntos_cam

        mask_points = create_mask_cb(itex.shape, puntos_cam, offset=offset_mask)

        # Extracción de fase vertical (V -> Fx) y horizontal (H -> Fy)
        fx_aux, mask_h, _, _, _, _ = unwrap_phase_gray_code(
            prefijo_v, fringe_pitch, n_step, n_bits, med_filt_size=5, gamma_th=gamma_th
        )
        fy_aux, mask_v, _, _, _, _ = unwrap_phase_gray_code(
            prefijo_h, fringe_pitch, n_step, n_bits, med_filt_size=5, gamma_th=gamma_th
        )

        fx_vol[:, :, i] = fx_aux
        fy_vol[:, :, i] = fy_aux
        mask_p_vol[:, :, i] = mask_points
        mask_vol[:, :, i] = mask_points & mask_h & mask_v
        images_vol[:, :, i] = itex

        # Interpolación bilineal directa (equivalente a interp2 en MATLAB)
        pts_x = puntos_cam[:, 0].astype(np.float32)
        pts_y = puntos_cam[:, 1].astype(np.float32)
        phasex_pts = cv2.remap(
            fx_aux.astype(np.float32), pts_x, pts_y, cv2.INTER_LINEAR
        ).reshape(-1)
        phasey_pts = cv2.remap(
            fy_aux.astype(np.float32), pts_x, pts_y, cv2.INTER_LINEAR
        ).reshape(-1)

        m_correspondencias_raw[:, 0, i, 1] = phasex_pts * float(fringe_pitch) / (2.0 * np.pi)
        m_correspondencias_raw[:, 1, i, 1] = phasey_pts * float(fringe_pitch) / (2.0 * np.pi)

        print(
            f"  [{dir_pose.name}] {len(puntos_cam)} círculos detectados | "
            f"u_p=[{m_correspondencias_raw[:, 0, i, 1].min():.1f}, {m_correspondencias_raw[:, 0, i, 1].max():.1f}] px | "
            f"v_p=[{m_correspondencias_raw[:, 1, i, 1].min():.1f}, {m_correspondencias_raw[:, 1, i, 1].max():.1f}] px"
        )

    # Recorte de bordes de 15 píxeles en la máscara como en Traditional_StereoCalib.m (líneas 98-99)
    mask_vol[:15, :, :] = 0
    mask_vol[-15:, :, :] = 0
    mask_vol[:, :15, :] = 0
    mask_vol[:, -15:, :] = 0

    # Ajuste de superficie de fase de 5to orden (CleanPhase.m)
    print("\nAjustando superficies polinomiales de 5to orden (CleanPhase)...")
    fxa, fya, mask_x, mask_y, res_x, res_y = clean_phase(fx_vol, fy_vol, mask_vol)
    indi = np.where(mask_x > 0, 1.0, np.nan)

    # Evaluar las fases ajustadas fxa, fya en los centros de los círculos para correspondencia limpia
    for i in range(n_poses):
        pts_x = m_correspondencias[:, 0, i, 0].astype(np.float32)
        pts_y = m_correspondencias[:, 1, i, 0].astype(np.float32)
        px_clean = cv2.remap(
            fxa[:, :, i].astype(np.float32), pts_x, pts_y, cv2.INTER_LINEAR
        ).reshape(-1)
        py_clean = cv2.remap(
            fya[:, :, i].astype(np.float32), pts_x, pts_y, cv2.INTER_LINEAR
        ).reshape(-1)
        m_correspondencias[:, 0, i, 1] = px_clean * float(fringe_pitch) / (2.0 * np.pi)
        m_correspondencias[:, 1, i, 1] = py_clean * float(fringe_pitch) / (2.0 * np.pi)

    # Registro de coordenadas del mundo a imagen (RegWcordtoImage.m)
    maps = reg_wcord_to_image(m_correspondencias, world_points[:, :2], (alto_cam, ancho_cam))

    # Guardar archivo de datos de fase (equivalente a Estereo_PhasesData.mat)
    ruta_phases_data = directorio_patron / "patron_PhasesData.npz"
    np.savez_compressed(
        ruta_phases_data,
        Fx=fx_vol,
        Fy=fy_vol,
        Fxa=fxa,
        Fya=fya,
        M=m_correspondencias,
        M_raw=m_correspondencias_raw,
        Indi=indi,
        Mask=mask_vol,
        MaskP=mask_p_vol,
        Maps=maps,
        Images=images_vol,
        worldPoints=world_points,
    )
    print(f"[OK] Datos de fase guardados en: '{ruta_phases_data}'")

    # Preparar listas para OpenCV calibrateCamera / stereoCalibrate
    obj_pts_list = [world_points.astype(np.float32) for _ in range(n_poses)]
    cam_pts_list = [
        m_correspondencias[:, :, i, 0].reshape(-1, 1, 2).astype(np.float32)
        for i in range(n_poses)
    ]
    proj_pts_list = [
        m_correspondencias[:, :, i, 1].reshape(-1, 1, 2).astype(np.float32)
        for i in range(n_poses)
    ]

    # En MATLAB: NRcoef = 2, SkewFlag = 0, EstimateTangentialDistortion = true
    # En OpenCV: CALIB_FIX_K3 fija el 3er coef radial a 0, estimando (k1, k2, p1, p2)
    flags_indep = cv2.CALIB_FIX_K3

    rms_cam, k_cam, dist_cam, rvecs_cam, tvecs_cam = cv2.calibrateCamera(
        obj_pts_list, cam_pts_list, cam_size_wh, None, None, flags=flags_indep
    )
    rms_proj, k_proj, dist_proj, rvecs_proj, tvecs_proj = cv2.calibrateCamera(
        obj_pts_list, proj_pts_list, proj_size_wh, None, None, flags=flags_indep
    )

    # 1) Calibración Estéreo fijando intrínsecos independientes (estimateStereoBaseline en MATLAB)
    rms_stereo_indep, k_cam_1, dist_cam_1, k_proj_1, dist_proj_1, r_mat, t_vec, e_mat, f_mat = (
        cv2.stereoCalibrate(
            obj_pts_list,
            cam_pts_list,
            proj_pts_list,
            k_cam.copy(),
            dist_cam.copy(),
            k_proj.copy(),
            dist_proj.copy(),
            cam_size_wh,
            flags=cv2.CALIB_FIX_INTRINSIC,
        )
    )

    # 2) Calibración Estéreo conjunta (_J en Traditional_StereoCalib.m)
    rms_stereo_joint, k_cam_j, dist_cam_j, k_proj_j, dist_proj_j, r_mat_j, t_vec_j, e_mat_j, f_mat_j = (
        cv2.stereoCalibrate(
            obj_pts_list,
            cam_pts_list,
            proj_pts_list,
            k_cam.copy(),
            dist_cam.copy(),
            k_proj.copy(),
            dist_proj.copy(),
            cam_size_wh,
            flags=cv2.CALIB_USE_INTRINSIC_GUESS | cv2.CALIB_FIX_K3,
        )
    )

    print("\n================ RESULTADOS DE CALIBRACIÓN ESTÉREO ================")
    print(f"  Error RMS Cámara (independiente)   : {rms_cam:.4f} px")
    print(f"  Error RMS Proyector (independiente): {rms_proj:.4f} px")
    print(f"  Error RMS Estéreo (fijo, TSC_0_2)  : {rms_stereo_indep:.4f} px")
    print(f"  Error RMS Estéreo (conjunto, _J)   : {rms_stereo_joint:.4f} px")
    print("\nMatriz Intrínseca Cámara (Ac):")
    print(k_cam_1)
    print("Distorsión Cámara [k1, k2, p1, p2, k3]:", dist_cam_1.ravel())
    print("\nMatriz Intrínseca Proyector (Ap):")
    print(k_proj_1)
    print("Distorsión Proyector [k1, k2, p1, p2, k3]:", dist_proj_1.ravel())
    print("\nRotación Proyector respecto a Cámara (R):")
    print(r_mat)
    print("Traslación Proyector respecto a Cámara (T en mm):", t_vec.ravel())
    print("===================================================================\n")

    # Guardar parámetros estéreo (equivalente a Estereo_TSC_0_2.mat y Estereo_TSC_0_2_J.mat)
    ruta_tsc = directorio_patron / "Estereo_TSC_0_2.npz"
    np.savez(
        ruta_tsc,
        Ac=k_cam_1,
        Ap=k_proj_1,
        dist_cam=dist_cam_1.ravel(),
        dist_proj=dist_proj_1.ravel(),
        Kr1=np.array([dist_cam_1.ravel()[0], dist_cam_1.ravel()[1], dist_cam_1.ravel()[4]]),
        Kt1=np.array([dist_cam_1.ravel()[2], dist_cam_1.ravel()[3]]),
        Kr2=np.array([dist_proj_1.ravel()[0], dist_proj_1.ravel()[1], dist_proj_1.ravel()[4]]),
        Kt2=np.array([dist_proj_1.ravel()[2], dist_proj_1.ravel()[3]]),
        R=r_mat,
        T=t_vec.reshape(3, 1),
        E=e_mat,
        F=f_mat,
        rms_cam=rms_cam,
        rms_proj=rms_proj,
        rms_stereo=rms_stereo_indep,
        cam_size_wh=np.array(cam_size_wh),
        proj_size_wh=np.array(proj_size_wh),
        fringe_pitch=fringe_pitch,
        rvecs_cam=np.array(rvecs_cam),
        tvecs_cam=np.array(tvecs_cam),
    )

    ruta_tsc_j = directorio_patron / "Estereo_TSC_0_2_J.npz"
    np.savez(
        ruta_tsc_j,
        Ac=k_cam_j,
        Ap=k_proj_j,
        dist_cam=dist_cam_j.ravel(),
        dist_proj=dist_proj_j.ravel(),
        Kr1=np.array([dist_cam_j.ravel()[0], dist_cam_j.ravel()[1], dist_cam_j.ravel()[4]]),
        Kt1=np.array([dist_cam_j.ravel()[2], dist_cam_j.ravel()[3]]),
        Kr2=np.array([dist_proj_j.ravel()[0], dist_proj_j.ravel()[1], dist_proj_j.ravel()[4]]),
        Kt2=np.array([dist_proj_j.ravel()[2], dist_proj_j.ravel()[3]]),
        R=r_mat_j,
        T=t_vec_j.reshape(3, 1),
        E=e_mat_j,
        F=f_mat_j,
        rms_cam=rms_cam,
        rms_proj=rms_proj,
        rms_stereo=rms_stereo_joint,
        cam_size_wh=np.array(cam_size_wh),
        proj_size_wh=np.array(proj_size_wh),
        fringe_pitch=fringe_pitch,
    )

    # Guardar resumen legible en JSON
    ruta_json = directorio_patron / "Estereo_TSC_0_2.json"
    resumen_json = {
        "n_poses": n_poses,
        "pattern_size": list(pattern_size),
        "center_distance_mm": center_distance,
        "fringe_pitch": fringe_pitch,
        "rms_cam_px": float(rms_cam),
        "rms_proj_px": float(rms_proj),
        "rms_stereo_indep_px": float(rms_stereo_indep),
        "rms_stereo_joint_px": float(rms_stereo_joint),
        "Ac": k_cam_1.tolist(),
        "dist_cam": dist_cam_1.ravel().tolist(),
        "Ap": k_proj_1.tolist(),
        "dist_proj": dist_proj_1.ravel().tolist(),
        "R": r_mat.tolist(),
        "T_mm": t_vec.ravel().tolist(),
    }
    ruta_json.write_text(json.dumps(resumen_json, indent=2), encoding="utf-8")

    # Generar gráficas diagnósticas (equivalentes a las figuras de MATLAB)
    _guardar_figuras_diagnostico(
        directorio_patron,
        images_vol,
        fx_vol,
        fy_vol,
        mask_vol,
        res_x,
        res_y,
        m_correspondencias,
        obj_pts_list,
        cam_pts_list,
        proj_pts_list,
        k_cam_1,
        dist_cam_1,
        rvecs_cam,
        tvecs_cam,
        k_proj_1,
        dist_proj_1,
        rvecs_proj,
        tvecs_proj,
    )

    print(f"[OK] Calibración guardada en:\n  - {ruta_tsc}\n  - {ruta_tsc_j}\n  - {ruta_json}")
    return resumen_json


def _normalizar_mapa_color(
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

    if vmin is None:
        vmin = float(np.nanmin(mapa[valido]))
    if vmax is None:
        vmax = float(np.nanmax(mapa[valido]))
    escala = (vmax - vmin) if abs(vmax - vmin) > 1e-9 else 1.0

    mapa_limpio = np.where(valido, mapa, vmin)
    norm_u8 = np.clip((mapa_limpio - vmin) / escala * 255.0, 0, 255).astype(np.uint8)
    color_bgr = cv2.applyColorMap(norm_u8, colormap)
    color_bgr[~valido] = 0
    return color_bgr


def _guardar_figuras_diagnostico(
    directorio_salida: Path,
    images_vol: np.ndarray,
    fx_vol: np.ndarray,
    fy_vol: np.ndarray,
    mask_vol: np.ndarray,
    res_x: np.ndarray,
    res_y: np.ndarray,
    m_corr: np.ndarray,
    obj_pts_list: list[np.ndarray],
    cam_pts_list: list[np.ndarray],
    proj_pts_list: list[np.ndarray],
    k_cam: np.ndarray,
    dist_cam: np.ndarray,
    rvecs_cam: list[np.ndarray],
    tvecs_cam: list[np.ndarray],
    k_proj: np.ndarray,
    dist_proj: np.ndarray,
    rvecs_proj: list[np.ndarray],
    tvecs_proj: list[np.ndarray],
) -> None:
    """Genera paneles diagnósticos de detección de círculos, fases desenvueltas y residuales usando OpenCV."""
    img0_bgr = cv2.cvtColor(images_vol[:, :, 0], cv2.COLOR_GRAY2BGR)
    for idx_pt, (ux, uy) in enumerate(m_corr[:, :, 0, 0]):
        color = (0, 255, 0) if idx_pt == 0 else (0, 0, 255)
        radio = 8 if idx_pt == 0 else 4
        cv2.circle(img0_bgr, (int(round(ux)), int(round(uy))), radio, color, -1)
    cv2.putText(
        img0_bgr,
        "Pose 00: Circulos Detectados",
        (25, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (0, 255, 255),
        2,
    )

    fx_bgr = _normalizar_mapa_color(fx_vol[:, :, 0], mask_vol[:, :, 0], colormap=cv2.COLORMAP_JET)
    cv2.putText(
        fx_bgr,
        "Pose 00: Fase Desenvuelta Fx (V)",
        (25, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (255, 255, 255),
        2,
    )

    fy_bgr = _normalizar_mapa_color(fy_vol[:, :, 0], mask_vol[:, :, 0], colormap=cv2.COLORMAP_JET)
    cv2.putText(
        fy_bgr,
        "Pose 00: Fase Desenvuelta Fy (H)",
        (25, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (255, 255, 255),
        2,
    )

    res_bgr = _normalizar_mapa_color(
        res_y[:, :, 0], mask_vol[:, :, 0], vmin=-0.08, vmax=0.08, colormap=cv2.COLORMAP_TURBO
    )
    cv2.putText(
        res_bgr,
        "Pose 00: Residual CleanPhase Fy [-0.08, 0.08] rad",
        (25, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
    )

    panel = np.vstack([np.hstack([img0_bgr, fx_bgr]), np.hstack([fy_bgr, res_bgr])])
    panel_redim = cv2.resize(panel, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(directorio_salida / "diagnostico_fases_pose00.png"), panel_redim)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibración Estéreo Tradicional Cámara-Proyector (adaptado de MATLAB)."
    )
    parser.add_argument(
        "--directorio",
        type=Path,
        default=Path("capturas_ordenadas/patron"),
        help="Directorio con las carpetas pose_XX del patrón de calibración",
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
        help="Número de bits de código Gray leídos (por defecto: 7, igual que en MATLAB)",
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=9,
        help="Columnas del patrón de círculos (por defecto: 9)",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=12,
        help="Filas del patrón de círculos (por defecto: 12)",
    )
    parser.add_argument(
        "--distancia",
        type=float,
        default=15.0,
        help="Distancia entre centros de círculos en mm (por defecto: 15.0)",
    )
    parser.add_argument(
        "--tipo-patron",
        type=str,
        default="symmetric",
        choices=["symmetric", "asymmetric"],
        help="Tipo de grilla de círculos (por defecto: symmetric)",
    )
    args = parser.parse_args()

    ejecutar_calibracion_estereo(
        directorio_patron=args.directorio,
        fringe_pitch=args.pitch,
        n_step=args.nstep,
        n_bits=args.nbits,
        pattern_size=(args.cols, args.rows),
        center_distance=args.distancia,
        pattern_type=args.tipo_patron,
    )


if __name__ == "__main__":
    main()

