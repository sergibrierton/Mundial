#!/usr/bin/env bash
# Mundial Studio - lanzador para macOS / Linux
set -e
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "[ERROR] No se ha encontrado Python. Instala Python 3.9+."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "[1/2] Creando entorno (solo la primera vez)..."
  "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f ".venv/.instalado" ]; then
  echo "[2/2] Instalando dependencias (puede tardar)..."
  python -m pip install --upgrade pip >/dev/null
  pip install -r requirements.txt
  touch .venv/.instalado
fi

echo "Abriendo Mundial Studio en el navegador..."
python app.py
