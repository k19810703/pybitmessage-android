"""Targeted diagnostics for the two questions users actually ask.

"When the app shows 0 connections, why?" and "I pressed send, the message never
arrived, why?" A generic log full of INFO lines does not answer either: the
answer lives in state that is spread over the pool, the knownnodes table, the
config, the sender worker and the ``sent`` table.

This module snapshots all of it into the log file (see :mod:`applog`):

* ``log_network(tag)`` -- counts, a per-connection table (handshake progress,
  close reason, idle time), knownnodes statistics, the settings that decide how
  many outbound connections the node even tries, and whether the network
  threads are still alive;
* ``note_peer_error(...)`` -- every ``error`` packet a peer sends us, counted
  per peer and kept as text: this is where "Too many connections from your IP"
  and "Your time is too far in the past" come from, i.e. the usual reason a
  connection never completes;
* ``describe_send(addr)`` -- is the address valid, do we already hold its
  pubkey, what happened to previous sends to it;
* ``watch_sent(ackdata)`` -- follows one message through
  ``awaitingpubkey -> doingpubkeypow -> doingmsgpow -> msgsent -> ackreceived``
  and logs each transition with a timestamp, so "it never sent" becomes "it sat
  in doingmsgpow for 9 minutes" or "it waited for a pubkey that never came".

Everything degrades to a no-op off-device and never raises.
"""

import threading
import time

PEER_ERRORS = {}
PEER_ERRORS_LOCK = threading.Lock()
MAX_PEERS_TRACKED = 32

_periodic_started = False
_hooks_installed = False
_last_established = None


def _say(text):
    """print() is teed into the log file by applog."""
    print('[DIAG] %s' % text, flush=True)


# ---------------------------------------------------------------------------
# peer error packets: the usual reason a handshake dies
# ---------------------------------------------------------------------------

def note_peer_error(host, port, fatal, text):
    key = '%s:%s' % (host, port)
    try:
        text = str(text)
    except Exception:  # noqa: BLE001
        text = repr(text)
    with PEER_ERRORS_LOCK:
        entry = PEER_ERRORS.setdefault(
            key, {'count': 0, 'last': '', 'fatal': fatal})
        entry['count'] += 1
        entry['last'] = text
        entry['fatal'] = fatal
        if len(PEER_ERRORS) > MAX_PEERS_TRACKED:
            for stale in list(PEER_ERRORS)[:-MAX_PEERS_TRACKED]:
                PEER_ERRORS.pop(stale, None)


def peer_errors():
    with PEER_ERRORS_LOCK:
        return {k: dict(v) for k, v in PEER_ERRORS.items()}


def install_hooks():
    """Record the text of every peer ``error`` packet.

    ``bm_command_error`` decodes the payload with ``decode_payload_content``,
    which advances ``payloadOffset``; the offset is saved and restored here so
    the real handler still sees the same position.
    """
    global _hooks_installed
    if _hooks_installed:
        return True
    try:
        from network.bmproto import BMProto
    except Exception as exc:  # noqa: BLE001 - core not importable yet
        _say('install_hooks skipped: %r' % (exc,))
        return False

    original = BMProto.bm_command_error

    def bm_command_error(self):
        try:
            saved = self.payloadOffset
            try:
                values = self.decode_payload_content("vvlsls")
                note_peer_error(
                    getattr(self.destination, 'host', '?'),
                    getattr(self.destination, 'port', '?'),
                    values[0], values[3])
            finally:
                self.payloadOffset = saved
        except Exception:  # noqa: BLE001 - never break the real handler
            pass
        return original(self)

    BMProto.bm_command_error = bm_command_error
    _hooks_installed = True
    _say('hooks installed (peer error packets are now counted)')
    return True


# ---------------------------------------------------------------------------
# the snapshot
# ---------------------------------------------------------------------------

def _pool():
    try:
        from network import stats
        return getattr(stats, 'pool', None)
    except Exception:  # noqa: BLE001
        return None


