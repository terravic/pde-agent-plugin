#!/usr/bin/env bash
PKDE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PKDE_ROOT
export PKDE_TOOLS_HOME="$PKDE_ROOT/tools"
export PKDE_ENV_SOURCE="$PKDE_TOOLS_HOME/ENV_VERSION"
export PYTHONPATH="$PKDE_ROOT:$PKDE_ROOT/tools:$PKDE_ROOT/tools/vendor/hypex${PKDE_EXTRA_PYTHONPATH:+:$PKDE_EXTRA_PYTHONPATH}"
if [ -n "${PKDE_PYTHON:-}" ] && [ -x "${PKDE_PYTHON}" ]; then
  export PKDE_PYTHON
elif [ -x "$PKDE_ROOT/.venv/bin/python" ]; then
  export PKDE_PYTHON="$PKDE_ROOT/.venv/bin/python"
else
  export PKDE_PYTHON="python3"
fi
if [ -d "$PKDE_ROOT/.venv/bin" ]; then
  export PATH="$PKDE_ROOT/bin:$PKDE_ROOT/.venv/bin:$PATH"
else
  export PATH="$PKDE_ROOT/bin:$PATH"
fi
export PKDE_NO_DIRTY_WARNING=1
if [ -z "${PKDE_PROJECT:-}" ]; then
  if [ -d "$PKDE_ROOT/.pkde-workspace/.pkde" ] && [ -d "$PKDE_ROOT/.pkde-workspace/raw" ] && [ -n "$(ls -A "$PKDE_ROOT/.pkde-workspace/raw" 2>/dev/null)" ]; then
    export PKDE_PROJECT="$PKDE_ROOT/.pkde-workspace"
  else
    export PKDE_PROJECT="$PKDE_ROOT/.pkde-workspace/default-program"
    if [ ! -d "$PKDE_PROJECT/.pkde" ]; then
      mkdir -p "$PKDE_ROOT/.pkde-workspace"
      "$PKDE_PYTHON" -m pkde.cli init "$PKDE_PROJECT" >/dev/null 2>&1 || true
    fi
  fi
fi
