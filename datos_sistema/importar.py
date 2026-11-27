"""Importa capturas tomadas antes (o en otro equipo) como un proceso nuevo, listo para procesar.

La carpeta de origen debe tener subcarpetas por categoría (patron, plano, objeto; también se
reconocen nombres como pattern, calib, plane, object…). Dentro de cada una, cada captura puede ser:
- una subcarpeta con sus imágenes (como las que guarda este sistema: `20261030_095750/`),
- un video (.avi, .mp4…),
- o, si la categoría no tiene subcarpetas, sus imágenes directamente (una sola captura).

Se COPIA todo (la carpeta original no se toca; con `--mover` se mueve) a
`capturas/<AAAA-MM-DD_HHMM>/<cat>/<captura>/`, con su `proceso.json`, y se registra el proceso. Las
capturas que ya existen en el sistema (misma categoría y nombre) se omiten, para no duplicarlas.
La fecha del proceso sale del nombre de las capturas (AAAAMMDD_HHMMSS) o de la fecha de sus archivos.

Uso:
    .env/bin/python -m datos_sistema.importar /ruta/a/la/carpeta                 # muestra qué importaría
    .env/bin/python -m datos_sistema.importar /ruta/a/la/carpeta --aplicar       # importa
    .env/bin/python -m datos_sistema.importar /ruta/a/la/carpeta --aplicar --procesar   # e importa y procesa todo
En la interfaz: pestaña Archivos → «Importar capturas».
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from datos_sistema import configuracion as cfg
from datos_sistema import rutas
from datos_sistema import sesiones

EXT_IMAGEN = {".tiff", ".tif", ".png", ".bmp", ".jpg", ".jpeg", ".pgm"}
EXT_VIDEO = {".avi", ".mp4", ".mov", ".mkv", ".mj2", ".wmv", ".m4v", ".mpg", ".mpeg"}


def _categoria(nombre: str) -> str | None:
    from procesamiento.organizar_capturas import categoria_por_nombre

    return categoria_por_nombre(Path(nombre), None)


def _hora(ruta: Path) -> datetime:
    """Hora de una captura: de su nombre (AAAAMMDD_HHMMSS) o de su archivo más antiguo."""
    hora = sesiones.hora_de_carpeta(ruta.name)
    if hora:
        return hora
    archivos = [ruta] if ruta.is_file() else [p for p in ruta.rglob("*") if p.is_file()]
    return datetime.fromtimestamp(min((p.stat().st_mtime for p in archivos), default=ruta.stat().st_mtime))


def _tamano(ruta: Path) -> int:
    return ruta.stat().st_size if ruta.is_file() else sum(p.stat().st_size for p in ruta.rglob("*") if p.is_file())


def elegir_carpeta(inicial: str | None = None, titulo: str = "Carpeta con patron/, plano/ y objeto/") -> str | None:
    """Abre la ventana del sistema para elegir una carpeta (en esta máquina). Devuelve la ruta, o
    None si se canceló. Prueba zenity (GNOME), kdialog (KDE) y tkinter, en ese orden."""
    import os
    import subprocess
    import sys

    inicio = str(Path(inicial).expanduser()) if inicial and Path(inicial).expanduser().is_dir() else str(Path.home())
    opciones = []
    if shutil.which("zenity"):
        opciones.append(["zenity", "--file-selection", "--directory", f"--title={titulo}", f"--filename={inicio.rstrip('/')}/"])
    if shutil.which("kdialog"):
        opciones.append(["kdialog", "--getexistingdirectory", inicio, "--title", titulo])
    opciones.append([sys.executable, "-c", "import sys, tkinter as tk, tkinter.filedialog as fd; r = tk.Tk(); r.withdraw(); "
                     "r.attributes('-topmost', True); print(fd.askdirectory(initialdir=sys.argv[1], title=sys.argv[2]) or '')",
                     inicio, titulo])
    for cmd in opciones:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0:
            return r.stdout.strip() or None
        if r.returncode == 1 and not r.stderr.strip():
            return None  # el usuario canceló
    raise RuntimeError("No se pudo abrir la ventana para elegir carpetas (no hay zenity, kdialog ni tkinter con pantalla)")


def analizar(carpeta: str | Path) -> dict:
    """Qué se importaría, sin copiar nada: capturas por categoría, omitidas y el nombre del proceso."""
    origen = Path(carpeta).expanduser()
    if not origen.is_dir():
        raise FileNotFoundError(f"No existe la carpeta '{origen}'")
    if origen.resolve() == cfg.DATOS.resolve() or cfg.DIR_CAPTURAS.resolve() in [origen.resolve(), *origen.resolve().parents]:
        raise ValueError("Esa carpeta ya está dentro de los datos del sistema: no hace falta importarla")
    existentes = {f"{c}/{n}" for c, n, _p, _pr in rutas.capturas_en_disco()}
    capturas: dict[str, list[dict]] = {}
    omitidas, ignoradas = [], []
    for sub in sorted(p for p in origen.iterdir() if p.is_dir() and not p.name.startswith(".")):
        cat = _categoria(sub.name)
        if cat is None:
            ignoradas.append(sub.name)
            continue
        hijos = sorted(p for p in sub.iterdir() if not p.name.startswith("."))
        carpetas = [p for p in hijos if p.is_dir() and any(q.suffix.lower() in EXT_IMAGEN | EXT_VIDEO for q in p.rglob("*"))]
        videos = [p for p in hijos if p.is_file() and p.suffix.lower() in EXT_VIDEO]
        imagenes_sueltas = [p for p in hijos if p.is_file() and p.suffix.lower() in EXT_IMAGEN]
        unidades = carpetas + videos
        if not unidades and imagenes_sueltas:
            unidades = [sub]  # las imágenes están directamente en la carpeta de la categoría: una captura
        for u in unidades:
            nombre = u.name if u is not sub else f"{_hora(u):%Y%m%d_%H%M%S}_importada"
            if f"{cat}/{nombre}" in existentes:
                omitidas.append(f"{cat}/{nombre}")
                continue
            sueltas = u is sub
            capturas.setdefault(cat, []).append({
                "origen": str(u), "nombre": nombre, "hora": _hora(u).isoformat(timespec="seconds"),
                "bytes": sum(q.stat().st_size for q in imagenes_sueltas) if sueltas else _tamano(u),
                "tipo": "video" if u.is_file() else "sueltas" if sueltas else "carpeta"})
    horas = [datetime.fromisoformat(c["hora"]) for lista in capturas.values() for c in lista]
    inicio = min(horas) if horas else datetime.now()
    return {"origen": str(origen), "proceso": rutas.nombre_proceso(inicio, etiqueta=origen.name),
            "nombre": origen.name, "inicio": inicio.isoformat(timespec="seconds"),
            "capturas": capturas, "omitidas": omitidas, "ignoradas": ignoradas,
            "bytes": sum(c["bytes"] for lista in capturas.values() for c in lista)}


def importar(carpeta: str | Path, nombre: str | None = None, mover: bool = False) -> dict:
    """Copia (o mueve) las capturas como un proceso nuevo y lo registra. Devuelve el análisis más
    `id` (el id del proceso en el sistema, para elegirlo como configuración en uso)."""
    plan = analizar(carpeta)
    if not plan["capturas"]:
        raise ValueError("No hay capturas nuevas para importar" + (f" ({len(plan['omitidas'])} ya estaban en el sistema)"
                                                                     if plan["omitidas"] else ""))
    # nombre: el que eligió el usuario (por defecto, el de la carpeta de origen) o una carpeta completa
    if nombre and rutas.es_proceso(nombre):
        proceso, etiqueta = nombre, None
    else:
        etiqueta = (nombre or "").strip() or plan["nombre"]
        proceso = rutas.nombre_proceso(datetime.fromisoformat(plan["inicio"]), etiqueta=etiqueta)
    destino_proceso = cfg.DIR_CAPTURAS / proceso
    if destino_proceso.exists():
        raise FileExistsError(f"Ya existe {destino_proceso}")
    copiadas = []
    for cat, lista in plan["capturas"].items():
        for c in lista:
            origen, destino = Path(c["origen"]), destino_proceso / cat / c["nombre"]
            destino.parent.mkdir(parents=True, exist_ok=True)
            print(f"  {'Moviendo' if mover else 'Copiando'} {cat}/{c['nombre']} ({c['bytes'] / 1e6:.0f} MB)…", flush=True)
            pasar = shutil.move if mover else shutil.copy2  # copy2 conserva la fecha de cada archivo
            if c["tipo"] == "video":
                destino.mkdir(parents=True)
                pasar(str(origen), str(destino / origen.name))
            elif c["tipo"] == "sueltas":  # imágenes directamente en la carpeta de la categoría
                destino.mkdir(parents=True)
                for img in sorted(q for q in origen.iterdir() if q.is_file() and q.suffix.lower() in EXT_IMAGEN):
                    pasar(str(img), str(destino / img.name))
            elif mover:
                shutil.move(str(origen), str(destino))
            else:
                shutil.copytree(origen, destino, copy_function=shutil.copy2)
            copiadas.append(destino)
    sesiones.escribir_json(destino_proceso / "proceso.json", {
        "proceso": proceso, "montaje": cfg.MONTAJE, **({"nombre": etiqueta[:80]} if etiqueta else {}),
        "inicio": plan["inicio"], "importado": datetime.now().isoformat(timespec="seconds"),
        "origen": plan["origen"], "capturas": {cat: [c["nombre"] for c in lista] for cat, lista in plan["capturas"].items()},
        "poses": {},
    })
    sesiones.registrar_proceso(copiadas, [(cat, len(lista)) for cat, lista in plan["capturas"].items()])
    sesiones._cache.clear()
    ident = next((p["id"] for p in sesiones.procesos() if p.get("carpeta") == proceso), None)
    print(f"[OK] Importado como el proceso {proceso}: " + ", ".join(f"{c} {len(v)}" for c, v in plan["capturas"].items()), flush=True)
    return {**plan, "proceso": proceso, "id": ident}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("carpeta", type=Path, help="Carpeta con subcarpetas patron/, plano/, objeto/")
    parser.add_argument("--aplicar", action="store_true", help="Importa (sin esto solo muestra qué haría)")
    parser.add_argument("--mover", action="store_true", help="Mueve en vez de copiar (la carpeta original queda vacía)")
    parser.add_argument("--nombre", help="Nombre del proceso (p. ej. 'cilindro con pintas'); por defecto, el de la carpeta")
    parser.add_argument("--procesar", action="store_true",
                        help="Después de importar: organizar, fases, calibración (si hay patrón) y reconstrucción")
    args = parser.parse_args()
    plan = analizar(args.carpeta)
    print(f"Proceso: {plan['proceso']} (inicio {plan['inicio']})")
    for cat, lista in plan["capturas"].items():
        print(f"  {cat}: {len(lista)} captura(s) — " + ", ".join(c["nombre"] for c in lista[:6]) + (" …" if len(lista) > 6 else ""))
    if plan["omitidas"]:
        print(f"  Ya estaban en el sistema (se omiten): {', '.join(plan['omitidas'])}")
    if plan["ignoradas"]:
        print(f"  Carpetas sin categoría reconocible (se ignoran): {', '.join(plan['ignoradas'])}")
    print(f"  Total: {plan['bytes'] / 1e6:.0f} MB")
    if not args.aplicar:
        print("\nModo de prueba: no se copió nada. Para importar: --aplicar")
        return
    res = importar(args.carpeta, args.nombre, args.mover)
    if args.procesar:
        import pipeline

        sesiones.fijar_solo_proceso(res["proceso"])  # se procesa exactamente este proceso
        for etapa in pipeline.ETAPAS:
            pipeline.ETAPAS[etapa] = etapa in ("organizar", "fase_relativa", "fase_absoluta", "reconstruccion") or (
                etapa == "calibracion" and "patron" in res["capturas"])
        pipeline.main()


if __name__ == "__main__":
    main()