def _connection_rows(pool):
    rows = []
    for kind, mapping in (('out', getattr(pool, 'outboundConnections', {})),
                          ('in', getattr(pool, 'inboundConnections', {}))):
        for key, conn in list(mapping.items()):
            dest = getattr(conn, 'destination', key)
            host = getattr(dest, 'host', '?')
            port = getattr(dest, 'port', '?')
            idle = '?'
            try:
                idle = '%.0fs' % (time.time() - conn.lastTx)
            except Exception:  # noqa: BLE001
                pass
            rows.append(
                '%s %s:%s est=%s connected=%s verack(sent=%s recv=%s)'
                ' state=%s idle=%s reason=%r' % (
                    kind, host, port,
                    getattr(conn, 'fullyEstablished', '?'),
                    getattr(conn, 'connected', '?'),
                    getattr(conn, 'verackSent', '?'),
                    getattr(conn, 'verackReceived', '?'),
                    getattr(conn, 'state', '?'),
                    idle,
                    getattr(conn, 'close_reason', None)))
    return rows


def _knownnode_stats():
    try:
        from network import knownnodes
    except Exception:  # noqa: BLE001
        return '?'
    total = rated = 0
    try:
        with knownnodes.knownNodesLock:
            for stream in knownnodes.knownNodes:
                for _peer, info in knownnodes.knownNodes[stream].items():
                    total += 1
                    try:
                        if info.get('rating', 0) > 0:
                            rated += 1
                    except AttributeError:
                        pass
    except Exception:  # noqa: BLE001
        return '?'
    return '%d (rating>0: %d)' % (total, rated)


def _threads():
    wanted = ('Asyncore', 'Downloader', 'Uploader', 'InvBroadcaster',
              'AddrBroadcaster', 'ReceiveQueue_0', 'ReceiveQueue_1',
              'ReceiveQueue_2', 'singleCleaner', 'objectProcessor',
              'singleWorker', 'SQL')
    alive = {t.name: t.is_alive() for t in threading.enumerate()}
    return ', '.join('%s=%s' % (n, alive.get(n, 'missing')) for n in wanted)


def _settings():
    try:
        from bmconfigparser import config
    except Exception:  # noqa: BLE001
        return '?'
    keys = ('maxoutboundconnections', 'maxbootstrapconnections',
            'maxtotalconnections', 'port', 'extport', 'udp',
            'socksproxytype', 'sendoutgoingconnections')
    parts = []
    for key in keys:
        parts.append('%s=%s' % (key, config.safeGet(
            'bitmessagesettings', key, '?')))
    try:
        from network import dandelion
        parts.append('dandelion=%s' % getattr(dandelion, 'enabled', '?'))
    except Exception:  # noqa: BLE001
        pass
    return ' '.join(parts)


def network_snapshot():
    """Everything needed to explain "why 0 connections" as a dict."""
    pool = _pool()
    snap = {
        'established': '?', 'outbound': '?', 'inbound': '?',
        'knownnodes': _knownnode_stats(),
        'settings': _settings(),
        'threads': _threads(),
        'connections': [],
        'peer_errors': peer_errors(),
    }
    if pool is None:
        snap['note'] = 'pool is None (network never started)'
        return snap
    try:
        snap['established'] = len(pool.establishedConnections())
        snap['outbound'] = len(pool.outboundConnections)
        snap['inbound'] = len(pool.inboundConnections)
        snap['connections'] = _connection_rows(pool)
    except Exception as exc:  # noqa: BLE001
        snap['note'] = 'snapshot failed: %r' % (exc,)
    return snap


def log_network(tag):
    """Write one diagnostic block to the log file."""
    snap = network_snapshot()
    _say('--- %s ---' % tag)
    _say('连接 established=%s outbound=%s inbound=%s | knownnodes=%s' % (
        snap['established'], snap['outbound'], snap['inbound'],
        snap['knownnodes']))
    _say('设置 %s' % snap['settings'])
    _say('线程 %s' % snap['threads'])
    if snap.get('note'):
        _say('注意 %s' % snap['note'])
    for row in snap['connections'][:24]:
        _say('  %s' % row)
    if len(snap['connections']) > 24:
        _say('  ...（共 %d 条，只列前 24）' % len(snap['connections']))
    errors = snap['peer_errors']
    if errors:
        _say('对端 error 包 %d 个对端：' % len(errors))
        for key, info in list(errors.items())[:12]:
            _say('  %s ×%d fatal=%s %r' % (
                key, info['count'], info['fatal'], info['last'][:80]))
    else:
        _say('对端 error 包：无（说明不是被对端拒绝，可能是 DNS/防火墙/无出站）')
    return snap


