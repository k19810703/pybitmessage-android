#!/usr/bin/env bash
# Build bitmsghash (the ctypes PoW library) natively for THIS machine
# (macOS / Linux), so a desktop test node gets C-speed PoW instead of the
# pure-Python fallback (minutes per object at protocol difficulty).
#
# Output: PyBitmessage/src/bitmsghash/bitmsghash.so
# proofofwork.init() picks it up automatically via the bitmsghash*.so glob.
#
#   ./scripts/build-bitmsghash-native.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/PyBitmessage/src/bitmsghash"

CXX="${CXX:-clang++}"
CC="${CC:-clang}"
command -v "$CXX" >/dev/null || { echo "clang++ not found (brew install llvm or set CXX)" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

"$CXX" -O3 -fPIC -I"$SRC/shim" -c "$SRC/bitmsghash.cpp" -o "$TMP/bm.o"
"$CC"  -O3 -fPIC -I"$SRC/shim" -c "$SRC/shim/sha512_shim.c" -o "$TMP/sha.o"
"$CXX" -shared -o "$SRC/bitmsghash.so" "$TMP/bm.o" "$TMP/sha.o"

echo "wrote $SRC/bitmsghash.so"
python3 - "$SRC/bitmsghash.so" <<'PY'
import ctypes, hashlib, sys, time
bso = ctypes.CDLL(sys.argv[1])
bso.BitmessagePOW.restype = ctypes.c_ulonglong
h = hashlib.sha512(b'selftest').digest()
buf = ctypes.create_string_buffer(h, 64)
t0 = time.time()
nonce = bso.BitmessagePOW(ctypes.pointer(buf), ctypes.c_ulonglong(2**64 // 1500))
print('selftest OK: nonce=%s in %.2fs' % (nonce, time.time() - t0))
PY
