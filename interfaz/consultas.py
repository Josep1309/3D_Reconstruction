"""Consultas del servidor: inventario de poses, archivos, calibración, sistema, comparaciones y
vigilancia de resultados nuevos."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

from comun import DIR_CALIBRACION, DIR_COMPARACIONES, RAIZ, _archivos_pose, _mtime, listar_poses
from ejecucion import difusor, ejecucion
from imagenes import cargar_npz

import numpy as np
import configuracion as cfg
import mascara
import rutas


def _firma_pose(ruta: Path, tipo: str) -> str | None:
    """Parámetros con los que se calculó la fase de una pose (los anteriores a la firma: los de
    configuracion.py). None si la pose aún no tiene esa fase."""
    import fase

    if _mtime(ruta) is None:
        return None
    try:
        npz = cargar_npz(ruta)
        return str(npz["firma"]) if "firma" in npz else fase._firma_original(tipo)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return None


def inventario() -> dict:
    import ajustes

    esperada_rel, esperada_abs = ajustes.firmas_esperadas()
    import archivos

    notas = archivos.leer_notas()
    datos = {}
    for cat in cfg.CATEGORIAS:
        resumen_ruta = rutas.dir_resumen(cat) / f"{cat}_resumen.json"
        resumen = {}
        if resumen_ruta.exists():
            try:
                resumen = json.loads(resumen_ruta.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        poses = []
        for pose in listar_poses(cat):
            archivos = _archivos_pose(cat, pose)
            estado = {k: _mtime(r) is not None for k, r in archivos.items()}
            info = resumen.get(pose, {})
            # Procedencia: ¿se calculó con los ajustes actuales? (si no, hay que volver a procesar)
            f_rel, f_abs = _firma_pose(archivos["relativa"], "rel"), _firma_pose(archivos["absoluta"], "abs")
            distintos = [f for f, esperada in ((f_rel, esperada_rel), (f_abs, esperada_abs)) if f and f != esperada]
            firma_mascara = mascara.firma(cat, pose)
            poses.append({"pose": pose, **estado, "puntos": info.get("puntos"), "erms_mm": info.get("erms_mm"),
                          # máscara de la pestaña «Máscara»; pendiente = guardada pero la nube no la usa aún
                          "mascara": firma_mascara is not None,
                          "mascara_pendiente": estado["reconstruida"] and info.get("mascara") != firma_mascara,
                          "nota": notas.get(f"pose:{cat}/{pose}"),
                          "z": [info.get("z_p1_mm"), info.get("z_p99_mm")],
                          "ajustes_ok": not distintos,
                          "calculada_con": " · ".join(ajustes.describir_firma(f) for f in (f_rel, f_abs) if f)})
        datos[cat] = poses
    return datos


def resumen_calibracion() -> dict | None:
    ruta = DIR_CALIBRACION / "Estereo_TSC_0_2.json"
    if not ruta.exists():
        return None
    try:
        info = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    claves = ("fecha", "poses", "rms_cam_px", "rms_proj_px", "rms_stereo_indep_px", "linea_base_mm",
              "T_mm", "cobertura_up_px", "cobertura_vp_px", "center_distance_mm")
    return {k: info.get(k) for k in claves}


def listado_archivos() -> dict:
    """Todas las capturas agrupadas por proceso, con sus poses y lo calculado de cada una."""
    import archivos
    import calibracion_estereo as ce
    import sesiones

    lista = sesiones.procesos()
    conf = sesiones.configuracion_vigente()
    rangos = sesiones.configuraciones(lista)
    notas = archivos.leer_notas()
    calibs = ce.listar_calibraciones(DIR_CALIBRACION)
    proceso_calib = {}
    for c in calibs:
        proceso_calib.setdefault(sesiones.proceso_de_poses("patron", c["poses"]), []).append(
            {"id": c["id"], "activa": c["activa"], "rms_stereo_px": c["rms_stereo_px"]})
    salida = []
    for i, p in enumerate(lista):
        config = next((lista[a]["id"] for a, b in rangos if a <= i < b), None)
        items = []
        for it in p["items"]:
            poses = []
            for pose in it["poses"]:
                estado = {k: _mtime(r) is not None for k, r in _archivos_pose(it["cat"], pose).items()}
                poses.append({"pose": pose, **estado})
            # Espacio: captura cruda + poses organizadas (lo que se libera al borrarla, sin contar resultados)
            bytes_item = archivos.tamano(rutas.ruta_captura(it["carpeta"])) + sum(
                archivos.tamano(rutas.dir_pose_ordenada(it["cat"], p["pose"])) for p in poses)
            items.append({"cat": it["cat"], "carpeta": it["carpeta"], "hora": it["hora"].isoformat(timespec="seconds"),
                          "existe": it["existe"], "poses": poses, "rechazo": it.get("rechazo"),
                          "pureza": it.get("pureza"), "bytes": bytes_item,
                          "nota": notas.get(f"pose:{it['cat']}/{it['poses'][0]}") if it["poses"] else None})
        salida.append({
            "id": p["id"], "fin": p["fin"].isoformat(timespec="seconds"), "registrado": p["registrado"],
            "nota": notas.get(f"proceso:{p['id']}"), "bytes": sum(i["bytes"] for i in items),
            "patron": p["patron"], "configuracion": config, "vigente": bool(conf) and config == conf["proceso"],
            "inicia_configuracion": config == p["id"], "calibraciones": proceso_calib.get(p["id"], []),
            "items": items,
        })
    return {"procesos": salida, "vigente": sesiones.info_vigente(), "papelera": archivos.info_papelera(),
            "lotes": archivos.listar_papelera()}


def _tamano(ruta: Path) -> int:
    total = 0
    pila = [ruta]
    while pila:
        try:
            with os.scandir(pila.pop()) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        pila.append(e.path)
                    elif e.is_file(follow_symlinks=False):
                        total += e.stat(follow_symlinks=False).st_size
        except OSError:
            pass
    return total


_cache_sistema: dict = {}


def estado_sistema(con_hardware: bool, forzar: bool = False) -> dict:
    """Comprobación del sistema (verificar.py --json) más el espacio en disco. Se cachea 60 s.

    Con un proceso en curso no se busca el hardware: la cámara está ocupada por el pipeline."""
    con_hardware = con_hardware and not ejecucion.estado()["ejecutando"]
    clave = con_hardware
    if not forzar and clave in _cache_sistema and time.time() - _cache_sistema[clave]["t"] < 60:
        return _cache_sistema[clave]["datos"]
    comando = [sys.executable, str(RAIZ / "verificar.py"), "--json"] + ([] if con_hardware else ["--sin-hardware"])
    try:
        r = subprocess.run(comando, capture_output=True, text=True, timeout=90, cwd=RAIZ, env={**os.environ})
        verif = json.loads(r.stdout.strip().splitlines()[-1])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, IndexError) as exc:
        verif = {"resumen": {"ok": 0, "aviso": 0, "error": 1},
                 "resultados": [{"grupo": "verificar.py", "nivel": "error", "texto": f"No se pudo ejecutar: {exc}",
                                 "solucion": "", "seccion": "§20"}]}
    import shutil

    disco = shutil.disk_usage(cfg.DATOS)
    import archivos

    datos = {
        **verif, "con_hardware": con_hardware, "hora": time.strftime("%H:%M:%S"),
        "disco": {"libre": disco.free, "total": disco.total,
                  "carpetas": {nombre: _tamano(ruta) for nombre, ruta in (
                      ("capturas", cfg.DIR_CAPTURAS), ("capturas_ordenadas", cfg.DIR_ORDENADAS),
                      ("resultados", cfg.DIR_RESULTADOS), ("papelera", archivos.PAPELERA))}},
    }
    _cache_sistema[clave] = {"t": time.time(), "datos": datos}
    return datos


_cache_errores: dict = {}
_lock_errores = threading.Lock()


def _puntos_calibracion(info: dict) -> dict:
    """Correspondencias de la calibración en uso: las que guardó al calibrar
    (`Estereo_TSC_0_2_puntos.npz`) o, si es anterior a ese archivo, las recalculadas una vez desde
    las fases de sus poses (se guardan en resultados/calibracion/puntos_<fecha>.npz)."""
    import calibracion_estereo as ce

    ruta = DIR_CALIBRACION / ce.ARCHIVO_PUNTOS
    nuevo = ruta.exists()
    if not nuevo:
        ruta = cfg.DIR_RESULTADOS / "calibracion" / f"puntos_{re.sub(r'[^0-9T]', '', info.get('fecha') or 'sin_fecha')}.npz"
        if not ruta.exists():
            calc = ce.puntos_desde_fases(info)
            if not calc["poses"]:
                raise FileNotFoundError("no quedan fases de las poses de esta calibración (¿se borraron?)")
            ruta.parent.mkdir(parents=True, exist_ok=True)
            np.savez(ruta, poses=np.array(calc["poses"]), usadas=np.array(calc["usadas"]),
                     cam=np.stack(calc["cam"]).astype(np.float32), proj=np.stack(calc["proj"]).astype(np.float32),
                     worldPoints=calc["worldPoints"], faltan=np.array(calc["faltan"], dtype=str))
    with np.load(ruta) as d:
        return {"poses": [str(x) for x in d["poses"]], "usadas": {str(x) for x in d["usadas"]},
                "cam": d["cam"], "proj": d["proj"], "mundo": d["worldPoints"],
                "faltan": [str(x) for x in d["faltan"]] if "faltan" in d.files else [], "completo": nuevo}


def errores_calibracion(variante: str = "independiente") -> dict:
    """Errores de reproyección por pose con la calibración en uso, evaluada con SUS poses del
    patrón (las usadas y, en las calibraciones nuevas, también las detectadas que no entraron).
    Se recalcula solo cuando cambia la calibración en uso."""
    import calibracion_estereo as ce

    nombre = "Estereo_TSC_0_2_J.npz" if variante == "conjunta" else "Estereo_TSC_0_2.npz"
    ruta_cal = DIR_CALIBRACION / nombre
    ruta_json = DIR_CALIBRACION / "Estereo_TSC_0_2.json"
    if _mtime(ruta_cal) is None:
        raise FileNotFoundError("no hay calibración guardada")
    clave = (variante, *(_mtime(r) for r in (ruta_cal, ruta_json, DIR_CALIBRACION / ce.ARCHIVO_PUNTOS)))
    with _lock_errores:
        if clave in _cache_errores:
            return _cache_errores[clave]
        with np.load(ruta_cal) as d:
            calib = {k: d[k] for k in d.files}
        try:
            info = json.loads(ruta_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            info = {}
        pts = _puntos_calibracion(info)
        poses = pts["poses"]
        detalle = info.get("errores_por_pose", {})
        sesiones = ce.sesiones_patron()
        errores = ce.errores_reproyeccion(calib, list(pts["cam"]), list(pts["proj"]), pts["mundo"], residuos=True)
        datos = {
            "variante": variante,
            "fecha": info.get("fecha"),
            "criterio": info.get("poses_criterio", "todas"),
            "rms": {"cam": info.get("rms_cam_px"), "proj": info.get("rms_proj_px"),
                    "estereo": float(calib["rms_stereo"]) if "rms_stereo" in calib else info.get("rms_stereo_indep_px")},
            "cam_wh": [int(v) for v in calib.get("cam_size_wh", (1280, 1024))],
            "proj_wh": [int(v) for v in calib.get("proj_size_wh", (cfg.PROYECTOR_ANCHO, cfg.PROYECTOR_ALTO))],
            "completo": pts["completo"],
            "faltan": pts["faltan"],
            "poses": [{"pose": n, "usada": n in pts["usadas"], **sesiones.get(n, {}),
                       **{k: detalle[n][k] for k in ("hora", "sesion") if k in detalle.get(n, {})}, **e}
                      for n, e in zip(poses, errores)],
        }
        _cache_errores.clear()
        _cache_errores[clave] = datos
        return datos


def fuentes_demo() -> list[str]:
    """Capturas existentes que puede reproducir la cámara simulada (solo del montaje vigente)."""
    import sesiones

    return [str(p.relative_to(cfg.DIR_CAPTURAS)) for _cat, nombre, p, _proc in rutas.capturas_en_disco()
            if p.is_dir() and not nombre.endswith("_simulada") and sesiones.captura_vigente(p)]


def vigilar() -> None:
    """Emite 'cambio' cuando aparece o se actualiza un resultado de una pose.

    Solo avisa cuando la fecha de modificación se mantiene en dos sondeos seguidos, para no
    anunciar un archivo que aún se está escribiendo."""
    visto: dict[tuple, float] = {}
    candidato: dict[tuple, float] = {}
    primera = True
    while True:
        actual = {}
        for cat in cfg.CATEGORIAS:
            for pose in listar_poses(cat):
                for tipo, ruta in _archivos_pose(cat, pose).items():
                    m = _mtime(ruta)
                    if m is not None:
                        actual[(cat, pose, tipo)] = m
        ahora = time.time()
        for clave, m in actual.items():
            # Un archivo viejo que «aparece» no es un resultado nuevo: es una pose que pasó a ser
            # visible al cambiar de configuración. Se registra sin avisar (si no, «Seguir la
            # última» movería la vista a ella)
            if primera or (clave not in visto and m < ahora - 30):
                visto[clave] = m
            elif visto.get(clave) != m:
                if candidato.get(clave) == m:
                    visto[clave] = m
                    candidato.pop(clave)
                    difusor.emitir("cambio", {"cat": clave[0], "pose": clave[1], "tipo": clave[2]})
                else:
                    candidato[clave] = m
        primera = False
        time.sleep(0.7)


def guardar_comparacion(cat: str, pose: str) -> dict:
    """Copia el resultado actual de una pose (X, Y, Z, Mask, E) para compararlo después, p. ej. tras
    cambiar un ajuste (el reprocesado sobrescribe el resultado)."""
    import archivos

    origen = _archivos_pose(cat, pose)["reconstruida"]
    if not origen.exists():
        raise FileNotFoundError("esta pose aún no tiene reconstrucción")
    inv = next((p for p in inventario().get(cat, []) if p["pose"] == pose), {})
    ident = f"{time.strftime('%Y%m%d_%H%M%S')}_{cat}_{pose}"
    DIR_COMPARACIONES.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copyfile(origen, DIR_COMPARACIONES / f"{ident}.npz")
    meta = {"id": ident, "cat": cat, "pose": pose, "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "calculada_con": inv.get("calculada_con"), "puntos": inv.get("puntos"), "erms_mm": inv.get("erms_mm"),
            "nota": archivos.leer_notas().get(f"pose:{cat}/{pose}")}
    (DIR_COMPARACIONES / f"{ident}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def listar_comparaciones(cat: str) -> list[dict]:
    if not DIR_COMPARACIONES.is_dir():
        return []
    salida = []
    for ruta in sorted(DIR_COMPARACIONES.glob(f"*_{cat}_pose_*.json"), reverse=True):
        try:
            salida.append(json.loads(ruta.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return salida


def _distancia_tablero() -> tuple[float, float]:
    d = cfg.VALORES_ORIGINALES["PATRON_DISTANCIA_MM"]
    return (float(d), float(d)) if not isinstance(d, (tuple, list)) else (float(d[0]), float(d[1]))


def configuracion_por_defecto() -> dict:
    import pipeline as p

    return {
        "etapas": {**p.ETAPAS, "visualizacion": False},
        "categorias": p.CATEGORIAS,
        "captura": {"categoria": p.CAPTURA_CATEGORIA, "poses": p.CAPTURA_POSES,
                    "ciclos": p.CAPTURA_CICLOS, "esperar_enter": p.CAPTURA_ESPERAR_ENTER},
        "rehacer": p.REHACER, "fase": p.FASE_TRIANGULACION, "calibracion": p.CALIBRACION_USADA,
        "calib_poses": p.CALIBRACION_POSES,
        "parametros": {k: getattr(cfg, k) for k in (
            "PERIODO", "N_BITS_GRAY", "GAMMA_TH", "GAMMA_TH_Y", "SUAVIZADO_FASE_PX", "UMBRAL_INTENSIDAD",
            "MED_FILT", "BORDE_MASCARA", "ORDEN_BITS_GRAY", "SALTO_MAX_MM", "PLANO_UMBRAL_MM", "FILTRO_VECINOS_SIGMA",
            "CAM_EXPOSICION_US", "PATRON_COLUMNAS", "PATRON_FILAS", "PATRON_DISTANCIA_MM", "Z_MIN_MM", "Z_MAX_MM")},
        "fuentes_demo": fuentes_demo(),
        "tablero_mm": list(_distancia_tablero()),
        "datos": str(cfg.DATOS),
    }
