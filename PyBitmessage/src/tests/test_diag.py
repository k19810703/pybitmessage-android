"""Tests for the targeted diagnostics (``src/diag.py``).

Run from ``PyBitmessage/src``::

    python3 -m unittest tests.test_diag -v

Only the parts that work without a device/network are covered here; the
on-device behaviour (real pool, real peer error packets) is exercised by
running the app.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_HOME = tempfile.mkdtemp(prefix='diag-test-')
os.environ['BITMESSAGE_HOME'] = _HOME


def setUpModule():  # noqa: N802 - unittest hook name
    import state
    state.appdata = _HOME + os.sep


class PeerErrorTest(unittest.TestCase):

    def setUp(self):
        import diag
        self.diag = diag
        diag.PEER_ERRORS.clear()

    def test_errors_are_counted_per_peer(self):
        self.diag.note_peer_error('1.2.3.4', 8444, 2,
                                  "b'Too many connections from your IP.'")
        self.diag.note_peer_error('1.2.3.4', 8444, 2, 'again')
        self.diag.note_peer_error('5.6.7.8', 8080, 2, 'time offset')
        errors = self.diag.peer_errors()
        self.assertEqual(errors['1.2.3.4:8444']['count'], 2)
        self.assertEqual(errors['1.2.3.4:8444']['last'], 'again')
        self.assertEqual(errors['5.6.7.8:8080']['count'], 1)

    def test_table_is_bounded(self):
        for index in range(self.diag.MAX_PEERS_TRACKED + 10):
            self.diag.note_peer_error('10.0.0.%d' % index, 8444, 2, 'x')
        self.assertLessEqual(
            len(self.diag.peer_errors()), self.diag.MAX_PEERS_TRACKED)

    def test_peer_errors_returns_a_copy(self):
        self.diag.note_peer_error('1.2.3.4', 8444, 2, 'x')
        snapshot = self.diag.peer_errors()
        snapshot['1.2.3.4:8444']['count'] = 999
        self.assertEqual(self.diag.peer_errors()['1.2.3.4:8444']['count'], 1)


class SnapshotTest(unittest.TestCase):

    def setUp(self):
        import diag
        self.diag = diag

    def test_snapshot_without_pool_says_so(self):
        snap = self.diag.network_snapshot()
        self.assertIn('note', snap)
        self.assertIn('pool', snap['note'])

    def test_log_network_does_not_raise(self):
        self.assertTrue(self.diag.log_network('单元测试'))

    def test_periodic_starts_only_once(self):
        import diag
        diag._periodic_started = False
        self.assertTrue(diag.start_periodic(interval=3600, watch_every=3600))
        self.assertFalse(diag.start_periodic(interval=3600, watch_every=3600))
        diag._periodic_started = False


class DescribeSendTest(unittest.TestCase):

    def setUp(self):
        import diag
        self.diag = diag

    def test_invalid_address_is_reported_as_fatal(self):
        import contextlib
        import io
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.diag.describe_send('not-an-address')
        text = buffer.getvalue()
        self.assertIn('地址解析失败', text)
        self.assertIn('这一条就足以导致发送失败', text)

    def test_watch_sent_without_ackdata_is_a_noop(self):
        self.assertFalse(self.diag.watch_sent(None))


if __name__ == '__main__':
    unittest.main()
