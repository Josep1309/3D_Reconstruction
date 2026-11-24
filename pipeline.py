"""Control del proceso completo de reconstrucción 3D por proyección de franjas (phase shifting).

Toda la configuración se hace en la sección 'CONFIGURACIÓN DEL PIPELINE' de abajo: activa (True)
o desactiva (False) cada etapa y ajusta sus opciones. Luego ejecuta:
    .env/bin/python pipeline.py

Etapas, en orden:
    patrones        Genera la secuencia .bmp para el LightCrafter (secuencia_patrones.py)
    lightcrafter    Configura exposición/período del LightCrafter por USB (configurar_lightcrafter.py)
    captura         Captura poses con la cámara FLIR y trigger externo (capturar_patrones.py)
    organizar       Ordena capturas crudas en capturas_ordenadas/<categoria>/pose_XX (organizar_capturas.py)
    fase_relativa   Fase envuelta por N-step phase shifting (fase.py)
    fase_absoluta   Desenvolvimiento con código Gray y coordenadas del proyector (fase.py)
    calibracion     Calibración estéreo cámara-proyector con el patrón de círculos (calibracion_estereo.py)
    reconstruccion  Triangulación 3D, nubes .ply y error de planitud (reconstruccion_3d.py)
    visualizacion   Cuadrícula con cada paso del proceso y ventana 3D (visualizacion.py)

Los parámetros físicos del sistema (proyector, cámara, patrón de círculos, umbrales) están en
configuracion.py.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import configuracion as cfg

# ==============================================================================
# --- CONFIGURACIÓN DEL PIPELINE (EDITA AQUÍ) ---
# ==============================================================================
# Etapas a ejecutar: True = se ejecuta, False = se omite. Siempre corren en este orden.
#
# Flujo típico para MEDIR OBJETOS con el sistema ya calibrado (calibracion = False):
#     captura -> organizar -> fase_relativa -> fase_absoluta -> reconstruccion -> visualizacion
# La reconstrucción usa la última calibración guardada en resultados/calibracion/.
#
# Para RECALIBRAR: captura con CAPTURA_CATEGORIA = "patron" (10-15 poses) y calibracion = True.
# Las fases del patrón solo se calculan cuando 'calibracion' está activa.
ETAPAS = {
    "patrones": False,        # solo cuando cambian los patrones a cargar en el LightCrafter
    "lightcrafter": False,    # requiere el LightCrafter conectado por USB
    "captura": False,         # requiere cámara FLIR + Arduino
    "organizar": True,        # ordena lo nuevo de capturas/ (lo ya organizado se omite)
    "fase_relativa": True,    # solo calcula poses nuevas o modificadas
    "fase_absoluta": True,
    "calibracion": False,     # OPCIONAL: solo si se capturaron poses nuevas del patrón
    "reconstruccion": True,
    "visualizacion": True,    # abre la cuadrícula del proceso y la ventana 3D
}

# Categorías a procesar en las etapas de fase y reconstrucción ("plano" y/o "objeto").
# "patron" se agrega solo cuando 'calibracion' está activa.
CATEGORIAS = ["plano", "objeto"]

# --- Captura ---
CAPTURA_CATEGORIA = "objeto"           # "patron", "plano" u "objeto"
CAPTURA_POSES = 1                      # poses a capturar (pide Enter antes de cada una)
CAPTURA_CICLOS = cfg.CICLOS_POR_CAPTURA  # ciclos de 50 patrones por pose (se promedian)
CAPTURA_ESPERAR_ENTER = True

# --- Organización ---
ORGANIZAR_ENTRADAS = [cfg.DIR_CAPTURAS]  # carpetas o archivos con capturas crudas
ORGANIZAR_CATEGORIA_FORZADA = None       # None, o "patron"/"plano"/"objeto" para todo lo nuevo
ORGANIZAR_REHACER = False                # True = reorganiza todo desde cero

# --- Caché ---
# Las fases y la reconstrucción de cada pose se reutilizan si sus entradas no cambiaron.
# True = recalcula fases y reconstrucción de todas las poses (p. ej. tras cambiar un umbral).
REHACER = False

# --- Reconstrucción ---
FASE_TRIANGULACION = cfg.FASE_TRIANGULACION  # "auto", "ambas", "Fx" o "Fy"
CALIBRACION_USADA = cfg.CALIBRACION          # "independiente" o "conjunta"

# --- Visualización ---
VIS_CATEGORIA = "objeto"
VIS_POSE = "ultima"                          # "ultima" o un nombre como "pose_00"
VIS_COLOR_3D = "profundidad"                 # "profundidad" o "textura"
# ==============================================================================

DIR_FASES = cfg.DIR_RESULTADOS / "fases"
DIR_CALIBRACION = cfg.DIR_CALIBRACION
DIR_RECONSTRUCCION = cfg.DIR_RESULTADOS / "reconstruccion"


def etapa_patrones() -> None:
    import secuencia_patrones as sp

    sp.guardar_secuencia(sp.crear_secuencia_completa())
    print(f"[OK] Patrones en '{cfg.DIR_PATRONES}'. Cárgalos en el LightCrafter en ese orden "
          f"(f_00 .. f_{cfg.IMAGENES_POR_CICLO - 1:02d}).")


def etapa_lightcrafter() -> None:
    import configurar_lightcrafter as lcr

    lcr.main(cfg.LCR_EXPOSICION_US, cfg.LCR_PERIODO_US, reiniciar=True, solo_leer=False)


def etapa_captura() -> None:
    import capturar_patrones as cp

    cp.capturar_poses(CAPTURA_CATEGORIA, CAPTURA_POSES, CAPTURA_CICLOS, cfg.DIR_CAPTURAS, CAPTURA_ESPERAR_ENTER)


def etapa_organizar() -> None:
    import organizar_capturas as oc

    nuevas = oc.organizar(
        [Path(e) for e in ORGANIZAR_ENTRADAS], cfg.DIR_ORDENADAS,
        categoria_forzada=ORGANIZAR_CATEGORIA_FORZADA, rehacer=ORGANIZAR_REHACER,
    )
    total = sum(len(v) for v in nuevas.values())
    print(f"[OK] {total} poses nuevas organizadas en '{cfg.DIR_ORDENADAS}'.")


def _categorias_fase() -> list[str]:
    """Categorías cuyas fases se calculan: las de CATEGORIAS, más 'patron' solo si se calibra."""
    categorias = [c for c in CATEGORIAS if c != "patron"]
    if ETAPAS.get("calibracion"):
        categorias.insert(0, "patron")
    return categorias


def ruta_calibracion() -> Path:
    nombre = "Estereo_TSC_0_2_J.npz" if CALIBRACION_USADA == "conjunta" else "Estereo_TSC_0_2.npz"
    return DIR_CALIBRACION / nombre


def _verificar_calibracion_existente() -> None:
    """Si se reconstruye sin recalibrar, comprueba ANTES de capturar que haya una calibración y la
    describe, para no descubrir el problema al final del proceso."""
    ruta = ruta_calibracion()
    if not ruta.exists():
        raise SystemExit(
            f"[PIPELINE] No existe la calibración '{ruta}'.\n"
            f"           Activa la etapa 'calibracion' (con poses del patrón organizadas) o copia "
            f"una calibración previa a esa carpeta (MANUAL.md §20.5)."
        )
    resumen = ruta.with_name("Estereo_TSC_0_2.json")
    texto = ""
    if resumen.exists():
        info = json.loads(resumen.read_text(encoding="utf-8"))
        texto = (f" | {len(info.get('poses', []))} poses, RMS estéreo "
                 f"{info.get('rms_stereo_indep_px', float('nan')):.3f} px, fecha {info.get('fecha', '?')}")
    print(f"[PIPELINE] Sin recalibrar: se usa '{ruta.name}'{texto}")


def etapa_fase_relativa() -> None:
    import fase

    fase.etapa_fase_relativa(
        cfg.DIR_ORDENADAS, DIR_FASES, _categorias_fase(), n_step=cfg.N_PASOS,
        gamma_th=cfg.GAMMA_TH, prefijo=cfg.PREFIJO_ORDENADAS, rehacer=REHACER,
        gamma_th_y=cfg.GAMMA_TH_Y, suavizado=cfg.SUAVIZADO_FASE_PX,
    )


def etapa_fase_absoluta() -> None:
    import fase

    fase.etapa_fase_absoluta(
        cfg.DIR_ORDENADAS, DIR_FASES, _categorias_fase(), fringe_pitch=cfg.PERIODO, n_step=cfg.N_PASOS,
        n_bits=cfg.N_BITS_GRAY, gamma_th=cfg.GAMMA_TH, med_filt_size=cfg.MED_FILT,
        orden_bits=cfg.ORDEN_BITS_GRAY, umbral_intensidad=cfg.UMBRAL_INTENSIDAD, borde=cfg.BORDE_MASCARA,
        prefijo=cfg.PREFIJO_ORDENADAS, rehacer=REHACER, gamma_th_y=cfg.GAMMA_TH_Y,
    )


def etapa_calibracion() -> None:
    import calibracion_estereo as ce

    ce.ejecutar_calibracion_estereo(DIR_FASES, DIR_CALIBRACION)


def etapa_reconstruccion() -> None:
    import reconstruccion_3d as r3d

    categorias = [c for c in CATEGORIAS if c != "patron"] or ["objeto"]
    r3d.procesar_reconstruccion(DIR_FASES, ruta_calibracion(), DIR_RECONSTRUCCION, categorias,
                                FASE_TRIANGULACION, rehacer=REHACER)


def etapa_visualizacion() -> None:
    import visualizacion

    visualizacion.visualizar_pose(VIS_CATEGORIA, VIS_POSE, color_3d=VIS_COLOR_3D)


# Sección del manual con los problemas frecuentes de cada etapa
AYUDA_ETAPA = {
    "patrones": "§16.2", "lightcrafter": "§16.2", "captura": "§16.3", "organizar": "§16.4",
    "fase_relativa": "§16.5", "fase_absoluta": "§16.5", "calibracion": "§16.6",
    "reconstruccion": "§16.7", "visualizacion": "§16.8",
}

FUNCIONES = {
    "patrones": etapa_patrones,
    "lightcrafter": etapa_lightcrafter,
    "captura": etapa_captura,
    "organizar": etapa_organizar,
    "fase_relativa": etapa_fase_relativa,
    "fase_absoluta": etapa_fase_absoluta,
    "calibracion": etapa_calibracion,
    "reconstruccion": etapa_reconstruccion,
    "visualizacion": etapa_visualizacion,
}


def main() -> None:
    desconocidas = set(ETAPAS) - set(FUNCIONES)
    if desconocidas:
        raise SystemExit(f"Etapas desconocidas en ETAPAS: {sorted(desconocidas)}")
    elegidas = [e for e in FUNCIONES if ETAPAS.get(e, False)]
    if not elegidas:
        raise SystemExit("No hay etapas activas: pon en True alguna etapa en ETAPAS.")

    print(f"\n[PIPELINE] Etapas: {' -> '.join(elegidas)}")
    if ETAPAS.get("captura") and not ETAPAS.get("organizar"):
        print("[AVISO] 'captura' activa sin 'organizar': las capturas nuevas no se procesarán.")
    if ETAPAS.get("reconstruccion") and not ETAPAS.get("calibracion"):
        _verificar_calibracion_existente()
    t_total = time.perf_counter()
    for etapa in elegidas:
        print(f"\n{'#' * 78}\n# ETAPA: {etapa}\n{'#' * 78}")
        t0 = time.perf_counter()
        try:
            FUNCIONES[etapa]()
        except KeyboardInterrupt:
            raise SystemExit(f"\n[PIPELINE] Interrumpido en la etapa '{etapa}'.")
        except Exception as exc:
            print(f"\n[ERROR] La etapa '{etapa}' falló: {exc}")
            print(f"        Posibles causas y soluciones: MANUAL.md {AYUDA_ETAPA.get(etapa, '§16')} "
                  f"(o ejecuta .env/bin/python verificar.py)")
            raise SystemExit(1) from exc
        print(f"[PIPELINE] '{etapa}' terminada en {time.perf_counter() - t0:.1f} s")
    print(f"\n[PIPELINE] Proceso completo en {time.perf_counter() - t_total:.1f} s. "
          f"Resultados en '{cfg.DIR_RESULTADOS}'.")


if __name__ == "__main__":
    main()
