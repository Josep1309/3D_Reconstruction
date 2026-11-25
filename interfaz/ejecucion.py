"""Ejecución del pipeline en un subproceso y difusión de eventos (SSE) a los navegadores.

Lee la salida del ejecutor: registro, etapa, progreso, preguntas (@@pregunta/@@meta), control
de calidad de cada pose (@@calidad) y vista en vivo (@@vivo/@@previa)."""

from __future__ import annotations

import codecs
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from comun import RAIZ


RE_MARCA = re.compile(r"@@(vivo) (\d+) (\d+)|@@(previa) ([\d.]+)(?: ([\d.]+))?(?: (\d+))?|@@exposicion [\d.]+")
RE_PREGUNTA = re.compile(r"^@@pregunta (.*)$")  # el ejecutor anuncia así cada input() (ejecutor._input_marcado)
RE_META = re.compile(r"^@@meta (\{.*\})$")        # datos de la próxima pregunta (capturar_patrones.preguntar)
RE_CALIDAD = re.compile(r"^@@calidad (\{.*\})$")  # control de una pose recién capturada


# Progreso: «=== Fase relativa: 'plano' (3 poses) ===», «=== RECONSTRUCCIÓN 3D: 'PLANO' (3 poses) ===»,
# «=== Calibración Estéreo Tradicional (8 poses, …» y una línea «  [pose_XX] …» por pose terminada
RE_TOTAL = re.compile(r"^=+ *[^:(]+?(?:: '(\w+)')? \((\d+) poses")
RE_POSE_HECHA = re.compile(r"^\s+\[pose_\d+\]")


class Difusor:
    def __init__(self) -> None:
        self.clientes: list[queue.Queue] = []
        self.lock = threading.Lock()
        self.historial: list[str] = []  # registro reciente para quien se conecta tarde

    def suscribir(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=2000)
        with self.lock:
            self.clientes.append(q)
            for texto in self.historial[-400:]:
                q.put(("log", {"texto": texto}))
        return q

    def desuscribir(self, q: queue.Queue) -> None:
        with self.lock:
            if q in self.clientes:
                self.clientes.remove(q)

    def emitir(self, evento: str, datos: dict) -> None:
        if evento == "log":
            self.historial.append(datos["texto"])
            del self.historial[:-2000]
        with self.lock:
            for q in list(self.clientes):
                try:
                    q.put_nowait((evento, datos))
                except queue.Full:
                    pass


difusor = Difusor()


