# Reconstrucción 3D por proyección de franjas (phase shifting + código Gray)

Sistema cámara–proyector que reconstruye la forma 3D de un objeto. Un proyector **TI DLP
LightCrafter 4500** proyecta franjas binarias desplazadas y código Gray, y una cámara **FLIR
Blackfly S**, disparada por el mismo pulso de un **Arduino**, las captura. Luego se calcula la fase,
se desenvuelve con el código Gray, se obtienen las coordenadas del proyector y se triangula cada
píxel con la calibración estéreo cámara–proyector.

Adaptación a Python de los scripts de MATLAB de `Matlab_Codes/Codes/`.

**📖 La documentación completa está en [`MANUAL.md`](MANUAL.md)**: teoría, uso, cada etapa,
funciones principales, diagnóstico y correspondencia con el MATLAB.

## Inicio rápido

**Interfaz web** (control de todo el proceso, vista en vivo, fases y nube de puntos 3D):

```bash
cd ~/Documents/Tesis
.env/bin/python interfaz/servidor.py      # abre http://127.0.0.1:8000
```

Tiene un *modo demo* con cámara simulada para probarla sin el montaje (§19 del manual).

**Por script:**

```bash
.env/bin/python pipeline.py
```

Se configura editando la cabecera de `pipeline.py` (qué etapas correr) y `configuracion.py`
(parámetros físicos y umbrales).

| Quiero… | Etapas en `True` en `pipeline.py` |
|---|---|
| Medir objetos (sistema ya calibrado) | `captura`, `organizar`, `fase_relativa`, `fase_absoluta`, `reconstruccion`, `visualizacion` |
| Recalibrar | Lo mismo con `CAPTURA_CATEGORIA = "patron"` (10–15 poses) y además `calibracion` |
| Procesar capturas copiadas a `capturas/` | `organizar` → `reconstruccion` |
| Ver resultados ya calculados | `visualizacion` |

La calibración es **opcional**: si no se activa, se usa la guardada en `calibraciones/`
(versionada en git, viaja con el código). Las poses ya procesadas se reutilizan.

## Instalación en otro computador

```bash
git clone <url> Tesis && cd Tesis
./instalar.sh                    # entorno Python + dependencias + patrones + verificación
./instalar.sh --udev             # opcional: LightCrafter sin sudo
./instalar.sh --pyspin <wheel>   # opcional: cámara FLIR (requiere el Spinnaker SDK)
.env/bin/python verificar.py     # dice qué falta y dónde buscar la solución
```

La instalación de la cámara (Spinnaker SDK + PySpin) está explicada paso a paso en el §20.3 de
[`MANUAL.md`](MANUAL.md). Los problemas frecuentes de cada etapa, con su causa y solución, están
en el §16.

## Estado actual (montaje del 2026-11-24)

- Calibración en uso: 7 poses del patrón, RMS estéreo **0.59 px**, línea base de 95.3 mm (casi
  vertical).
- Error de planitud en los planos de referencia de esa sesión: **≈ 0.62 mm**.
- Pendiente físico (ver `AUDITORIA.md` §5):
  - medir el tamaño real del tablero, porque hoy hay ~1 % de incertidumbre de escala;
  - recalibrar con poses que cubran todo el ancho del proyector, porque hoy cubren el 59 %.
- La interfaz web solo muestra y procesa la configuración vigente del montaje (§9.1 del manual).
  Lo anterior queda en la pestaña *Archivos*.
