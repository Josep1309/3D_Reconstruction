"""Configuración por USB (HID) del proyector TI DLP LightCrafter 4500 (DLPC350).

Modifica los parámetros en la sección 'PARÁMETROS DE CONFIGURACIÓN' de abajo
y ejecuta, desde la carpeta del proyecto:
    .env/bin/python configurar_lightcrafter.py

Si da error de permisos sobre /dev/hidrawX, instala una vez la regla udev:
    ./instalar.sh --udev        (ver MANUAL.md §20.4)
"""

from __future__ import annotations

import os
import select
import struct
import time
from pathlib import Path

import configuracion as cfg

# ==============================================================================
# --- PARÁMETROS DE CONFIGURACIÓN (EDITA AQUÍ) ---
# ==============================================================================
# Para un trigger externo de 20 Hz (un pulso del Arduino cada 50 000 us):
# - EXPOSICION_US: Tiempo que el patrón permanece encendido (en microsegundos).
# - PERIODO_US:    Tiempo total del ciclo del patrón (en microsegundos).
#                  Nota: Si tu secuencia en el LightCrafter tiene "Clear DMD after
#                  exposure" (Insert Black) activado, PERIODO_US debe ser al menos
#                  EXPOSICION_US + 230 us (ej. 45000 y 48000). Si lo tiene desactivado,
#                  el DLPC350 exige EXPOSICION_US == PERIODO_US (el script lo ajusta
#                  automáticamente si detecta esa bandera en la validación).
EXPOSICION_US = cfg.LCR_EXPOSICION_US   # 49.7 ms de exposición del patrón (en configuracion.py)
PERIODO_US = cfg.LCR_PERIODO_US         # 50 ms de período (= pulso de 20 Hz del Arduino)

REINICIAR_SECUENCIA = True     # True = inicia (START) la proyección tras validar los tiempos
SOLO_LEER = False              # True = solo consulta los valores actuales sin modificarlos
DISPOSITIVO_HID = None         # None = buscar automáticamente (o ej. "/dev/hidraw2")
# ==============================================================================


# Identificadores USB del TI DLP LightCrafter 4500 (DLPC350)
VID_TI = 0x0451
PID_LCR4500 = 0x6401

# Comandos USB (16-bit: CMD2=0x1A, CMD3=0xXX) del controlador DLPC350 (DLPU010)
CMD_STATUS_HW = 0x1A0A         # Estado interno del hardware/secuenciador
CMD_VALIDATE_DATA = 0x1A1A     # Inicia y consulta validación de la secuencia (I2C 0x7D)
CMD_DISPLAY_MODE = 0x1A1B      # 0x00 = Video Mode, 0x01 = Pattern Display Mode
CMD_SEQ_CONTROL = 0x1A24       # 0x00 = Stop, 0x01 = Pause, 0x02 = Start
CMD_EXPOSURE_PERIOD = 0x1A29   # <II (exposure_us, period_us)


