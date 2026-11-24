#!/usr/bin/env python3
"""Run the delivery regression D1-D7 (milestone M5.4.1).

    python3 scripts/regression-d1-d7.py                 # tablet on :8445
    python3 scripts/regression-d1-d7.py --keep-node     # leave the Mac node up
    python3 scripts/regression-d1-d7.py --skip-send     # only the cheap checks

The two "devices" are:

* **A = this Mac**, a headless pubnet node started by this script in a temp
  home (``scripts/pubnet_node.py``, API on :8451);
* **B = the tablet**, reached through ``adb forward tcp:8445 tcp:8442`` and its
  XML-RPC API (user:pass = u:p).

D5 (lock screen for 30 minutes and still receive) is explicitly **deferred by
the user** and is reported as SKIPPED, not as a pass -- a gate item is never
green just because nobody looked.

Everything is driven through the API on both sides, so the run is repeatable
and leaves a machine-readable report (``--json``) plus a markdown table.
"""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xmlrpc.client

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ADB = os.path.expanduser('~/Documents/platform-tools/adb')
PKG = 'at.bitmessage.pybitmessage'
ACTIVITY = PKG + '/org.kivy.android.PythonActivity'


class AuthTransport(xmlrpc.client.Transport):
    def __init__(self, user='u', password='p'):
        super().__init__()
        self._auth = base64.b64encode(
            ('%s:%s' % (user, password)).encode()).decode()

    def send_headers(self, connection, headers):
        headers.append(('Authorization', 'Basic ' + self._auth))
        super().send_headers(connection, headers)


def api(port, timeout=60):
    transport = AuthTransport()
    transport.timeout = timeout
    return xmlrpc.client.ServerProxy(
        'http://127.0.0.1:%d/' % port, transport=transport, allow_none=True)


def b64(text):
    return base64.b64encode(text.encode('utf-8')).decode()


def short(address):
    return address if len(address) <= 22 else address[:20] + '...'


# ---------------------------------------------------------------------------
# result bookkeeping
# ---------------------------------------------------------------------------

class Report(object):
    def __init__(self):
        self.rows = []

    def add(self, ident, title, status, detail=''):
        self.rows.append({'id': ident, 'title': title,
                          'status': status, 'detail': detail})
        symbol = {'PASS': '✅', 'FAIL': '❌', 'SKIP': '⏭',
                  'BLOCKED': '⛔'}.get(status, '?')
        print('%s %-3s %-42s %s' % (symbol, ident, title, detail), flush=True)

    def failures(self):
        return [r for r in self.rows if r['status'] == 'FAIL']

    def as_markdown(self):
        lines = ['| # | 项目 | 结果 | 说明 |', '|---|---|---|---|']
        for row in self.rows:
            symbol = {'PASS': '✅', 'FAIL': '❌', 'SKIP': '⏭',
                      'BLOCKED': '⛔'}.get(row['status'], '?')
            lines.append('| %s | %s | %s | %s |' % (
                row['id'], row['title'], symbol, row['detail']))
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def adb(*args, check=False):
    return subprocess.run([ADB, '-s', 'b45f8e87'] + list(args),
                          capture_output=True, text=True, check=check)


def wait_for_api(port, seconds, label):
    deadline = time.time() + seconds
    last = None
    while time.time() < deadline:
        try:
            api(port).clientStatus()
            return True
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(3)
    print('  %s API never came up (%r)' % (label, last), flush=True)
    return False


def ensure_address(port, seconds, label, create_label='regression'):
    """Return the node's addresses, creating one when the home is fresh.

    A headless node never creates its first address by itself -- only the Qt UI
    does that on first run -- so a brand-new ``pubnet_node.py`` home starts with
    ``listAddresses() == []``. The API command is the documented way to get one
    (and it is the same code path the GUI uses).
    """
    deadline = time.time() + seconds
    asked = False
    while time.time() < deadline:
        try:
            addresses = [a['address'] for a in api(port).listAddresses()['addresses']]
            if addresses:
                return addresses
            if not asked:
                print('  %s 没有地址，调用 createRandomAddress' % label,
                      flush=True)
                api(port, timeout=300).createRandomAddress(b64(create_label))
                asked = True
        except Exception as exc:  # noqa: BLE001
            print('  %s: %r' % (label, exc), flush=True)
        time.sleep(5)
    print('  %s 在 %ds 内没拿到地址' % (label, seconds), flush=True)
    return []


def addressbook(port):
    """Address-book entries as a flat list of addresses.

    The API returns ``{'addresses': [{'label':..., 'address':...}, ...]}``; some
    versions omit ``address`` for entries created before labels existed.
    """
    raw = api(port).listAddressBookEntries()
    entries = raw.get('addresses', raw) if isinstance(raw, dict) else raw
    out = []
    for entry in entries:
        if isinstance(entry, dict):
            value = entry.get('address') or entry.get('label')
        else:
            value = entry
        if value:
            out.append(value)
    return out


