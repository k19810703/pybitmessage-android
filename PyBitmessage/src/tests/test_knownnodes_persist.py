"""knownnodes persistence tests (M4.4.1 / M4.8.1 follow-up).

Run from ``PyBitmessage/src``::

    python3 -m unittest tests.test_knownnodes_persist -v

The bug these pin down: ``cleanupKnownNodes()`` wrote ``knownnodes.dat`` only
when it had *deleted* a node, so nodes learned from peers were never saved.
On the tablet the file still held 4 hand-written seeds from 25 hours earlier
while the in-memory table had grown to hundreds, which is why every restart
fell back to a stale peer list (M4.4.1 evidence).
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_HOME = tempfile.mkdtemp(prefix='knownnodes-test-')


def setUpModule():  # noqa: N802 - unittest hook name
    os.environ['BITMESSAGE_HOME'] = _HOME
    import state
    state.appdata = _HOME + os.sep


def tearDownModule():  # noqa: N802 - unittest hook name
    shutil.rmtree(_HOME, ignore_errors=True)


class _Pool(object):
    """Stub pool: cleanupKnownNodes asks for its streams and connections."""

    streams = [1]

    def connections(self):
        return []


class KnownNodesPersistenceTest(unittest.TestCase):

    def setUp(self):
        import state
        import network.knownnodes as kn
        from network.knownnodes import Peer
        from bmconfigparser import config

        self.kn = kn
        self.Peer = Peer
        self.config = config
        state.appdata = _HOME + os.sep
        with kn.knownNodesLock:
            kn.knownNodes.clear()
            kn.knownNodes[1] = {}
        kn.knownNodesDirty = False
        self.path = os.path.join(_HOME, 'knownnodes.dat')
        if os.path.exists(self.path):
            os.unlink(self.path)

    def _on_disk(self):
        with open(self.path) as handle:
            return json.load(handle)

    def test_learned_node_is_written_by_cleanup(self):
        self.assertTrue(self.kn.addKnownNode(1, self.Peer('1.2.3.4', 8444)))
        self.assertTrue(self.kn.knownNodesDirty,
                        'adding a node must mark the table dirty')
        self.assertFalse(os.path.exists(self.path))

        self.kn.cleanupKnownNodes(_Pool())

        self.assertTrue(os.path.exists(self.path), 'cleanup must write the file')
        hosts = [row['peer']['host'] for row in self._on_disk()]
        self.assertIn('1.2.3.4', hosts)
        self.assertFalse(self.kn.knownNodesDirty, 'dirty flag must reset')

    def test_second_cleanup_does_not_rewrite_when_nothing_changed(self):
        self.kn.addKnownNode(1, self.Peer('1.2.3.4', 8444))
        self.kn.cleanupKnownNodes(_Pool())
        first = os.stat(self.path).st_mtime_ns
        time.sleep(0.02)
        self.kn.cleanupKnownNodes(_Pool())
        self.assertEqual(
            os.stat(self.path).st_mtime_ns, first,
            'an unchanged table must not be rewritten every cycle')

    def test_newer_lastseen_marks_dirty(self):
        peer = self.Peer('5.6.7.8', 8444)
        self.kn.addKnownNode(1, peer, lastseen=int(time.time()) - 600)
        self.kn.saveKnownNodes()
        self.assertFalse(self.kn.knownNodesDirty)

        self.kn.addKnownNode(1, peer, lastseen=int(time.time()))
        self.assertTrue(self.kn.knownNodesDirty,
                        'a newer lastseen must be persisted')

    def test_save_resets_dirty(self):
        self.kn.addKnownNode(1, self.Peer('9.9.9.9', 8444))
        self.kn.saveKnownNodes()
        self.assertFalse(self.kn.knownNodesDirty)

    def test_reload_after_save_sees_the_node(self):
        self.kn.addKnownNode(1, self.Peer('4.3.2.1', 8444))
        self.kn.cleanupKnownNodes(_Pool())

        with self.kn.knownNodesLock:
            self.kn.knownNodes.clear()
            self.kn.knownNodes[1] = {}
        self.kn.readKnownNodes()

        hosts = {str(peer.host) for peer in self.kn.knownNodes[1]}
        self.assertIn('4.3.2.1', hosts)


if __name__ == '__main__':
    unittest.main()
