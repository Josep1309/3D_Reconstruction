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

```bash
cd ~/Documents/Tesis
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

La calibración es **opcional**: si no se activa, se usa la última guardada en
`resultados/calibracion/`. Las poses ya procesadas se reutilizan.

## Estado actual (capturas del 2026-10-30)

- Calibración: RMS estéreo 0.51 px, línea base de 91.6 mm (casi vertical).
- Error de planitud medio en 8 planos de referencia: **0.50 mm**.
- Proceso completo de 17 poses (incluida la calibración): ≈ 70 s.
- Pendiente físico: recalibrar con poses que cubran todo el ancho del proyector (hoy solo el
  43 %) y medir el tamaño real del tablero. Ver §16 del manual.
