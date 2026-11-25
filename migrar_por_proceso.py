"""Reordena los datos existentes por proceso de captura (una vez, al pasar a la nueva estructura).

Antes:  capturas/<cat>/<captura>         capturas_ordenadas/<cat>/pose_XX     resultados/fases/<cat>/…
Ahora:  capturas/<P>/<cat>/<captura>     capturas_ordenadas/<P>/<cat>/pose_XX resultados/<P>/fases/<cat>/…
        (P = AAAA-MM-DD_HHMM, el inicio del proceso; ver rutas.py)

- Los procesos se toman como los agrupa hoy el sistema (registro de captura, o capturas seguidas;
  `sesiones.procesos()`): son los mismos que muestra la pestaña Archivos.
- Solo se MUEVEN carpetas y archivos (renombrar dentro del mismo disco): ninguna imagen se modifica,
  y las fechas de los archivos se conservan, así que la caché de fases y reconstrucciones sigue
  valiendo (no hay que recalcular nada).
- El manifiesto se actualiza (fuente, carpeta y firma de cada pose; capturas rechazadas). Se
  escriben `proceso.json` en cada proceso y `origen.json` en cada pose organizada.
- Los nombres de pose NO cambian: calibraciones, notas y selecciones siguen valiendo.
- Antes de cambiar nada se respalda el manifiesto y el registro en `<DATOS>/respaldo_migracion_<fecha>/`,
  junto con la lista de movimientos, que permite deshacerlo todo (`--deshacer`).

Uso:
    .env/bin/python migrar_por_proceso.py              # solo muestra qué haría (no toca nada)
    .env/bin/python migrar_por_proceso.py --aplicar    # lo hace
    .env/bin/python migrar_por_proceso.py --deshacer respaldo_migracion_20261125_103000
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import configuracion as cfg
import rutas
import sesiones


def planificar() -> dict:
    """Movimientos necesarios, sin hacer nada: {"procesos": [...], "movimientos": [(origen, destino)]}."""
    manifiesto = json.loads((cfg.DIR_ORDENADAS / "manifiesto.json").read_text(encoding="utf-8")) \
        if (cfg.DIR_ORDENADAS / "manifiesto.json").exists() else {"poses": []}
    entrada_de = {(e["categoria"], f"pose_{int(e['pose']):02d}"): e for e in manifiesto.get("poses", [])}
    ocupados: set[str] = set()
    procesos, movimientos = [], []
    for p in sesiones.procesos():
        sueltos = [it for it in p["items"] if not it.get("proceso_dir")]
        if not sueltos:
            continue  # ya está en una carpeta de proceso
        nombre = rutas.nombre_proceso(p["inicio"], ocupados)
        ocupados.add(nombre)
        info = {"proceso": nombre, "id": p["id"], "capturas": {}, "poses": {}, "registrado": p["registrado"]}
        for it in sueltos:
            cat, captura = it["carpeta"].split("/")
            origen = cfg.DIR_CAPTURAS / cat / captura
            if origen.exists():
                movimientos.append((origen, cfg.DIR_CAPTURAS / nombre / cat / captura))
                info["capturas"].setdefault(cat, []).append(captura)
            for pose in it["poses"]:
                info["poses"].setdefault(cat, []).append(pose)
                e = entrada_de.get((cat, pose), {})
                # Pose organizada
                ordenada = cfg.DIR_ORDENADAS / cat / pose
                if ordenada.is_dir():
                    movimientos.append((ordenada, cfg.DIR_ORDENADAS / nombre / cat / pose))
                # Fases y reconstrucción (si la pose aún no tiene proceso en el manifiesto)
                if rutas.proceso_en_ruta(e.get("carpeta", "")):
                    continue
                for archivo in sorted((cfg.DIR_RESULTADOS / "fases" / cat).glob(f"{pose}[._]*")):
                    movimientos.append((archivo, cfg.DIR_RESULTADOS / nombre / "fases" / cat / archivo.name))
                dir_rec = cfg.DIR_RESULTADOS / "reconstruccion" / cat
                for archivo in sorted([*dir_rec.glob(f"{cat}_{pose}.*"), *dir_rec.glob(f"reconstruccion_{cat}_{pose}.*")]):
                    movimientos.append((archivo, cfg.DIR_RESULTADOS / nombre / "reconstruccion" / cat / archivo.name))
        procesos.append(info)
    return {"procesos": procesos, "movimientos": movimientos, "manifiesto": manifiesto}


def _actualizar_manifiesto(manifiesto: dict, procesos: list[dict]) -> dict:
    """Nuevas rutas de fuente y carpeta, y la firma (que incluye la ruta de la fuente)."""
    proceso_de = {(cat, c): p["proceso"] for p in procesos for cat, lista in p["capturas"].items() for c in lista}
    proceso_de_pose = {(cat, pose): p["proceso"] for p in procesos for cat, lista in p["poses"].items() for pose in lista}

    def nueva_fuente(fuente: str) -> str:
        partes = Path(fuente).parts
        if len(partes) >= 3 and partes[-3] == "capturas" and (partes[-2], partes[-1]) in proceso_de:
            return str(Path(*partes[:-2]) / proceso_de[(partes[-2], partes[-1])] / partes[-2] / partes[-1])
        return fuente

    def nueva_firma(firma: str, vieja: str, nueva: str) -> str:
        partes = firma.split("|")
        if len(partes) >= 2 and partes[1] == vieja:
            partes[1] = nueva
        return "|".join(partes)

    for e in manifiesto.get("poses", []):
        vieja = e.get("fuente", "")
        nueva = nueva_fuente(vieja)
        e["fuente"], e["firma"] = nueva, nueva_firma(e.get("firma", ""), vieja, nueva)
        proceso = proceso_de_pose.get((e["categoria"], f"pose_{int(e['pose']):02d}"))
        if proceso and not rutas.proceso_en_ruta(e.get("carpeta", "")):
            e["carpeta"] = str(Path(cfg.DIR_ORDENADAS.name) / proceso / e["categoria"] / f"pose_{int(e['pose']):02d}")
    rechazadas = {}
    for firma, r in manifiesto.get("rechazadas", {}).items():
        vieja = r.get("fuente", "")
        nueva = nueva_fuente(vieja)
        rechazadas[nueva_firma(firma, vieja, nueva)] = {**r, "fuente": nueva}
    manifiesto["rechazadas"] = rechazadas
    return manifiesto


def aplicar(plan: dict) -> Path:
    base = cfg.DATOS / f"respaldo_migracion_{datetime.now():%Y%m%d_%H%M%S}"
    respaldo, k = base, 2
    while respaldo.exists():  # dos migraciones en el mismo segundo
        respaldo, k = base.with_name(f"{base.name}_{k}"), k + 1
    respaldo.mkdir(parents=True)
    for ruta in (cfg.DIR_ORDENADAS / "manifiesto.json", sesiones.REGISTRO):
        if ruta.exists():
            shutil.copy2(ruta, respaldo / ruta.name)
    hechos = []
    try:
        for origen, destino in plan["movimientos"]:
            if destino.exists():
                raise FileExistsError(f"ya existe {destino}")
            destino.parent.mkdir(parents=True, exist_ok=True)
            os.rename(origen, destino)  # mismo disco: renombrar, sin copiar ni cambiar fechas
            hechos.append((origen, destino))
    finally:
        (respaldo / "movimientos.json").write_text(json.dumps(
            [[str(o), str(d)] for o, d in plan["movimientos"][:len(hechos)]], indent=1, ensure_ascii=False), encoding="utf-8")
    manifiesto = _actualizar_manifiesto(plan["manifiesto"], plan["procesos"])
    sesiones.escribir_json(cfg.DIR_ORDENADAS / "manifiesto.json", manifiesto, indent=2)
    # proceso.json de cada proceso y origen.json de cada pose
    import organizar_capturas as oc

    entrada_de = {(e["categoria"], f"pose_{int(e['pose']):02d}"): e for e in manifiesto.get("poses", [])}
    for p in plan["procesos"]:
        carpeta = cfg.DIR_CAPTURAS / p["proceso"]
        carpeta.mkdir(parents=True, exist_ok=True)
        inicio = datetime.fromisoformat(p["id"])
        sesiones.escribir_json(carpeta / "proceso.json", {
            "proceso": p["proceso"], "inicio": inicio.isoformat(timespec="seconds"),
            "capturas": p["capturas"], "poses": p["poses"], "migrado": datetime.now().isoformat(timespec="seconds"),
            "nota": "Proceso reconstruido al migrar a la estructura por proceso (agrupado como en la pestaña Archivos).",
        })
        for cat, poses in p["poses"].items():
            for pose in poses:
                dir_pose = cfg.DIR_ORDENADAS / p["proceso"] / cat / pose
                if dir_pose.is_dir() and (cat, pose) in entrada_de:
                    oc.escribir_origen(dir_pose, entrada_de[(cat, pose)])
    # Quitar las carpetas de categoría que quedaron vacías (estructura anterior)
    for base in (cfg.DIR_CAPTURAS, cfg.DIR_ORDENADAS, cfg.DIR_RESULTADOS / "fases"):
        for cat in cfg.CATEGORIAS:
            d = base / cat
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
    if (cfg.DIR_RESULTADOS / "fases").is_dir() and not any((cfg.DIR_RESULTADOS / "fases").iterdir()):
        (cfg.DIR_RESULTADOS / "fases").rmdir()
    sesiones._cache.clear()
    return respaldo


def deshacer(nombre_respaldo: str) -> None:
    respaldo = cfg.DATOS / nombre_respaldo
    movimientos = json.loads((respaldo / "movimientos.json").read_text(encoding="utf-8"))
    for origen, destino in reversed(movimientos):
        o, d = Path(origen), Path(destino)
        if d.exists() and not o.exists():
            o.parent.mkdir(parents=True, exist_ok=True)
            os.rename(d, o)
    for nombre in ("manifiesto.json", sesiones.REGISTRO.name):
        if (respaldo / nombre).exists():
            destino = cfg.DIR_ORDENADAS / nombre if nombre == "manifiesto.json" else sesiones.REGISTRO
            shutil.copy2(respaldo / nombre, destino)
    # proceso.json / origen.json que quedaron y carpetas de proceso vacías
    for base in (cfg.DIR_CAPTURAS, cfg.DIR_ORDENADAS, cfg.DIR_RESULTADOS):
        for p in sorted(base.glob("*")) if base.is_dir() else []:
            if p.is_dir() and rutas.es_proceso(p.name):
                for o in p.rglob("origen.json"):
                    o.unlink()
                restos = [x for x in p.rglob("*") if x.is_file() and x.name != "proceso.json"]
                if not restos:
                    shutil.rmtree(p)
    sesiones._cache.clear()
    print(f"[OK] Migración deshecha con {respaldo}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aplicar", action="store_true", help="Hace los cambios (sin esto solo los muestra)")
    parser.add_argument("--deshacer", metavar="RESPALDO", help="Deshace una migración (carpeta respaldo_migracion_…)")
    args = parser.parse_args()
    if args.deshacer:
        deshacer(args.deshacer)
        return
    plan = planificar()
    if not plan["movimientos"]:
        print("[OK] No hay nada que migrar: todo está ordenado por proceso.")
        return
    print(f"Se reordenarán {len(plan['procesos'])} procesos ({len(plan['movimientos'])} movimientos):\n")
    for p in plan["procesos"]:
        caps = ", ".join(f"{c} {len(v)}" for c, v in p["capturas"].items())
        poses = ", ".join(f"{c} {len(v)}" for c, v in p["poses"].items())
        print(f"  {p['proceso']}   capturas: {caps or '—'}   poses: {poses or '—'}")
    if not args.aplicar:
        print("\nModo de prueba: no se cambió nada. Para hacerlo: --aplicar")
        return
    respaldo = aplicar(plan)
    print(f"\n[OK] Migración hecha. Respaldo y lista de movimientos en {respaldo}")
    print(f"     Para deshacerla: .env/bin/python migrar_por_proceso.py --deshacer {respaldo.name}")


if __name__ == "__main__":
    main()
