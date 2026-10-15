#!/usr/bin/env bash
# PkDE Tools Environment Installer & Provisioner (Ubuntu Linux & macOS)
# Usage: ./tools/install.sh [--update] [--core-only] [--binaries-only]
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKDE_ROOT="$(cd "$TOOLS_DIR/.." && pwd)"
VENV_DIR="$PKDE_ROOT/.venv"
BIN_DIR="$PKDE_ROOT/bin"
TOOLS_BIN_DIR="$TOOLS_DIR/bin"
ARCH_ROOT_DIR="$TOOLS_BIN_DIR/arch"

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

echo "==> PkDE Provisioner starting (mode: $MODE, root: $PKDE_ROOT)"
mkdir -p "$BIN_DIR" "$TOOLS_BIN_DIR" "$ARCH_ROOT_DIR"

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
    echo "==> Installing PkDE core dependencies..."
    if command -v uv >/dev/null 2>&1; then
      uv pip install --python "$VENV_DIR/bin/python" -e "$PKDE_ROOT"
    else
      "$VENV_DIR/bin/pip" install --upgrade pip
      "$VENV_DIR/bin/pip" install -e "$PKDE_ROOT"
    fi
  else
    echo "==> Installing PkDE + [science] + [dev] dependencies (rdkit, gemmi, biopython, scipy, pubchempy)..."
    if command -v uv >/dev/null 2>&1; then
      uv pip install --python "$VENV_DIR/bin/python" -e "${PKDE_ROOT}[science]" pytest pytest-asyncio || exit 3
      if [ -d "$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/prox" ]; then
        uv pip install --python "$VENV_DIR/bin/python" -e "$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/prox" || true
      fi
    else
      "$VENV_DIR/bin/pip" install --upgrade pip
      "$VENV_DIR/bin/pip" install -e "${PKDE_ROOT}[science]" pytest pytest-asyncio || exit 3
      if [ -d "$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/prox" ]; then
        "$VENV_DIR/bin/pip" install -e "$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/prox" || true
      fi
    fi
  fi
fi

# 2. Build or verify multi-architecture Hypex CLI binaries (hypex, elo) and prox
HYPEX_SRC="$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/hypex"
ELO_SRC="$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/elo"
PROX_SRC="$TOOLS_DIR/vendor/hypex/hypothesis-explorer/tools/prox"

TARGETS=("linux:amd64" "linux:arm64" "darwin:arm64" "darwin:amd64")

write_multiarch_wrapper() {
  local name="$1"
  local out_bin="$2"
  cat > "$out_bin" <<EOF
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
if [ -d "\$SCRIPT_DIR/../tools/bin/arch" ]; then
  ROOT_DIR="\$(cd "\$SCRIPT_DIR/.." && pwd)"
elif [ -d "\$SCRIPT_DIR/arch" ]; then
  ROOT_DIR="\$(cd "\$SCRIPT_DIR/../.." && pwd)"
else
  ROOT_DIR="\$(cd "\$SCRIPT_DIR/.." && pwd)"
fi

OS="\$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH_RAW="\$(uname -m)"
case "\$ARCH_RAW" in
  x86_64|amd64) ARCH="amd64" ;;
  arm64|aarch64) ARCH="arm64" ;;
  *) ARCH="\$ARCH_RAW" ;;
esac

NATIVE_BIN="\$ROOT_DIR/tools/bin/arch/\${OS}-\${ARCH}/$name"
if [ -x "\$NATIVE_BIN" ]; then
  exec "\$NATIVE_BIN" "\$@"
fi

echo "$name: no native binary found for \${OS}-\${ARCH} at \$NATIVE_BIN" >&2
exit 127
EOF
  chmod +x "$out_bin"
}

provision_multiarch_go_tool() {
  local name="$1"
  local src_dir="$2"

  if command -v go >/dev/null 2>&1 && [ -d "$src_dir" ]; then
    for target in "${TARGETS[@]}"; do
      local goos="${target%%:*}"
      local goarch="${target##*:}"
      local target_dir="$ARCH_ROOT_DIR/${goos}-${goarch}"
      mkdir -p "$target_dir"
      echo "==> Cross-compiling $name (${goos}/${goarch}) from Go source..."
      (
        cd "$src_dir"
        CGO_ENABLED=0 GOOS="$goos" GOARCH="$goarch" \
          go build -trimpath -ldflags="-s -w -buildid=" -o "$target_dir/$name" .
      )
      chmod +x "$target_dir/$name"
    done
  else
    echo "==> Go compiler not on PATH; using prebuilt multi-arch binaries in $ARCH_ROOT_DIR/*/$name"
  fi

  write_multiarch_wrapper "$name" "$BIN_DIR/$name"
  write_multiarch_wrapper "$name" "$TOOLS_BIN_DIR/$name"
}

provision_multiarch_go_tool "hypex" "$HYPEX_SRC"
provision_multiarch_go_tool "elo" "$ELO_SRC"

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
export PYTHONPATH="$PROX_DIR${PKDE_EXTRA_PYTHONPATH:+:$PKDE_EXTRA_PYTHONPATH}"
exec "$PY_BIN" -c "import sys; from prox.cli import main; sys.exit(main())" "$@"
EOF
chmod +x "$BIN_DIR/prox"
cp -f "$BIN_DIR/prox" "$TOOLS_BIN_DIR/prox"
chmod +x "$TOOLS_BIN_DIR/prox"

# Also copy pkde into tools/bin/pkde so tools_home/bin is self-contained
if [ -f "$BIN_DIR/pkde" ]; then
  cp -f "$BIN_DIR/pkde" "$TOOLS_BIN_DIR/pkde"
  chmod +x "$TOOLS_BIN_DIR/pkde"
fi

# 3. Stamp the environment manifest
echo "==> Stamping PkDE environment manifest (ENV_VERSION)..."
(
  source "$BIN_DIR/env.sh"
  "$BIN_DIR/pkde" env stamp --note "provisioned via tools/install.sh ($MODE)" >/dev/null 2>&1 || true
)

echo "==> PkDE Provisioner complete!"
