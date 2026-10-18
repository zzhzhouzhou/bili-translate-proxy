#!/usr/bin/env bash
# Index-Translate local proxy - convenience launcher (macOS / Linux)
# Usage: ./run.sh [serve|install|uninstall|test] [extra args]
# For background/silent keep-alive use: ./run.sh serve   then  ./run.sh install
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then PY="python"; fi
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "[ERROR] Python 3 not found. Install Python 3.8+." >&2
  exit 1
fi
# The keep-alive watchdog is a separate minimal script (watchdog.py) that the
# install/setup flow launches automatically.
exec "$PY" proxy.py "$@"
