#!/usr/bin/env python3
"""Headless desktop PyBitmessage node for public-network tests.

No Android emulator needed: this runs the real core on the Mac, with the
same TLS behaviour as the APK, a deterministic knownnodes list of live
public nodes, and the API on a port that does not collide with adb
forwards. Use scripts/pubnet_ctl.py to drive it.

  # first time (or after a code change affecting PoW):
  ./scripts/build-bitmsghash-native.sh

  # run the node (Ctrl-C or SIGTERM to stop):
  ./scripts/pubnet_node.py                        # defaults, maxout=1
  ./scripts/pubnet_node.py --maxout 2 --home /tmp/pubnet2

Data (keys.dat, messages.dat, knownnodes.dat) lives under --home, so the
node's address survives restarts. knownnodes.dat is seeded with the live
peers below on first start; --reset-peers rewrites it (learned nodes are
then discarded).

Why maxout=1 by default: connectionpool.addConnection() keys the first
inbound connection from an IP by host string and later ones by Peer,
and peerValidityChecks() then rejects the 2nd concurrent connection from
the same IP with "Too many connections from your IP" (EVIDENCE.md 1.24).
A single outbound connection per public peer avoids triggering it while
we test from an IP that may already be in a bad state.
"""
import argparse
import json
import os
import sys
import time

# live public nodes, verified 2026-11-19 (dig bootstrap{8444,8080} + nc)
DEFAULT_PEERS = [
    '85.114.135.102:8444',
    '194.164.163.84:8444',
    '185.158.248.216:8444',
    '158.69.63.42:8080',
]

SRC = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'PyBitmessage', 'src')
SRC = os.path.abspath(SRC)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', default='/tmp/pubnet',
                        help='BITMESSAGE_HOME (default /tmp/pubnet)')
    parser.add_argument('--api-port', type=int, default=8451,
                        help='API port (default 8451, never 8442: adb)')
    parser.add_argument('--maxout', type=int, default=1,
                        help='maxoutboundconnections (default 1, see doc)')
    parser.add_argument('--peer', action='append', default=None,
                        help='host:port to seed knownnodes (repeatable)')
    parser.add_argument('--reset-peers', action='store_true',
                        help='rewrite knownnodes.dat even if it exists')
    parser.add_argument('--disable-tls', action='store_true',
                        help='plaintext peer links (local tests only)')
    args = parser.parse_args()

    peers = args.peer or DEFAULT_PEERS
    parsed = []
    for p in peers:
        host, _, port = p.partition(':')
        parsed.append((host, int(port or 8444)))

    os.makedirs(args.home, exist_ok=True)
    os.environ['BITMESSAGE_HOME'] = args.home

    sys.path.insert(0, SRC)
    os.chdir(SRC)

    import state
    state.kivy = True
    state.disable_tls = bool(args.disable_tls)

    import bitmessagemain
    from bmconfigparser import config

    config.set('bitmessagesettings', 'daemon', 'true')
    config.set('bitmessagesettings', 'apienabled', 'true')
    config.set('bitmessagesettings', 'apivariant', 'xml')
    config.set('bitmessagesettings', 'apiport', str(args.api_port))
    config.set('bitmessagesettings', 'apiusername', 'u')
    config.set('bitmessagesettings', 'apipassword', 'p')
    config.set('bitmessagesettings', 'maxoutboundconnections',
               str(args.maxout))
    config.set('network', 'dandelion', '0')

    kn = os.path.join(args.home, 'knownnodes.dat')
    if args.reset_peers or not os.path.exists(kn):
        with open(kn, 'w') as fh:
            json.dump([{
                'stream': 1,
                'peer': {'host': h, 'port': p},
                'info': {'lastseen': int(time.time()), 'rating': 1,
                         'self': False}
            } for h, p in parsed], fh)
        print('knownnodes.dat: %d peers' % len(parsed))

    # keep logs on stdout instead of the daemon fork's /dev/null
    bitmessagemain.Main.daemonize = lambda self: None

    # bitmessagemain.Main.start() getopt-parses sys.argv; drop our own
    # arguments so they don't leak into it and trigger usage()/exit(2)
    sys.argv = [sys.argv[0]]

    print('starting node: home=%s api=127.0.0.1:%d maxout=%d tls=%s' % (
        args.home, args.api_port, args.maxout, not args.disable_tls))
    bitmessagemain.main()


if __name__ == '__main__':
    main()
