"""Organiza y renombra las imágenes capturadas en secuencias H y V por pose.

Adapta la lógica de MATLAB (`SaveImagesFromVidAvi.m` y `savePatterns.m`) al
flujo actual de captura por carpetas en `capturas/` (`patron`, `plano`, `objeto`),
sin eliminar ni modificar las imágenes originales.

Para cada subcarpeta de adquisición:
1. Carga los 50 frames `.tiff` (o el `.avi` si no hubiera `.tiff`).
2. Detecta automáticamente el salto entre el patrón negro (`f_48`) y el blanco
   (`f_49`) mediante la derivada de la suma de intensidades (`max(diff(col))`).
3. Alinea circularmente (`circshift` / `np.roll`) la secuencia de 50 patrones
   para que el patrón blanco quede en la última posición (índice 49).
4. Guarda en `<salida>/<categoria>/pose_XX/H/` y `V/` los archivos renombrados
   como `P18_F00.tiff` .. `P18_F25.tiff` (conservando el formato `.tiff` sin
   pérdida):
   - `H/`: índices `[0..23, 48, 49]` (18 binarios H + 6 Gray H + negro + blanco)
   - `V/`: índices `[24..47, 48, 49]` (18 binarios V + 6 Gray V + negro + blanco)

Ejemplo de uso:
    python organizar_capturas.py --entrada capturas --salida capturas_ordenadas
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np


CATEGORIAS_POR_DEFECTO = ("patron", "plano", "objeto")
PREFIJO_POR_DEFECTO = "P18_F"
SEC_N = (24, 24, 2)  # (num_H, inicio_V, num_control_negro_blanco)


def cargar_frames_carpeta(carpeta_pose: Path) -> list[np.ndarray]:
    """Carga los frames `.tiff` ordenados de una carpeta de captura (o del `.avi`)."""
    archivos_tiff = sorted(carpeta_pose.glob("*.tiff")) + sorted(
        carpeta_pose.glob("*.tif")
    )
    if archivos_tiff:
        frames: list[np.ndarray] = []
        for ruta in archivos_tiff:
            img = cv2.imread(str(ruta), cv2.IMREAD_UNCHANGED)
            if img is None:
                raise OSError(f"No se pudo leer la imagen: {ruta}")
            if img.ndim == 3:
                img = img[:, :, 0]
            frames.append(img)
        return frames

    # Respaldo: leer desde archivo .avi si no existen archivos .tiff
    archivos_avi = sorted(carpeta_pose.glob("*.avi"))
    if not archivos_avi:
        raise FileNotFoundError(
            f"No se encontraron imágenes .tiff ni videos .avi en {carpeta_pose}"
        )

    cap = cv2.VideoCapture(str(archivos_avi[0]))
    if not cap.isOpened():
        raise OSError(f"No se pudo abrir el video: {archivos_avi[0]}")

    frames = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame.ndim == 3:
                frame = frame[:, :, 0]
            frames.append(frame)
    finally:
        cap.release()

    if not frames:
        raise ValueError(f"El video {archivos_avi[0]} no contiene frames")
    return frames


def detectar_indice_referencia(frames: Sequence[np.ndarray]) -> tuple[int, int]:
    """Detecta el índice (0-based) del frame negro y del frame blanco de referencia.

    Replica exactamente la lógica de `SaveImagesFromVidAvi.m`:
        col = shiftdim(sum(double(Frames), [1 2]));
        [~, PointN] = max(diff([col; col(1)]));
        if (PointN == 50), PointN = 0; end
        nImaRef = PointN + 1;
    """
    sumas = np.array([ np.sum(f, dtype=np.float64) for f in frames ], dtype=np.float64)
    # Diferencia circular entre cada frame y el siguiente: col(k+1) - col(k)
    sumas_circular = np.append(sumas, sumas[0])
    diffs = np.diff(sumas_circular)

    idx_negro = int(np.argmax(diffs))
    idx_blanco = (idx_negro + 1) % len(frames)
    return idx_negro, idx_blanco


def guardar_patrones_pose(
    directorio_pose: Path,
    prefijo: str,
    frames: Sequence[np.ndarray],
    idx_blanco: int | None,
    sec_n: tuple[int, int, int] = SEC_N,
    extension: str = ".tiff",
) -> None:
    """Alinea la secuencia con `idx_blanco` al final y guarda las carpetas `H/` y `V/`.

    Replica `savePatterns(Dire, nomb, patterns, nImaRef, secN)` de MATLAB.
    """
    n_imags = len(frames)
    if n_imags < sum(sec_n):
        raise ValueError(
            f"Se esperaban al menos {sum(sec_n)} frames y se recibieron {n_imags}"
        )

    # En MATLAB: circshift(patterns, size(patterns, 3) - nImaRef, 3)
    # En Python (0-based): desplazar para que idx_blanco quede en la posición n_imags - 1
    if idx_blanco is not None:
        desplazamiento = (n_imags - 1) - idx_blanco
        patrones = list(np.roll(np.asarray(frames), desplazamiento, axis=0))
    else:
        patrones = list(frames)

    dir_h = directorio_pose / "H"
    dir_v = directorio_pose / "V"
    dir_h.mkdir(parents=True, exist_ok=True)
    dir_v.mkdir(parents=True, exist_ok=True)

    # Índices para H: [0 .. secN(1)-1] + [Nimags-secN(3) .. Nimags-1]
    indices_h = list(range(0, sec_n[0])) + list(
        range(n_imags - sec_n[2], n_imags)
    )
    for k, i in enumerate(indices_h):
        ruta_h = dir_h / f"{prefijo}{k:02d}{extension}"
        if not cv2.imwrite(str(ruta_h), patrones[i]):
            raise OSError(f"No se pudo escribir {ruta_h}")

    # Índices para V: [secN(2) .. Nimags-1]
    for k, i in enumerate(range(sec_n[1], n_imags)):
        ruta_v = dir_v / f"{prefijo}{k:02d}{extension}"
        if not cv2.imwrite(str(ruta_v), patrones[i]):
            raise OSError(f"No se pudo escribir {ruta_v}")


def organizar_todas_las_capturas(
    directorio_entrada: Path,
    directorio_salida: Path,
    categorias: Sequence[str] = CATEGORIAS_POR_DEFECTO,
    prefijo: str = PREFIJO_POR_DEFECTO,
    extension: str = ".tiff",
) -> dict[str, list[Path]]:
    """Recorre las categorías en `directorio_entrada` y genera `pose_XX/H` y `V`."""
    if directorio_entrada.resolve() == directorio_salida.resolve():
        raise ValueError(
            "El directorio de salida debe ser distinto al de entrada para no "
            "modificar ni sobrescribir las capturas originales."
        )

    resumen: dict[str, list[Path]] = {}

    for categoria in categorias:
        dir_cat_in = directorio_entrada / categoria
        if not dir_cat_in.is_dir():
            print(f"[AVISO] No existe la carpeta '{dir_cat_in}', se omite.")
            continue

        subcarpetas = sorted(
            p for p in dir_cat_in.iterdir() if p.is_dir()
        )
        if not subcarpetas:
            print(f"[AVISO] No hay subcarpetas de captura en '{dir_cat_in}'.")
            continue

        print(
            f"\n=== Procesando categoría '{categoria}' "
            f"({len(subcarpetas)} poses encontradas) ==="
        )
        poses_creadas: list[Path] = []

        for idx_pose, carpeta_origen in enumerate(subcarpetas):
            frames = cargar_frames_carpeta(carpeta_origen)
            idx_negro, idx_blanco = detectar_indice_referencia(frames)

            nombre_pose = f"pose_{idx_pose:02d}"
            dir_pose_out = directorio_salida / categoria / nombre_pose

            guardar_patrones_pose(
                directorio_pose=dir_pose_out,
                prefijo=prefijo,
                frames=frames,
                idx_blanco=idx_blanco,
                sec_n=SEC_N,
                extension=extension,
            )
            poses_creadas.append(dir_pose_out)
            print(
                f"  [{nombre_pose}] origen='{carpeta_origen.name}' | "
                f"frames={len(frames)} | negro={idx_negro:02d}, blanco={idx_blanco:02d} "
                f"-> '{dir_pose_out}'"
            )

        resumen[categoria] = poses_creadas

    return resumen


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reordena y separa en H/ y V/ las capturas sin modificar la carpeta original."
    )
    parser.add_argument(
        "--entrada",
        type=Path,
        default=Path("capturas"),
        help="Carpeta raíz con las capturas originales (por defecto: capturas)",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=Path("capturas_ordenadas"),
        help="Carpeta donde se guardarán las poses organizadas (por defecto: capturas_ordenadas)",
    )
    parser.add_argument(
        "--categorias",
        nargs="+",
        default=list(CATEGORIAS_POR_DEFECTO),
        help="Subcarpetas a procesar (por defecto: patron plano objeto)",
    )
    parser.add_argument(
        "--prefijo",
        type=str,
        default=PREFIJO_POR_DEFECTO,
        help="Prefijo de los archivos de salida (por defecto: P18_F)",
    )
    parser.add_argument(
        "--ext",
        type=str,
        default=".tiff",
        choices=[".tiff", ".tif", ".png"],
        help="Extensión de imagen de salida (por defecto: .tiff)",
    )
    args = parser.parse_args()

    organizar_todas_las_capturas(
        directorio_entrada=args.entrada,
        directorio_salida=args.salida,
        categorias=args.categorias,
        prefijo=args.prefijo,
        extension=args.ext,
    )
    print("\n[OK] Organización de capturas finalizada exitosamente.")


if __name__ == "__main__":
    main()

