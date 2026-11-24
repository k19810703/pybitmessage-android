"""shutdown function"""

import os
import sys
import threading
import time

from six.moves import queue

import state
from debug import logger
from helper_sql import sqlQuery, sqlStoredProcedure
from network import StoppableThread
from network.knownnodes import saveKnownNodes
from queues import (
    addressGeneratorQueue, objectProcessorQueue, UISignalQueue, workerQueue)


#: How long a clean shutdown may take before it is forced (M4.8.3). The
#: graceful path normally finishes in well under a second; the budget is
#: generous because a slow disk (or an Android device waking up) may need to
#: commit the inventory and the database first.
SHUTDOWN_GRACE_SECONDS = 10.0
_shutdown_started = False


def removeLeftoverLock():
    """Delete a singleton lock file that the OS says is not held (M4.8.3).

    On POSIX the lock is an ``flock()``, so a file left behind by a killed
    process does not block a new instance. It used to be harmless -- and it
    is worth deleting anyway, because a stale file whose pid was reused by
    another process reads like "another instance is running" to anybody
    (human or script) inspecting the data directory afterwards.
    """
    path = os.path.join(state.appdata, 'singleton.lock')
    try:
        if os.path.exists(path):
            os.unlink(path)
            logger.debug('Removed stale singleton lock %s', path)
    except OSError as exc:
        logger.debug('Could not remove %s: %s', path, exc)


def _shutdown_threads():
    """Threads that keep the process alive; everything else may stay."""
    for thread in threading.enumerate():
        if not thread.is_alive() or thread is threading.main_thread():
            continue
        if thread.daemon is False:
            yield thread


class ShutdownWatchdog(threading.Thread):
    """Force the process down if doCleanShutdown() does not finish in time.

    Set the budget before calling doCleanShutdown() (tests patch the module
    constant and re-read it here).
    """

    def __init__(self, grace=None):
        super(ShutdownWatchdog, self).__init__(name='ShutdownWatchdog')
        self.daemon = True
        self.grace = SHUTDOWN_GRACE_SECONDS if grace is None else grace

    def run(self):
        deadline = time.time() + self.grace
        while time.time() < deadline:
            if not any(True for _ in _shutdown_threads()):
                return  # everything joined in time: nothing to force
            time.sleep(0.1)
        stuck = ', '.join(t.name for t in _shutdown_threads())
        print('SHUTDOWN TIMEOUT after %ss; threads still alive: %s'
              % (self.grace, stuck), flush=True)
        logger.error(
            'Clean shutdown did not finish in %ss (threads: %s); forcing'
            ' exit. Data written so far is kept; inventory flush may be'
            ' incomplete.', self.grace, stuck)
        try:
            saveKnownNodes()
        except Exception as exc:  # noqa: BLE001 - best effort on the way out
            logger.error('Could not save knownnodes during forced exit: %s',
                         exc)
        try:
            state.thisapp.cleanup()
        except Exception:  # noqa: BLE001
            pass
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)


def forcedExit(threads, grace=None):
    """Wait *grace* seconds for *threads*, then leave regardless (M4.8.3).

    ``thread.join()`` without a timeout is what made the Windows/curses
    shutdown path hang: one thread blocked in a socket read is enough.
    Returns False (and exits) when a thread overstayed.
    """
    if grace is None:
        grace = SHUTDOWN_GRACE_SECONDS
    deadline = time.time() + grace
    for thread in threads:
        if thread is threading.current_thread():
            continue
        remaining = max(0.0, deadline - time.time())
        if thread.is_alive():
            logger.debug('Waiting up to %.1fs for thread %s',
                         remaining, thread.name)
            thread.join(remaining)
        # A thread that finished its work but has not been reaped yet is
        # still "alive" for a moment; re-check it against the deadline.
        if thread.is_alive() and time.time() >= deadline:
            print('SHUTDOWN TIMEOUT: thread %s still alive after %ss; '
                  'exiting anyway' % (thread.name, grace), flush=True)
            logger.error(
                'Thread %s did not stop within %ss; forcing exit.',
                thread.name, grace)
            try:
                saveKnownNodes()
            except Exception:  # noqa: BLE001
                pass
            try:
                state.thisapp.cleanup()
            except Exception:  # noqa: BLE001
                pass
            os._exit(1)
    return bool(threads) and not any(t.is_alive() for t in threads)


def doCleanShutdown():
    """
    Used to tell all the treads to finish work and exit.
    """
    global _shutdown_started
    if _shutdown_started:
        # A second signal (users press Ctrl-C twice, init sends TERM + KILL)
        # must not re-enter the flush while threads are half torn down.
        logger.info('Clean shutdown already in progress; ignoring')
        return
    _shutdown_started = True
    state.shutdown = 1

    objectProcessorQueue.put(('checkShutdownVariable', 'no data'))
    for thread in threading.enumerate():
        if thread.is_alive() and isinstance(thread, StoppableThread):
            thread.stopThread()

    UISignalQueue.put((
        'updateStatusBar',
        'Saving the knownNodes list of peers to disk...'))
    logger.info('Saving knownNodes list of peers to disk')
    saveKnownNodes()
    logger.info('Done saving knownNodes list of peers to disk')
    UISignalQueue.put((
        'updateStatusBar',
        'Done saving the knownNodes list of peers to disk.'))
    logger.info('Flushing inventory in memory out to disk...')
    UISignalQueue.put((
        'updateStatusBar',
        'Flushing inventory in memory out to disk.'
        ' This should normally only take a second...'))
    state.Inventory.flush()

    # Verify that the objectProcessor has finished exiting. It should have
    # incremented the shutdown variable from 1 to 2. This must finish before
    # we command the sqlThread to exit.
    while state.shutdown == 1:
        time.sleep(.1)

    # Wait long enough to guarantee that any running proof of work worker
    # threads will check the shutdown variable and exit. If the main thread
    # closes before they do then they won't stop.
    time.sleep(.25)

    for thread in threading.enumerate():
        if (
                thread is not threading.currentThread()
                and isinstance(thread, StoppableThread)
                and thread.name != 'SQL'
        ):
            logger.debug("Waiting for thread %s", thread.name)
            # M4.8.3: never join() without a timeout -- one thread blocked in
            # a socket read was enough to hang the whole shutdown.
            forcedExit([thread])

    # This one last useless query will guarantee that the previous flush
    # committed and that the
    # objectProcessorThread committed before we close the program.
    sqlQuery('SELECT address FROM subscriptions')
    logger.info('Finished flushing inventory.')
    sqlStoredProcedure('exit')

    # flush queues
    for q in (
            workerQueue, UISignalQueue, addressGeneratorQueue,
            objectProcessorQueue):
        while True:
            try:
                q.get(False)
                q.task_done()
            except queue.Empty:
                break

    if state.thisapp.daemon or not state.enableGUI:
        logger.info('Clean shutdown complete.')
        state.thisapp.cleanup()
        os._exit(0)  # pylint: disable=protected-access
    else:
        logger.info('Core shutdown complete.')
    for thread in threading.enumerate():
        logger.debug('Thread %s still running', thread.name)
