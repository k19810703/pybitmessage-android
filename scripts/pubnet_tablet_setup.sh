#!/usr/bin/env bash
# Configure the tablet's PyBitmessage app for a public-network test:
# enable the API, cap outbound connections, and seed knownnodes.dat with
# live public nodes (a fresh install only has dead 2017 defaults, so its
# outbound loop would sit in SYN_SENT forever).
#
#   ./scripts/pubnet_tablet_setup.sh [serial]     # default b45f8e87
#
# Assumes the app is already installed (TLS-fix APK, personal key) and
# has been started at least once (keys.dat exists). The script restarts
# the app and prints the current address + connection status.
#
# Pitfalls encoded below (all hit on 2026-11-19, see EVIDENCE.md 1.24):
#  - API keys live in [bitmessagesettings], NOT [api]
#  - keys.dat may already contain apiinterface/apiport: duplicates crash
#    startup with DuplicateOptionError -> dedupe before injecting
#  - the path is files/bitmessage/keys.dat (not files/keys.dat)
set -euo pipefail

SERIAL="${1:-b45f8e87}"
PKG=at.bitmessage.pybitmessage
ADB="$HOME/Documents/platform-tools/adb -s $SERIAL"
API_FWD_PORT=8445

# live public nodes (keep in sync with scripts/pubnet_node.py)
NODES='[
 {"host":"85.114.135.102","port":8444},
 {"host":"194.164.163.84","port":8444},
 {"host":"185.158.248.216","port":8444},
 {"host":"158.69.63.42","port":8080}]'

echo "== device =="
$ADB shell getprop ro.product.model || { echo "device $SERIAL not found" >&2; exit 1; }
$ADB shell pm path $PKG >/dev/null 2>&1 || { echo "app not installed" >&2; exit 1; }

echo "== wait for keys.dat (start the app once if missing) =="
if ! $ADB shell run-as $PKG ls files/bitmessage/keys.dat >/dev/null 2>&1; then
  echo "keys.dat missing, starting app for first boot..."
  $ADB shell am start -n $PKG/org.kivy.android.PythonActivity
  for i in $(seq 1 12); do
    sleep 10
    $ADB shell run-as $PKG ls files/bitmessage/keys.dat >/dev/null 2>&1 && break
  done
  $ADB shell run-as $PKG ls files/bitmessage/keys.dat >/dev/null 2>&1 \
    || { echo "keys.dat never appeared" >&2; exit 1; }
fi

echo "== inject API config + maxoutboundconnections into keys.dat =="
$ADB exec-out run-as $PKG cat files/bitmessage/keys.dat > /tmp/pubnet_keys.dat
python3 - <<'PY'
lines = open('/tmp/pubnet_keys.dat').read().splitlines()
out, seen, section = [], set(), ''
inject = {
    'apienabled': 'true', 'apiinterface': '127.0.0.1', 'apiport': '8442',
    'apivariant': 'xml', 'apiusername': 'u', 'apipassword': 'p',
    'maxoutboundconnections': '2',
}
for ln in lines:
    s = ln.strip()
    if s.startswith('[') and s.endswith(']'):
        section = s
    if '=' in ln and not ln.startswith((' ', '\t')) and section == '[bitmessagesettings]':
        key = ln.split('=')[0].strip()
        if key in inject:
            out.append('%s = %s' % (key, inject.pop(key)))
            seen.add(key)
            continue
    out.append(ln)
extra = ''.join('\n%s = %s' % (k, v) for k, v in inject.items())
# append remaining keys right under the section header
if extra:
    out.insert(out.index('[bitmessagesettings]') + 1, extra.strip('\n'))
open('/tmp/pubnet_keys.dat', 'w').write('\n'.join(out) + '\n')
print('keys.dat: injected', ', '.join(sorted(seen | set(inject))))
PY
$ADB push /tmp/pubnet_keys.dat /data/local/tmp/pubnet_keys.dat >/dev/null
$ADB shell run-as $PKG sh -c 'cat /data/local/tmp/pubnet_keys.dat > files/bitmessage/keys.dat'
$ADB shell rm /data/local/tmp/pubnet_keys.dat

echo "== write knownnodes.dat with live nodes =="
python3 - "$NODES" <<'PY' > /tmp/pubnet_knownnodes.dat
import json, sys, time
nodes = json.loads(sys.argv[1])
print(json.dumps([{
    'stream': 1, 'peer': n,
    'info': {'lastseen': int(time.time()), 'rating': 1, 'self': False}
} for n in nodes]))
PY
$ADB push /tmp/pubnet_knownnodes.dat /data/local/tmp/kn.dat >/dev/null
$ADB shell run-as $PKG sh -c 'cat /data/local/tmp/kn.dat > files/bitmessage/knownnodes.dat'
$ADB shell rm /data/local/tmp/kn.dat

echo "== restart app =="
$ADB shell am force-stop $PKG
sleep 2
$ADB shell am start -n $PKG/org.kivy.android.PythonActivity
echo "waiting 90s for startup (known stall, see HANDOFF.md)..."
sleep 90

echo "== status =="
$ADB forward tcp:$API_FWD_PORT tcp:8442
REPO="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$REPO/scripts/pubnet_ctl.py" --port $API_FWD_PORT status || true
python3 "$REPO/scripts/pubnet_ctl.py" --port $API_FWD_PORT addresses || true
echo
echo "tablet ready. further checks:"
echo "  python3 scripts/pubnet_ctl.py --port $API_FWD_PORT status"
