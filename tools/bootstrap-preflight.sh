#!/usr/bin/env bash
# PDE Bootstrap Preflight Check (Ubuntu Linux & macOS)
set -euo pipefail

MISSING=()
OS_NAME="$(uname -s)"

if ! command -v python3 >/dev/null 2>&1; then
  MISSING+=("python3")
else
  if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    MISSING+=("python3>=3.11")
  fi
  if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1; then
    if ! command -v uv >/dev/null 2>&1; then
      MISSING+=("python3-venv")
    fi
  fi
fi

if [ "${#MISSING[@]}" -gt 0 ]; then
  echo "BOOTSTRAP_PREFLIGHT: MISSING PREREQUISITES: ${MISSING[*]}"
  if [ "$OS_NAME" = "Linux" ]; then
    echo "Run: sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-dev build-essential golang-go"
  elif [ "$OS_NAME" = "Darwin" ]; then
    echo "Run: brew install python@3.12 go uv"
  fi
  exit 1
fi

echo "BOOTSTRAP_PREFLIGHT: OK (${OS_NAME}, $(python3 --version 2>&1))"
exit 0
