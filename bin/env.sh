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
  _ACTIVE_PTR="$PKDE_ROOT/.pkde-workspace/active-project.json"
  _RESOLVED_PROJ=""
  if [ -f "$_ACTIVE_PTR" ]; then
    _REL_ROOT=$("$PKDE_PYTHON" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("project_root","").strip())' "$_ACTIVE_PTR" 2>/dev/null || true)
    if [ -n "$_REL_ROOT" ] && [ "$_REL_ROOT" != "." ]; then
      case "$_REL_ROOT" in
        /*) _CAND="$_REL_ROOT" ;;
        *)  _CAND="$PKDE_ROOT/$_REL_ROOT" ;;
      esac
      if [ -d "$_CAND/.pkde" ]; then
        _RESOLVED_PROJ="$_CAND"
      fi
    fi
  fi
  if [ -n "$_RESOLVED_PROJ" ]; then
    export PKDE_PROJECT="$_RESOLVED_PROJ"
  else
    export PKDE_PROJECT="$PKDE_ROOT/.pkde-workspace/default-program"
    if [ ! -d "$PKDE_PROJECT/.pkde" ]; then
      mkdir -p "$PKDE_ROOT/.pkde-workspace"
      "$PKDE_PYTHON" -m pkde.cli init "$PKDE_PROJECT" >/dev/null 2>&1 || true
    fi
  fi
  unset _ACTIVE_PTR _RESOLVED_PROJ _REL_ROOT _CAND
fi
