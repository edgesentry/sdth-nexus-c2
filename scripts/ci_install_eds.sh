#!/usr/bin/env bash
# Install eds CLI + libedgesentry_bridge for CI / local Linux demos (#83).
#
# Usage (from repo root):
#   ./scripts/ci_install_eds.sh
#
# Env:
#   EDS_VERSION   release tag (default: v0.2.0)
#   EDS_RS_DIR    checkout path (default: $RUNNER_TEMP/edgesentry-rs or /tmp/edgesentry-rs)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="${EDS_VERSION:-v0.2.0}"
ARCH="${EDS_ARCH:-x86_64-unknown-linux-gnu}"
EDS_RS_DIR="${EDS_RS_DIR:-${RUNNER_TEMP:-/tmp}/edgesentry-rs}"
OUT_DIR="${OUT_DIR:-$ROOT/.eds}"

echo "==> Installing eds CLI ${VER} (${ARCH})"
curl -fsSL \
  "https://github.com/edgesentry/edgesentry-rs/releases/download/${VER}/eds-${VER}-${ARCH}.tar.gz" \
  | tar -xz -C /tmp
if command -v sudo >/dev/null 2>&1; then
  sudo install -m 755 /tmp/eds /usr/local/bin/eds
else
  mkdir -p "$HOME/.local/bin"
  install -m 755 /tmp/eds "$HOME/.local/bin/eds"
  export PATH="$HOME/.local/bin:$PATH"
fi
eds --version

echo "==> Building libedgesentry_bridge from edgesentry-rs@${VER}"
if [[ ! -d "$EDS_RS_DIR/.git" ]]; then
  rm -rf "$EDS_RS_DIR"
  git clone --depth 1 --branch "$VER" https://github.com/edgesentry/edgesentry-rs.git "$EDS_RS_DIR"
fi
(
  cd "$EDS_RS_DIR"
  cargo build -p edgesentry-bridge --release
)

mkdir -p "$OUT_DIR"
SO_SRC="$EDS_RS_DIR/target/release/libedgesentry_bridge.so"
if [[ ! -f "$SO_SRC" ]]; then
  echo "error: missing $SO_SRC" >&2
  exit 1
fi
cp -f "$SO_SRC" "$OUT_DIR/libedgesentry_bridge.so"
# Also expose via env for callers that source this script's output.
echo "EDS_BRIDGE_LIB=$OUT_DIR/libedgesentry_bridge.so"
export EDS_BRIDGE_LIB="$OUT_DIR/libedgesentry_bridge.so"

echo "==> Smoke-load bridge"
python3 - <<'PY'
import os, sys
from pathlib import Path
root = Path(os.environ.get("GITHUB_WORKSPACE") or Path.cwd())
sys.path.insert(0, str(root))
# Prefer installed package path when running under uv in CI after sync.
try:
    from core.audit_eds import bridge_available, eds_cli_available
except ImportError:
    # Fallback: load via ctypes only
    import ctypes
    lib = os.environ["EDS_BRIDGE_LIB"]
    ctypes.CDLL(lib)
    print(f"ctypes OK {lib}")
else:
    assert eds_cli_available(), "eds CLI missing"
    assert bridge_available(), "bridge not loadable"
    print("bridge_available=True eds_cli_available=True")
PY

echo "==> eds + bridge ready"
