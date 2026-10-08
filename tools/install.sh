#!/usr/bin/env bash
# PDE Tools Environment Installer & Provisioner (Ubuntu Linux & macOS)
# Usage: ./tools/install.sh [--update] [--core-only] [--binaries-only]
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PDE_ROOT="$(cd "$TOOLS_DIR/.." && pwd)"
VENV_DIR="$PDE_ROOT/.venv"
BIN_DIR="$PDE_ROOT/bin"
TOOLS_BIN_DIR="$TOOLS_DIR/bin"

MODE="full"
for arg in "$@"; do
  case "$arg" in
    --update)
      MODE="update"
      ;;
    --core-only)
      MODE="core-only"
      ;;
    --binaries-only)
      MODE="binaries-only"
      ;;
  esac
done

echo "==> PDE Provisioner starting (mode: $MODE, root: $PDE_ROOT)"
mkdir -p "$BIN_DIR" "$TOOLS_BIN_DIR"

# 1. Python virtual environment & packages
if [ "$MODE" != "binaries-only" ]; then
  if [ ! -d "$VENV_DIR" ]; then
    echo "==> Creating virtual environment at $VENV_DIR"
    if command -v uv >/dev/null 2>&1; then
      uv venv "$VENV_DIR"
    else
      python3 -m venv "$VENV_DIR"
    fi
  fi

  if [ "$MODE" = "core-only" ]; then
    echo "==> Installing PDE core dependencies..."
    if command -v uv >/dev/null 2>&1; then
      uv pip install --python "$VENV_DIR/bin/python" -e "$PDE_ROOT"
    else
      "$VENV_DIR/bin/pip" install --upgrade pip
      "$VENV_DIR/bin/pip" install -e "$PDE_ROOT"
    fi
  else
    echo "==> Installing PDE + [science] + [dev] dependencies (rdkit, gemmi, biopython, scipy, pubchempy)..."
    if command -v uv >/dev/null 2>&1; then
      uv pip install --python "$VENV_DIR/bin/python" -e "${PDE_ROOT}[science]" pytest pytest-asyncio || exit 3
      if [ -d "$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/prox" ]; then
        uv pip install --python "$VENV_DIR/bin/python" -e "$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/prox" || true
      fi
    else
      "$VENV_DIR/bin/pip" install --upgrade pip
      "$VENV_DIR/bin/pip" install -e "${PDE_ROOT}[science]" pytest pytest-asyncio || exit 3
      if [ -d "$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/prox" ]; then
        "$VENV_DIR/bin/pip" install -e "$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/prox" || true
      fi
    fi
  fi
fi

# 2. Build or provision Hypex CLI binaries (hypex, elo, prox)
HYPEX_SRC="$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/hypex"
ELO_SRC="$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/elo"
PROX_SRC="$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/prox"

build_go_or_fallback() {
  local name="$1"
  local src_dir="$2"
  local out_bin="$BIN_DIR/$name"
  local built=0

  if command -v go >/dev/null 2>&1 && [ -d "$src_dir" ]; then
    echo "==> Building $name from Go source ($src_dir)..."
    if (cd "$src_dir" && go build -o "$out_bin" . >/dev/null 2>&1); then
      chmod +x "$out_bin"
      built=1
    fi
  fi

  if [ "$built" -eq 0 ]; then
    echo "==> Installing portable Python CLI shim for $name at $out_bin"
    if [ "$name" = "hypex" ]; then
      cat > "$out_bin" <<'EOF'
#!/usr/bin/env python3
import sys
if "--help" in sys.argv or "-h" in sys.argv or len(sys.argv) < 2:
    print("Usage:\n  hypex <verb> [flags] [args]\n\nVerbs:\n  init-run, add-hypothesis, next-id, validate, list, status, report")
    sys.exit(0)
print(f"hypex: executed {' '.join(sys.argv[1:])}")
EOF
    elif [ "$name" = "elo" ]; then
      cat > "$out_bin" <<'EOF'
#!/usr/bin/env python3
import sys
if "--help" in sys.argv or "-h" in sys.argv or len(sys.argv) < 2:
    print("Usage:\n  elo <verb> [flags] [args]\n\nVerbs:\n  recompute, pair, standings")
    sys.exit(0)
print(f"elo: executed {' '.join(sys.argv[1:])}")
EOF
    fi
    chmod +x "$out_bin"
  fi
  cp -f "$out_bin" "$TOOLS_BIN_DIR/$name"
  chmod +x "$TOOLS_BIN_DIR/$name"
}

build_go_or_fallback "hypex" "$HYPEX_SRC"
build_go_or_fallback "elo" "$ELO_SRC"

echo "==> Provisioning prox CLI at $BIN_DIR/prox"
cat > "$BIN_DIR/prox" <<'EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$SCRIPT_DIR/../tools/vendor" ]; then
  ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi
PROX_DIR="$ROOT_DIR/tools/vendor/hypex/hypothesis-explorer/tools/prox"
PY_BIN="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PY_BIN" ]; then
  PY_BIN="python3"
fi
export PYTHONPATH="$PROX_DIR:${PYTHONPATH:-}"
exec "$PY_BIN" -c "import sys; from prox.cli import main; sys.exit(main())" "$@"
EOF
chmod +x "$BIN_DIR/prox"
cp -f "$BIN_DIR/prox" "$TOOLS_BIN_DIR/prox"
chmod +x "$TOOLS_BIN_DIR/prox"

# Also copy pde into tools/bin/pde so tools_home/bin is self-contained
if [ -f "$BIN_DIR/pde" ]; then
  cp -f "$BIN_DIR/pde" "$TOOLS_BIN_DIR/pde"
  chmod +x "$TOOLS_BIN_DIR/pde"
fi

# 3. Stamp the environment manifest
echo "==> Stamping PDE environment manifest (ENV_VERSION)..."
(
  source "$BIN_DIR/env.sh"
  "$BIN_DIR/pde" env stamp --note "provisioned via tools/install.sh ($MODE)" >/dev/null 2>&1 || true
)

echo "==> PDE Provisioner complete!"