class Ejecucion:
    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.etapa: str | None = None
        self.esperando = False
        self.pregunta = ""
        self.inicio: float | None = None
        self.ultimo_codigo: int | None = None
        self.meta: dict | None = None       # datos de la pregunta en curso (tipo, pose, motivos…)
        self.progreso: dict | None = None   # {"cat", "i", "n", "t0"} de la etapa en curso
        self.calidades: list[dict] = []      # control de cada pose capturada en esta ejecución
        self.ultimo_error = ""               # última línea [ERROR] (se muestra si el proceso falla)
        self.lock = threading.Lock()

    @property
    def activa(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def estado(self) -> dict:
        return {
            "ejecutando": self.activa, "etapa": self.etapa, "esperando": self.esperando,
            "pregunta": self.pregunta if self.esperando else "",
            "meta": self.meta if self.esperando else None,
            "progreso": self._progreso(),
            "calidades": self.calidades[-60:],
            "error": self.ultimo_error if self.ultimo_codigo not in (None, 0) else "",
            "codigo": self.ultimo_codigo,
            "segundos": round(time.time() - self.inicio, 1) if self.inicio and self.activa else None,
        }

    def _progreso(self) -> dict | None:
        p = self.progreso
        if not p or not self.activa:
            return None
        transcurrido = time.time() - p["t0"]
        restante = transcurrido / p["i"] * (p["n"] - p["i"]) if p["i"] else None
        return {"cat": p["cat"], "i": p["i"], "n": p["n"], "restante_s": round(restante) if restante is not None else None}

    def _emitir_estado(self) -> None:
        difusor.emitir("estado", self.estado())

    def lanzar(self, conf: dict) -> None:
        with self.lock:
            if self.activa:
                raise RuntimeError("Ya hay un proceso en ejecución.")
            ruta = Path(tempfile.mkstemp(prefix="pipeline_", suffix=".json")[1])
            ruta.write_text(json.dumps(conf), encoding="utf-8")
            env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
            self.proc = subprocess.Popen(
                [sys.executable, "-u", str(Path(__file__).with_name("ejecutor.py")), str(ruta)],
                cwd=RAIZ, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            self.etapa, self.esperando, self.inicio, self.ultimo_codigo = None, False, time.time(), None
            self.meta, self.progreso, self.calidades, self.ultimo_error = None, None, [], ""
        difusor.emitir("log", {"texto": f"\n▶ Ejecución iniciada {time.strftime('%H:%M:%S')}"})
        self._emitir_estado()
        threading.Thread(target=self._leer_salida, args=(self.proc, ruta), daemon=True).start()

    def _linea(self, linea: str) -> None:
        # Mensajes internos de la vista en vivo: se extraen aunque otro hilo los haya pegado a
        # una línea del registro
        for m in RE_MARCA.finditer(linea):
            if m.group(1):
                difusor.emitir("vivo", {"i": int(m.group(2)), "n": int(m.group(3))})
            elif m.group(4):
                difusor.emitir("vivo", {"previa": True, "saturacion": float(m.group(5)),
                                        "nitidez": float(m.group(6) or 0),
                                        "tablero": None if m.group(7) is None else int(m.group(7))})
        linea = RE_MARCA.sub("", linea)
        if not linea.strip():
            return
        m = RE_META.match(linea.strip())
        if m:
            try:
                self.meta = json.loads(m.group(1))
            except json.JSONDecodeError:
                self.meta = None
            return
        m = RE_CALIDAD.match(linea.strip())
        if m:
            try:
                calidad = json.loads(m.group(1))
            except json.JSONDecodeError:
                return
            self.calidades.append(calidad)
            difusor.emitir("calidad", calidad)
            return
        m = RE_TOTAL.match(linea.strip())
        if m:
            self.progreso = {"cat": (m.group(1) or "patron").lower(), "i": 0, "n": int(m.group(2)), "t0": time.time()}
            self._emitir_estado()
        elif self.progreso and RE_POSE_HECHA.match(linea):
            self.progreso["i"] = min(self.progreso["i"] + 1, self.progreso["n"])
            self._emitir_estado()
        if "[ERROR]" in linea:
            self.ultimo_error = linea.strip()
        m = RE_PREGUNTA.match(linea.strip())
        if m:  # el proceso espera una respuesta
            self.pregunta = m.group(1)
            self.esperando = True
            difusor.emitir("log", {"texto": self.pregunta})
            self._emitir_estado()
            return
        m = re.match(r"# ETAPA: (\w+)", linea)
        if m:
            self.etapa = m.group(1)
            self.progreso = None
            self._emitir_estado()
        if set(linea.strip()) == {"#"}:
            return  # separadores decorativos
        difusor.emitir("log", {"texto": linea})

    def _leer_salida(self, proc: subprocess.Popen, ruta_conf: Path) -> None:
        decodificador = codecs.getincrementaldecoder("utf-8")(errors="replace")
        pendiente = ""
        fd = proc.stdout.fileno()
        while True:
            bloque = os.read(fd, 4096)
            if not bloque:
                break
            pendiente += decodificador.decode(bloque)
            *lineas, pendiente = pendiente.split("\n")
            for linea in lineas:
                self._linea(linea.rstrip("\r"))
        if pendiente:
            self._linea(pendiente)
        codigo = proc.wait()
        ruta_conf.unlink(missing_ok=True)
        self.ultimo_codigo, self.esperando, self.etapa = codigo, False, None
        texto = "✔ Proceso terminado correctamente" if codigo == 0 else f"✖ Proceso terminado con código {codigo}"
        difusor.emitir("log", {"texto": f"{texto} ({time.time() - (self.inicio or time.time()):.1f} s)"})
        self._emitir_estado()

    def entrada(self, texto: str) -> None:
        if not self.activa or self.proc.stdin is None:
            raise RuntimeError("No hay un proceso esperando entrada.")
        self.proc.stdin.write((texto + "\n").encode())
        self.proc.stdin.flush()
        self.esperando = False
        self.meta = None
        difusor.emitir("log", {"texto": f"  ⏎ {texto or '(Enter)'}"})
        self._emitir_estado()

    def detener(self) -> None:
        if self.activa:
            self.proc.terminate()  # el ejecutor lo convierte en KeyboardInterrupt y cierra la cámara
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            difusor.emitir("log", {"texto": "■ Proceso detenido por el usuario"})


ejecucion = Ejecucion()
