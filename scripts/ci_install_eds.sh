#!/usr/bin/env bash
# Install prebuilt eds CLI + libedgesentry_bridge from GitHub Releases (#83 / #459).
#
# Usage (from repo root):
#   ./scripts/ci_install_eds.sh
#
# Env:
#   EDS_VERSION   release tag (default: v0.2.3)
#   EDS_ARCH      target triple (auto-detected if unset)
#   OUT_DIR       where to place the shared library (default: <repo>/.eds)
#   SKIP_SMOKE    set to 1 to skip the Python load check

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="${EDS_VERSION:-v0.2.3}"
OUT_DIR="${OUT_DIR:-$ROOT/.eds}"
BASE="https://github.com/edgesentry/edgesentry-rs/releases/download/${VER}"

detect_arch() {
  local os arch
  os="$(uname -s)"
  arch="$(uname -m)"
  case "${os}:${arch}" in
    Linux:x86_64) echo "x86_64-unknown-linux-gnu" ;;
    Linux:aarch64 | Linux:arm64) echo "aarch64-unknown-linux-gnu" ;;
    Darwin:arm64) echo "aarch64-apple-darwin" ;;
    Darwin:x86_64) echo "x86_64-apple-darwin" ;;
    *)
      echo "error: unsupported platform ${os}/${arch}; set EDS_ARCH" >&2
      exit 1
      ;;
  esac
}

ARCH="${EDS_ARCH:-$(detect_arch)}"
case "$ARCH" in
  *-apple-darwin) LIB_NAME="libedgesentry_bridge.dylib" ;;
  *) LIB_NAME="libedgesentry_bridge.so" ;;
esac

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> Installing eds CLI ${VER} (${ARCH})"
curl -fsSL "${BASE}/eds-${VER}-${ARCH}.tar.gz" | tar -xz -C "$TMP"
mkdir -p "$OUT_DIR"
# Always keep a repo-local copy (works without sudo / outside sandbox).
cp -f "$TMP/eds" "$OUT_DIR/eds"
chmod 755 "$OUT_DIR/eds"
if [[ -w /usr/local/bin ]]; then
  cp -f "$OUT_DIR/eds" /usr/local/bin/eds
elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  sudo cp -f "$OUT_DIR/eds" /usr/local/bin/eds
  sudo chmod 755 /usr/local/bin/eds
else
  mkdir -p "$HOME/.local/bin"
  if cp -f "$OUT_DIR/eds" "$HOME/.local/bin/eds" 2>/dev/null; then
    chmod 755 "$HOME/.local/bin/eds"
  fi
fi
export PATH="$OUT_DIR:$PATH"
eds --version

echo "==> Installing ${LIB_NAME} ${VER} (${ARCH})"
curl -fsSL "${BASE}/libedgesentry_bridge-${VER}-${ARCH}.tar.gz" | tar -xz -C "$TMP"
cp -f "$TMP/${LIB_NAME}" "$OUT_DIR/${LIB_NAME}"
chmod 755 "$OUT_DIR/${LIB_NAME}"
if [[ -f "$TMP/edgesentry_bridge.h" ]]; then
  cp -f "$TMP/edgesentry_bridge.h" "$OUT_DIR/edgesentry_bridge.h"
fi

export EDS_BRIDGE_LIB="$OUT_DIR/${LIB_NAME}"
echo "EDS_BRIDGE_LIB=${EDS_BRIDGE_LIB}"
if [[ -n "${GITHUB_ENV:-}" ]]; then
  echo "EDS_BRIDGE_LIB=${EDS_BRIDGE_LIB}" >>"$GITHUB_ENV"
  echo "EDS_BIN=$(command -v eds)" >>"$GITHUB_ENV"
fi

if [[ "${SKIP_SMOKE:-0}" != "1" ]]; then
  echo "==> Smoke-load bridge"
  (
    cd "$ROOT"
    if command -v uv >/dev/null 2>&1 && [[ -f "$ROOT/pyproject.toml" ]]; then
      uv run python - <<'PY'
from core.audit_eds import bridge_available, eds_cli_available
assert eds_cli_available(), "eds CLI missing"
assert bridge_available(), "bridge not loadable"
print("bridge_available=True eds_cli_available=True")
PY
    else
      python3 -c "import ctypes, os; ctypes.CDLL(os.environ['EDS_BRIDGE_LIB']); print('ctypes OK')"
    fi
  )
fi

echo "==> eds + bridge ready (${VER})"
