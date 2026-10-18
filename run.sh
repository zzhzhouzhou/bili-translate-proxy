#!/usr/bin/env bash
# Index-Translate local proxy - convenience launcher (macOS / Linux)
# Usage: ./run.sh [serve|install|uninstall|test|watchdog] [extra args]
# For background/silent use: ./run.sh watchdog   (keeps serve alive)
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then PY="python"; fi
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "[ERROR] Python 3 not found. Install Python 3.8+." >&2
  exit 1
fi
exec "$PY" proxy.py "$@"
