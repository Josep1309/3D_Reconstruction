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
