"""Trace the post-handshake pipeline (diagnostic for M4.8.x, not shipped).

Compares what a node *thinks* it has established with what it actually has,
and walks one inbound `inv` from arrival to `getdata`:

  python3 scripts/pipeline_trace.py --home /tmp/pl --api-port 8470 \
      --disable-tls --peer 9.9.9.9:8444 --seconds 120

Prints every 10 s:

  PL pool  inbound=<dict keys>  established=<list>  downloader=<thread alive>

and, per received inventory hash, from `handleReceivedInventory` to the
DownloadThread request.
"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pubnet_node  # noqa: E402

sys.path.insert(0, pubnet_node.SRC)


def _install():
    import network.objectracker as ot
    from network import connectionpool as cp
    from network import downloadthread as dt

    orig_hri = ot.ObjectTracker.handleReceivedInventory
    orig_establish = cp.BMConnectionPool.establishedConnections

    def handleReceivedInventory(self, hashId):
        print('PL INV %s:%s %s' % (
            getattr(self.destination, 'host', '?'),
            getattr(self.destination, 'port', '?'),
            hashId.hex()[:12]), flush=True)
        return orig_hri(self, hashId)

    def establishedConnections(self):
        res = orig_establish(self)
        print('PL establishedConnections -> %d' % len(res), flush=True)
        return res

    ot.ObjectTracker.handleReceivedInventory = handleReceivedInventory
    cp.BMConnectionPool.establishedConnections = establishedConnections

    orig_run = dt.DownloadThread.run

    def run(self):
        last = [0]

        def loop():
            return orig_run(self)
        print('PL DownloadThread started', flush=True)
        return loop()

    dt.DownloadThread.run = run

    def reporter():
        import time
        while True:
            time.sleep(10)
            pool = cp.pool
            dl = [t for t in threading.enumerate()
                  if t.name == 'Downloader']
            if pool is None:
                print('PL pool=None', flush=True)
                continue
            out = []
            for k, c in pool.outboundConnections.items():
                out.append('%s est=%s ol=%d ria=%d theirnew=%d' % (
                    k.host, c.fullyEstablished,
                    len(c.objectsNewToMe) if hasattr(c.objectsNewToMe, '__len__') else -1,
                    len(getattr(c.objectsNewToMe, 'keys', lambda: [])()),
                    len(c.objectsNewToThem)))
            print('PL pool inbound=%s established=%d missing=%d dl=%s out=%s' % (
                list(pool.inboundConnections.keys()),
                len(pool.establishedConnections()),
                len(ot.missingObjects),
                [(t.name, t.is_alive()) for t in dl], out), flush=True)

    threading.Thread(target=reporter, daemon=True).start()


if __name__ == '__main__':
    _install()
    pubnet_node.main()
