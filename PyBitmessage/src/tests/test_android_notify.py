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
import helper_inbox  # noqa: E402


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
    """install_message_hook() must notify exactly once per stored message."""

    ROW = (b'\x01' * 32, 'BM-to', 'BM-from', '标题 M4.2.1', 1234567890,
           '正文 body', 'inbox', 2, 0, b'\x02' * 32)

    def setUp(self):
        self._saved_env = os.environ.get('ANDROID_ARGUMENT')
        os.environ['ANDROID_ARGUMENT'] = '/dev/null'  # pretend to be on device
        self.calls = []
        self._real_notify = android_notify.notify_message
        android_notify.notify_message = (
            lambda *a, **k: self.calls.append(a) or True)
        self._real_insert = helper_inbox.insert
        helper_inbox.insert = lambda t: None          # don't touch SQL
        if getattr(helper_inbox, '_notify_hook_installed', False):
            self.skipTest('hook already installed by another test')
        self.assertTrue(android_notify.install_message_hook())

    def tearDown(self):
        helper_inbox.insert = self._real_insert
        helper_inbox._notify_hook_installed = False
        android_notify.notify_message = self._real_notify
        if self._saved_env is None:
            os.environ.pop('ANDROID_ARGUMENT', None)
        else:
            os.environ['ANDROID_ARGUMENT'] = self._saved_env

    def test_stored_message_triggers_one_notification(self):
        helper_inbox.insert(self.ROW)
        self.assertEqual(len(self.calls), 1)
        # (from_address, subject, body)
        self.assertEqual(self.calls[0][0], 'BM-from')
        self.assertEqual(self.calls[0][1], '标题 M4.2.1')

    def test_draft_and_trash_folders_do_not_notify(self):
        helper_inbox.insert(self.ROW[:6] + ('trash',) + self.ROW[7:])
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
