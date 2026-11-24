#!/usr/bin/env bash
# Re-sign a debug APK with a personal, stable key so that later builds can be
# installed over it (`adb install -r`) without uninstalling.
#
# Why: every CI run generates a fresh debug keystore, so two builds never share
# a signature and Android refuses the upgrade with
# INSTALL_FAILED_UPDATE_INCOMPATIBLE.
#
#   ./scripts/resign-apk.sh path/to/app.apk
#
# The keystore lives in ~/.pybitmessage-android/signing.keystore (created on
# first use, password: pybitmessage). Keep it: it is the identity of your
# sideloaded app.
set -euo pipefail

APK="${1:?usage: $0 <apk>}"
KEYDIR="$HOME/.pybitmessage-android"
KEYSTORE="$KEYDIR/signing.keystore"
ALIAS=pybitmessage
PASS=pybitmessage

SDK="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}"
BUILD_TOOLS="$(ls -d "$SDK"/build-tools/* 2>/dev/null | sort -V | tail -1)"
if [[ -z "${BUILD_TOOLS:-}" ]]; then
    echo "Android build-tools not found under $SDK" >&2
    exit 1
fi

mkdir -p "$KEYDIR"
if [[ ! -f "$KEYSTORE" ]]; then
    echo "creating $KEYSTORE"
    keytool -genkeypair -v \
        -keystore "$KEYSTORE" -alias "$ALIAS" \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -storepass "$PASS" -keypass "$PASS" \
        -dname "CN=PyBitmessage Android, O=PyBitmessage, C=CN"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

"$BUILD_TOOLS/zipalign" -f -p 4 "$APK" "$TMP/aligned.apk"
"$BUILD_TOOLS/apksigner" sign \
    --ks "$KEYSTORE" --ks-pass "pass:$PASS" --key-pass "pass:$PASS" \
    --out "$TMP/signed.apk" "$TMP/aligned.apk"
mv "$TMP/signed.apk" "$APK"
echo "re-signed $APK"

# Print the certificate identity so two builds can be compared, and so the
# fingerprint below can be recorded in the docs (M5.2.1):
#   82463dfe0a7ef14821c33fef5e462e1f7bed070387de2bee7e9dd4fdebc551c7
# Losing ~/.pybitmessage-android/signing.keystore means every installed copy has
# to be uninstalled (= private keys gone) before it can be replaced again.
"$BUILD_TOOLS/apksigner" verify --print-certs "$APK" \
    | grep -E "certificate SHA-256 digest" || true
