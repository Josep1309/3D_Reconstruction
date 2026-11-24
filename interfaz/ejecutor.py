"""Ejecuta el pipeline en un subproceso con la configuración que envía la interfaz web.

Uso (lo lanza `servidor.py`; no hace falta correrlo a mano):
    python interfaz/ejecutor.py <config.json>

El JSON puede tener:
    etapas       {"captura": true, ...}        sobrescribe pipeline.ETAPAS
    categorias   ["plano", "objeto"]
    captura      {"categoria", "poses", "ciclos", "esperar_enter"}
    rehacer, fase, calibracion
    simular      ruta de una captura existente para usar la cámara simulada (o null)

La vista en vivo de la cámara se escribe en `<resultados>/.vivo/frame.jpg` como máximo ~6 veces por
segundo, desde un hilo aparte para no retrasar la adquisición. Las líneas que empiezan con `@@` son
mensajes para el servidor (estado de la captura en vivo), no para el usuario.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from functools import partial
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import matplotlib  # noqa: E402

matplotlib.use("Agg")  # la interfaz web reemplaza a las ventanas de matplotlib

import cv2  # noqa: E402

import configuracion as cfg  # noqa: E402
import pipeline  # noqa: E402

DIR_VIVO = cfg.DIR_RESULTADOS / ".vivo"


class VistaEnVivo:
    """Guarda el último frame recibido y lo escribe como JPEG en un hilo, a cadencia limitada."""

    def __init__(self, total: int, intervalo_s: float = 0.15) -> None:
        self.total = total
        self.intervalo_s = intervalo_s
        self.ultimo: tuple[int, object] | None = None
        self.escrito = -1
        self.activo = True
        DIR_VIVO.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=self._bucle, daemon=True).start()

    def __call__(self, indice: int, frame) -> None:
        self.ultimo = (indice, frame)  # solo una asignación: no frena la captura

    def _bucle(self) -> None:
        while self.activo:
            time.sleep(self.intervalo_s)
            dato = self.ultimo
            if dato is None or dato[0] == self.escrito:
                continue
            indice, frame = dato
            img = frame if frame.dtype == "uint8" else (frame >> 8).astype("uint8")
            img = cv2.resize(img, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
            tmp = DIR_VIVO / "frame_tmp.jpg"
            cv2.imwrite(str(tmp), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            os.replace(tmp, DIR_VIVO / "frame.jpg")  # reemplazo atómico: el navegador nunca lee a medias
            self.escrito = indice
            print(f"@@vivo {indice + 1} {self.total}", flush=True)


def configurar(conf: dict) -> None:
    p = pipeline
    for etapa, activa in conf.get("etapas", {}).items():
        if etapa in p.ETAPAS:
            p.ETAPAS[etapa] = bool(activa)
    p.ETAPAS["visualizacion"] = False  # la visualización la hace la web
    if conf.get("categorias"):
        p.CATEGORIAS = list(conf["categorias"])
    cap = conf.get("captura", {})
    p.CAPTURA_CATEGORIA = cap.get("categoria", p.CAPTURA_CATEGORIA)
    p.CAPTURA_POSES = int(cap.get("poses", p.CAPTURA_POSES))
    p.CAPTURA_CICLOS = int(cap.get("ciclos", p.CAPTURA_CICLOS))
    p.CAPTURA_ESPERAR_ENTER = bool(cap.get("esperar_enter", p.CAPTURA_ESPERAR_ENTER))
    p.REHACER = bool(conf.get("rehacer", p.REHACER))
    p.FASE_TRIANGULACION = conf.get("fase", p.FASE_TRIANGULACION)
    p.CALIBRACION_USADA = conf.get("calibracion", p.CALIBRACION_USADA)

    # Captura: vista en vivo y, opcionalmente, cámara simulada
    import capturar_patrones as cp

    extra: dict = {"al_frame": VistaEnVivo(cfg.IMAGENES_POR_CICLO * max(p.CAPTURA_CICLOS, 1))}
    simular = conf.get("simular")
    if simular and p.ETAPAS.get("captura"):
        extra["camara"] = cp.CamaraSimulada(cfg.DIR_CAPTURAS / simular)
        extra["sufijo"] = "_simulada"
    cp.capturar_poses = partial(cp.capturar_poses, **extra)


def main() -> None:
    conf = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        configurar(conf)
        pipeline.main()
    except SystemExit as exc:
        if isinstance(exc.code, str):  # pipeline.main() sale con un mensaje de texto
            print(exc.code, flush=True)
        sys.stdout.flush()
        raise SystemExit(exc.code if isinstance(exc.code, int) else 1) from None


if __name__ == "__main__":
    main()
