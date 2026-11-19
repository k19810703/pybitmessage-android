#!/usr/bin/env bash
# Cross-compile bitmsghash (the ctypes PoW library) for Android arm64-v8a.
#
# Upstream builds it with OpenSSL's SHA512; we compile against a tiny bundled
# shim (src/bitmsghash/shim) so the NDK alone is enough — no libcrypto needed.
#
#   ./scripts/build-bitmsghash.sh [path-to-ndk]
#
# Output: PyBitmessage/packages/android/libs/arm64-v8a/libbitmsghash.so
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/PyBitmessage/src/bitmsghash"
OUT="$ROOT/PyBitmessage/packages/android/libs/arm64-v8a"
NDK="${1:-}"

if [[ -z "$NDK" ]]; then
    for cand in "$HOME/.buildozer/android/platform"/android-ndk-* \
                "$HOME/Library/Android/sdk/ndk"/* \
                "${ANDROID_NDK_HOME:-}"; do
        [[ -d "$cand" ]] && NDK="$cand" && break
    done
fi
[[ -n "$NDK" && -d "$NDK" ]] || { echo "NDK not found; pass it as \$1" >&2; exit 1; }

HOST_TAG=linux-x86_64
[[ "$(uname -s)" == "Darwin" ]] && HOST_TAG=darwin-x86_64
BIN="$NDK/toolchains/llvm/prebuilt/$HOST_TAG/bin"
CXX="$BIN/clang++"
CC="$BIN/clang"
[[ -x "$CXX" ]] || { echo "clang++ not found in $BIN" >&2; exit 1; }

TARGET=aarch64-linux-android24
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

"$CXX" --target=$TARGET -O3 -fPIC -I"$SRC/shim" -c "$SRC/bitmsghash.cpp" -o "$TMP/bm.o"
"$CC"  --target=$TARGET -O3 -fPIC -I"$SRC/shim" -c "$SRC/shim/sha512_shim.c" -o "$TMP/sha.o"
# -static-libstdc++: the APK does not ship libc++_shared.so, and dlopen
# refuses to load a library whose dependencies are missing.
"$CXX" --target=$TARGET -shared -static-libstdc++ -o "$TMP/libbitmsghash.so" \
    "$TMP/bm.o" "$TMP/sha.o"

mkdir -p "$OUT"
cp "$TMP/libbitmsghash.so" "$OUT/libbitmsghash.so"
echo "wrote $OUT/libbitmsghash.so"
"$BIN/llvm-readelf" -h "$OUT/libbitmsghash.so" 2>/dev/null | grep -E "Machine|Class" || true
