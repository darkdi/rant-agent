#!/bin/sh
set -eu
cd "$(dirname "$0")"
CONNECT_PYTHON="${PYTHON_BIN:-python3}"
"$CONNECT_PYTHON" -c "import sys, tkinter; assert sys.version_info >= (3,12), 'Python 3.12+ is required'"
if [ ! -x .venv/bin/python ]; then
  "$CONNECT_PYTHON" -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
exec .venv/bin/python rant_connect.py
