"""Compatibilidad Linux/Windows (datos_sistema/compat.py) y transporte HID del LightCrafter."""

from __future__ import annotations

import os
import struct
import sys
import types

import pytest

from datos_sistema import compat


@pytest.mark.parametrize("nombre", ["2026-11-26_1016", "20261126_125256", "pose_42", "a b"])
def test_nombre_seguro_acepta(nombre):
    assert compat.nombre_seguro(nombre)


@pytest.mark.parametrize("nombre", ["", ".", "..", ".oculto", "a/b", "a\\b", "..\\x", "C:x", "C:\\Windows", "a\0b"])
def test_nombre_seguro_rechaza(nombre):
    assert not compat.nombre_seguro(nombre)


def test_reemplazar_reintenta_en_windows(tmp_path, monkeypatch):
    origen, destino = tmp_path / "a.tmp", tmp_path / "a.json"
    origen.write_text("nuevo")
    destino.write_text("viejo")
    fallos = {"n": 0}
    real = os.replace

    def replace_ocupado(a, b):
        if fallos["n"] < 3:  # el destino está abierto por otro proceso las primeras veces
            fallos["n"] += 1
            raise PermissionError("en uso")
        real(a, b)

    monkeypatch.setattr(compat.os, "replace", replace_ocupado)
    monkeypatch.setattr(compat.time, "sleep", lambda s: None)
    monkeypatch.setattr(compat, "ES_WINDOWS", True)
    compat.reemplazar(origen, destino)
    assert destino.read_text() == "nuevo" and fallos["n"] == 3
    # en Linux no se reintenta: el error es real
    fallos["n"] = 0
    origen.write_text("otro")
    monkeypatch.setattr(compat, "ES_WINDOWS", False)
    with pytest.raises(PermissionError):
        compat.reemplazar(origen, destino)


def test_validadores_rechazan_rutas_de_windows(tmp_path):
    from datos_sistema import rutas
    from procesamiento import calibracion_estereo as ce

    for malo in ("objeto/..\\..\\x", "objeto/C:x"):
        with pytest.raises(ValueError):
            rutas.ruta_captura(malo)
    for malo in ("..\\x", "C:x"):
        with pytest.raises(ValueError):
            ce.exportar_parametros(malo, tmp_path)
        with pytest.raises(FileNotFoundError):
            ce.activar_calibracion(malo, tmp_path)


class _DispositivoFalso:
    """hid.device() de hidapi: responde a la lectura de exposición y período del DLPC350."""

    def __init__(self):
        self.abierto, self.escrito, self.pendiente, self.no_bloqueante = None, [], [], False

    def open_path(self, ruta):
        self.abierto = ruta

    def set_nonblocking(self, v):
        self.no_bloqueante = bool(v)

    def write(self, datos):
        self.escrito.append(bytes(datos))
        flags, seq = datos[1], datos[2]
        if flags & 0x80:  # lectura: responde exposición 49700 µs y período 50000 µs (sin Report ID)
            carga = struct.pack("<II", 49_700, 50_000)
            self.pendiente.append(bytes([0x40, seq]) + struct.pack("<H", len(carga)) + carga + bytes(64 - 4 - len(carga)))
        return len(datos)

    def read(self, n, espera_ms=0):
        assert self.no_bloqueante, "sin set_nonblocking, read(…, 0) se queda esperando para siempre"
        return list(self.pendiente.pop(0)) if self.pendiente else []

    def close(self):
        self.abierto = None

    def error(self):
        return ""


def test_lightcrafter_con_hidapi(monkeypatch):
    dev = _DispositivoFalso()
    hid = types.SimpleNamespace(
        device=lambda: dev,
        enumerate=lambda vid, pid: [{"path": b"otra", "interface_number": 1, "usage_page": 1},
                                    {"path": b"control", "interface_number": 0, "usage_page": 0xFF00}])
    monkeypatch.setitem(sys.modules, "hid", hid)
    monkeypatch.setattr(compat, "ES_WINDOWS", True)
    from captura import configurar_lightcrafter as lcr

    with lcr.LightCrafter4500() as d:
        assert dev.abierto == b"control" and d.device_path == b"control"  # la interfaz 0, la de control
        assert d.leer_exposicion_y_periodo() == (49_700, 50_000)
    assert dev.abierto is None
    assert all(len(p) == 65 and p[0] == 0 for p in dev.escrito)  # Report ID 0 + 64 bytes


def test_pantallas_en_windows_usa_la_api(monkeypatch):
    from captura import proyector_hdmi as ph

    lista = [{"nombre": "DISPLAY1", "principal": True, "ancho": 1920, "alto": 1080, "x": 0, "y": 0},
             {"nombre": "DISPLAY2", "principal": False, "ancho": 1280, "alto": 800, "x": 1920, "y": 0}]
    monkeypatch.setattr(compat, "ES_WINDOWS", True)
    monkeypatch.setattr(compat, "pantallas_windows", lambda: lista)
    assert ph.ubicar_pantalla(1280, 800, "auto")["nombre"] == "DISPLAY2"


def test_detener_en_windows_envia_ctrl_break_y_cierra_la_entrada(monkeypatch):
    import signal

    import ejecucion as ej

    llamadas = []

    class Entrada:
        def close(self):
            llamadas.append("stdin cerrada")

    class Proceso:
        stdin = Entrada()

        def send_signal(self, s):
            llamadas.append(("señal", s))

        def terminate(self):
            llamadas.append("terminate")

    monkeypatch.setattr(signal, "CTRL_BREAK_EVENT", 1, raising=False)
    monkeypatch.setattr(compat, "ES_WINDOWS", True)
    e = ej.Ejecucion()
    e.proc = Proceso()
    e._senal_detener()
    assert llamadas == [("señal", 1), "stdin cerrada"]  # nunca terminate(): mataría sin cerrar la cámara
    llamadas.clear()
    monkeypatch.setattr(compat, "ES_WINDOWS", False)
    e._senal_detener()
    assert llamadas == ["terminate"]  # Linux: SIGTERM
