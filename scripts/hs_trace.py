"""Standalone handshake-trace wrapper (diagnostic for M4.8.6, not shipped).

The network layer only logs a handful of points. This wraps the read/write
hooks of :class:`network.advanceddispatcher.AdvancedDispatcher` and the
asyncore connect event to print *every* stage of one connection, so we can
tell "bytes never arrive" from "bytes arrive but the state machine stalls".

  python3 scripts/hs_trace.py --home /tmp/trace --peer 127.0.0.1:8444 \
      --disable-tls --maxout 1

Run it as a node exactly like ``scripts/pubnet_node.py`` (same arguments);
the extra output goes to stdout next to the normal node log.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pubnet_node  # noqa: E402  (reuses its argument handling)

_SRC = pubnet_node.SRC

# imported before the core so the patched classes are the ones asyncore uses
sys.path.insert(0, _SRC)


def _install():
    from network.advanceddispatcher import AdvancedDispatcher

    orig_read = AdvancedDispatcher.handle_read
    orig_write = AdvancedDispatcher.handle_write
    orig_cce = AdvancedDispatcher.handle_connect_event
    orig_close = AdvancedDispatcher.handle_close

    def _tag(obj):
        return '%s:%s' % (
            getattr(obj.destination, 'host', '?'),
            getattr(obj.destination, 'port', '?'))

    def handle_read(self):
        before = len(self.read_buf)
        orig_read(self)
        added = len(self.read_buf) - before
        try:
            state = self.state
        except AttributeError:
            state = '?'
        print('HS READ %s +%dB buf=%dB state=%s tls=%s' % (
            _tag(self), added, len(self.read_buf), state,
            getattr(self, 'isSSL', None)), flush=True)

    def handle_write(self):
        before = len(self.write_buf)
        orig_write(self)
        try:
            state = self.state
        except AttributeError:
            state = '?'
        print('HS WRITE %s %dB->%dB state=%s expect=%s' % (
            _tag(self), before, len(self.write_buf), state,
            getattr(self, 'expectBytes', None)), flush=True)

    def handle_connect_event(self):
        print('HS CONNECT %s' % (_tag(self),), flush=True)
        orig_cce(self)

    def handle_close(self):
        print('HS CLOSE %s reason=%r state=%r' % (
            _tag(self), getattr(self, 'close_reason', None),
            getattr(self, 'state', None)), flush=True)
        orig_close(self)

    AdvancedDispatcher.handle_read = handle_read
    AdvancedDispatcher.handle_write = handle_write
    AdvancedDispatcher.handle_connect_event = handle_connect_event
    AdvancedDispatcher.handle_close = handle_close
    print('HS trace installed', flush=True)


if __name__ == '__main__':
    # pubnet_node.main() parses sys.argv itself, so patch first, then run.
    _install()
    pubnet_node.main()
