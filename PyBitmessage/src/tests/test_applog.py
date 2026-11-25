"""Tests for the diagnostic log (``src/applog.py``).

Run from ``PyBitmessage/src``::

    python3 -m unittest tests.test_applog -v

These cover the parts that are pure Python: the stdout tee, daily filenames and
3-day retention, the per-day size cap, the archive contents, and the tail used
by the clipboard fallback. The Android share sheet (MediaStore + chooser) needs
a device and is verified there instead.

One of these tests exists because review missed a real bug: ``_write`` assigned
to a module global without declaring it, which made the name local, raised
``UnboundLocalError`` on the first read and -- because the write is wrapped in
``except: pass`` -- silently dropped every log line.
"""

import datetime
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_HOME = tempfile.mkdtemp(prefix='applog-test-')


def setUpModule():  # noqa: N802 - unittest hook name
    os.environ['BITMESSAGE_HOME'] = _HOME
    import state
    state.appdata = _HOME + os.sep


def tearDownModule():  # noqa: N802 - unittest hook name
    shutil.rmtree(_HOME, ignore_errors=True)


class _Fresh(object):
    """Reset applog's module state between tests."""

    def setUp(self):
        import applog
        self.applog = applog
        applog.reset_for_tests()
        shutil.rmtree(os.path.join(_HOME, 'logs'), ignore_errors=True)
        shutil.rmtree(os.path.join(_HOME, 'cache'), ignore_errors=True)

    def tearDown(self):
        self.applog.reset_for_tests()


class TeeTest(_Fresh, unittest.TestCase):

    def test_print_reaches_the_file(self):
        self.assertTrue(self.applog.install())
        print('单元测试标记 42')
        files = self.applog.log_files()
        self.assertTrue(files, '当天日志文件应存在')
        with open(files[0], encoding='utf-8') as handle:
            text = handle.read()
        self.assertIn('单元测试标记 42', text)
        self.assertIn('PyBitmessage Android 诊断信息', text)

    def test_install_is_idempotent(self):
        self.assertTrue(self.applog.install())
        stdout_after_first = sys.stdout
        self.assertTrue(self.applog.install())
        self.assertIs(sys.stdout, stdout_after_first,
                      '重复 install 不能把 stdout 套第二层')

    def test_filename_is_daily(self):
        self.applog.install()
        today = datetime.date.today().strftime('%Y%m%d')
        names = [os.path.basename(p) for p in self.applog.log_files()]
        self.assertIn('app-%s.log' % today, names)


class RetentionTest(_Fresh, unittest.TestCase):

    def _touch(self, days_ago):
        day = datetime.date.today() - datetime.timedelta(days=days_ago)
        path = os.path.join(self.applog.log_dir(),
                            'app-%s.log' % day.strftime('%Y%m%d'))
        with open(path, 'w') as handle:
            handle.write('old\n')
        return path

    def test_only_three_days_are_kept(self):
        kept0 = self._touch(0)
        kept1 = self._touch(1)
        kept2 = self._touch(2)
        gone3 = self._touch(3)
        gone9 = self._touch(9)

        self.applog.install()   # install prunes on the first write

        self.assertTrue(os.path.exists(kept0))
        self.assertTrue(os.path.exists(kept1))
        self.assertTrue(os.path.exists(kept2))
        self.assertFalse(os.path.exists(gone3), '第 4 天应被清理')
        self.assertFalse(os.path.exists(gone9))

    def test_unrelated_files_are_untouched(self):
        other = os.path.join(self.applog.log_dir(), 'notes.txt')
        with open(other, 'w') as handle:
            handle.write('keep me\n')
        self._touch(9)
        self.applog.install()
        self.assertTrue(os.path.exists(other))


class SizeCapTest(_Fresh, unittest.TestCase):

    def test_writes_stop_at_the_cap(self):
        import applog
        saved = applog.MAX_BYTES_PER_DAY
        applog.MAX_BYTES_PER_DAY = 200
        try:
            applog.install()
            for _ in range(50):
                applog._write('x' * 40 + '\n')
            files = applog.log_files()
            size = os.path.getsize(files[0])
            self.assertLess(size, 2000, '超过上限后应停止写入（留下提示行）')
            with open(files[0], encoding='utf-8') as handle:
                text = handle.read()
            self.assertIn('不再写入本文件', text)
        finally:
            applog.MAX_BYTES_PER_DAY = saved


class ArchiveTest(_Fresh, unittest.TestCase):

    def test_archive_contains_meta_logs_and_tail(self):
        self.applog.install()
        print('归档测试内容')
        path = self.applog.build_archive()

        self.assertTrue(os.path.exists(path))
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            self.assertIn('meta.txt', names)
            self.assertIn('tail-400.txt', names)
            self.assertTrue(any(n.startswith('app-') for n in names))
            meta = archive.read('meta.txt').decode('utf-8')
            self.assertIn('诊断信息', meta)
            tail = archive.read('tail-400.txt').decode('utf-8')
            self.assertIn('归档测试内容', tail)

    def test_recent_text_handles_no_logs(self):
        self.assertEqual(self.applog.recent_text(), '（还没有日志）')


class OffDeviceShareTest(_Fresh, unittest.TestCase):

    def test_share_reports_it_needs_android(self):
        saved = os.environ.pop('ANDROID_ARGUMENT', None)
        try:
            ok, message = self.applog.share_archive()
        finally:
            if saved is not None:
                os.environ['ANDROID_ARGUMENT'] = saved
        self.assertFalse(ok)
        self.assertIn('安卓', message)


if __name__ == '__main__':
    unittest.main()