class LightCrafter4500:
    """Controlador USB HID directo en Linux (/dev/hidraw*) para DLP LightCrafter 4500."""

    def __init__(self, device_path: str | None = None) -> None:
        self.device_path = device_path or self._buscar_hidraw()
        self.fd: int | None = None
        self._seq = 1

    @staticmethod
    def _buscar_hidraw() -> str:
        """Busca en /sys/class/hidraw la interfaz de control (input0) del DLPC350 (0451:6401)."""
        base = Path("/sys/class/hidraw")
        candidatos: list[str] = []
        if base.exists():
            for hid_dir in sorted(base.iterdir()):
                uevent_file = hid_dir / "device" / "uevent"
                if not uevent_file.exists():
                    continue
                contenido = uevent_file.read_text(errors="ignore").upper()
                es_dlpc350 = (
                    f"{VID_TI:08X}:{PID_LCR4500:08X}" in contenido
                    or f"{VID_TI:04X}:{PID_LCR4500:04X}" in contenido
                    or "DLPC350" in contenido
                )
                if not es_dlpc350:
                    continue

                dev_node = f"/dev/{hid_dir.name}"
                rd_file = hid_dir / "device" / "report_descriptor"
                if rd_file.exists():
                    rd = rd_file.read_bytes()
                    if rd.startswith(b"\x06\x00\xff"):
                        return dev_node
                if "INPUT0" in contenido:
                    return dev_node
                candidatos.append(dev_node)

        if candidatos:
            return candidatos[0]

        raise FileNotFoundError(
            "No se detectó el DLP LightCrafter 4500 por USB (VID=0x0451, PID=0x6401).\n"
            "Verifica que el cable mini-USB del LightCrafter esté conectado a esta PC "
            "y que el proyector esté encendido."
        )

    def open(self) -> None:
        if self.fd is None:
            try:
                self.fd = os.open(self.device_path, os.O_RDWR | os.O_NONBLOCK)
            except PermissionError as exc:
                raiz = Path(__file__).resolve().parent
                raise PermissionError(
                    f"Sin permisos para abrir '{self.device_path}'.\n"
                    f"Solución permanente (una sola vez), desde '{raiz}':\n"
                    f"    ./instalar.sh --udev\n"
                    f"y desconecta/conecta el USB del LightCrafter. Solución temporal (hasta reiniciar):\n"
                    f"    sudo chmod a+rw {self.device_path}\n"
                    f"Más detalles: MANUAL.md §20.4"
                ) from exc

    def close(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self) -> LightCrafter4500:
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _vaciar_buffer_lectura(self) -> None:
        assert self.fd is not None
        while True:
            r, _, _ = select.select([self.fd], [], [], 0.0)
            if not r:
                break
            try:
                os.read(self.fd, 65)
            except BlockingIOError:
                break

    def _enviar_comando(
        self, cmd: int, payload: bytes = b"", lectura: bool = False
    ) -> bytes:
        """Envía un paquete HID de 64 bytes (con Report ID 0x00) al DLPC350."""
        if self.fd is None:
            self.open()
        assert self.fd is not None

        self._vaciar_buffer_lectura()

        # Byte de banderas: Bit 7 = Read(1)/Write(0), Bit 6 = Reply solicitada (1)
        flags = 0xC0 if lectura else 0x40
        seq = self._seq & 0xFF
        self._seq = (self._seq + 1) & 0xFF

        data_len = 2 + len(payload)
        paquete = bytearray(65)
        paquete[0] = 0x00  # Report ID
        paquete[1] = flags
        paquete[2] = seq
        struct.pack_into("<H", paquete, 3, data_len)
        struct.pack_into("<H", paquete, 5, cmd)
        paquete[7 : 7 + len(payload)] = payload

        os.write(self.fd, bytes(paquete))

        # Esperar respuesta del controlador DLPC350
        r, _, _ = select.select([self.fd], [], [], 2.0)
        if not r:
            raise TimeoutError(
                f"Timeout esperando respuesta del LightCrafter para el comando 0x{cmd:04X}"
            )

        resp = os.read(self.fd, 65)
        offset = 1 if len(resp) == 65 else 0
        resp_flags = resp[offset]
        if resp_flags & 0x20:  # Bit 5 indica error NACK del DLPC350
            raise RuntimeError(
                f"El LightCrafter reportó un error (NACK) en el comando 0x{cmd:04X}"
            )

        resp_len = struct.unpack_from("<H", resp, offset + 2)[0]
        # En hidMessageStruct del DLPC350, 'cmd' y 'data' comparten un union en el byte 4:
        # en las respuestas (Reply), los datos comienzan en offset + 4 con longitud resp_len.
        inicio = offset + 4
        return bytes(resp[inicio : inicio + resp_len])

    def detener_secuencia(self) -> None:
        """Detiene la proyección de patrones (necesario antes de cambiar tiempos)."""
        self._enviar_comando(CMD_SEQ_CONTROL, b"\x00")
        time.sleep(0.1)

    def pausar_secuencia(self) -> None:
        """Pausa la secuencia de patrones actual."""
        self._enviar_comando(CMD_SEQ_CONTROL, b"\x01")
        time.sleep(0.05)

    def iniciar_secuencia(self) -> None:
        """Inicia la secuencia de patrones previamente validada."""
        self._enviar_comando(CMD_SEQ_CONTROL, b"\x02")
        time.sleep(0.05)

    def leer_exposicion_y_periodo(self) -> tuple[int, int]:
        """Lee (exposicion_us, periodo_us) actualmente configurados en el DLPC350."""
        datos = self._enviar_comando(CMD_EXPOSURE_PERIOD, lectura=True)
        if len(datos) < 8:
            raise RuntimeError(
                f"Respuesta incompleta al leer exposición/período ({len(datos)} bytes)"
            )
        exposure_us, period_us = struct.unpack("<II", datos[:8])
        return exposure_us, period_us

    def _validar_lut(self) -> int:
        """Ejecuta el comando Validate Data (0x1A1A) y espera a que termine."""
        # Iniciar validación escribiendo 0x00 en 0x1A1A
        self._enviar_comando(CMD_VALIDATE_DATA, b"\x00", lectura=False)

        # Consultar 0x1A1A hasta que el bit 7 (Busy) se limpie o pasen 2 segundos
        for _ in range(40):
            time.sleep(0.05)
            estado = self._enviar_comando(CMD_VALIDATE_DATA, lectura=True)
            if not estado:
                continue
            val_byte = estado[0]
            # En DLPC350, el bit 7 indica que la validación sigue en curso
            if (val_byte & 0x80) == 0:
                return val_byte

        return val_byte

    def configurar_exposicion_y_periodo(
        self, exposure_us: int, period_us: int, reiniciar: bool = True
    ) -> int:
        """Configura el tiempo de exposición y el período del patrón en microsegundos."""
        if exposure_us <= 0 or period_us <= 0:
            raise ValueError("La exposición y el período deben ser mayores que 0 us.")
        if exposure_us > period_us:
            raise ValueError(
                f"La exposición ({exposure_us} us) no puede ser mayor que el período ({period_us} us)."
            )

        # 1. Verificar que esté en Pattern Display Mode (0x01) sin reiniciarlo si ya lo está
        modo_actual = self._enviar_comando(CMD_DISPLAY_MODE, lectura=True)
        if not modo_actual or modo_actual[0] != 0x01:
            self._enviar_comando(CMD_DISPLAY_MODE, b"\x01")
            time.sleep(0.1)

        # 2. Detener la secuencia antes de modificar registros
        self.detener_secuencia()

        # 3. Enviar nuevo Exposure Time y Frame Period (en microsegundos, uint32 little-endian)
        payload = struct.pack("<II", int(exposure_us), int(period_us))
        self._enviar_comando(CMD_EXPOSURE_PERIOD, payload, lectura=False)
        time.sleep(0.05)

        # 4. Ejecutar validación de hardware del DLPC350 (0x1A1A - obligatorio antes de Start)
        codigo_val = self._validar_lut()

        # Si el bit 3 (0x08) o bit 0 (0x01) se activa porque la LUT fue creada sin
        # "Clear DMD after exposure" (Insert Black desactivado), el DLPC350 exige
        # que Exposure == Period. Probamos igualando Period = Exposure automáticamente.
        if (codigo_val & 0x09) != 0 and exposure_us != period_us:
            print(
                f"[INFO] La secuencia en el LightCrafter requiere Exposición == Período "
                f"(validación=0x{codigo_val:02X}). Ajustando ambos a {exposure_us} us..."
            )
            payload_igual = struct.pack("<II", int(exposure_us), int(exposure_us))
            self._enviar_comando(CMD_EXPOSURE_PERIOD, payload_igual, lectura=False)
            time.sleep(0.05)
            codigo_val = self._validar_lut()

        if codigo_val != 0:
            print(f"[WARN] Bandera de validación DLPC350 = 0x{codigo_val:02X}")
            if codigo_val & 0x01:
                print("       - Bit 0: Exposición o período fuera de rango para la profundidad de bits.")
            if codigo_val & 0x04:
                print("       - Bit 2: Trigger de salida continuo se solapa con vector negro.")
            if codigo_val & 0x08:
                print("       - Bit 3: Falta vector negro (Insert Black) cuando Exposición < Período.")
            if codigo_val & 0x10:
                print("       - Bit 4: La diferencia (Período - Exposición) es menor a 230 us.")

        # 5. Reiniciar la proyección de la secuencia (0x1A24 -> 0x02 Start)
        if reiniciar:
            self.iniciar_secuencia()

        return codigo_val


