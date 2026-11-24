"""
This is based upon the singleton class from
`tendo <https://github.com/pycontribs/tendo>`_
which is under the Python Software Foundation License version 2
"""

import atexit
import os
import sys

import state

try:
    import fcntl  # @UnresolvedImport
except ImportError:
    pass


class singleinstance(object):
    """
    Implements a single instance application by creating a lock file
    at appdata.
    """
    def __init__(self, flavor_id="", daemon=False):
        self.initialized = False
        self.counter = 0
        self.daemon = daemon
        self.lockPid = None
        self.lockfile = os.path.normpath(
            os.path.join(state.appdata, 'singleton%s.lock' % flavor_id))

        if (state.enableGUI and not self.daemon and not state.curses
                and not state.kivy):
            # Tells the already running (if any) application to get focus.
            import bitmessageqt
            bitmessageqt.init()

        try:
            self.lock()
        except SystemExit:
            # Genuine "another instance is already running" -- keep it fatal.
            raise
        except Exception as exc:  # noqa: BLE001 - never block startup
            # Android can have odd filesystems where flock() is unavailable;
            # the OS already guarantees one process per app, so degrade to a
            # warning instead of refusing to start.
            print('WARNING: single instance lock unavailable: %s' % exc)

        # M4.8.3: drop a leftover lock from a killed instance. flock() is
        # released by the OS, so the file only misleads people reading the
        # data directory; removing it keeps "is a node running?" honest.
        self._remove_stale_lockfile()

        self.initialized = True
        atexit.register(self.cleanup)

    def _remove_stale_lockfile(self):
        """Delete the lock file if it is not held by any live process."""
        try:
            if sys.platform == 'win32':
                return  # the Windows path relies on O_EXCL
            with open(self.lockfile, 'a+') as fp:
                # lockf() needs a file opened for writing; a read-only
                # handle raises EBADF, which must NOT be read as "held".
                try:
                    fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (IOError, OSError):
                    return  # a live instance holds it
                finally:
                    try:
                        fcntl.lockf(fp, fcntl.LOCK_UN)
                    except (IOError, OSError):
                        pass
            os.unlink(self.lockfile)
            print('Removed stale single instance lock %s' % self.lockfile)
        except (IOError, OSError, NameError):
            # Either another instance holds it (normal) or the file does
            # not exist yet (first start).
            pass

    def lock(self):
        """Obtain single instance lock"""
        if self.lockPid is None:
            self.lockPid = os.getpid()
        if sys.platform == 'win32':
            try:
                # file already exists, we try to remove
                # (in case previous execution was interrupted)
                if os.path.exists(self.lockfile):
                    os.unlink(self.lockfile)
                self.fd = os.open(
                    self.lockfile,
                    os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_TRUNC
                )
            except OSError as e:
                if e.errno == 13:
                    sys.exit(
                        'Another instance of this application is'
                        ' already running')
                raise
            else:
                pidLine = "%i\n" % self.lockPid
                os.write(self.fd, pidLine)
        else:  # non Windows
            self.fp = open(self.lockfile, 'a+')
            try:
                if self.daemon and self.lockPid != os.getpid():
                    # wait for parent to finish
                    fcntl.lockf(self.fp, fcntl.LOCK_EX)
                else:
                    fcntl.lockf(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.lockPid = os.getpid()
            except IOError:
                sys.exit(
                    'Another instance of this application is'
                    ' already running')
            else:
                pidLine = "%i\n" % self.lockPid
                self.fp.truncate(0)
                self.fp.write(pidLine)
                self.fp.flush()

    def cleanup(self):
        """Release single instance lock"""
        if not self.initialized:
            return
        if self.daemon and self.lockPid == os.getpid():
            # these are the two initial forks while daemonizing
            try:
                if sys.platform == 'win32':
                    if hasattr(self, 'fd'):
                        os.close(self.fd)
                else:
                    fcntl.lockf(self.fp, fcntl.LOCK_UN)
            except (IOError, OSError):
                pass

            return

        try:
            if sys.platform == 'win32':
                if hasattr(self, 'fd'):
                    os.close(self.fd)
                    os.unlink(self.lockfile)
            else:
                fcntl.lockf(self.fp, fcntl.LOCK_UN)
                if os.path.isfile(self.lockfile):
                    os.unlink(self.lockfile)
        except (IOError, OSError):
            pass
