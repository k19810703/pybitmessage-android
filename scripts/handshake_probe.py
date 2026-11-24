"""One-shot probe of the TCP handshake state machine (diagnostic, M4.8.x).

Takes a complete TCP handshake byte stream from
``tests/fixtures/handshake/`` (captured from two real PyBitmessage nodes:
client ``version``, client ``verack``, server ``version``, server
``verack``) and feeds it to a :class:`network.bmproto.BMProto` instance
sitting on a socket pair. A correct state machine ends with
``fullyEstablished == True`` after the four packets.

Why: on a live node the version/verack exchange does *not* complete
(``verack received (verackSent=False)`` is logged for the peer's verack that
arrives before our own version is parsed), while the identical object works
in isolation. This isolates the state machine from the event loop.

  python3 scripts/handshake_probe.py [--legacy-bmproto /tmp/old_copy.py]
"""
import argparse
import os
import socket
import sys

SRC = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'PyBitmessage', 'src'))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', 'tests', 'fixtures', 'handshake')


class _Pool(object):
    """Minimal stand-in for BMConnectionPool (fields BMProto touches)."""
    streams = [1]
    inboundConnections = {}

    def __len__(self):
        return 0

    def isAlreadyConnected(self, nonce):
        return False

    def connections(self):
        return []

    def establishedConnections(self):
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--legacy-bmproto', default=None,
                        help='path to an older bmproto.py to compare against')
    args = parser.parse_args()

    os.environ.setdefault('BITMESSAGE_HOME', '/tmp/hsprobe')
    os.makedirs(os.environ['BITMESSAGE_HOME'], exist_ok=True)
    sys.path.insert(0, SRC)
    os.chdir(SRC)

    import state
    state.kivy = True
    state.disable_tls = True

    from helper_startup import loadConfig
    loadConfig()
    from bmconfigparser import config
    if not config.has_section('network'):
        config.add_section('network')
    config.set('network', 'dandelion', '0')

    if args.legacy_bmproto:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'network.legacy_bmproto', args.legacy_bmproto)
        legacy = importlib.util.module_from_spec(spec)
        sys.modules['network.legacy_bmproto'] = legacy
        spec.loader.exec_module(legacy)
        import network.tcp as tcpmod
        tcpmod.BMProto = legacy.BMProto
        print('PROBE using legacy bmproto:', args.legacy_bmproto)

    from network.tcp import TCPConnection

    data = {}
    for name in ('client_version', 'server_version', 'client_verack',
                 'server_verack'):
        with open(os.path.join(FIXTURES, name + '.bin'), 'rb') as fh:
            data[name] = fh.read()

    # outbound=False so our side behaves like the server half: it answers
    # with its own version, exactly as a real node does.
    a, b = socket.socketpair()

    class _FakeSock(object):
        """Delegates to the socketpair end but reports a peer address."""
        def __init__(self, sock):
            self._sock = sock

        def getpeername(self):
            return ('127.0.0.1', 8444)

        def __getattr__(self, name):
            return getattr(self._sock, name)

    # server-side constructor path takes the peer from getpeername()
    conn = TCPConnection(address=None, sock=_FakeSock(a))
    conn.pool = _Pool()
    conn.socket = a  # send/receive on the real end
    b.setblocking(False)

    order = [
        ('client version', 'client_version'),
        ('client verack', 'client_verack'),
        ('server version -> conntest side', 'server_version'),
        ('server verack -> conntest side', 'server_verack'),
    ]
    steps = 0
    while steps < 40:
        steps += 1
        for label, key in order:
            if conn.read_buf:
                break
        if conn.read_buf:
            pass
        # push the next fixture we have not consumed yet
        if not getattr(conn, '_probe_done', None):
            for label, key in order:
                if getattr(conn, '_probe_' + key, False):
                    continue
                conn.read_buf.extend(data[key])
                setattr(conn, '_probe_' + key, True)
                print('PROBE injected %-34s %4dB  state=%s' % (
                    label, len(data[key]), conn.state))
                break
        # drive outgoing bytes to the peer before advancing
        try:
            if conn.write_buf:
                b.send(conn.write_buf)
                del conn.write_buf[:]
        except BlockingIOError:
            pass
        try:
            conn.process()
        except Exception as exc:  # noqa: BLE001 - diagnostic
            print('PROBE process raised: %r' % (exc,))
            break
        print('PROBE after process    state=%-26s est=%s verackSent=%s '
              'verackRecv=%s' % (conn.state, conn.fullyEstablished,
                                 conn.verackSent, conn.verackReceived))
        if conn.fullyEstablished:
            break
        if getattr(conn, '_probe_server_verack', False) and not conn.read_buf:
            break
    print('PROBE RESULT fullyEstablished=%s state=%s' % (
        conn.fullyEstablished, conn.state))


if __name__ == '__main__':
    main()
