"""Interfaz web local para controlar y visualizar el sistema de proyección de franjas.

Ejecuta:
    .env/bin/python interfaz/servidor.py            # abre http://127.0.0.1:8000 en el navegador
    .env/bin/python interfaz/servidor.py --puerto 8080 --sin-navegador
    .env/bin/python interfaz/servidor.py --host 0.0.0.0   # accesible desde otra PC de la red (¡sin clave!)

Solo usa la librería estándar de Python más NumPy/OpenCV del proyecto. El pipeline corre en un
subproceso (`ejecutor.py`) para poder detenerlo y para responder a las pausas de la captura desde
la web. El navegador recibe en tiempo real (Server-Sent Events) el registro, la etapa en curso, la
vista en vivo de la cámara y cada resultado nuevo (pose organizada, fase relativa, fase absoluta,
reconstrucción), que se detectan vigilando las carpetas de resultados.

API (todas las respuestas JSON salvo imágenes y nube):
    GET  /api/config                       valores por defecto de pipeline.py / configuracion.py
    GET  /api/estado                       ejecución, calibración y poses disponibles
    POST /api/ejecutar   {config}          lanza el pipeline
    POST /api/detener                      termina el subproceso
    POST /api/entrada    {"texto": "..."}  responde a una pausa (Enter, q)
    GET  /api/eventos                      flujo SSE
    GET  /api/imagen?cat=&pose=&tipo=&ancho=   PNG de un paso (cabecera X-Rango con la escala)
    GET  /api/nube?cat=&pose=&max=         nube binaria: uint32 N | float32 xyz*N | uint8 gris*N
    GET  /api/vivo.jpg                     último frame de la cámara durante la captura
"""

from __future__ import annotations

import argparse
import json
import queue
import os
import re
import sys
import threading
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from comun import ARCHIVO_VIVO, DIR_CALIBRACION, DIR_ESTATICO, RAIZ, RE_POSE
from ejecucion import difusor, ejecucion
from imagenes import _cache_mapas, _lock_npz, _xyz, diferencia_z, generar_imagen, generar_nube, estado_mascara, guardar_mascara, histograma_plano, medidas_rapidas, perfil_3d, previa_mascara, punto_3d
from consultas import _cache_errores, _lock_errores, configuracion_por_defecto, errores_calibracion, estado_sistema, guardar_comparacion, inventario, listado_archivos, listar_comparaciones, resumen_calibracion, vigilar

import cv2
import numpy as np
from datos_sistema import compat
from datos_sistema import configuracion as cfg


TIPOS_MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
              ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}


