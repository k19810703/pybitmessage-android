"""Unit tests for :mod:`android_notify` (milestone M4.2.1).

Run from ``PyBitmessage/src``::

    python3 -m unittest tests.test_android_notify -v

The module is Android-only in practice; off-device every jnius call returns
``None``/``False`` early, which is exactly what the first test pins down.
The queue hook is tested with the real ``queues.UISignalQueue`` but a fake
notifier, so no Android runtime is needed.
"""

import os
import queue
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import android_notify  # noqa: E402
from queues import UISignalQueue  # noqa: E402


class OffDeviceTest(unittest.TestCase):

    def setUp(self):
        self._saved = os.environ.pop('ANDROID_ARGUMENT', None)

    def tearDown(self):
        if self._saved is not None:
            os.environ['ANDROID_ARGUMENT'] = self._saved

    def test_all_entry_points_are_noops_without_android(self):
        self.assertFalse(android_notify.request_permission_once())
        self.assertFalse(android_notify.ensure_channel())
        self.assertTrue(android_notify.has_permission())
        self.assertFalse(android_notify.notify_message('BM-x', 'hi'))
        self.assertFalse(android_notify.install_message_hook())


class MessageHookTest(unittest.TestCase):

    def setUp(self):
        self._saved = os.environ.get('ANDROID_ARGUMENT')
        os.environ['ANDROID_ARGUMENT'] = '/dev/null'  # pretend to be on device
        self.calls = []
        self._real = android_notify.notify_message
        android_notify.notify_message = (
            lambda *a, **k: self.calls.append(a) or True)
        while not UISignalQueue.empty():
            UISignalQueue.get_nowait()
        self.assertTrue(android_notify.install_message_hook())

    def tearDown(self):
        android_notify.notify_message = self._real
        while not UISignalQueue.empty():
            UISignalQueue.get_nowait()
        if self._saved is None:
            os.environ.pop('ANDROID_ARGUMENT', None)
        else:
            os.environ['ANDROID_ARGUMENT'] = self._saved

    def _wait_for(self, predicate, timeout=6.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.1)
        return False

    def test_inbox_signal_is_notified_and_requeued(self):
        UISignalQueue.put(('displayNewInboxMessage',
                           ('inv', 'BM-to', 'BM-from', '标题', '正文')))
        self.assertTrue(self._wait_for(lambda: self.calls))
        self.assertEqual(
            self.calls[0][:3], ('BM-from', '标题', '正文'))
        # the real consumer (UIkivySignaler) must still see the signal
        self.assertTrue(self._wait_for(lambda: not UISignalQueue.empty()))
        command, data = UISignalQueue.get_nowait()
        self.assertEqual(command, 'displayNewInboxMessage')
        self.assertEqual(data[2], 'BM-from')

    def test_other_commands_are_not_notified(self):
        UISignalQueue.put(('updateSentItemStatusByAckdata', ('ack', 's')))
        self.assertTrue(self._wait_for(lambda: not UISignalQueue.empty()))
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
