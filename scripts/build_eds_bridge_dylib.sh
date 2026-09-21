#!/usr/bin/env bash
# Rebuild a dlopen-able libedgesentry_bridge.dylib from the static archive.
#
# On macOS 27+, rustc's release cdylib can fail ctypes.CDLL with
# "mis-aligned LINKEDIT string pool". Apple's ld64 linking of the .a is fine.
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
