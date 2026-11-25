"""Recuperación de fase relativa (envuelta) y absoluta (desenvuelta) por phase shifting + código Gray.

Adapta `PhaseRecoveryCodes/ComputeNStepPhase.m` y `PhaseRecoveryCodes/UnwrapPhaseGrayCode.m`
(S. Zhang) a la secuencia que genera `secuencia_patrones.py`:

    por orientación: N corrimientos binarios de 1 px (N = período P) + B bits Gray + negro + blanco

Convenciones:
- Fase relativa:  phi = -atan2(S, C) en [-pi, pi), con S = sum I_n sin(2*pi*n/N), C = sum I_n cos(2*pi*n/N).
- Fase absoluta:  Phi = phi + 2*pi*k, con k = orden de franja decodificado del código Gray.
- Coordenada del proyector:  u_p = Phi * P / (2*pi)  (P = período en píxeles del proyector).

El orden en que el LightCrafter proyecta los bits Gray depende de cómo se cargó la secuencia en el
firmware. Con las capturas actuales los bits llegan del menos significativo al más significativo
(igual que asumía la LUT de `GenInverseGrayCodeLUT.m`). `detectar_orden_bits` lo verifica sobre los
datos y `orden_bits="auto"` lo resuelve en cada captura.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from datos_sistema import rutas


EXTENSIONES_IMAGEN = (".tiff", ".tif", ".png", ".bmp", ".jpg", ".jpeg")


# ==============================================================================
# Lectura de secuencias organizadas (<pose>/<H|V>/P18_FXX.ext)
# ==============================================================================


def buscar_imagen_patron(prefijo_ruta: Path, indice: int) -> Path:
    """Busca `<prefijo><indice:02d>` con cualquiera de las extensiones de imagen admitidas."""
    for ext in EXTENSIONES_IMAGEN:
        candidato = prefijo_ruta.parent / f"{prefijo_ruta.name}{indice:02d}{ext}"
        if candidato.exists():
            return candidato
    raise FileNotFoundError(
        f"No se encontró imagen para {prefijo_ruta}{indice:02d}.[{'|'.join(e[1:] for e in EXTENSIONES_IMAGEN)}]"
    )


def leer_gris(ruta: Path) -> np.ndarray:
    """Lee una imagen en escala de grises conservando la profundidad de bits."""
    img = cv2.imread(str(ruta), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise OSError(f"No se pudo leer {ruta}")
    if img.ndim == 3:
        img = img[:, :, 0]
    return img


def cargar_secuencia(
    prefijo_ruta: Path, n_imagenes: int, inicio: int = 0, dtype=np.float32
) -> np.ndarray:
    """Carga las imágenes `<prefijo>{inicio}..{inicio + n_imagenes - 1}` como arreglo (N, H, W).

    Se usa float32: las capturas son de 8 bits, así que no se pierde precisión y se usa la mitad
    de memoria que con float64.
    """
    return np.stack(
        [
            leer_gris(buscar_imagen_patron(prefijo_ruta, k)).astype(dtype)
            for k in range(inicio, inicio + n_imagenes)
        ]
    )


# ==============================================================================
# Fase relativa (envuelta)
# ==============================================================================


def fase_relativa(
    imagenes: np.ndarray, gamma_th: float = 0.15, suavizado: float = 0.0
) -> dict[str, np.ndarray]:
    """N-Step phase shifting (`ComputeNStepPhase.m`).

    La fase se obtiene del coeficiente de Fourier temporal en la frecuencia fundamental:

        X1 = sum_n I_n exp(-i 2 pi n / N) = C - i S
        phi = -atan2(S, C),   B = 2 |X1| / N,   A = mean(I_n)

    Nota sobre el filtro de `ComputeNStepPhase.m`: el MATLAB convoluciona la pila en el eje temporal
    con un coseno ventaneado (Hanning) antes de calcular S y C. Como S y C solo miran la frecuencia
    fundamental, ese filtro equivale EXACTAMENTE a multiplicar X1 por la constante H[1] (verificado
    numéricamente: rotación de -0.0052 rad = -0.015 px y ganancia constante). Los armónicos de la
    onda cuadrada ya se rechazan porque N = P (18 pasos de 1 px): un armónico k solo contamina la
    fundamental si k = N +- 1. Por eso aquí se omite el filtro (y sus 3 FFT sobre toda la pila), y el
    resultado coincide con la columna real del proyector sin el sesgo de 0.015 px.

    Parámetros:
    - imagenes: (N, H, W) corrimientos de fase en orden.
    - gamma_th: umbral de modulación gm = B / A para la máscara.
    - suavizado: sigma (px de cámara) de un filtro gaussiano aplicado a S y C antes del atan2.
      Promediar el numerador complejo (y no la fase) no sesga la fase en superficies suaves y
      reduce el ruido y el moteado de la rejilla del DMD; a cambio suaviza los bordes de
      discontinuidades de profundidad. 0 = sin filtro (como el MATLAB).

    Retorna un dict con:
    - phi: fase envuelta en [-pi, pi].
    - A: intensidad media (fondo), B: amplitud de modulación, gm = B / A.
    - mascara: gm >= gamma_th.
    - textura: uint8(A + B) (imagen sin franjas).
    """
    n_step = imagenes.shape[0]
    pila = np.asarray(imagenes, dtype=np.float32)
    a_media = np.mean(pila, axis=0, dtype=np.float64)

    angulos = (2.0 * np.pi / n_step) * np.arange(n_step, dtype=np.float64)
    # Productos punto en el eje temporal (BLAS): mucho más rápido que sumar pila * sin(...)
    plano = pila.reshape(n_step, -1)
    s_sum = (np.sin(angulos).astype(np.float32) @ plano).astype(np.float64).reshape(a_media.shape)
    c_sum = (np.cos(angulos).astype(np.float32) @ plano).astype(np.float64).reshape(a_media.shape)
    # B (y por tanto la máscara gm) se calcula SIN suavizar, para que el umbral gamma signifique
    # lo mismo con o sin filtro; el filtro solo mejora la estimación de la fase.
    b_mod = 2.0 * np.hypot(c_sum, s_sum) / float(n_step)
    if suavizado > 0:
        s_sum = cv2.GaussianBlur(s_sum, (0, 0), suavizado)
        c_sum = cv2.GaussianBlur(c_sum, (0, 0), suavizado)

    phi = -np.arctan2(s_sum, c_sum)
    gm = np.divide(b_mod, a_media, out=np.zeros_like(b_mod), where=np.abs(a_media) > 1e-6)
    return {
        "phi": phi,
        "A": a_media,
        "B": b_mod,
        "gm": gm,
        "mascara": gm >= gamma_th,
        "textura": np.clip(a_media + b_mod, 0, 255).astype(np.uint8),
    }


# ==============================================================================
# Código Gray y fase absoluta (desenvuelta)
# ==============================================================================


def bits_gray(imagenes_gray: np.ndarray, umbral: np.ndarray, med_filt_size: int = 5) -> np.ndarray:
    """Binariza los planos Gray capturados (B, H, W) contra la imagen umbral (H, W).

    El filtro de mediana sobre cada plano binario elimina el moteado que produce la rejilla de
    micro-espejos del DMD sin desplazar los bordes rectos del código.
    """
    bits = (imagenes_gray > umbral[np.newaxis]).astype(np.uint8)
    if med_filt_size > 1:
        ksize = med_filt_size if med_filt_size % 2 == 1 else med_filt_size + 1
        bits = np.stack([cv2.medianBlur(b, ksize) for b in bits])
    return bits.astype(np.int32)


def decodificar_gray(bits: np.ndarray, orden_bits: str = "lsb") -> np.ndarray:
    """Convierte los planos Gray binarizados (B, H, W) en el orden de franja k (0 .. 2^B - 1).

    `orden_bits="msb"`: el primer plano capturado es el bit más significativo (orden de los .bmp).
    `orden_bits="lsb"`: el primer plano capturado es el bit menos significativo.
    """
    if orden_bits not in ("msb", "lsb"):
        raise ValueError("orden_bits debe ser 'msb' o 'lsb'")
    planos = bits if orden_bits == "msb" else bits[::-1]
    # Gray -> binario: b_i = b_{i-1} XOR g_i, recorriendo desde el bit más significativo
    binario = planos[0].copy()
    k = binario.copy()
    for g in planos[1:]:
        binario = np.bitwise_xor(binario, g)
        k = (k << 1) | binario
    return k


def _saltos_fase(fase: np.ndarray, mascara: np.ndarray) -> float:
    """Fracción de píxeles vecinos con salto mayor a pi (medida de mala decodificación)."""
    dx = np.abs(np.diff(fase, axis=1)) > np.pi
    m = mascara[:, 1:] & mascara[:, :-1]
    dy = np.abs(np.diff(fase, axis=0)) > np.pi
    n = mascara[1:, :] & mascara[:-1, :]
    total = np.count_nonzero(m) + np.count_nonzero(n)
    return float(np.count_nonzero(dx & m) + np.count_nonzero(dy & n)) / max(total, 1)


def desfase_corte(fringe_pitch: int) -> float:
    """Desfase entre la fase envuelta y los bordes del código Gray para la onda cuadrada de `patterns.py`.

    El patrón binario es blanco donde (x + n) mod P < P/2, de modo que el centro de la franja
    blanca está en c = (ceil(P/2) - 1) / 2 y phi(x) = 2*pi*(x - c)/P. Los bordes del código Gray
    caen en x = jP - 0.5, es decir en phi = -2*pi*(c + 0.5)/P (= -pi/2 para P = 18).
    """
    centro = (np.ceil(fringe_pitch / 2.0) - 1.0) / 2.0
    return -2.0 * np.pi * (centro + 0.5) / float(fringe_pitch)


def fase_absoluta(
    phi: np.ndarray,
    k: np.ndarray,
    fringe_pitch: int,
    med_filt_size: int = 5,
) -> np.ndarray:
    """Desenvuelve la fase con el orden de franja Gray (`UnwrapPhaseGrayCode.m`).

    Se rota la fase envuelta para que su corte de rama coincida con los bordes del código Gray,
    se suma 2*pi*k y se corrigen los errores de +-1 orden en los bordes con un filtro de mediana.
    La fase resultante cumple Phi = 2*pi*(x_p - c)/P, con x_p la coordenada del proyector.
    """
    corte = desfase_corte(fringe_pitch)
    shift = -np.pi - corte
    phi_rot = np.arctan2(np.sin(phi + shift), np.cos(phi + shift))
    uph = phi_rot + 2.0 * np.pi * k.astype(np.float64) - shift

    if med_filt_size > 1:
        ksize = med_filt_size if med_filt_size % 2 == 1 else med_filt_size + 1
        suph = cv2.medianBlur(uph.astype(np.float32), ksize).astype(np.float64)
        uph = uph - np.round((uph - suph) / (2.0 * np.pi)) * (2.0 * np.pi)
    return uph


def coordenada_proyector(fase_abs: np.ndarray, fringe_pitch: int) -> np.ndarray:
    """Coordenada del proyector en píxeles a partir de la fase absoluta: u_p = Phi * P / (2*pi) + c."""
    centro = (np.ceil(fringe_pitch / 2.0) - 1.0) / 2.0
    return fase_abs * float(fringe_pitch) / (2.0 * np.pi) + centro


def detectar_orden_bits(
    phi: np.ndarray,
    bits: np.ndarray,
    fringe_pitch: int,
    mascara: np.ndarray,
    med_filt_size: int = 5,
) -> tuple[str, dict[str, float]]:
    """Elige el orden de bits Gray ('msb' o 'lsb') que produce la fase absoluta más continua.

    Con el orden equivocado el orden de franja k salta de forma caótica, así que la diferencia de
    continuidad es enorme; basta evaluarla en una versión submuestreada (1/4 de los píxeles).
    """
    sub = (slice(None, None, 2), slice(None, None, 2))
    phi_s, mask_s = np.ascontiguousarray(phi[sub]), mascara[sub]
    bits_s = np.ascontiguousarray(bits[(slice(None),) + sub])
    puntajes = {}
    for orden in ("msb", "lsb"):
        k = decodificar_gray(bits_s, orden)
        fase_abs = fase_absoluta(phi_s, k, fringe_pitch, med_filt_size)
        puntajes[orden] = _saltos_fase(fase_abs, mask_s)
    return min(puntajes, key=puntajes.get), puntajes


def mascara_valida(
    gm: np.ndarray,
    itex: np.ndarray,
    gamma_th: float,
    umbral_intensidad: float,
    borde: int,
) -> np.ndarray:
    """Píxeles con modulación suficiente, iluminados y alejados del borde de la imagen."""
    mascara = (gm >= gamma_th) & (itex > umbral_intensidad)
    if borde > 0:
        mascara[:borde, :] = False
        mascara[-borde:, :] = False
        mascara[:, :borde] = False
        mascara[:, -borde:] = False
    return mascara


# ==============================================================================
# Etapas del pipeline: fase relativa y fase absoluta por categoría
# ==============================================================================


def listar_poses(categoria: str | Path) -> list[Path]:
    """Carpetas `pose_XX` de una categoría organizada, en orden, donde estén (`rutas.py`: en la
    carpeta de su proceso o en la estructura anterior).

    Solo las de la configuración vigente del montaje (`sesiones.py`), salvo que
    `SOLO_CONFIGURACION_ACTUAL = False`. Acepta también la ruta de la categoría (uso anterior).
    """
    from datos_sistema import rutas
    from datos_sistema import sesiones

    cat = categoria.name if isinstance(categoria, Path) else categoria
    vigentes = sesiones.poses_vigentes(cat)
    dirs = [rutas.dir_pose_ordenada(cat, p) for p in rutas.poses(cat) if vigentes is None or p in vigentes]
    return [d for d in dirs if d.is_dir()]


def _imagenes_pose(dir_pose: Path) -> list[Path]:
    """Lo que, si cambia, obliga a recalcular la fase: las imágenes H/ y V/ (no origen.json)."""
    return [dir_pose / "H", dir_pose / "V"]


def _firma_guardada(ruta: Path) -> str | None:
    """Parámetros con los que se calculó un `.npz` de fase (None en los anteriores a la firma)."""
    try:
        with np.load(ruta) as d:
            return str(d["firma"]) if "firma" in d.files else None
    except (OSError, ValueError, KeyError):
        return ""


def _firma_original(tipo: str) -> str:
    """Firma con los valores de configuracion.py tal como están en el archivo: la de los
    resultados calculados antes de que se guardara la firma."""
    from datos_sistema import configuracion as cfg

    o = cfg.VALORES_ORIGINALES
    if tipo == "rel":
        return firma_relativa(o["N_PASOS"], o["SUAVIZADO_FASE_PX"])
    return firma_absoluta(o["PERIODO"], o["N_BITS_GRAY"], o["GAMMA_TH"], o["GAMMA_TH_Y"], o["MED_FILT"],
                          o["ORDEN_BITS_GRAY"], o["UMBRAL_INTENSIDAD"], o["BORDE_MASCARA"])


def _actualizado(salida: Path, entradas: Sequence[Path], firma: str | None = None) -> bool:
    """True si `salida` existe, es más reciente que todos los archivos de `entradas` (carpetas o
    archivos) y se calculó con los mismos parámetros (`firma`)."""
    if not salida.exists():
        return False
    if firma is not None:
        guardada = _firma_guardada(salida)
        if guardada is None:  # anterior a la firma: se calculó con los valores de configuracion.py
            guardada = _firma_original(firma.split("|")[0])
        if guardada != firma:
            return False
    t_salida = salida.stat().st_mtime
    for entrada in entradas:
        archivos = entrada.rglob("*") if entrada.is_dir() else [entrada]
        if any(a.stat().st_mtime > t_salida for a in archivos if a.is_file()):
            return False
    return True


def _imagen_color(mapa: np.ndarray, mascara: np.ndarray, colormap: int = cv2.COLORMAP_JET) -> np.ndarray:
    valido = mascara & np.isfinite(mapa)
    salida = np.zeros((*mapa.shape, 3), dtype=np.uint8)
    if not np.any(valido):
        return salida
    vmin, vmax = np.percentile(mapa[valido], [0.5, 99.5])
    norm = np.clip((mapa - vmin) / max(vmax - vmin, 1e-9) * 255.0, 0, 255)
    salida = cv2.applyColorMap(np.nan_to_num(norm).astype(np.uint8), colormap)
    salida[~valido] = 0
    return salida


def _guardar_panel(ruta: Path, imagenes: Sequence[np.ndarray], titulos: Sequence[str]) -> None:
    paneles = []
    for img, titulo in zip(imagenes, titulos):
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img.copy()
        cv2.putText(img, titulo, (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
        paneles.append(img)
    panel = np.hstack(paneles)
    cv2.imwrite(str(ruta), cv2.resize(panel, (0, 0), fx=0.4, fy=0.4, interpolation=cv2.INTER_AREA))


def etapa_fase_relativa(
    dir_ordenadas: Path,
    dir_salida: Path,
    categorias: Sequence[str],
    n_step: int = 18,
    gamma_th: float = 0.15,
    prefijo: str = "P18_F",
    rehacer: bool = False,
    gamma_th_y: float | None = None,
    suavizado: float = 0.0,
) -> list[Path]:
    """Calcula y guarda la fase envuelta de `V/` (phiX) y `H/` (phiY) de cada pose.

    Salida: `<dir_salida>/<categoria>/pose_XX_relativa.npz` y una figura diagnóstica `.png`.
    Las poses cuyo resultado es más reciente que sus imágenes se omiten salvo con `rehacer=True`.
    Las poses pendientes se procesan en paralelo (`_en_paralelo`).
    """
    gamma_th_y = gamma_th if gamma_th_y is None else gamma_th_y
    firma = firma_relativa(n_step, suavizado)
    generados = []
    for categoria in categorias:
        poses = listar_poses(categoria)
        if not poses:
            print(f"[AVISO] No hay poses organizadas de '{categoria}', se omite.")
            continue
        print(f"\n=== Fase relativa: '{categoria}' ({len(poses)} poses) ===")
        pendientes = []
        for dir_pose in poses:
            ruta = rutas.fase_relativa(categoria, dir_pose.name)  # en la carpeta de su proceso
            generados.append(ruta)
            if not rehacer and _actualizado(ruta, _imagenes_pose(dir_pose), firma):
                print(f"  [{dir_pose.name}] sin cambios, se reutiliza '{ruta.name}'")
            else:
                pendientes.append((dir_pose, ruta))
        for mensaje in _en_paralelo(
            _fase_relativa_pose,
            [(d, r, n_step, gamma_th, gamma_th_y, prefijo, suavizado, firma) for d, r in pendientes],
        ):
            print(mensaje)
    return generados


def _en_paralelo(funcion, argumentos: list[tuple], hilos: int | None = None):
    """Ejecuta `funcion(*args)` para cada tupla en hilos y devuelve los resultados en orden.

    NumPy y OpenCV liberan el GIL en las operaciones pesadas (lectura de TIFF, BLAS, mediana), así
    que varios hilos procesan varias poses a la vez sin copiar datos entre procesos. Se limita a
    4 hilos para no agotar la memoria (cada pose ocupa ~200 MB mientras se procesa).
    """
    if not argumentos:
        return []
    hilos = hilos or min(4, len(argumentos), os.cpu_count() or 1)
    if hilos <= 1:
        return [funcion(*a) for a in argumentos]
    with ThreadPoolExecutor(max_workers=hilos) as ejecutor:
        return list(ejecutor.map(lambda a: funcion(*a), argumentos))


def firma_relativa(n_step: int, suavizado: float) -> str:
    """Parámetros que determinan la fase envuelta (los umbrales solo afectan a la figura)."""
    return f"rel|{n_step}|{float(suavizado):g}"


def firma_absoluta(fringe_pitch, n_bits, gamma_th, gamma_th_y, med_filt_size, orden_bits,
                   umbral_intensidad, borde) -> str:
    """Parámetros que determinan la fase absoluta y sus máscaras."""
    return (f"abs|{fringe_pitch}|{n_bits}|{float(gamma_th):g}|{float(gamma_th_y):g}|{int(med_filt_size)}|"
            f"{orden_bits}|{float(umbral_intensidad):g}|{int(borde)}")


def _fase_relativa_pose(
    dir_pose: Path, ruta: Path, n_step: int, gamma_th: float, gamma_th_y: float, prefijo: str,
    suavizado: float = 0.0, firma: str | None = None,
) -> str:
    datos = {"firma": np.array(firma or firma_relativa(n_step, suavizado))}
    for orient, eje in (("V", "X"), ("H", "Y")):
        rel = fase_relativa(cargar_secuencia(dir_pose / orient / prefijo, n_step), gamma_th, suavizado)
        datos[f"phi{eje}"] = rel["phi"].astype(np.float32)
        datos[f"A{eje}"] = rel["A"].astype(np.float32)
        datos[f"B{eje}"] = rel["B"].astype(np.float32)
        datos[f"q{eje}"] = rel["gm"].astype(np.float32)
    guardar_fases_pose(ruta, datos)

    todo = np.ones(datos["phiX"].shape, dtype=bool)
    _guardar_panel(
        ruta.with_suffix(".png"),
        [
            _imagen_color(datos["phiX"], datos["qX"] >= gamma_th),
            _imagen_color(datos["phiY"], datos["qY"] >= gamma_th_y),
            _imagen_color(datos["qX"], todo, cv2.COLORMAP_VIRIDIS),
            _imagen_color(datos["qY"], todo, cv2.COLORMAP_VIRIDIS),
        ],
        ["phi X (V)", "phi Y (H)", "modulacion X", "modulacion Y"],
    )
    return (
        f"  [{dir_pose.name}] modulación mediana X={np.median(datos['qX']):.3f} "
        f"Y={np.median(datos['qY']):.3f} -> '{ruta.name}'"
    )


def etapa_fase_absoluta(
    dir_ordenadas: Path,
    dir_salida: Path,
    categorias: Sequence[str],
    fringe_pitch: int = 18,
    n_step: int = 18,
    n_bits: int = 6,
    gamma_th: float = 0.15,
    med_filt_size: int = 5,
    orden_bits: str = "auto",
    umbral_intensidad: float = 25.0,
    borde: int = 15,
    prefijo: str = "P18_F",
    rehacer: bool = False,
    gamma_th_y: float | None = None,
) -> list[Path]:
    """Desenvuelve la fase relativa con el código Gray y calcula las coordenadas del proyector.

    Requiere `pose_XX_relativa.npz` (etapa anterior). Salida `<dir_salida>/<categoria>/pose_XX.npz`
    con `Fx`, `Fy` (fase absoluta), `up`, `vp` (píxeles del proyector), `qFx`, `qFy`, `Itex`,
    `MaskX`, `MaskY` y `MaskC = MaskX & MaskY` (como `RecoveryPhases_objects.m`).

    `gamma_th_y` es el umbral de modulación de las franjas horizontales (fase Y). Es menor que el de
    X porque el DMD en diamante del LightCrafter 4500 reproduce con poco contraste las franjas
    horizontales finas, y aun así Fy es la fase más sensible a la profundidad en este montaje.
    """
    gamma_th_y = gamma_th if gamma_th_y is None else gamma_th_y
    generados = []
    for categoria in categorias:
        poses = listar_poses(categoria)
        if not poses:
            print(f"[AVISO] No hay poses organizadas de '{categoria}', se omite.")
            continue
        print(f"\n=== Fase absoluta: '{categoria}' ({len(poses)} poses) ===")
        firma = firma_absoluta(fringe_pitch, n_bits, gamma_th, gamma_th_y, med_filt_size, orden_bits,
                               umbral_intensidad, borde)
        pendientes = []
        for dir_pose in poses:
            ruta_rel = rutas.fase_relativa(categoria, dir_pose.name)
            if not ruta_rel.exists():
                raise FileNotFoundError(
                    f"Falta '{ruta_rel}'. Ejecuta antes la etapa 'fase_relativa'."
                )
            ruta = rutas.fase_absoluta(categoria, dir_pose.name)
            generados.append(ruta)
            if not rehacer and _actualizado(ruta, [*_imagenes_pose(dir_pose), ruta_rel], firma):
                print(f"  [{dir_pose.name}] sin cambios, se reutiliza '{ruta.name}'")
            else:
                pendientes.append((dir_pose, ruta_rel, ruta))
        parametros = dict(
            fringe_pitch=fringe_pitch, n_step=n_step, n_bits=n_bits, umbrales=(gamma_th, gamma_th_y),
            med_filt_size=med_filt_size, orden_bits=orden_bits, umbral_intensidad=umbral_intensidad,
            borde=borde, prefijo=prefijo, firma=firma,
        )
        for mensaje in _en_paralelo(
            lambda d, rr, r: _fase_absoluta_pose(d, rr, r, **parametros), pendientes
        ):
            print(mensaje)
    return generados


def _fase_absoluta_pose(
    dir_pose: Path,
    ruta_rel: Path,
    ruta: Path,
    fringe_pitch: int,
    n_step: int,
    n_bits: int,
    umbrales: tuple[float, float],
    med_filt_size: int,
    orden_bits: str,
    umbral_intensidad: float,
    borde: int,
    prefijo: str,
    firma: str = "",
) -> str:
    """Fase absoluta de una pose (V -> X, H -> Y). Devuelve la línea de resumen."""
    rel = cargar_fases_pose(ruta_rel)
    datos: dict[str, np.ndarray] = {"firma": np.array(firma)}
    # Textura = imagen blanca (último frame de la carpeta H); solo se leen las imágenes necesarias
    blanco = cargar_secuencia(dir_pose / "H" / prefijo, 1, inicio=n_step + n_bits + 1)[0]
    itex = np.clip(blanco, 0, 255).astype(np.uint8)
    for (orient, eje, nombre), umbral in zip((("V", "X", "x"), ("H", "Y", "y")), umbrales):
        gray = cargar_secuencia(dir_pose / orient / prefijo, n_bits, inicio=n_step)
        phi = rel[f"phi{eje}"].astype(np.float64)
        bits = bits_gray(gray, rel[f"A{eje}"].astype(np.float64), med_filt_size)
        orden = orden_bits
        if orden == "auto":
            orden, _ = detectar_orden_bits(
                phi, bits, fringe_pitch, rel[f"q{eje}"] >= umbral, med_filt_size
            )
        k = decodificar_gray(bits, orden)
        fase_abs = fase_absoluta(phi, k, fringe_pitch, med_filt_size)
        datos[f"F{nombre}"] = fase_abs.astype(np.float32)
        datos[f"{'u' if eje == 'X' else 'v'}p"] = coordenada_proyector(fase_abs, fringe_pitch).astype(np.float32)
        datos[f"k{eje}"] = k.astype(np.int16)
        datos[f"qF{nombre}"] = rel[f"q{eje}"]
        datos[f"B{eje}"] = rel[f"B{eje}"]
        datos[f"Mask{eje}"] = mascara_valida(rel[f"q{eje}"], itex, umbral, umbral_intensidad, borde)
        datos[f"orden_bits_{orient}"] = np.array(orden)
    datos["Itex"] = itex
    datos["MaskC"] = datos["MaskX"] & datos["MaskY"]

    guardar_fases_pose(ruta, datos)
    _guardar_panel(
        ruta.with_suffix(".png"),
        [itex, _imagen_color(datos["up"], datos["MaskX"]), _imagen_color(datos["vp"], datos["MaskY"])],
        ["textura", "u_p (Fx)", "v_p (Fy)"],
    )
    if not np.any(datos["MaskX"]):
        return f"  [{dir_pose.name}] [AVISO] sin píxeles válidos en X"
    return (
        f"  [{dir_pose.name}] bits Gray V={datos['orden_bits_V']} H={datos['orden_bits_H']} | "
        f"válidos X={100 * datos['MaskX'].mean():.1f}% Y={100 * datos['MaskY'].mean():.1f}% | "
        f"u_p=[{np.percentile(datos['up'][datos['MaskX']], 1):.0f}, "
        f"{np.percentile(datos['up'][datos['MaskX']], 99):.0f}] px -> '{ruta.name}'"
    )


def guardar_npz_atomico(ruta: Path, **datos) -> None:
    """`np.savez_compressed` a un temporal y luego renombrado atómico.

    Así quien lea el archivo mientras se escribe (la interfaz web) ve la versión anterior completa
    o la nueva completa, nunca un zip a medias (`BadZipFile`).
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")  # no termina en .npz: nadie lo confunde con un resultado
    try:
        with open(tmp, "wb") as f:
            np.savez_compressed(f, **datos)
        os.replace(tmp, ruta)
    finally:
        tmp.unlink(missing_ok=True)


