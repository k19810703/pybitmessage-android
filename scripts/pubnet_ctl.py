#!/usr/bin/env python3
"""Control client for a pubnet node (scripts/pubnet_node.py or a device).

XML-RPC over the API, basic-auth u:p. Examples:

  ./scripts/pubnet_ctl.py status
  ./scripts/pubnet_ctl.py wait-conn 300          # until networkConnections>=1
  ./scripts/pubnet_ctl.py addresses
  ./scripts/pubnet_ctl.py create mac-test        # new address, prints it
  ./scripts/pubnet_ctl.py send BM-... BM-... ' subj' ' hello'
  ./scripts/pubnet_ctl.py inbox
  ./scripts/pubnet_ctl.py sent                   # watch awaitingpubkey->msgsent
  ./scripts/pubnet_ctl.py --port 8445 status     # tablet via adb forward
"""
import argparse
import base64
import json
import sys
import time
import xmlrpc.client


class AuthTransport(xmlrpc.client.Transport):
    def __init__(self, user='u', password='p'):
        super().__init__()
        self._auth = base64.b64encode(
            ('%s:%s' % (user, password)).encode()).decode()

    def send_headers(self, connection, headers):
        headers.append(('Authorization', 'Basic ' + self._auth))
        super().send_headers(connection, headers)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', type=int, default=8451)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('command', choices=[
        'status', 'addresses', 'create', 'send', 'inbox', 'sent',
        'wait-conn'])
    parser.add_argument('args', nargs='*')
    opts = parser.parse_args()

    proxy = xmlrpc.client.ServerProxy(
        'http://%s:%d/' % (opts.host, opts.port),
        transport=AuthTransport(), allow_none=True)

    try:
        if opts.command == 'status':
            print(json.dumps(proxy.clientStatus(), indent=1,
                             default=str, ensure_ascii=False))
        elif opts.command == 'wait-conn':
            deadline = time.time() + int(opts.args[0] if opts.args else 300)
            while time.time() < deadline:
                st = proxy.clientStatus()
                n = st['networkConnections']
                if n and int(n) >= 1:
                    print('connected: %s (status=%s)' % (
                        n, st['networkStatus']))
                    return 0
                time.sleep(5)
            print('timeout waiting for a connection', file=sys.stderr)
            return 1
        elif opts.command == 'addresses':
            for a in proxy.listAddresses()['addresses']:
                print(a['address'], a.get('label', ''))
        elif opts.command == 'create':
            label = opts.args[0] if opts.args else 'pubnet-test'
            print(proxy.createRandomAddress(label))
        elif opts.command == 'send':
            if len(opts.args) < 4:
                parser.error('send needs: TO FROM SUBJECT BODY')
            to, frm, subject, body = opts.args[:4]
            ack = proxy.sendMessage(to, frm, subject, body)
            print('ackdata:', ack)
        elif opts.command == 'inbox':
            msgs = proxy.getAllInboxMessages()['inboxMessages']
            for m in msgs:
                print('--- %s' % m['msgid'][:16])
                print('  from: %s  to: %s  received: %s' % (
                    m['fromAddress'], m['toAddress'], m['receivedTime']))
                print('  subject: %s' % m['subject'])
                print('  %s' % m['message'])
            if not msgs:
                print('(inbox empty)')
        elif opts.command == 'sent':
            msgs = proxy.getAllSentMessages()['sentMessages']
            for m in msgs:
                print('%s  to=%-20s status=%-14s ack=%s' % (
                    m['msgid'][:16], m['toAddress'], m['status'],
                    m['ackData'][:16]))
            if not msgs:
                print('(nothing sent)')
    except Exception as e:
        print('API error: %s' % e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