def start_periodic(interval=300, watch_every=30):
    """Log a snapshot every *interval* seconds and on any big change.

    "0 connections" is only actionable with the timeline around it, and a
    change in the established count is exactly when something interesting
    happened (peers accepted us, or dropped us).
    """
    global _periodic_started
    if _periodic_started:
        return False
    _periodic_started = True

    def loop():
        # `global` inside the nested function: assigning _last_established here
        # without it would make the name local to loop() and the comparison
        # would raise UnboundLocalError (same trap as applog._write).
        global _last_established
        last_full = 0.0
        while True:
            time.sleep(watch_every)
            try:
                established = network_snapshot()['established']
            except Exception:  # noqa: BLE001
                continue
            try:
                changed = (established != _last_established)
                _last_established = established
                now = time.time()
                if changed:
                    log_network('连接数变化 -> %s' % established)
                    last_full = now
                elif now - last_full >= interval:
                    log_network('周期快照')
                    last_full = now
            except Exception:  # noqa: BLE001
                pass

    thread = threading.Thread(target=loop, name='diag', daemon=True)
    thread.start()
    _say('周期快照已启动（每 %ds 检查，变化即记录，最长 %ds 一次）'
         % (watch_every, interval))
    return True


# ---------------------------------------------------------------------------
# sending
# ---------------------------------------------------------------------------

def describe_send(to_address, from_address=None):
    """Pre-send facts: valid address? pubkey known? earlier attempts?"""
    _say('--- 发送诊断 ---')
    _say('收件地址 %s' % to_address)
    try:
        from addresses import decodeAddress
        version, stream, ripe = decodeAddress(to_address)
        _say('地址解析 OK version=%s stream=%s ripe=%s' % (
            version, stream, ripe.hex()[:12]))
    except Exception as exc:  # noqa: BLE001
        _say('地址解析失败：%r  <-- 这一条就足以导致发送失败' % (exc,))
    if from_address:
        _say('发件地址 %s' % from_address)
    try:
        from helper_sql import sqlQuery
        rows = sqlQuery(
            'SELECT addressversion, time FROM pubkeys WHERE address=?',
            to_address)
        if rows:
            _say('已持有对方公钥（version=%s, %s）' % (
                rows[0][0], time.strftime(
                    '%Y-%m-%d %H:%M', time.localtime(rows[0][1]))))
        else:
            _say('尚未持有对方公钥 -> 会先广播 getpubkey 等对方上线，'
                 '这一步可能永远等不到')
        previous = sqlQuery(
            "SELECT status, senttime FROM sent WHERE toaddress=? "
            "ORDER BY senttime DESC LIMIT 3", to_address)
        for status, senttime in previous:
            _say('  历史: status=%s sent=%s' % (
                status, time.strftime(
                    '%Y-%m-%d %H:%M', time.localtime(senttime))))
    except Exception as exc:  # noqa: BLE001
        _say('查询 pubkeys/sent 失败：%r' % (exc,))
    try:
        established = network_snapshot()['established']
        _say('当前连接数 %s%s' % (
            established,
            '  <-- 0 连接时消息发不出去也收不到回执' if established == 0 else ''))
    except Exception:  # noqa: BLE001
        pass


#: Terminal states of a send; anything else means "still trying".
_DONE = ('msgsent', 'msgsentnoackexpected', 'ackreceived', 'broadcastsent',
         'awaitingpubkey', 'error')


def watch_sent(ackdata, timeout=1800, interval=15):
    """Follow one send through the worker's status transitions."""
    if ackdata is None:
        return False

    def loop():
        seen = None
        started = time.time()
        while time.time() - started < timeout:
            try:
                from helper_sql import sqlQuery
                rows = sqlQuery(
                    "SELECT status, retrynumber FROM sent WHERE ackdata=?",
                    ackdata)
                status = rows[0][0] if rows else 'gone'
            except Exception as exc:  # noqa: BLE001
                _say('watch_sent 查询失败：%r' % (exc,))
                return
            if status != seen:
                _say('发送状态 %s -> %s（%.0fs）' % (
                    seen, status, time.time() - started))
                seen = status
            if status in ('ackreceived', 'broadcastsent'):
                return
            time.sleep(interval)
        _say('发送监视超时：%ds 后仍停在 %s（这不是"已发送"，是卡住了）'
             % (timeout, seen))

    thread = threading.Thread(target=loop, name='diag-send', daemon=True)
    thread.start()
    return True
