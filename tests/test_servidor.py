"""Servidor web: protección contra peticiones de otras páginas y API básica."""

from __future__ import annotations

import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

import servidor


@pytest.fixture(scope="module")
def puerto():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Manejador)
    srv.daemon_threads = True
    srv.red_abierta = False
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


def pedir(puerto, metodo, ruta, cuerpo=None, cabeceras=None):
    con = http.client.HTTPConnection("127.0.0.1", puerto, timeout=10)
    datos = json.dumps(cuerpo).encode() if isinstance(cuerpo, dict) else cuerpo
    con.request(metodo, ruta, body=datos, headers=cabeceras or {})
    r = con.getresponse()
    return r.status, r.read()


def test_get_normal(puerto):
    estado, cuerpo = pedir(puerto, "GET", "/api/config")
    assert estado == 200 and b"etapas" in cuerpo


def test_host_ajeno_rechazado(puerto):
    estado, _ = pedir(puerto, "GET", "/api/estado", cabeceras={"Host": "malo.com"})
    assert estado == 403


def test_formulario_de_otra_pagina_rechazado(puerto):
    """Un formulario text/plain (lo único que una página ajena puede enviar sin CORS)."""
    estado, _ = pedir(puerto, "POST", "/api/ejecutar", b'{"etapas": {}}', {"Content-Type": "text/plain"})
    assert estado == 403


def test_origen_ajeno_rechazado(puerto):
    estado, _ = pedir(puerto, "POST", "/api/entrada", {"texto": ""},
                      {"Content-Type": "application/json", "Origin": "http://malo.com"})
    assert estado == 403


def test_post_propio_aceptado(puerto):
    estado, cuerpo = pedir(puerto, "POST", "/api/entrada", {"texto": ""},
                           {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{puerto}",
                            "Host": f"127.0.0.1:{puerto}"})
    assert estado == 409 and "esperando" in cuerpo.decode()  # pasa la seguridad; no hay proceso


def test_borrar_sin_capturas_es_error_400(puerto):
    estado, _ = pedir(puerto, "POST", "/api/archivos/borrar", {"carpetas": []}, {"Content-Type": "application/json"})
    assert estado == 400


def test_borrar_ruta_fuera_de_capturas_rechazado(puerto):
    estado, _ = pedir(puerto, "POST", "/api/archivos/borrar", {"carpetas": ["../../etc"]},
                      {"Content-Type": "application/json"})
    assert estado == 400


def test_elegir_carpeta_con_ventana_del_sistema(puerto, tmp_path, monkeypatch):
    """La ventana la abre el servidor (zenity); aquí uno falso que responde una ruta o cancela."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    falso = bin_ / "zenity"
    falso.write_text("#!/bin/sh\necho /home/alguien/capturas_viejas\n")
    falso.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}:/usr/bin:/bin")
    estado, cuerpo = pedir(puerto, "POST", "/api/importar/elegir", {}, {"Content-Type": "application/json"})
    assert estado == 200 and json.loads(cuerpo)["ruta"] == "/home/alguien/capturas_viejas"
    falso.write_text("#!/bin/sh\nexit 1\n")  # el usuario cancela
    estado, cuerpo = pedir(puerto, "POST", "/api/importar/elegir", {}, {"Content-Type": "application/json"})
    assert estado == 200 and json.loads(cuerpo)["ruta"] is None


def test_avance_de_etapas_desde_la_salida():
    """El panel de avance se arma con la salida del pipeline: plan, etapa, paso, i/n y partes."""
    import ejecucion

    e = ejecucion.Ejecucion()
    e.__class__ = type("EjecucionActiva", (ejecucion.Ejecucion,), {"activa": property(lambda s: True)})
    for linea in ["[PIPELINE] Etapas: fase_relativa -> calibracion -> reconstruccion", "# ETAPA: fase_relativa",
                  "[PIPELINE] 'fase_relativa' terminada en 1.5 s", "# ETAPA: calibracion",
                  '@@avance {"paso": "Cargando las fases del patrón"}',
                  "=== Calibración Estéreo Tradicional (8 poses, cámara 1280x1024) ===", "  [pose_23] 108 círculos"]:
        e._linea(linea)
    s = e.estado()
    assert s["plan"] == ["fase_relativa", "calibracion", "reconstruccion"] and s["etapa"] == "calibracion"
    assert s["hechas"] == {"fase_relativa": 1.5}
    assert s["paso"] == "Calibración Estéreo Tradicional" and (s["progreso"]["i"], s["progreso"]["n"]) == (1, 8)
    for linea in ["# ETAPA: reconstruccion", '@@avance {"partes": 2}', "=== RECONSTRUCCIÓN 3D: 'PLANO' (2 poses) ===",
                  "  [pose_17] 1 puntos", "  [pose_18] 1 puntos", "=== RECONSTRUCCIÓN 3D: 'OBJETO' (2 poses) ===", "  [pose_06] 1 puntos"]:
        e._linea(linea)
    s = e.estado()
    assert "calibracion" in s["hechas"] and s["paso"] == "Reconstrucción 3D: 'objeto'"
    assert s["progreso"]["fraccion_etapa"] == 0.75  # plano completo (1 de 2 partes) + objeto 1/2