def guardar_fases_pose(ruta: Path, datos: dict) -> None:
    """Guarda un diccionario de mapas en un `.npz` comprimido."""
    guardar_npz_atomico(ruta, **{k: np.asarray(v) for k, v in datos.items()})


def cargar_fases_pose(ruta: Path) -> dict[str, np.ndarray]:
    with np.load(ruta) as datos:
        return {k: datos[k] for k in datos.files}


def cargar_fases_categoria(dir_fases: Path, categoria: str) -> tuple[list[str], list[dict[str, np.ndarray]]]:
    """Carga los `pose_XX.npz` (fase absoluta) de una categoría (de la configuración vigente),
    estén en la carpeta de su proceso o en la estructura anterior. `dir_fases` se ignora: queda
    por compatibilidad."""
    from datos_sistema import sesiones

    vigentes = sesiones.poses_vigentes(categoria)
    archivos = [rutas.fase_absoluta(categoria, p) for p in rutas.poses(categoria) if vigentes is None or p in vigentes]
    archivos = [r for r in archivos if r.exists()]
    if not archivos:
        raise FileNotFoundError(f"No hay fases absolutas de '{categoria}'. Ejecuta antes 'fase_absoluta'.")
    return [r.stem for r in archivos], [cargar_fases_pose(r) for r in archivos]