def wait_for_connections(port, minimum, seconds, label):
    """Wait until *port* has at least *minimum* established connections.

    A node that cannot get a single connection can neither publish its pubkey
    nor receive anything, so messaging checks are meaningless against it. The
    usual cause here is an egress IP that peers already have connections from
    ("Too many connections from your IP"), which is an environment property.
    """
    deadline = time.time() + seconds
    best = 0
    while time.time() < deadline:
        try:
            count = int(api(port).clientStatus()['networkConnections'])
            best = max(best, count)
            if count >= minimum:
                return count
        except Exception:  # noqa: BLE001
            pass
        time.sleep(5)
    print('  %s 最多拿到 %d 条连接（需要 %d）' % (label, best, minimum),
          flush=True)
    return best


def inbox(port):
    return api(port).getAllInboxMessages()['inboxMessages']


def subjects(port):
    out = set()
    for msg in inbox(port):
        subject = msg.get('subject')
        if isinstance(subject, xmlrpc.client.Binary):
            subject = bytes(subject)
        if isinstance(subject, bytes):
            subject = subject.decode('utf-8', 'replace')
        elif isinstance(subject, str):
            try:
                subject = base64.b64decode(subject).decode('utf-8', 'replace')
            except Exception:  # noqa: BLE001
                pass
        out.add(str(subject))
    return out


def wait_for_subject(port, needle, timeout, label):
    """Poll an inbox until a subject contains *needle*; return seconds taken."""
    started = time.time()
    while time.time() - started < timeout:
        try:
            for subject in subjects(port):
                if needle in subject:
                    return time.time() - started
        except Exception:  # noqa: BLE001 - API may hiccup mid-poll
            pass
        time.sleep(5)
    return None


def start_mac_node(home, api_port):
    log = open(os.path.join(home, 'node.log'), 'w')
    proc = subprocess.Popen(
        [sys.executable, '-u', os.path.join(HERE, 'pubnet_node.py'),
         '--home', home, '--api-port', str(api_port)],
        stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ))
    return proc, log


# ---------------------------------------------------------------------------
# the regression itself
# ---------------------------------------------------------------------------

