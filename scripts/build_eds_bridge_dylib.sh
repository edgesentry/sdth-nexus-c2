#!/usr/bin/env bash
# Fallback: rebuild a dlopen-able libedgesentry_bridge from the static archive.
#
# Prefer the prebuilt release instead:
#   ./scripts/ci_install_eds.sh          # downloads v0.2.3+ .so/.dylib into .eds/
#
# Use this script only when the release dylib fails to load (historical macOS 27
# LINKEDIT issue) or you need an unreleased bridge build.
#
# Usage:
#   ./scripts/build_eds_bridge_dylib.sh
#   EDS_RS=/path/to/edgesentry-rs ./scripts/build_eds_bridge_dylib.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EDS_RS="${EDS_RS:-$ROOT/../edgesentry-rs}"
OUT_DIR="${OUT_DIR:-$ROOT/.eds}"
A_LIB="$EDS_RS/target/release/libedgesentry_bridge.a"

if [[ ! -f "$A_LIB" ]]; then
  echo "Building edgesentry-bridge release staticlib in $EDS_RS …" >&2
  (cd "$EDS_RS" && cargo build -p edgesentry-bridge --release)
fi

if [[ ! -f "$A_LIB" ]]; then
  echo "error: missing $A_LIB" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
KEEPALIVE="$OUT_DIR/keepalive.c"
cat >"$KEEPALIVE" <<'EOF'
/* Keep the force-loaded archive linked into the shared library. */
int eds_bridge_keepalive(void) { return 1; }
EOF

case "$(uname -s)" in
  Darwin)
    OUT="$OUT_DIR/libedgesentry_bridge.dylib"
    cc -dynamiclib -o "$OUT" "$KEEPALIVE" \
      -Wl,-force_load,"$A_LIB" \
      -framework Security -framework CoreFoundation
    ;;
  Linux)
    OUT="$OUT_DIR/libedgesentry_bridge.so"
    cc -shared -o "$OUT" "$KEEPALIVE" \
      -Wl,--whole-archive,"$A_LIB",--no-whole-archive \
      -lpthread -ldl -lm
    ;;
  *)
    echo "error: unsupported OS $(uname -s)" >&2
    exit 1
    ;;
esac

echo "Wrote $OUT"
echo "Prefer: ./scripts/ci_install_eds.sh  (prebuilt from edgesentry-rs releases)"
