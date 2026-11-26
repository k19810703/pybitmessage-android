"""Contract tests for the message list helpers (``mail_list.load_folder``).

Run from ``PyBitmessage/src``::

    python3 -m unittest tests.test_mail_list -v

These exist because adding ``msgid`` to the row dicts is easy to break in two
directions: the SQL must select it, and every consumer of ``messaging.inbox()``
must unpack the extra element. The second one did break once (``inbox.py``
still unpacked a 4-tuple and would have raised ValueError on opening the
folder), so the shape is pinned here.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:                       # these modules build Kivy widgets at import time
    import kivy            # noqa: F401
    HAVE_KIVY = True
except Exception:          # noqa: BLE001 - a plain desktop without Kivy
    HAVE_KIVY = False

WHY = 'Kivy 未安装：这些断言只在带 Kivy 的环境（设备/桌面 Kivy）里跑'


@unittest.skipUnless(HAVE_KIVY, WHY)
class LoadFolderTest(unittest.TestCase):

    def setUp(self):
        from pybitmessage.bitmessagekivy.baseclass import mail_list
        self.mail_list = mail_list
        self.original = mail_list.sqlQuery
        self.queries = []

    def tearDown(self):
        self.mail_list.sqlQuery = self.original

    def _stub(self, rows):
        def fake(sql, *args):
            self.queries.append(sql)
            return rows
        self.mail_list.sqlQuery = fake

    def test_rows_carry_msgid_and_table(self):
        self._stub([('to@x', 'from@x', 'subj', 'body', 111, 'msgsent',
                     b'\x01\x02\x03')])
        rows = self.mail_list.load_folder('sent')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIn('msgid', row, '删除需要 msgid')
        self.assertEqual(row['msgid'], b'\x01\x02\x03')
        self.assertEqual(row['table'], 'sent')
        self.assertTrue(
            any('msgid' in sql for sql in self.queries),
            'SELECT 必须带上 msgid')

    def test_trash_reads_both_tables(self):
        self._stub([])
        self.mail_list.load_folder('trash')
        tables = ' '.join(self.queries)
        self.assertIn('FROM sent', tables)
        self.assertIn('FROM inbox', tables)

    def test_unknown_folder_is_not_an_error(self):
        self._stub([])
        self.assertEqual(self.mail_list.load_folder('nope'), [])

    def test_query_failure_is_survivable(self):
        def boom(sql, *args):
            raise RuntimeError('database is locked')
        self.mail_list.sqlQuery = boom
        self.assertEqual(self.mail_list.load_folder('inbox'), [])


@unittest.skipUnless(HAVE_KIVY, WHY)
class InboxShapeTest(unittest.TestCase):
    """``messaging.inbox()`` returns 5-tuples; consumers must agree."""

    def test_inbox_selects_msgid(self):
        from pybitmessage.bitmessagekivy import messaging
        original = messaging.sqlQuery
        seen = []

        def fake(sql, *args):
            seen.append(sql)
            return [('from@x', 'subj', 'body', 123, b'\x09\x08')]

        messaging.sqlQuery = fake
        try:
            rows = messaging.inbox()
        finally:
            messaging.sqlQuery = original

        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]), 5, 'from/subject/body/received/msgid')
        self.assertEqual(rows[0][4], b'\x09\x08')
        self.assertIn('msgid', seen[0])
        self.assertIn("folder='inbox'", seen[0],
                      '回收站里的消息不能再出现在收件箱')


if __name__ == '__main__':
    unittest.main()