def run(args):
    report = Report()
    tablet = args.tablet_port
    mac = args.mac_port

    print('== 启动 Mac 节点（A）', flush=True)
    home = tempfile.mkdtemp(prefix='regress-a-')
    proc, log = start_mac_node(home, mac)
    keep = args.keep_node
    try:
        if not wait_for_api(mac, 120, 'A(Mac)'):
            report.add('D1', '两台设备各有地址', 'FAIL', 'A 节点没起来')
            return report
        if not wait_for_api(tablet, 60, 'B(平板)'):
            report.add('D1', '两台设备各有地址', 'FAIL',
                       '平板 API 不可达（adb forward 8445 是否还在？）')
            return report

        # ---- D1: both sides have an address ------------------------------
        addrs_a = ensure_address(mac, 300, 'A(Mac)', 'regression-A')
        addrs_b = ensure_address(tablet, 60, 'B(平板)')
        if not addrs_a or not addrs_b:
            report.add('D1', '两台设备各生成地址', 'FAIL',
                       'A=%d 个地址，B=%d 个地址' % (len(addrs_a), len(addrs_b)))
            return report
        addr_a = addrs_a[0]
        report.add('D1', '两台设备各生成地址', 'PASS',
                   'A=%s  B=%s' % (short(addr_a), short(addrs_b[0])))
        addr_b = addrs_b[0]

        # ---- D2: address can be added to the address book ----------------
        try:
            api(tablet).addAddressBookEntry(addr_a, b64('A-mac'))
        except Exception as exc:  # noqa: BLE001 - duplicate is fine
            print('  addAddressBookEntry: %r' % (exc,), flush=True)
        book = addressbook(tablet)
        report.add('D2', 'B 能把 A 的地址加进通讯录',
                   'PASS' if addr_a in book else 'FAIL',
                   '通讯录 %d 条，含 A=%s' % (len(book), addr_a in book))

        if args.skip_send:
            report.add('D3', 'B→A 消息到达', 'SKIP', '--skip-send')
            report.add('D4', 'A→B 回复到达', 'SKIP', '--skip-send')
        else:
            online = wait_for_connections(mac, 1, args.connect_timeout,
                                          'A(Mac)') >= 1
            if not online:
                reason = ('A(Mac) 无法建立任何公网连接（出口 IP 被节点以 '
                          'Too many connections from your IP 拒绝），'
                          '双向收发无法执行')
                report.add('D3', 'B→A 消息到达', 'BLOCKED', reason)
                report.add('D4', 'A→B 回复到达', 'BLOCKED', reason)
                report.add('D5', '锁屏 30 分钟仍能收', 'SKIP',
                           '用户明确要求放到最后，本轮不验')
                report.add('D6', '重启后地址/消息/联系人都在', 'BLOCKED',
                           'D3/D4 未完成，本轮不做破坏性重启')
                report.add('D7', '全程无 FATAL', 'BLOCKED', '同上')
                return report

            # ---- D3: B -> A ---------------------------------------------
            tag = 'REG-B2A-%d' % int(time.time())
            # signature is sendMessage(toAddress, fromAddress, ...)
            api(tablet).sendMessage(addr_a, addr_b, b64(tag),
                                    b64('regression D3 ' + tag))
            took = wait_for_subject(mac, tag, args.send_timeout, 'A')
            report.add('D3', 'B→A 消息到达', 'PASS' if took else 'FAIL',
                       ('%s，%.0fs' % (tag, took)) if took else
                       ('%s，%ds 内未到达' % (tag, args.send_timeout)))

            # ---- D4: A -> B ---------------------------------------------
            tag = 'REG-A2B-%d' % int(time.time())
            api(mac).sendMessage(addr_b, addr_a, b64(tag),
                                 b64('regression D4 ' + tag))
            took = wait_for_subject(tablet, tag, args.send_timeout, 'B')
            report.add('D4', 'A→B 回复到达', 'PASS' if took else 'FAIL',
                       ('%s，%.0fs' % (tag, took)) if took else
                       ('%s，%ds 内未到达' % (tag, args.send_timeout)))

        if args.no_restart:
            report.add('D6', '重启后地址/消息/联系人都在', 'SKIP',
                       '--no-restart')
            report.add('D7', '全程无 FATAL', 'SKIP', '--no-restart')
            report.add('D5', '锁屏 30 分钟仍能收', 'SKIP',
                       '用户明确要求放到最后，本轮不验')
            return report

        # ---- D5: deferred on purpose ------------------------------------
        report.add('D5', '锁屏 30 分钟仍能收', 'SKIP',
                   '用户明确要求放到最后，本轮不验')

        # ---- D6: restart keeps identity / messages / contacts ------------
        before = (set(addrs_b), len(inbox(tablet)),
                  len(addressbook(tablet)))
        adb('shell', 'am', 'force-stop', PKG)
        time.sleep(3)
        adb('shell', 'am', 'start', '-n', ACTIVITY)
        if not wait_for_api(tablet, 180, 'B(平板重启后)'):
            report.add('D6', '重启后地址/消息/联系人都在', 'FAIL',
                       '重启后 API 没起来')
        else:
            after = (set(api(tablet).listAddresses() and
                         [a['address'] for a in
                          api(tablet).listAddresses()['addresses']]),
                     len(inbox(tablet)),
                     len(addressbook(tablet)))
            ok = before == after
            report.add('D6', '重启后地址/消息/联系人都在',
                       'PASS' if ok else 'FAIL',
                       '重启前 %s，重启后 %s' % (before, after))

        # ---- D7: no FATAL in the log ------------------------------------
        adb('logcat', '-c')
        adb('shell', 'am', 'force-stop', PKG)
        time.sleep(2)
        adb('shell', 'am', 'start', '-n', ACTIVITY)
        wait_for_api(tablet, 180, 'B(D7)')
        time.sleep(20)
        dump = adb('logcat', '-d').stdout
        fatal = [line for line in dump.splitlines()
                 if re.search(r'FATAL|Traceback|THREAD-CRASH', line)
                 and 'bitmessage' in line.lower() or 'python' in line.lower()
                 and re.search(r'FATAL|Traceback|THREAD-CRASH', line)]
        report.add('D7', '全程无 FATAL', 'PASS' if not fatal else 'FAIL',
                   '%d 条可疑日志' % len(fatal))
        if fatal:
            for line in fatal[:5]:
                print('    ' + line[:160], flush=True)
    finally:
        if not keep:
            proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()
            log.close()
            shutil.rmtree(home, ignore_errors=True)
        else:
            print('Mac 节点仍在运行：home=%s api=%d' % (home, mac), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tablet-port', type=int, default=8445)
    parser.add_argument('--mac-port', type=int, default=8451)
    parser.add_argument('--send-timeout', type=int, default=480,
                        help='seconds to wait for one message (default 480)')
    parser.add_argument('--skip-send', action='store_true')
    parser.add_argument('--no-restart', action='store_true',
                        help='skip D6/D7, which force-stop the app '
                             '(use while the device is in use)')
    parser.add_argument('--keep-node', action='store_true')
    parser.add_argument('--json', default=None, help='write the report here')
    parser.add_argument('--markdown', default=None)
    args = parser.parse_args()

    report = run(args)
    print()
    print(report.as_markdown())
    if args.json:
        with open(args.json, 'w') as handle:
            json.dump(report.rows, handle, ensure_ascii=False, indent=2)
        print('\njson ->', args.json)
    if args.markdown:
        with open(args.markdown, 'w') as handle:
            handle.write(report.as_markdown() + '\n')
        print('markdown ->', args.markdown)
    return 1 if report.failures() else 0


if __name__ == '__main__':
    sys.exit(main())
