#!/usr/bin/env bash
# Turn the low-difficulty PoW profile on (or off) for an installed debug APK.
#
# The device is not rooted, so this goes through `adb run-as`, which only works
# for debuggable packages (our CI builds are debug builds).
#
#   ./scripts/enable-low-pow.sh            # enable
#   ./scripts/enable-low-pow.sh off        # disable
#   ADB=~/Documents/platform-tools/adb SERIAL=emulator-5554 ./scripts/enable-low-pow.sh
set -euo pipefail

PKG="${PKG:-at.bitmessage.pybitmessage}"
ADB="${ADB:-adb}"
SERIAL="${SERIAL:-}"
VALUE="${1:-on}"

if [[ -n "$SERIAL" ]]; then
    ADB="$ADB -s $SERIAL"
fi

if [[ "$VALUE" == "off" ]]; then
    WANT="false"
else
    WANT="true"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

$ADB shell am force-stop "$PKG" >/dev/null 2>&1 || true
$ADB shell "run-as $PKG cat files/bitmessage/keys.dat" > "$TMP/keys.dat"

python3 - "$TMP/keys.dat" "$WANT" <<'PY'
import re
import sys

path, want = sys.argv[1], sys.argv[2]
text = open(path).read()

if 'extralowdifficulty' in text:
    text = re.sub(r'^extralowdifficulty\s*=.*$',
                  'extralowdifficulty = %s' % want, text, flags=re.M)
else:
    text = re.sub(r'^\[bitmessagesettings\]\n',
                  '[bitmessagesettings]\nextralowdifficulty = %s\n' % want,
                  text, count=1, flags=re.M)

open(path, 'w').write(text)
print('extralowdifficulty =', want)
PY

B64="$(base64 < "$TMP/keys.dat" | tr -d '\n')"
$ADB shell "run-as $PKG sh -c 'echo $B64 | base64 -d > files/bitmessage/keys.dat'"
$ADB shell am start -n "$PKG/org.kivy.android.PythonActivity" >/dev/null
echo "Restarted $PKG. Check with:"
echo "  $ADB shell run-as $PKG grep extralowdifficulty files/bitmessage/keys.dat"
