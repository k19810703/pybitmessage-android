"""Tests for the bounded / idempotent shutdown path (milestone M4.8.3).

Run from ``PyBitmessage/src``::

    python3 -m unittest tests.test_shutdown -v

The watchdog and ``forcedExit`` both end the process with ``os._exit``, so
these tests patch that out and assert on the decision instead of letting
the test runner die.
"""

import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shutdown  # noqa: E402
import state  # noqa: E402
import singleinstance  # noqa: E402


class _BlockingThread(threading.Thread):
    """A non-daemon thread that never stops by itself."""

    def __init__(self, stop_event):
        super(_BlockingThread, self).__init__(name='BlockingWorker',
                                              daemon=False)
        self.stop_event = stop_event
        self.started = threading.Event()

    def run(self):
        self.started.set()
        self.stop_event.wait(30)


class WatchdogTest(unittest.TestCase):

    def setUp(self):
        self.exits = []
        self._saved_exit = shutdown.os._exit
        shutdown.os._exit = lambda code: self.exits.append(code)

    def tearDown(self):
        shutdown.os._exit = self._saved_exit

    def test_watchdog_is_quiet_when_all_threads_finish(self):
        stop = threading.Event()
        worker = _BlockingThread(stop)
        worker.start()
        watchdog = shutdown.ShutdownWatchdog(grace=2.0)
        watchdog.start()
        time.sleep(0.3)
        stop.set()          # thread exits during the grace window
        worker.join(2)
        watchdog.join(3)
        self.assertEqual(self.exits, [])

    def test_watchdog_forces_exit_when_a_thread_hangs(self):
        stop = threading.Event()
        worker = _BlockingThread(stop)
        worker.start()
        self.assertTrue(worker.started.wait(2), 'worker did not start')
        watchdog = shutdown.ShutdownWatchdog(grace=0.4)
        started = time.time()
        watchdog.start()
        watchdog.join(5)
        elapsed = time.time() - started
        stop.set()
        worker.join(2)
        self.assertEqual(self.exits, [1])
        self.assertLess(elapsed, 3.0)

    def test_forced_exit_returns_true_when_thread_stopped(self):
        stop = threading.Event()
        worker = _BlockingThread(stop)
        worker.start()
        stop.set()
        self.assertTrue(shutdown.forcedExit([worker], grace=2.0))
        self.assertEqual(self.exits, [])

    def test_forced_exit_gives_up_on_a_hung_thread(self):
        stop = threading.Event()
        worker = _BlockingThread(stop)
        worker.start()
        self.assertTrue(worker.started.wait(2), 'worker did not start')
        try:
            ok = shutdown.forcedExit([worker], grace=0.3)
        finally:
            stop.set()
            worker.join(2)
        self.assertFalse(ok)
        self.assertEqual(self.exits, [1])


class CleanShutdownGuardTest(unittest.TestCase):

    def test_second_call_does_not_re_enter(self):
        saved_flag = shutdown._shutdown_started
        saved_shutdown = state.shutdown
        shutdown._shutdown_started = True
        try:
            # must return immediately instead of flushing again
            started = time.time()
            shutdown.doCleanShutdown()
            self.assertLess(time.time() - started, 1.0)
        finally:
            shutdown._shutdown_started = saved_flag
            state.shutdown = saved_shutdown


class StaleLockTest(unittest.TestCase):

    def test_unlocked_lockfile_is_removed(self):
        saved_home = os.environ.get('BITMESSAGE_HOME')
        tmp = tempfile.mkdtemp()
        try:
            os.environ['BITMESSAGE_HOME'] = tmp
            state.appdata = tmp + os.sep
            path = os.path.join(tmp, 'singleton.lock')
            with open(path, 'w') as fh:
                fh.write('99999\n')      # pid of a long-gone process
            # fresh instance construction should clean it up
            instance = singleinstance.singleinstance('', daemon=True)
            self.assertFalse(os.path.exists(path),
                             'stale lock should have been removed')
            instance.cleanup()
        finally:
            if saved_home is not None:
                os.environ['BITMESSAGE_HOME'] = saved_home
            else:
                os.environ.pop('BITMESSAGE_HOME', None)
            try:
                os.unlink(os.path.join(tmp, 'singleton.lock'))
            except OSError:
                pass
            os.rmdir(tmp)


if __name__ == '__main__':
    unittest.main()
