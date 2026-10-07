#!/usr/bin/env bash
PDE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PDE_ROOT
export PDE_TOOLS_HOME="$PDE_ROOT/tools"
export PDE_ENV_SOURCE="$PDE_TOOLS_HOME/ENV_VERSION"
export PYTHONPATH="$PDE_ROOT:$PDE_ROOT/tools:$PDE_ROOT/tools/vendor/hypex:${PYTHONPATH:-}"
if [ -d "$PDE_ROOT/.venv/bin" ]; then
  export PATH="$PDE_ROOT/bin:$PDE_ROOT/.venv/bin:$PATH"
else
  export PATH="$PDE_ROOT/bin:$PATH"
fi
export PDE_NO_DIRTY_WARNING=1
if [ -z "${PDE_PROJECT:-}" ]; then
  export PDE_PROJECT="$PDE_ROOT/.pde-workspace/default-program"
  if [ ! -d "$PDE_PROJECT/.pde" ]; then
    mkdir -p "$PDE_ROOT/.pde-workspace"
    python3 -m pde.cli init "$PDE_PROJECT" >/dev/null 2>&1 || true
  fi
fi