class Manejador(BaseHTTPRequestHandler):
    server_version = "TesisFranjas/1.0"

    def log_message(self, formato, *args):  # silencio: el registro útil va a la web
        pass

    # --- utilidades ---
    def _enviar(self, codigo: int, cuerpo: bytes, tipo: str, extra: dict | None = None) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, datos, codigo: int = 200) -> None:
        self._enviar(codigo, json.dumps(datos, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _error(self, codigo: int, mensaje: str) -> None:
        self._json({"error": mensaje}, codigo)

    def _cuerpo(self) -> dict:
        largo = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(largo) or b"{}")

    # --- rutas ---
    # --- seguridad: solo peticiones de la propia interfaz ---
    def _host_valido(self) -> bool:
        """Rechaza nombres de host ajenos (DNS rebinding): solo 127.0.0.1/localhost, salvo --host 0.0.0.0."""
        if getattr(self.server, "red_abierta", False):
            return True
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in ("127.0.0.1", "localhost", "::1")

    def _post_valido(self) -> bool:
        """Contra CSRF: una página ajena puede enviar un formulario a 127.0.0.1, pero no con
        Content-Type JSON sin permiso CORS (que este servidor nunca da), ni con un Origin ajeno."""
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return False
        origen = self.headers.get("Origin")
        return origen is None or urlparse(origen).netloc == self.headers.get("Host")

    def do_GET(self) -> None:
        if not self._host_valido():
            return self._error(403, "host no permitido")
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path in ("/", "/index.html"):
                return self._estatico("index.html")
            if url.path.startswith("/estatico/"):
                return self._estatico(url.path.removeprefix("/estatico/"))
            if url.path == "/api/config":
                return self._json(configuracion_por_defecto())
            if url.path == "/api/estado":
                from datos_sistema import sesiones

                return self._json({"ejecucion": ejecucion.estado(), "calibracion": resumen_calibracion(),
                                   "poses": inventario(), "vigente": sesiones.info_vigente()})
            if url.path == "/api/eventos":
                return self._eventos()
            if url.path == "/api/vivo.jpg":
                if not ARCHIVO_VIVO.exists():
                    return self._error(404, "sin vista en vivo")
                return self._enviar(200, ARCHIVO_VIVO.read_bytes(), "image/jpeg")
            if url.path == "/api/imagen":
                return self._imagen(q)
            if url.path == "/api/punto":
                cat, pose = self._cat_pose(q)
                radio = int(min(max(float(q.get("radio", 6)), 1), 40))
                return self._json(punto_3d(cat, pose, float(q["fx"]), float(q["fy"]), radio))
            if url.path == "/api/medidas_rapidas":
                cat, pose = self._cat_pose(q)
                recorte = min(max(float(q.get("recorte", 0.1)), 0.0), 5.0)
                return self._json(medidas_rapidas(cat, pose, recorte, q.get("principal", "1") != "0"))
            if url.path == "/api/mediciones":
                from datos_sistema import mediciones

                cat, pose = self._cat_pose(q)
                return self._json(mediciones.listar(cat, pose))
            if url.path == "/api/mascara":
                cat, pose = self._cat_pose(q)
                return self._json(estado_mascara(cat, pose))
            if url.path == "/api/metodos":
                from procesamiento import metodos

                return self._json({"metodos": metodos.listar()})
            if url.path == "/api/metodos/comparar":
                from procesamiento import metodos

                cat, pose = self._cat_pose(q)
                lista = [m for m in q.get("metodos", "").split(",") if m in metodos.METODOS] or None
                return self._json(metodos.comparar(cat, pose, lista, avisar=lambda t: None))
            if url.path == "/api/escaneos":
                from procesamiento import escaneo

                return self._json({"escaneos": escaneo.listar()})
            if url.path == "/api/escaneo":
                from procesamiento import escaneo

                return self._json(escaneo.leer(q.get("id", "")))
            if url.path in ("/api/escaneo/malla", "/api/escaneo/stl", "/api/escaneo/malla.ply"):
                from procesamiento import escaneo

                d = escaneo.carpeta(q.get("id", ""))
                if url.path.endswith("malla"):
                    return self._enviar(200, escaneo.malla_binaria(q.get("id", "")), "application/octet-stream")
                archivo = "malla.stl" if url.path.endswith("stl") else "malla.ply"
                return self._enviar(200, (d / archivo).read_bytes(), "application/octet-stream",
                                    {"Content-Disposition": f'attachment; filename="escaneo_{d.name}_{archivo}"'})
            if url.path in ("/api/escaneo/nube", "/api/escaneo/ply"):
                from procesamiento import escaneo

                d = escaneo.carpeta(q.get("id", ""))
                if url.path.endswith("ply"):
                    return self._enviar(200, (d / "nube.ply").read_bytes(), "application/octet-stream",
                                        {"Content-Disposition": f'attachment; filename="escaneo_{d.name}.ply"'})
                return self._enviar(200, escaneo.nube_binaria(q.get("id", ""), int(q.get("max", 1_500_000))),
                                    "application/octet-stream")
            if url.path == "/api/perfil":
                cat, pose = self._cat_pose(q)
                return self._json(perfil_3d(cat, pose, (float(q["ax"]), float(q["ay"])), (float(q["bx"]), float(q["by"]))))
            if url.path == "/api/comparaciones":
                cat = q.get("cat", "")
                if cat not in cfg.CATEGORIAS:
                    raise ValueError("categoría inválida")
                return self._json(listar_comparaciones(cat))
            if url.path == "/api/comparar":
                cat, pose = self._cat_pose(q)
                return self._json(diferencia_z(cat, pose, q.get("ref", ""))[1])
            if url.path == "/api/histograma":
                cat, pose = self._cat_pose(q)
                return self._json(histograma_plano(cat, pose))
            if url.path == "/api/descargar":
                return self._descargar(q)
            if url.path == "/api/ajustes":
                from datos_sistema import ajustes

                return self._json(ajustes.leer())
            if url.path == "/api/sistema":
                return self._json(estado_sistema(q.get("hw", "1") == "1", q.get("forzar") == "1"))
            if url.path == "/api/manual":  # MANUAL.md, que la interfaz muestra con su índice
                return self._enviar(200, (RAIZ / "docs" / "MANUAL.md").read_bytes(), "text/markdown; charset=utf-8")
            if url.path == "/api/calibraciones":
                from procesamiento import calibracion_estereo as ce
                from datos_sistema import sesiones

                lista = ce.listar_calibraciones(DIR_CALIBRACION)
                for c in lista:
                    c["proceso"] = sesiones.proceso_de_poses("patron", c["poses"])
                return self._json(lista)
            if url.path == "/api/archivos":
                return self._json(listado_archivos())
            if url.path == "/api/captura/lista":
                from datos_sistema import archivos

                return self._json([p.name for p in archivos.frames_captura(q.get("carpeta", ""))])
            if url.path == "/api/captura/imagen":
                from datos_sistema import archivos

                return self._imagen(q, archivos.leer_frame(q.get("carpeta", ""), int(q.get("i", 0))), "intensidad")
            if url.path == "/api/calibracion":
                return self._json(errores_calibracion(q.get("variante", "independiente")))
            if url.path == "/api/nube":
                cat, pose = self._cat_pose(q)
                maximo = max(1000, min(int(q.get("max", 400_000)), 2_000_000))
                datos = generar_nube(cat, pose, maximo, q.get("indices") == "1", q.get("metodo"))
                return self._enviar(200, datos, "application/octet-stream")
            return self._error(404, "ruta desconocida")
        except FileNotFoundError as exc:
            return self._error(404, f"no disponible todavía: {exc}")
        except (ValueError, KeyError) as exc:
            return self._error(400, str(exc))
        except (OSError, EOFError, zipfile.BadZipFile) as exc:  # p. ej. .npz a medio escribir (versión vieja)
            return self._error(503, f"reintentar: {exc}")

    def do_POST(self) -> None:
        if not (self._host_valido() and self._post_valido()):
            return self._error(403, "petición rechazada: solo se aceptan peticiones JSON de la propia interfaz")
        url = urlparse(self.path)
        try:
            if url.path == "/api/ejecutar":
                ejecucion.lanzar(self._cuerpo())
                return self._json({"ok": True})
            if url.path == "/api/detener":
                ejecucion.detener()
                return self._json({"ok": True})
            if url.path == "/api/ajustes":  # los guarda la interfaz al cambiar cualquier ajuste
                from datos_sistema import ajustes

                cuerpo = self._cuerpo()
                if not isinstance(cuerpo.get("efectivos"), dict):
                    raise ValueError("faltan los ajustes efectivos")
                ajustes.guardar({k: cuerpo.get(k) for k in ("efectivos", "valores", "selects")})
                return self._json({"ok": True})
            if url.path == "/api/camara":  # exposición en vivo: la aplica el ejecutor (VistaEnVivo)
                us = float(self._cuerpo().get("exposicion_us", 0))
                if not 50 <= us <= 1_000_000:
                    raise ValueError("exposición fuera de rango")
                dir_vivo = cfg.DIR_RESULTADOS / ".vivo"
                dir_vivo.mkdir(parents=True, exist_ok=True)
                tmp = dir_vivo / "control.tmp"
                tmp.write_text(json.dumps({"exposicion_us": us}), encoding="utf-8")
                compat.reemplazar(tmp, dir_vivo / "control.json")
                return self._json({"ok": True, "activa": ejecucion.estado()["ejecutando"]})
            if url.path == "/api/comparacion/guardar":
                cuerpo = self._cuerpo()
                cat, pose = self._cat_pose({k: str(v) for k, v in cuerpo.items()})
                return self._json(guardar_comparacion(cat, pose))
            if url.path in ("/api/mediciones/guardar", "/api/mediciones/borrar", "/api/mediciones/actualizar"):
                from datos_sistema import mediciones

                cuerpo = self._cuerpo()
                cat, pose = self._cat_pose(cuerpo)
                if url.path.endswith("guardar"):
                    return self._json(mediciones.guardar(cat, pose, cuerpo.get("medicion") or {}))
                if url.path.endswith("borrar"):
                    return self._json(mediciones.borrar(cat, pose, str(cuerpo.get("id", ""))))
                return self._json(mediciones.actualizar(cat, pose, lambda fx, fy: punto_3d(cat, pose, fx, fy, 15)))
            if url.path in ("/api/mascara/previa", "/api/mascara/guardar", "/api/mascara/borrar"):
                cuerpo = self._cuerpo()
                cat, pose = self._cat_pose(cuerpo)
                if url.path.endswith("previa"):
                    return self._json(previa_mascara(cat, pose, cuerpo.get("parametros") or {},
                                                     vista=str(cuerpo.get("vista", "textura"))))
                if url.path.endswith("borrar"):
                    from procesamiento import mascara

                    otras = [p for p in cuerpo.get("poses") or [] if RE_POSE.match(str(p))]
                    return self._json({"borradas": [p for p in [pose, *otras] if mascara.borrar(cat, p)]})
                otras = [p for p in cuerpo.get("poses") or [] if RE_POSE.match(str(p))]
                return self._json(guardar_mascara(cat, pose, cuerpo.get("parametros") or {}, otras))
            if url.path == "/api/importar/elegir":  # ventana del sistema para elegir la carpeta
                from datos_sistema import importar

                if self.client_address[0] not in ("127.0.0.1", "::1"):  # se abriría en el equipo del servidor
                    return self._json({"error": "La ventana para elegir carpetas solo funciona en el equipo del servidor; escribe la ruta"}, 400)
                try:
                    return self._json({"ruta": importar.elegir_carpeta(self._cuerpo().get("inicial"))})
                except RuntimeError as exc:
                    return self._json({"error": str(exc)}, 500)
            if url.path == "/api/importar/analizar":  # qué se importaría de una carpeta (sin copiar nada)
                from datos_sistema import importar

                return self._json(importar.analizar(str(self._cuerpo().get("ruta", ""))))
            if url.path == "/api/notas":
                from datos_sistema import archivos

                cuerpo = self._cuerpo()
                archivos.guardar_nota(str(cuerpo.get("clave", "")), str(cuerpo.get("texto", "")))
                return self._json({"ok": True})
            if url.path == "/api/escaneo/borrar":
                import shutil

                from procesamiento import escaneo

                d = escaneo.carpeta(str(self._cuerpo().get("id", "")))
                if d.parent != escaneo.DIR_ESCANEOS or not d.is_dir():
                    raise ValueError("escaneo inválido")
                shutil.rmtree(d)
                return self._json({"ok": True})
            if url.path == "/api/poses/borrar":  # {cat, poses, simular}: simular = qué se movería
                from datos_sistema import archivos

                cuerpo = self._cuerpo()
                cat = str(cuerpo.get("cat", ""))
                poses = [str(p) for p in cuerpo.get("poses") or [] if RE_POSE.match(str(p))]
                if cat not in cfg.CATEGORIAS or not poses:
                    raise ValueError("categoría o poses inválidas")
                if cuerpo.get("simular"):
                    return self._json(archivos.capturas_de_poses(cat, poses))
                if ejecucion.estado()["ejecutando"]:
                    raise RuntimeError("hay un proceso en curso: espera a que termine")
                return self._json(archivos.borrar_poses(cat, poses))
            if url.path == "/api/montaje":  # cambia el montaje y reinicia el servidor (todo lee la configuración al arrancar)
                from datos_sistema import montajes

                if ejecucion.estado()["ejecutando"]:
                    raise RuntimeError("hay un proceso en curso: espera a que termine")
                montajes.fijar(str(self._cuerpo().get("id", "")))
                threading.Timer(0.6, _reiniciar).start()
                return self._json({"reinicia": True})
            if url.path == "/api/procesos/renombrar":
                from datos_sistema import archivos

                if ejecucion.estado()["ejecutando"]:
                    raise RuntimeError("hay un proceso en curso: espera a que termine")
                cuerpo = self._cuerpo()
                return self._json({"carpeta": archivos.renombrar_proceso(str(cuerpo.get("carpeta", "")),
                                                                         str(cuerpo.get("nombre", "")))})
            if url.path in ("/api/archivos/borrar", "/api/archivos/vaciar_papelera", "/api/configuracion/elegir",
                            "/api/archivos/restaurar"):
                if ejecucion.estado()["ejecutando"]:
                    raise RuntimeError("hay un proceso en curso: espera a que termine")
                return self._json(self._post_archivos(url.path, self._cuerpo()))
            if url.path == "/api/calibraciones/activar":
                from procesamiento import calibracion_estereo as ce
                if ejecucion.estado()["ejecutando"]:
                    raise RuntimeError("hay un proceso en curso: espera a que termine para cambiar de calibración")
                ident = str(self._cuerpo().get("id", ""))
                try:
                    with _lock_errores:
                        elegida = ce.activar_calibracion(ident, DIR_CALIBRACION)
                except FileNotFoundError as exc:
                    return self._error(404, str(exc))
                # Se ven y procesan las poses de la configuración de la que salió esa calibración
                descripcion = ce.usar_configuracion_de(elegida)
                difusor.emitir("log", {"texto": f"[OK] Calibración en uso: {ident}. Configuración vigente: "
                                                f"{descripcion}. Las poses se reconstruirán con ella en la próxima "
                                                f"ejecución."})
                return self._json(elegida)
            if url.path == "/api/entrada":
                ejecucion.entrada(str(self._cuerpo().get("texto", "")))
                return self._json({"ok": True})
            return self._error(404, "ruta desconocida")
        except RuntimeError as exc:
            return self._error(409, str(exc))
        except FileNotFoundError as exc:
            return self._error(404, str(exc))
        except (ValueError, KeyError, OSError) as exc:
            return self._error(400, str(exc))

    def _descargar(self, q: dict) -> None:
        """Archivos para llevarse: la nube .ply, los puntos en .csv o el informe de la calibración."""
        tipo = q.get("tipo", "")
        if tipo == "calibracion":
            ruta = DIR_CALIBRACION / "Estereo_TSC_0_2.json"
            if not ruta.exists():
                raise FileNotFoundError("no hay calibración")
            return self._enviar(200, ruta.read_bytes(), "application/json; charset=utf-8",
                                {"Content-Disposition": f'attachment; filename="calibracion_{ruta.stat().st_mtime:.0f}.json"'})
        if tipo == "parametros_calibracion":  # todos los parámetros de la calibración elegida (o la en uso)
            from procesamiento import calibracion_estereo as ce

            ident = q.get("id") or None
            datos = ce.exportar_parametros(ident, DIR_CALIBRACION)
            nombre = re.sub(r"[^\w.-]", "_", f"SL_TSC_{cfg.MONTAJE}_{ident or 'en_uso'}.json")
            return self._enviar(200, json.dumps(datos, indent=2, ensure_ascii=False).encode(),
                                "application/json; charset=utf-8",
                                {"Content-Disposition": f'attachment; filename="{nombre}"'})
        cat, pose = self._cat_pose(q)
        if tipo == "ply":
            from datos_sistema import rutas

            ruta = rutas.reconstruccion(cat, pose, "ply")
            if not ruta.exists():
                raise FileNotFoundError("esta pose aún no tiene reconstrucción")
            return self._enviar(200, ruta.read_bytes(), "application/octet-stream",
                                {"Content-Disposition": f'attachment; filename="{ruta.name}"'})
        if tipo == "csv":
            xyz = _xyz(cat, pose)
            m = xyz["Mask"].astype(bool) & np.isfinite(xyz["Z"])
            filas, cols = np.nonzero(m)
            datos = np.column_stack([cols, filas, xyz["X"][m], xyz["Y"][m], xyz["Z"][m]])
            import io

            buf = io.StringIO()
            buf.write("columna,fila,X_mm,Y_mm,Z_mm\n")
            np.savetxt(buf, datos, fmt=["%d", "%d", "%.3f", "%.3f", "%.3f"], delimiter=",")
            return self._enviar(200, buf.getvalue().encode(), "text/csv; charset=utf-8",
                                {"Content-Disposition": f'attachment; filename="{cat}_{pose}_xyz.csv"'})
        raise ValueError("tipo de descarga desconocido")

    def _post_archivos(self, ruta: str, cuerpo: dict) -> dict:
        from datos_sistema import archivos
        from procesamiento import calibracion_estereo as ce
        from datos_sistema import sesiones

        if ruta == "/api/archivos/borrar":
            carpetas = [str(c) for c in cuerpo.get("carpetas", [])]
            if not carpetas:
                raise ValueError("no se indicó qué borrar")
            with _lock_npz, _lock_errores:
                res = archivos.mover_a_papelera(carpetas)
                _cache_mapas.limpiar()
                _cache_errores.clear()
            difusor.emitir("log", {"texto": f"[OK] {len(carpetas)} captura(s) movidas a la papelera "
                                            f"({res['elementos']} elementos): {res['papelera']}"})
            return res
        if ruta == "/api/archivos/restaurar":
            with _lock_npz, _lock_errores:
                res = archivos.restaurar(str(cuerpo.get("lote", "")))
                _cache_mapas.limpiar()
                _cache_errores.clear()
            texto = f"[OK] Restaurado de la papelera: {res['devueltos']} elementos"
            if res["conflictos"]:
                texto += f" · [AVISO] {len(res['conflictos'])} ya existían y quedaron en la papelera"
            difusor.emitir("log", {"texto": texto})
            return res
        if ruta == "/api/archivos/vaciar_papelera":
            res = archivos.vaciar_papelera()
            difusor.emitir("log", {"texto": f"[OK] Papelera vaciada ({res['bytes'] / 1e6:.0f} MB liberados)."})
            return res
        # Elegir configuración: None = la última. Si hay una calibración hecha con sus poses, se pone en uso
        proceso = cuerpo.get("proceso") or None
        sesiones.fijar_configuracion(proceso)
        conf = sesiones.configuracion_vigente()
        objetivo = conf["proceso"] if conf else None  # también al volver a la última
        calib = None
        if objetivo:
            for c in ce.listar_calibraciones(DIR_CALIBRACION):  # de la más reciente a la más antigua
                if sesiones.proceso_de_poses("patron", c["poses"]) == objetivo:
                    calib = c["id"]
                    if not c["activa"]:
                        with _lock_errores:
                            ce.activar_calibracion(calib, DIR_CALIBRACION)
                    break
        texto = f"[OK] Configuración vigente: {'la última' if not proceso else 'desde ' + proceso}"
        if calib:
            texto += f" · calibración en uso: {calib}"
        elif objetivo:
            texto += " · [AVISO] ninguna calibración del historial salió de este proceso: calibra con él"
        difusor.emitir("log", {"texto": texto})
        return {"proceso": conf and conf["proceso"], "calibracion": calib}

    def _cat_pose(self, q: dict) -> tuple[str, str]:
        cat, pose = q.get("cat", ""), q.get("pose", "")
        if cat not in cfg.CATEGORIAS or not RE_POSE.match(pose):
            raise ValueError("categoría o pose inválida")
        return cat, pose

    def _estatico(self, nombre: str) -> None:
        ruta = (DIR_ESTATICO / nombre).resolve()
        if DIR_ESTATICO not in ruta.parents or not ruta.is_file():
            return self._error(404, "no encontrado")
        self._enviar(200, ruta.read_bytes(), TIPOS_MIME.get(ruta.suffix, "application/octet-stream"))

    def _imagen(self, q: dict, img: np.ndarray | None = None, escala: str = "") -> None:
        if img is None:
            cat, pose = self._cat_pose(q)
            img, escala = generar_imagen(cat, pose, q.get("tipo", ""))
        ancho = max(64, min(int(q.get("ancho", 900)), 2000))
        if img.shape[1] > ancho:
            f = ancho / img.shape[1]
            img = cv2.resize(img, (0, 0), fx=f, fy=f, interpolation=cv2.INTER_AREA)
        if img.dtype != np.uint8:
            img = np.clip(img, 0, 255).astype(np.uint8)
        # JPEG para mapas continuos y ruidosos (≈10x más liviano que PNG); PNG para la máscara (colores planos)
        tipo = q.get("tipo", "")
        ext, mime, params = (".png", "image/png", []) if tipo == "mascara" else (
            ".jpg", "image/jpeg", [cv2.IMWRITE_JPEG_QUALITY, 90])
        ok, datos = cv2.imencode(ext, img, params)
        if not ok:
            raise OSError("no se pudo codificar la imagen")
        self._enviar(200, datos.tobytes(), mime,
                     {"X-Escala": quote(escala),
                      "Access-Control-Expose-Headers": "X-Escala"})

    def _eventos(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = difusor.suscribir()
        try:
            self._sse("estado", ejecucion.estado())
            while True:
                try:
                    evento, datos = q.get(timeout=15)
                    self._sse(evento, datos)
                except queue.Empty:
                    self.wfile.write(b": latido\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            difusor.desuscribir(q)

    def _sse(self, evento: str, datos: dict) -> None:
        self.wfile.write(f"event: {evento}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n".encode())
        self.wfile.flush()


def _reiniciar() -> None:
    """Vuelve a lanzar el servidor con los mismos argumentos (tras cambiar de montaje). La página
    espera a que vuelva y se recarga; no se abre otro navegador."""
    print("[INFO] Reiniciando el servidor para aplicar el montaje nuevo…", flush=True)
    os.environ["TESIS_REINICIO"] = "1"
    if not compat.ES_WINDOWS:
        os.execv(sys.executable, [sys.executable, *sys.argv])
    # En Windows os.execv lanza otro proceso y termina este, y la consola queda a medias. Con el
    # lanzador (iniciar_interfaz.bat) se sale con el código 3 y el .bat lo vuelve a abrir; sin él,
    # se lanza el servidor nuevo y este termina (el nuevo reintenta el puerto mientras se libera).
    if os.environ.get("TESIS_LANZADOR") == "bat":
        os._exit(CODIGO_REINICIO)
    import subprocess

    subprocess.Popen([sys.executable, *sys.argv])
    os._exit(0)


CODIGO_REINICIO = 3


def _abrir_servidor(host: str, puerto: int) -> ThreadingHTTPServer:
    """Tras un reinicio el puerto puede tardar un momento en liberarse: se reintenta unos segundos."""
    for k in range(40):
        try:
            return ThreadingHTTPServer((host, puerto), Manejador)
        except OSError:
            if not os.environ.get("TESIS_REINICIO") or k == 39:
                raise
            import time

            time.sleep(0.25)
    raise AssertionError("inalcanzable")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interfaz web del sistema de proyección de franjas.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="127.0.0.1 = solo este equipo (por defecto); 0.0.0.0 = toda la red, sin autenticación")
    parser.add_argument("--puerto", type=int, default=8000)
    parser.add_argument("--sin-navegador", action="store_true", help="No abrir el navegador automáticamente")
    args = parser.parse_args()
    compat.consola_utf8()

    threading.Thread(target=vigilar, daemon=True).start()
    servidor = _abrir_servidor(args.host, args.puerto)
    servidor.daemon_threads = True
    servidor.red_abierta = args.host not in ("127.0.0.1", "localhost", "::1")
    url = f"http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{args.puerto}"
    print(f"[OK] Interfaz en {url}  (datos: {cfg.DATOS})  — Ctrl+C para salir")
    if args.host == "0.0.0.0":
        print("[AVISO] Accesible desde la red sin contraseña: cualquiera en la red puede lanzar capturas.")
    print(f"[OK] Montaje: {cfg.MONTAJE_INFO['nombre']}")
    if not args.sin_navegador and not os.environ.get("TESIS_REINICIO"):
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando…")
    finally:
        ejecucion.detener()
        servidor.server_close()


if __name__ == "__main__":
    main()
