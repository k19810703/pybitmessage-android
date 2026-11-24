"""Trace connection close handling on a live node (diagnostic, M4.8.x).

Prints one line per close event with enough context to tell which layer
noticed what:

  python3 scripts/close_trace.py --home /tmp/ct --api-port 8505 \
      --disable-tls --peer 185.158.248.216:8444 --reset-peers

Tags: ``CT CP`` (pool reap), ``CT CLOSE`` (AdvancedDispatcher.close),
``CT WRITE`` (send raised), ``CT READ`` (recv raised, from the poller).
"""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pubnet_node  # noqa: E402

sys.path.insert(0, pubnet_node.SRC)

def _install():
    from network import connectionpool as cp
    from network import asyncore_pollchoose as asyncore

    orig_remove = cp.BMConnectionPool.removeConnection
    orig_close = asyncore.dispatcher.close

    def removeConnection(self, connection):
        try:
            reason = getattr(connection, 'close_reason', None)
            State = getattr(connection, 'state', None)
            est = getattr(connection, 'fullyEstablished', None)
            dest = getattr(connection, 'destination', None)
            print('CT CP remove %s reason=%r state=%r est=%s poolconns=%d' % (
                dest, reason, State, est, len(self.connections())),
                flush=True)
            cp.BMConnectionPool._probe_on_remove(connection)
        finally:
            return orig_remove(self, connection)

    def close(self):
        try:
            print('CT CLOSE %s fileno=%r map=%s' % (
                getattr(self, 'destination', self), getattr(self, '_fileno', None),
                'yes' if getattr(self, '_map', None) else 'no'), flush=True)
        except Exception:
            pass
        return orig_close(self)

    cp.BMConnectionPool.removeConnection = removeConnection
    asyncore.dispatcher.close = close
    cp.BMConnectionPool._probe_on_remove = staticmethod(
        lambda connection: _probe(connection))


def _probe(connection):
    """What does the raw socket say right before the object is closed?"""
    import errno
    from network.tcp import TCPConnection
    from network import knownnodes
    sock = getattr(connection, 'socket', None)
    if sock is None:
        print('CT PROBE no socket', flush=True)
        return
    # 1) is there unsent data?
    print('CT PROBE pending write_buf=%dB' % len(
        getattr(connection, 'write_buf', b'')), flush=True)
    # 2) is the peer still there? (non-destructive peek)
    try:
        data = sock.recv(1, socket.MSG_PEEK)
        print('CT PROBE peek -> %r (b"" = FIN from peer)' % (data,),
              flush=True)
    except BlockingIOError:
        print('CT PROBE peek -> would block (peer silent, still open)',
              flush=True)
    except OSError as exc:
        print('CT PROBE peek -> %r' % (exc,), flush=True)
    # 3) replace the object with a fresh one to the same peer, wire the
    #    events exactly like the server branch does, and see whether the
    #    reconnected object can complete the version/verack exchange.
    dest = connection.destination
    if not isinstance(connection, TCPConnection):
        return
    try:
        probe = TCPConnection(address=dest)
        probe.pool = getattr(connection, 'pool', None)
        probe.add_channel()
        print('CT PROBE fresh %s connected=%s connecting=%s' % (
            dest, probe.connected, probe.connecting), flush=True)
        deadline = time.time() + 25
        while time.time() < deadline and not probe.fullyEstablished:
            if probe.write_buf and probe.connected:
                written = probe.send(probe.write_buf)
                del probe.write_buf[:written]
            time.sleep(0.05)
        print('CT PROBE result %s established=%s verackSent=%s '
              'verackRecv=%s state=%s close_reason=%r' % (
                  dest, probe.fullyEstablished, probe.verackSent,
                  probe.verackReceived, getattr(probe, 'state', None),
                  getattr(probe, 'close_reason', None)), flush=True)
    except Exception as exc:  # noqa: BLE001
        print('CT PROBE fresh failed: %r' % (exc,), flush=True)


if __name__ == '__main__':
    _install()
    pubnet_node.main()
