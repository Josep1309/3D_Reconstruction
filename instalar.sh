#!/usr/bin/env bash
# Instala el sistema de reconstrucción 3D por franjas en este computador (Linux).
#
#   ./instalar.sh                         entorno de Python + dependencias + verificación
#   ./instalar.sh --pyspin archivo.whl    además instala PySpin (cámara FLIR; requiere el Spinnaker SDK)
#   ./instalar.sh --udev                  además permite usar el LightCrafter sin sudo (pide la clave)
#   ./instalar.sh --python /usr/bin/python3.10   usa ese intérprete para crear el entorno
#
# Se puede ejecutar varias veces: lo que ya está hecho se omite. Detalles: MANUAL.md §20.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$RAIZ"
PYTHON=""
WHL_PYSPIN=""
UDEV=0
VERIFICAR=1

ayuda() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; }
ok()    { printf '  \033[32m✔\033[0m %s\n' "$*"; }
aviso() { printf '  \033[33m⚠\033[0m %s\n' "$*"; }
error() { printf '  \033[31m✖\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python) PYTHON="$2"; shift 2 ;;
    --pyspin) WHL_PYSPIN="$2"; shift 2 ;;
    --udev) UDEV=1; shift ;;
    --sin-verificar) VERIFICAR=0; shift ;;
    -h|--help) ayuda; exit 0 ;;
    *) echo "Opción desconocida: $1"; ayuda; exit 1 ;;
  esac
done

echo "== Instalación en $RAIZ"
[[ "$(uname -s)" == "Linux" ]] || aviso "Probado solo en Linux: la etapa 'lightcrafter' usa /dev/hidraw."

# ---------------------------------------------------------------- 1. Python
if [[ -z "$PYTHON" ]]; then
  for candidato in python3.10 python3; do
    if command -v "$candidato" >/dev/null 2>&1; then PYTHON="$(command -v "$candidato")"; break; fi
  done
fi
[[ -n "$PYTHON" ]] || error "No se encontró Python 3. Instálalo: sudo apt install python3.10 python3.10-venv"
VERSION="$("$PYTHON" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
  || error "Python $VERSION es demasiado antiguo: se necesita 3.9 o superior (recomendado 3.10)."
if [[ "$VERSION" == "3.10" ]]; then ok "Python $VERSION ($PYTHON)"
else aviso "Python $VERSION: funciona, pero el wheel de PySpin debe ser el de Python $VERSION (MANUAL.md §20.3)."; fi

# ---------------------------------------------------------------- 2. Entorno virtual (.env)
if [[ -x .env/bin/python ]]; then
  ok "Entorno virtual .env ya existe ($(.env/bin/python -V))"
else
  "$PYTHON" -m venv .env 2>/dev/null \
    || error "No se pudo crear el entorno. En Ubuntu/Debian: sudo apt install python${VERSION}-venv"
  ok "Entorno virtual creado en .env/"
fi

# ---------------------------------------------------------------- 3. Dependencias
echo "== Instalando dependencias (requirements.txt)…"
.env/bin/python -m pip install --quiet --upgrade pip
.env/bin/python -m pip install --quiet -r requirements.txt
ok "numpy, opencv-python y matplotlib instalados"

# ---------------------------------------------------------------- 4. PySpin (opcional)
if [[ -n "$WHL_PYSPIN" ]]; then
  [[ -f "$WHL_PYSPIN" ]] || error "No existe el archivo '$WHL_PYSPIN'"
  if ! ldconfig -p 2>/dev/null | grep -q libSpinnaker; then
    aviso "No se encontró libSpinnaker: instala primero el Spinnaker SDK de FLIR (MANUAL.md §20.3)."
  fi
  .env/bin/python -m pip install --quiet "$WHL_PYSPIN"
  .env/bin/python -c "import PySpin" && ok "PySpin instalado" \
    || error "PySpin se instaló pero no carga: revisa que el SDK y el wheel sean de la misma versión (MANUAL.md §20.3)."
elif .env/bin/python -c "import PySpin" 2>/dev/null; then
  ok "PySpin ya está instalado"
else
  aviso "PySpin no instalado: no se podrá capturar (procesar y visualizar sí). Ver MANUAL.md §20.3."
fi

# ---------------------------------------------------------------- 5. Regla udev del LightCrafter (opcional)
REGLA=/etc/udev/rules.d/99-lightcrafter.rules
if [[ $UDEV -eq 1 ]] && ! sudo -n true 2>/dev/null && [[ ! -t 0 ]]; then
  # Sin terminal interactiva sudo no puede pedir la contraseña: se indican los comandos
  aviso "sudo necesita la contraseña y no hay terminal interactiva. Ejecuta en una terminal:"
  echo "      sudo cp $RAIZ/instalacion/99-lightcrafter.rules $REGLA"
  echo "      sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=hidraw"
  echo "    (o simplemente: ./instalar.sh --udev desde una terminal normal)"
elif [[ $UDEV -eq 1 ]]; then
  sudo cp instalacion/99-lightcrafter.rules "$REGLA"
  sudo udevadm control --reload-rules
  sudo udevadm trigger --subsystem-match=hidraw
  ok "Regla udev instalada en $REGLA: desconecta y conecta el USB del LightCrafter"
elif [[ -f "$REGLA" ]]; then
  ok "Regla udev del LightCrafter ya instalada"
else
  aviso "Regla udev no instalada: para configurar el proyector sin sudo usa ./instalar.sh --udev"
fi

# ---------------------------------------------------------------- 6. Patrones del proyector
if [[ $(ls patterns/secuencia_completa_bmp/f_*.bmp 2>/dev/null | wc -l) -lt 50 ]]; then
  echo "== Generando los 50 patrones del proyector…"
  .env/bin/python secuencia_patrones.py >/dev/null
  ok "Patrones en patterns/secuencia_completa_bmp/ (deben coincidir con los cargados en el LightCrafter)"
else
  ok "Patrones del proyector presentes"
fi

# ---------------------------------------------------------------- 7. Verificación
if [[ $VERIFICAR -eq 1 ]]; then
  echo
  .env/bin/python verificar.py || true
fi
echo
echo "Listo. Interfaz web:  .env/bin/python interfaz/servidor.py"
echo "       Por script:    .env/bin/python pipeline.py"
