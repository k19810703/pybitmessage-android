"""Diagnose why public peers reject us (diagnostic, not shipped).

Public nodes answer our version with

    error 2: 'Too many connections from your IP. Closing connection.'

which ``peerValidityChecks()`` produces when the peer already has a live
connection from our (shared, CGNAT) public egress address. This script shows
what we *claim* as our public IP in the version message, and how many peers
reject us per attempt, so "our IP is blacklisted" can be told apart from
"we send a garbage address".

  python3 scripts/pubnet_diag.py --home /tmp/diag --seconds 120
"""
import argparse
import os
import re
import sys
import time

SRC = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'PyBitmessage', 'src'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--home', default='/tmp/pubnetdiag')
    parser.add_argument('--api-port', type=int, default=8466)
    parser.add_argument('--seconds', type=int, default=120)
    args = parser.parse_args()

    os.makedirs(args.home, exist_ok=True)
    os.environ['BITMESSAGE_HOME'] = args.home
    sys.path.insert(0, SRC)
    os.chdir(SRC)

    import state
    state.kivy = True

    import bitmessagemain
    from bmconfigparser import config
    from network import tcp

    # Log the sockNode we advertise (what we think our public IP is).
    orig_connect = tcp.TCPConnection.handle_connect

    def handle_connect(self):
        orig_connect(self)
        try:
            node = getattr(self, 'sockNode', None)
            print('DIAG connect %s:%s our-sockNode=%s peer-port=%s' % (
                self.destination.host, self.destination.port,
                node, getattr(getattr(self, 'peerNode', None), 'port', '?')),
                flush=True)
        except Exception as exc:  # noqa: BLE001
            print('DIAG connect probe failed: %r' % (exc,), flush=True)

    tcp.TCPConnection.handle_connect = handle_connect

    config.set('bitmessagesettings', 'daemon', 'true')
    config.set('bitmessagesettings', 'maxoutboundconnections', '4')
    config.set('network', 'dandelion', '0')
    bitmessagemain.Main.daemonize = lambda self: None
    sys.argv = [sys.argv[0]]

    kn = os.path.join(args.home, 'knownnodes.dat')
    if not os.path.exists(kn):
        import json
        peers = ['85.114.135.102:8444', '194.164.163.84:8444',
                 '185.158.248.216:8444', '158.69.63.42:8080']
        with open(kn, 'w') as fh:
            json.dump([{
                'stream': 1,
                'peer': {'host': h, 'port': int(p)},
                'info': {'lastseen': int(time.time()), 'rating': 1,
                         'self': False}
            } for h, p in (x.split(':') for x in peers)], fh)

    import threading
    def stopper():
        time.sleep(args.seconds)
        print('DIAG done', flush=True)
        os._exit(0)
    threading.Thread(target=stopper, daemon=True).start()

    bitmessagemain.main()


if __name__ == '__main__':
    main()
