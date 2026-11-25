import json
from pathlib import Path
from collections.abc import Mapping

import cv2
import numpy as np

from datos_sistema import configuracion as cfg
from captura.patterns import generar_patrones_binarios


ANCHO = cfg.PROYECTOR_ANCHO
ALTO = cfg.PROYECTOR_ALTO
PERIODO = cfg.PERIODO
BITS_GRAY = cfg.N_BITS_GRAY
DIRECTORIO_SALIDA = cfg.DIR_PATRONES


def crear_patrones_uniformes(ancho: int, alto: int) -> list[tuple[str, np.ndarray]]:
    """Crea las imágenes completamente negras y completamente blancas."""
    forma = (alto, ancho)
    return [
        ("pat_black", np.zeros(forma, dtype=np.uint8)),
        ("pat_white", np.full(forma, 255, dtype=np.uint8)),
    ]


def crear_patrones_gray(
    ancho: int, alto: int, paso: int, orientacion: str, cantidad_bits: int = 6
) -> list[np.ndarray]:
    """Crea los planos de bits del código Gray espacial."""
    if cantidad_bits < 1:
        raise ValueError("cantidad_bits debe ser mayor que cero")

    longitud = ancho if orientacion == "vertical" else alto
    posiciones = np.arange(longitud) // paso
    patrones = []

    for bit in range(cantidad_bits - 1, -1, -1):
        valores_gray = posiciones ^ (posiciones >> 1)
        plano = ((valores_gray >> bit) & 1).astype(np.uint8) * 255
        if orientacion == "vertical":
            patrones.append(np.tile(plano, (alto, 1)))
        else:
            patrones.append(np.tile(plano[:, np.newaxis], (1, ancho)))

    return patrones


def crear_patrones_binarios_1px(
    ancho: int, alto: int, periodo: int, orientacion: str
) -> list[np.ndarray]:
    """Crea un corrimiento de un píxel hasta completar un período."""
    patrones = generar_patrones_binarios(
        width=ancho,
        height=alto,
        periodo=periodo,
        num_pasos=periodo,
        orientacion=orientacion,
    )
    return patrones


def crear_secuencia_completa(
    ancho: int = ANCHO,
    alto: int = ALTO,
    periodo: int = PERIODO,
    directorio: Path = DIRECTORIO_SALIDA,
    nombres: Mapping[str, str] | None = None,
) -> list[tuple[Path, str, np.ndarray, bool, bool]]:
    """Devuelve todos los patrones para guardarlos en una sola carpeta.

    ``nombres`` permite cambiar el prefijo de cada grupo. Sus claves son:
    ``binaria_vertical``, ``binaria_horizontal``, ``gray_vertical``,
    ``gray_horizontal``, ``uniforme_negro`` y ``uniforme_blanco``.
    """
    nombres_predeterminados = {
        "binaria_vertical": "pat_V_binary",
        "binaria_horizontal": "pat_H_binary",
        "gray_vertical": "pat_V_gray",
        "gray_horizontal": "pat_H_gray",
        "uniforme_negro": "pat_black",
        "uniforme_blanco": "pat_white",
    }
    if nombres is not None:
        nombres_predeterminados.update(nombres)

    secuencia = []

    for orientacion in ("horizontal", "vertical"):
        binarios = crear_patrones_binarios_1px(
            ancho, alto, periodo, orientacion
        )
        secuencia.extend(
            (
                directorio,
                nombres_predeterminados[f"binaria_{orientacion}"],
                patron,
                True,
                True,
            )
            for patron in binarios
        )

        patrones_gray = crear_patrones_gray(
            ancho, alto, periodo, orientacion, cantidad_bits=BITS_GRAY
        )
        secuencia.extend(
            (
                directorio,
                nombres_predeterminados[f"gray_{orientacion}"],
                patron,
                False,
                True,
            )
            for patron in patrones_gray
        )

    patrones_controles = crear_patrones_uniformes(ancho, alto)
    secuencia.extend(
        (
            directorio,
            nombres_predeterminados[clave],
            patron,
            False,
            False,
        )
        for clave, (_, patron) in zip(
            ("uniforme_negro", "uniforme_blanco"), patrones_controles
        )
    )
    return secuencia


def guardar_secuencia(
    secuencia: list[tuple[Path, str, np.ndarray, bool, bool]],
) -> None:
    """Guarda `f_XX.bmp` y `secuencia.json` con el contenido de cada índice."""
    descripcion = []
    for indice, (directorio, nombre, imagen, _, _) in enumerate(secuencia):
        ruta = directorio / f"f_{indice:02d}.bmp"
        directorio.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(ruta), imagen):
            raise OSError(f"No se pudo guardar el patrón: {ruta}")
        descripcion.append({"archivo": ruta.name, "tipo": nombre})
        print(f"Guardado: {ruta}")
    if secuencia:
        (secuencia[0][0] / "secuencia.json").write_text(
            json.dumps(
                {
                    "ancho": ANCHO, "alto": ALTO, "periodo": PERIODO, "bits_gray": BITS_GRAY,
                    "nota": "Gray en orden MSB -> LSB dentro de cada orientación",
                    "patrones": descripcion,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    guardar_secuencia(
        crear_secuencia_completa(
            ancho=ANCHO,
            alto=ALTO,
            periodo=PERIODO,
        ),
    )
