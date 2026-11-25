"""Organiza capturas crudas (imágenes o videos, con cualquier nombre) en secuencias H/V por pose.

Adapta `SaveImagesFromVidAvi.m` y `savePatterns.m`, pero acepta cualquier forma de captura:

- Carpetas con imágenes (.tiff, .tif, .png, .bmp, .jpg, .pgm; TIFF multipágina incluido), ordenadas
  por nombre de forma natural (`img_2` antes que `img_10`).
- Videos (.avi, .mp4, .mov, .mkv, ...). Si un video duplica las imágenes de su misma carpeta
  (como el `.avi` que guarda `capturar_patrones.py`) se usa solo una de las dos fuentes.
- Cualquier cantidad de frames: un ciclo exacto de 50 que empieza en cualquier patrón, varios ciclos
  seguidos (se promedian si la escena no cambió, o se separan en poses distintas si cambió), o
  grabaciones con frames perdidos (se separan en tramos continuos).

Para cada fuente:
1. Detecta los pares negro -> blanco (`f_48`, `f_49`) por la intensidad media de cada frame y
   asigna a cada frame su índice de patrón (equivale al `circshift` de MATLAB).
2. Agrupa los ciclos completos por escena (correlación de la imagen blanca) y promedia los ciclos de
   una misma escena. Descarta ciclos donde la escena se movió durante la captura.
3. Verifica la estructura de la secuencia (corrimientos cíclicos en H y V).
4. Determina la categoría (`patron`, `plano`, `objeto`) por el nombre de la carpeta o archivo y, si
   no hay pista en el nombre, por el contenido: grilla de círculos -> `patron`; para distinguir
   `plano` de `objeto` se pregunta en la terminal (o se asigna `objeto` y se marca para verificar).
5. Escribe `<salida>/<categoria>/pose_XX/H/P18_F00..25` y `V/` y registra todo en
   `<salida>/manifiesto.json`. Las capturas originales nunca se modifican ni se borran.

La organización es incremental: las fuentes ya registradas en el manifiesto se omiten y las nuevas
reciben el siguiente número de pose. `--rehacer` reconstruye todo desde cero.

Ejemplos:
    python organizar_capturas.py                         # todo lo que haya en capturas/
    python organizar_capturas.py --entrada ~/Descargas/sesion3 --categoria objeto
    python organizar_capturas.py --simular               # solo muestra qué haría
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

import configuracion as cfg


EXT_IMAGEN = {".tiff", ".tif", ".png", ".bmp", ".jpg", ".jpeg", ".pgm"}
EXT_VIDEO = {".avi", ".mp4", ".mov", ".mkv", ".mj2", ".wmv", ".m4v", ".mpg", ".mpeg"}

PALABRAS_CATEGORIA = {
    "patron": ("patron", "pattern", "calib", "circulo", "circle", "tablero", "board", "target", "grid"),
    "plano": ("plano", "plane", "flat", "pared", "wall"),
    "objeto": ("objeto", "object", "obj", "pieza", "muestra", "sample", "escena", "scene"),
}

UMBRAL_MISMA_ESCENA = 0.98   # correlación mínima entre imágenes blancas de ciclos de una misma pose
UMBRAL_ESTABILIDAD = 0.97    # correlación mínima entre el fondo de H y de V dentro de un ciclo
NOMBRE_MANIFIESTO = "manifiesto.json"


# ==============================================================================
# Descubrimiento de fuentes
# ==============================================================================


@dataclass
class Fuente:
    """Una captura cruda: un video, o las imágenes de una carpeta."""

    ruta: Path
    tipo: str                       # "video" | "imagenes"
    archivos: list[Path] = field(default_factory=list)

    def firma(self) -> str:
        """Identificador estable para el manifiesto (ruta + tamaño + fecha de modificación)."""
        partes = []
        for archivo in self.archivos:
            st = archivo.stat()
            partes.append(f"{archivo.name}:{st.st_size}:{int(st.st_mtime)}")
        resumen = hashlib.sha1("\n".join(partes).encode()).hexdigest()[:12]
        return f"{self.tipo}|{_ruta_relativa(self.ruta)}|{len(partes)}|{resumen}"


def _clave_natural(ruta: Path) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", ruta.name)]


def _ruta_relativa(ruta: Path) -> str:
    try:
        return str(ruta.resolve().relative_to(cfg.RAIZ))
    except ValueError:
        return str(ruta.resolve())


def _contar_frames_video(ruta: Path) -> int:
    cap = cv2.VideoCapture(str(ruta))
    try:
        return int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if cap.isOpened() else 0
    finally:
        cap.release()


def descubrir_fuentes(raices: Sequence[Path], excluir: Sequence[Path] = ()) -> list[Fuente]:
    """Recorre las raíces y devuelve las fuentes de frames encontradas, en orden natural."""
    excluidos = {p.resolve() for p in excluir}
    fuentes: list[Fuente] = []

    for raiz in raices:
        raiz = raiz.expanduser()
        if raiz.is_file():
            ext = raiz.suffix.lower()
            if ext in EXT_VIDEO:
                fuentes.append(Fuente(raiz, "video", [raiz]))
            elif ext in EXT_IMAGEN:
                fuentes.append(Fuente(raiz, "imagenes", [raiz]))
            continue
        if not raiz.is_dir():
            print(f"[AVISO] No existe '{raiz}', se omite.")
            continue

        for carpeta, subdirs, archivos in os.walk(raiz):
            carpeta_p = Path(carpeta)
            subdirs[:] = sorted(
                d for d in subdirs
                if not d.startswith(".") and (carpeta_p / d).resolve() not in excluidos
            )
            rutas = sorted((carpeta_p / a for a in archivos if not a.startswith(".")), key=_clave_natural)
            imagenes = [r for r in rutas if r.suffix.lower() in EXT_IMAGEN]
            videos = [r for r in rutas if r.suffix.lower() in EXT_VIDEO]

            if imagenes:
                fuentes.append(Fuente(carpeta_p, "imagenes", imagenes))
            for video in videos:
                # El .avi que acompaña a los .tiff de una misma captura es redundante
                if imagenes and _contar_frames_video(video) == len(imagenes):
                    continue
                fuentes.append(Fuente(video, "video", [video]))
    return fuentes


# ==============================================================================
# Lectura de frames
# ==============================================================================


def _a_gris(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        img = img[:, :, :3]
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def cargar_frames(fuente: Fuente) -> list[np.ndarray]:
    """Lee todos los frames de la fuente en escala de grises conservando la profundidad de bits."""
    frames: list[np.ndarray] = []
    if fuente.tipo == "video":
        cap = cv2.VideoCapture(str(fuente.ruta))
        if not cap.isOpened():
            raise OSError(f"No se pudo abrir el video: {fuente.ruta}")
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frames.append(_a_gris(frame))
        finally:
            cap.release()
        return frames

    for ruta in fuente.archivos:
        if ruta.suffix.lower() in (".tif", ".tiff"):
            ok, paginas = cv2.imreadmulti(str(ruta), flags=cv2.IMREAD_UNCHANGED)
            if ok and paginas:
                frames.extend(_a_gris(p) for p in paginas)
                continue
        img = cv2.imread(str(ruta), cv2.IMREAD_UNCHANGED)
        if img is None:
            print(f"[AVISO] No se pudo leer '{ruta}', se omite.")
            continue
        frames.append(_a_gris(img))

    formas = {f.shape for f in frames}
    if len(formas) > 1:
        raise ValueError(f"Las imágenes de '{fuente.ruta}' tienen tamaños distintos: {formas}")
    return frames


# ==============================================================================
# Segmentación en ciclos de la secuencia proyectada
# ==============================================================================


def detectar_pares_negro_blanco(medias: np.ndarray, circular: bool) -> list[int]:
    """Índices de los frames blancos precedidos por un frame negro (último par de la secuencia)."""
    lo, hi = float(np.min(medias)), float(np.max(medias))
    rango = max(hi - lo, 1e-9)
    n = len(medias)
    blancos = []
    for i in range(0 if circular else 1, n):
        anterior = medias[i - 1]  # con i = 0 y circular, toma el último frame
        if anterior <= lo + 0.2 * rango and medias[i] >= hi - 0.2 * rango:
            blancos.append(i)
    return blancos


def _correlacion(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float64).ravel()[::7]
    b = b.astype(np.float64).ravel()[::7]
    a = a - a.mean()
    b = b - b.mean()
    den = np.sqrt(np.dot(a, a) * np.dot(b, b))
    return float(np.dot(a, b) / den) if den > 0 else 0.0


@dataclass
class Secuencia:
    """Un ciclo completo reordenado (índice 0 = f_00, último = f_49) y su procedencia."""

    frames: np.ndarray            # (L, H, W)
    indices_origen: list[int]     # índice del frame original para cada patrón (del primer ciclo)
    ciclos_promediados: int
    avisos: list[str] = field(default_factory=list)


def segmentar_secuencias(frames: list[np.ndarray], largo: int) -> tuple[list[Secuencia], list[str]]:
    """Divide los frames de una fuente en secuencias completas de `largo` patrones."""
    avisos: list[str] = []
    n = len(frames)
    if n < largo:
        return [], [f"solo {n} frames; se necesitan al menos {largo}"]

    medias = np.array([float(np.mean(f)) for f in frames])

    if n == largo:
        # Un ciclo exacto capturado desde cualquier punto del loop del proyector
        blancos = detectar_pares_negro_blanco(medias, circular=True)
        if not blancos:
            return [], ["no se encontró el par negro -> blanco"]
        if len(blancos) > 1:
            avisos.append(f"varios pares negro->blanco {blancos}; se usa el de mayor salto")
            blancos = [max(blancos, key=lambda i: medias[i] - medias[i - 1])]
        w = blancos[0]
        orden = [(w + 1 + p) % n for p in range(largo)]
        return [Secuencia(np.stack([frames[i] for i in orden]), orden, 1)], avisos

    blancos = detectar_pares_negro_blanco(medias, circular=False)
    if not blancos:
        return [], ["no se encontró el par negro -> blanco"]

    # Tramos continuos: blancos separados exactamente por múltiplos de `largo`
    tramos: list[list[int]] = [[blancos[0]]]
    for w in blancos[1:]:
        if (w - tramos[-1][-1]) % largo == 0:
            tramos[-1].append(w)
        else:
            avisos.append(
                f"salto inesperado entre frames {tramos[-1][-1]} y {w} (frame perdido o extra); "
                f"se separa en tramos"
            )
            tramos.append([w])

    secuencias: list[Secuencia] = []
    limite_inferior = 0
    for t_idx, tramo in enumerate(tramos):
        limite_superior = tramos[t_idx + 1][0] - largo if t_idx + 1 < len(tramos) else n - 1
        # Ciclos completos dentro del tramo: ventanas [w - largo + 1, w]
        ventanas = [w for w in tramo if w - largo + 1 >= limite_inferior]
        if not ventanas:
            # Ciclo partido alrededor del único blanco: se completa con frames antes y después
            w = tramo[0]
            orden = [w - largo + 1 + p for p in range(largo)]
            orden = [i if i >= limite_inferior else i + largo for i in orden]
            if all(limite_inferior <= i <= limite_superior for i in orden):
                secuencias.append(Secuencia(np.stack([frames[i] for i in orden]), orden, 1))
            else:
                avisos.append(f"tramo alrededor del frame {w} incompleto; se descarta")
        else:
            secuencias.extend(_agrupar_ciclos(frames, ventanas, largo, avisos))
        limite_inferior = tramo[-1] + 1
    return secuencias, avisos


def _ciclo_estable(ciclo: np.ndarray) -> float:
    """Correlación entre el fondo de los corrimientos H y V: ~1 si la escena no se movió."""
    n = cfg.N_PASOS
    a_h = ciclo[:n].astype(np.float32).mean(axis=0)
    a_v = ciclo[cfg.IMAGENES_POR_ORIENTACION : cfg.IMAGENES_POR_ORIENTACION + n].astype(np.float32).mean(axis=0)
    return _correlacion(a_h, a_v)


def _agrupar_ciclos(
    frames: list[np.ndarray], ventanas: list[int], largo: int, avisos: list[str]
) -> list[Secuencia]:
    """Agrupa ciclos consecutivos de la misma escena y los promedia."""
    grupos: list[list[int]] = []
    referencia = None
    for w in ventanas:
        ciclo = np.stack(frames[w - largo + 1 : w + 1])
        estabilidad = _ciclo_estable(ciclo)
        if estabilidad < UMBRAL_ESTABILIDAD:
            avisos.append(
                f"ciclo que termina en el frame {w}: la escena se movió (corr={estabilidad:.3f}); se descarta"
            )
            referencia = None
            continue
        if referencia is not None and _correlacion(frames[w], referencia) >= UMBRAL_MISMA_ESCENA:
            grupos[-1].append(w)
        else:
            grupos.append([w])
            referencia = frames[w]

    secuencias = []
    for grupo in grupos:
        primero = list(range(grupo[0] - largo + 1, grupo[0] + 1))
        if len(grupo) == 1:
            pila = np.stack([frames[i] for i in primero])
        else:
            pila = np.mean(
                [np.stack(frames[w - largo + 1 : w + 1]).astype(np.float32) for w in grupo], axis=0
            ).astype(np.float32)
        secuencias.append(Secuencia(pila, primero, len(grupo)))
    return secuencias


# ==============================================================================
# Verificación y clasificación
# ==============================================================================


def verificar_secuencia(sec: np.ndarray) -> dict[str, float]:
    """Comprueba la alineación de la secuencia y estima la modulación de H y V.

    `pureza_*`: fracción de la energía temporal (sin DC) de los corrimientos que cae en la frecuencia
    fundamental. Con la secuencia bien alineada es cercana a 1; si se coló un frame Gray, negro o
    blanco entre los corrimientos (frame perdido) cae por debajo de ~0.5.
    """
    n, por_orient = cfg.N_PASOS, cfg.IMAGENES_POR_ORIENTACION
    resultado = {}
    for nombre, inicio in (("H", 0), ("V", por_orient)):
        bloque = sec[inicio : inicio + n, ::4, ::4].astype(np.float64)
        media = bloque.mean(axis=0)
        espectro = np.abs(np.fft.rfft(bloque, axis=0)) ** 2
        energia = espectro[1:].sum(axis=0)
        iluminado = (media > cfg.UMBRAL_INTENSIDAD / 2) & (energia > 0)
        if not np.any(iluminado):
            resultado[f"pureza_{nombre}"] = 0.0
            resultado[f"modulacion_{nombre}"] = 0.0
            continue
        pureza = espectro[1][iluminado] / energia[iluminado]
        modulacion = 2.0 * np.sqrt(espectro[1][iluminado]) / n / media[iluminado]
        resultado[f"pureza_{nombre}"] = float(np.median(pureza))
        resultado[f"modulacion_{nombre}"] = float(np.median(modulacion))
    medias = sec.reshape(len(sec), -1).mean(axis=1)
    resultado["negro_es_minimo"] = float(np.argmin(medias) == len(sec) - 2)
    resultado["blanco_es_maximo"] = float(np.argmax(medias) == len(sec) - 1)
    return resultado


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return texto.lower()


def categoria_por_nombre(ruta: Path, raiz: Path | None) -> str | None:
    """Busca palabras clave en la ruta (desde la más cercana al archivo hacia la raíz)."""
    partes = list(ruta.parts)
    if raiz is not None:
        try:
            partes = list(ruta.resolve().relative_to(raiz.resolve()).parts) or [ruta.name]
        except ValueError:
            pass
    for parte in reversed(partes):
        tokens = re.split(r"[^a-z]+", _normalizar(Path(parte).stem))
        for categoria, palabras in PALABRAS_CATEGORIA.items():
            if any(tok.startswith(p) for tok in tokens if tok for p in palabras):
                return categoria
    return None


def categoria_por_contenido(sec: np.ndarray, descripcion: str, interactivo: bool) -> tuple[str, str]:
    """Clasifica por contenido: si hay grilla de círculos es `patron`.

    Distinguir `plano` de `objeto` solo por la imagen no es fiable en este montaje (los planos de
    referencia incluyen la placa de fondo a otra profundidad), así que se pregunta al usuario cuando
    hay terminal; si no, se asigna `objeto` y se deja constancia en el manifiesto.
    """
    from calibracion_estereo import detectar_puntos_tablero

    blanco = np.clip(sec[-1], 0, 255).astype(np.uint8)
    try:
        detectar_puntos_tablero(
            blanco, (cfg.PATRON_COLUMNAS, cfg.PATRON_FILAS), cfg.PATRON_TIPO, cfg.PATRON_COLOR_CIRCULOS
        )
        return "patron", "contenido: grilla de círculos detectada"
    except RuntimeError:
        pass

    if interactivo:
        while True:
            resp = input(
                f"  [?] '{descripcion}' no indica su categoría y no tiene grilla de círculos. "
                f"¿Es plano (p), objeto (o) o se omite (s)? "
            ).strip().lower()
            if resp in ("p", "plano"):
                return "plano", "indicada por el usuario al organizar"
            if resp in ("o", "objeto", ""):
                return "objeto", "indicada por el usuario al organizar"
            if resp in ("s", "omitir"):
                return "omitir", "omitida por el usuario"
    return "objeto", "por defecto (sin pista en el nombre): VERIFICAR"


# ==============================================================================
# Escritura y manifiesto
# ==============================================================================


def guardar_pose(
    dir_pose: Path, secuencia: np.ndarray, prefijo: str, extension: str = ".tiff"
) -> None:
    """Escribe `H/` = [f_00..f_23, negro, blanco] y `V/` = [f_24..f_47, negro, blanco] (`savePatterns.m`)."""
    largo = len(secuencia)
    por_orient = cfg.IMAGENES_POR_ORIENTACION
    indices = {
        "H": list(range(0, por_orient)) + [largo - 2, largo - 1],
        "V": list(range(por_orient, 2 * por_orient)) + [largo - 2, largo - 1],
    }
    for orient, lista in indices.items():
        carpeta = dir_pose / orient
        carpeta.mkdir(parents=True, exist_ok=True)
        for k, i in enumerate(lista):
            ruta = carpeta / f"{prefijo}{k:02d}{extension}"
            if not cv2.imwrite(str(ruta), secuencia[i]):
                raise OSError(f"No se pudo escribir {ruta}")


def cargar_manifiesto(dir_salida: Path) -> dict:
    ruta = dir_salida / NOMBRE_MANIFIESTO
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return {"version": 1, "poses": []}


def guardar_manifiesto(dir_salida: Path, manifiesto: dict) -> None:
    dir_salida.mkdir(parents=True, exist_ok=True)
    (dir_salida / NOMBRE_MANIFIESTO).write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _siguiente_pose(dir_salida: Path, categoria: str, manifiesto: dict) -> int:
    usados = {p["pose"] for p in manifiesto["poses"] if p["categoria"] == categoria}
    # Índices de poses borradas desde la interfaz (archivos.py): no se reutilizan, para que una pose
    # nueva nunca tome el nombre de una vieja (las calibraciones guardan los nombres de sus poses)
    usados |= set(range(int(manifiesto.get("ultimo_indice", {}).get(categoria, -1)) + 1))
    existentes = {
        int(p.name[5:]) for p in (dir_salida / categoria).glob("pose_*") if p.name[5:].isdigit()
    } if (dir_salida / categoria).is_dir() else set()
    todos = usados | existentes
    return max(todos) + 1 if todos else 0


def organizar(
    entradas: Sequence[Path],
    dir_salida: Path,
    categoria_forzada: str | None = None,
    categorias: Sequence[str] = cfg.CATEGORIAS,
    prefijo: str = cfg.PREFIJO_ORDENADAS,
    rehacer: bool = False,
    simular: bool = False,
    interactivo: bool | None = None,
) -> dict[str, list[str]]:
    """Organiza todas las fuentes encontradas en `entradas`. Devuelve {categoria: [poses nuevas]}."""
    for entrada in entradas:
        if entrada.resolve() == dir_salida.resolve():
            raise ValueError("La carpeta de salida debe ser distinta a la de entrada.")

    if interactivo is None:
        interactivo = sys.stdin.isatty()
    manifiesto = cargar_manifiesto(dir_salida)
    hay_poses_previas = any((dir_salida / c).glob("pose_*") for c in cfg.CATEGORIAS if (dir_salida / c).is_dir())
    if not manifiesto["poses"] and hay_poses_previas and not rehacer:
        print(
            "[INFO] Hay poses organizadas sin manifiesto (versión anterior del organizador): "
            "se reconstruyen desde las capturas crudas."
        )
        rehacer = True
    if rehacer:
        manifiesto = {"version": 1, "poses": []}
        siguiente: dict[str, int] = {c: 0 for c in cfg.CATEGORIAS}
    else:
        siguiente = {c: _siguiente_pose(dir_salida, c, manifiesto) for c in cfg.CATEGORIAS}

    ya_registradas = {p["firma"] + f"#{p['segmento']}" for p in manifiesto["poses"]}
    fuentes = descubrir_fuentes(entradas, excluir=[dir_salida, cfg.DIR_RESULTADOS])
    print(f"[INFO] {len(fuentes)} fuentes de captura encontradas en: {', '.join(map(str, entradas))}")

    nuevas: dict[str, list[str]] = {}
    for fuente in fuentes:
        firma = fuente.firma()
        if f"{firma}#0" in ya_registradas and not rehacer:
            print(f"  [=] '{_ruta_relativa(fuente.ruta)}' ya organizada, se omite.")
            continue

        frames = cargar_frames(fuente)
        secuencias, avisos = segmentar_secuencias(frames, cfg.IMAGENES_POR_CICLO)
        for aviso in avisos:
            print(f"  [AVISO] '{_ruta_relativa(fuente.ruta)}': {aviso}")
        if not secuencias:
            print(f"  [X] '{_ruta_relativa(fuente.ruta)}' ({len(frames)} frames): sin ciclos completos, se omite.")
            continue

        raiz = next((e for e in entradas if _es_subruta(fuente.ruta, e)), None)
        for s_idx, sec in enumerate(secuencias):
            if f"{firma}#{s_idx}" in ya_registradas and not rehacer:
                continue
            if categoria_forzada:
                categoria, metodo = categoria_forzada, "indicada por el usuario"
            else:
                categoria = categoria_por_nombre(fuente.ruta, raiz)
                metodo = "nombre de carpeta/archivo"
                if categoria is None:
                    categoria, metodo = categoria_por_contenido(
                        sec.frames, _ruta_relativa(fuente.ruta), interactivo and not simular
                    )
            if categoria not in categorias:
                continue

            calidad = verificar_secuencia(sec.frames)
            pose = siguiente[categoria]
            siguiente[categoria] += 1
            nombre_pose = f"pose_{pose:02d}"
            dir_pose = dir_salida / categoria / nombre_pose

            estado = "SIMULADO" if simular else "OK"
            print(
                f"  [{estado}] '{_ruta_relativa(fuente.ruta)}'"
                f"{f' (secuencia {s_idx + 1}/{len(secuencias)})' if len(secuencias) > 1 else ''}"
                f" -> {categoria}/{nombre_pose} | {metodo} | ciclos={sec.ciclos_promediados} | "
                f"modulación H={calidad['modulacion_H']:.2f} V={calidad['modulacion_V']:.2f}"
            )
            for orient in ("H", "V"):
                if calidad[f"pureza_{orient}"] < 0.5:
                    print(
                        f"      [AVISO] corrimientos {orient} poco sinusoidales "
                        f"(pureza={calidad[f'pureza_{orient}']:.2f}): posible frame perdido o desalineado."
                    )
                if calidad[f"modulacion_{orient}"] < cfg.GAMMA_TH:
                    print(
                        f"      [AVISO] modulación {orient} baja ({calidad[f'modulacion_{orient}']:.2f} < "
                        f"{cfg.GAMMA_TH}): franjas casi sin contraste (desenfoque o exposición)."
                    )
            if not (calidad["negro_es_minimo"] and calidad["blanco_es_maximo"]):
                print("      [AVISO] el negro/blanco no son los frames extremos: revisa la captura.")
            if simular:
                continue

            guardar_pose(dir_pose, sec.frames, prefijo)
            manifiesto["poses"].append(
                {
                    "categoria": categoria,
                    "pose": pose,
                    "carpeta": _ruta_relativa(dir_pose),
                    "fuente": _ruta_relativa(fuente.ruta),
                    "tipo_fuente": fuente.tipo,
                    "firma": firma,
                    "segmento": s_idx,
                    "frames_fuente": len(frames),
                    "indices_origen": sec.indices_origen,
                    "ciclos_promediados": sec.ciclos_promediados,
                    "metodo_categoria": metodo,
                    "calidad": calidad,
                    "fecha": datetime.now().isoformat(timespec="seconds"),
                }
            )
            nuevas.setdefault(categoria, []).append(nombre_pose)
            guardar_manifiesto(dir_salida, manifiesto)

    if not simular:
        guardar_manifiesto(dir_salida, manifiesto)
    return nuevas


def _es_subruta(ruta: Path, raiz: Path) -> bool:
    try:
        ruta.resolve().relative_to(raiz.resolve())
        return True
    except ValueError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Organiza capturas crudas (imágenes o videos) en poses H/V sin modificar los originales.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--entrada", type=Path, nargs="+", default=[cfg.DIR_CAPTURAS],
                        help=f"Carpetas o archivos con capturas crudas (por defecto: {cfg.DIR_CAPTURAS})")
    parser.add_argument("--salida", type=Path, default=cfg.DIR_ORDENADAS,
                        help=f"Carpeta de capturas organizadas (por defecto: {cfg.DIR_ORDENADAS})")
    parser.add_argument("--categoria", choices=cfg.CATEGORIAS, default=None,
                        help="Fuerza la categoría de todas las capturas de la entrada")
    parser.add_argument("--categorias", nargs="+", default=list(cfg.CATEGORIAS),
                        help="Solo organiza estas categorías")
    parser.add_argument("--rehacer", action="store_true",
                        help="Ignora el manifiesto y reorganiza todo desde cero")
    parser.add_argument("--simular", action="store_true",
                        help="Muestra qué se haría sin escribir nada")
    args = parser.parse_args()

    nuevas = organizar(args.entrada, args.salida, args.categoria, args.categorias,
                       rehacer=args.rehacer, simular=args.simular)
    total = sum(len(v) for v in nuevas.values())
    print(f"\n[OK] Organización finalizada: {total} poses nuevas "
          f"({', '.join(f'{c}: {len(v)}' for c, v in nuevas.items()) or 'ninguna'}).")


if __name__ == "__main__":
    main()