def main(
    exposicion_us: int = EXPOSICION_US,
    periodo_us: int = PERIODO_US,
    reiniciar: bool = REINICIAR_SECUENCIA,
    solo_leer: bool = SOLO_LEER,
) -> None:
    with LightCrafter4500(DISPOSITIVO_HID) as lcr:
        print(f"[OK] Conectado a DLP LightCrafter 4500 en '{lcr.device_path}'")

        exp_antes, per_antes = lcr.leer_exposicion_y_periodo()
        fps_antes = 1_000_000.0 / per_antes if per_antes > 0 else 0.0
        print(
            f"[INFO] Configuración actual -> "
            f"Exposición: {exp_antes} us ({exp_antes / 1000:.2f} ms) | "
            f"Período: {per_antes} us ({per_antes / 1000:.2f} ms, ~{fps_antes:.2f} Hz)"
        )

        if solo_leer:
            return

        print(
            f"[INFO] Enviando nuevos parámetros -> "
            f"Exposición: {exposicion_us} us | Período: {periodo_us} us..."
        )
        codigo_val = lcr.configurar_exposicion_y_periodo(
            exposure_us=exposicion_us,
            period_us=periodo_us,
            reiniciar=reiniciar,
        )

        exp_despues, per_despues = lcr.leer_exposicion_y_periodo()
        fps_despues = 1_000_000.0 / per_despues if per_despues > 0 else 0.0
        print(
            f"[OK]   Nueva configuración  -> "
            f"Exposición: {exp_despues} us ({exp_despues / 1000:.2f} ms) | "
            f"Período: {per_despues} us ({per_despues / 1000:.2f} ms, ~{fps_despues:.2f} Hz) | "
            f"Validación: 0x{codigo_val:02X}"
        )
        if reiniciar:
            print("[OK] Secuencia validada e iniciada (START enviado).")


if __name__ == "__main__":
    main()
