"""On-device diagnostic log: daily files, 3-day retention, share sheet.

Why this exists
---------------
A user who installs the APK and cannot receive messages has no adb, no logcat
and no way to tell us what happened. Until now every diagnostic in this project
was a bare ``print(...)`` -- it reached logcat and nothing else, so the phone was
a black box.

``install()`` fixes that by teeing ``sys.stdout``/``sys.stderr`` into
``<appdata>/logs/app-YYYYMMDD.log``: *every* existing ``print`` (PROBE,
BMPROTO handshake, INVTHREAD, PROCMSG, KEYSTORE, NOTIFY, KEEPALIVE ...) lands in
the file with no call-site changes. Uncaught exceptions from the main thread and
from any worker thread are appended with full tracebacks.

Retention is three days: files older than that are deleted at startup and at
rollover. A single day is capped so a stuck loop cannot fill the storage.

``share_archive()`` zips the retained logs plus a ``meta.txt`` describing the
install (version, Android release/model, address count, connection state), puts
the zip into the public Downloads collection through MediaStore and opens the
system share sheet -- that is the "send it to WeChat" button. MediaStore is used
instead of a FileProvider on purpose: it needs no ``<provider>`` in the manifest
and no extra gradle dependency, so it cannot break the build, and the copy in
Downloads is a usable fallback on its own.
"""

import datetime
import os
import platform
import sys
import threading
import zipfile

#: How many days of logs to keep (today included).
RETAIN_DAYS = 3
#: Hard cap for one day's file; writing stops and a marker is appended.
MAX_BYTES_PER_DAY = 8 * 1024 * 1024

LOG_DIRNAME = 'logs'
_log_dir = None
_current_date = None
_current_handle = None
_lock = threading.RLock()
_installed = False
_truncated_notice_written = False


def _log(message):
    """Write a line to the original stderr (logcat), never to the tee."""
    try:
        sys.__stderr__.write('APPLOG %s\n' % message)
        sys.__stderr__.flush()
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# paths and rotation
# ---------------------------------------------------------------------------

def log_dir():
    """Directory holding the daily log files."""
    global _log_dir
    if _log_dir:
        return _log_dir
    import state  # noqa: PLC0415 - needs BITMESSAGE_HOME / appdata first

    _log_dir = os.path.join(state.appdata, LOG_DIRNAME)
    if not os.path.isdir(_log_dir):
        os.makedirs(_log_dir)
    return _log_dir


def _filename(day):
    return 'app-%s.log' % day.strftime('%Y%m%d')


def _prune(today):
    """Delete logs older than RETAIN_DAYS-1 days (3 days in total)."""
    cutoff = today - datetime.timedelta(days=RETAIN_DAYS - 1)
    removed = 0
    for name in os.listdir(log_dir()):
        if not (name.startswith('app-') and name.endswith('.log')):
            continue
        try:
            day = datetime.datetime.strptime(name[4:-4], '%Y%m%d').date()
        except ValueError:
            continue
        if day < cutoff:
            try:
                os.unlink(os.path.join(log_dir(), name))
                removed += 1
            except OSError:
                pass
    return removed


def _open_for(day):
    global _current_date, _current_handle, _truncated_notice_written
    with _lock:
        if _current_handle is not None and _current_date == day:
            return _current_handle
        if _current_handle is not None:
            try:
                _current_handle.close()
            except Exception:  # noqa: BLE001
                pass
            _current_handle = None
        _prune(day)
        path = os.path.join(log_dir(), _filename(day))
        _current_handle = open(path, 'a', encoding='utf-8', errors='replace')
        _current_date = day
        _truncated_notice_written = False
        return _current_handle


def _write(text):
    """Append *text* to today's file, rolling over at midnight."""
    # NOTE: without this global the assignment below would make
    # _truncated_notice_written a *local*, the read would raise
    # UnboundLocalError, and the blanket except would silently swallow every
    # single write (found by the smoke test, not by review).
    global _truncated_notice_written
    if not text:
        return
    day = datetime.date.today()
    try:
        handle = _open_for(day)
    except Exception:  # noqa: BLE001 - logging must never break the app
        return
    with _lock:
        try:
            if (handle.tell() > MAX_BYTES_PER_DAY
                    and not _truncated_notice_written):
                handle.write(
                    '\n[APPLOG] 当天日志已达 %d MB，后续内容不再写入本文件。\n'
                    % (MAX_BYTES_PER_DAY // (1024 * 1024)))
                handle.flush()
                _truncated_notice_written = True
            if _truncated_notice_written:
                return
            handle.write(text)
            handle.flush()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# stdout/stderr tee
# ---------------------------------------------------------------------------

class _Tee(object):
    """Write to the original stream *and* to today's log file."""

    def __init__(self, stream, forward_to_file=True):
        self._stream = stream
        self._forward = forward_to_file

    def write(self, data):
        try:
            self._stream.write(data)
        except Exception:  # noqa: BLE001
            pass
        if self._forward:
            _write(data)
        return len(data)

    def flush(self):
        try:
            self._stream.flush()
        except Exception:  # noqa: BLE001
            pass
        with _lock:
            if _current_handle is not None:
                try:
                    _current_handle.flush()
                except Exception:  # noqa: BLE001
                    pass

    def isatty(self):
        return False

    def fileno(self):
        return self._stream.fileno()

    def __getattr__(self, name):
        return getattr(self._stream, name)


# ---------------------------------------------------------------------------
# exception capture
# ---------------------------------------------------------------------------

def _excepthook(exc_type, exc_value, exc_tb):
    import traceback
    text = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _write('\n[APPLOG] 未捕获异常 %s\n%s' % (
        datetime.datetime.now().isoformat(timespec='seconds'), text))
    try:
        sys.__stderr__.write(text)
    except Exception:  # noqa: BLE001
        pass


def _thread_excepthook(args):
    import traceback
    text = ''.join(traceback.format_exception(
        args.exc_type, args.exc_value, args.exc_traceback))
    _write('\n[APPLOG] 线程 %s 崩溃 %s\n%s' % (
        getattr(args.thread, 'name', '?'),
        datetime.datetime.now().isoformat(timespec='seconds'), text))
    try:
        sys.__stderr__.write('THREAD-CRASH %s: %r\n' % (
            getattr(args.thread, 'name', '?'), args.exc_value))
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

def install():
    """Start logging to file. Idempotent; never raises."""
    global _installed
    if _installed:
        return True
    try:
        log_dir()
    except Exception as exc:  # noqa: BLE001 - no writable home: skip silently
        _log('cannot create log dir: %r' % (exc,))
        return False

    _write('\n%s ===== 启动 %s =====\n'
           % ('-' * 8, datetime.datetime.now().isoformat(timespec='seconds')))
    _write(describe_install())

    if not isinstance(sys.stdout, _Tee):
        sys.stdout = _Tee(sys.stdout)
    if not isinstance(sys.stderr, _Tee):
        sys.stderr = _Tee(sys.stderr)

    sys.excepthook = _excepthook
    if hasattr(threading, 'excepthook'):
        previous = threading.excepthook

        def chained(args):
            _thread_excepthook(args)
            try:
                previous(args)
            except Exception:  # noqa: BLE001
                pass

        threading.excepthook = chained

    _installed = True
    _log('logging to %s (keep %d days)' % (log_dir(), RETAIN_DAYS))
    return True


# ---------------------------------------------------------------------------
# what to hand to a supporter
# ---------------------------------------------------------------------------

def describe_install():
    """A short block of context that makes a log actually interpretable."""
    lines = ['PyBitmessage Android 诊断信息',
             '时间: %s' % datetime.datetime.now().isoformat(timespec='seconds')]
    try:
        import version
        lines.append('软件版本: %s' % version.softwareVersion)
    except Exception:  # noqa: BLE001
        pass
    lines.append('Python: %s' % platform.python_version())
    lines.append('平台: %s %s' % (platform.system(), platform.release()))

    android = os.environ.get('ANDROID_ARGUMENT')
    lines.append('Android: %s' % ('yes' if android else 'no (desktop)'))
    if android:
        try:
            from jnius import autoclass
            Build = autoclass('android.os.Build')
            # Build.VERSION is a *nested* class: in jnius it must be spelled
            # with '$', otherwise the attribute simply does not exist.
            BuildVersion = autoclass('android.os.Build$VERSION')
            lines.append('设备: %s / %s / SDK %s' % (
                Build.MANUFACTURER, Build.MODEL, BuildVersion.SDK_INT))
            lines.append('Android 版本: %s' % BuildVersion.RELEASE)
        except Exception as exc:  # noqa: BLE001
            lines.append('设备: (读取失败 %r)' % (exc,))
    try:
        import state
        lines.append('数据目录: %s' % state.appdata)
    except Exception:  # noqa: BLE001
        pass
    try:
        from bmconfigparser import config
        addresses = config.addresses()
        lines.append('地址数量: %d' % len(addresses))
        for addr in addresses[:4]:
            lines.append('  %s (label=%s)' % (
                addr, config.safeGet(addr, 'label', '')))
    except Exception:  # noqa: BLE001
        pass
    try:
        from network import stats
        pool = getattr(stats, 'pool', None)
        if pool is not None:
            lines.append('连接: established=%d outbound=%d inbound=%d' % (
                len(pool.establishedConnections()),
                len(pool.outboundConnections),
                len(pool.inboundConnections)))
    except Exception:  # noqa: BLE001
        pass
    try:
        import state
        lines.append('已处理对象: %s' % state.numberOfMessagesProcessed)
    except Exception:  # noqa: BLE001
        pass
    return '\n'.join(lines) + '\n'


def log_files():
    """The log files that are currently retained, newest first."""
    try:
        names = [n for n in os.listdir(log_dir())
                 if n.startswith('app-') and n.endswith('.log')]
    except Exception:  # noqa: BLE001
        return []
    names.sort(reverse=True)
    return [os.path.join(log_dir(), n) for n in names]


def recent_text(max_lines=400, max_chars=60000):
    """Tail of today's log, for the clipboard fallback."""
    files = log_files()
    if not files:
        return '（还没有日志）'
    try:
        with open(files[0], encoding='utf-8', errors='replace') as handle:
            lines = handle.readlines()[-max_lines:]
    except OSError as exc:
        return '（读取日志失败：%r）' % (exc,)
    text = ''.join(lines)
    if len(text) > max_chars:
        text = text[-max_chars:]
    return text


def build_archive(dest_dir=None):
    """Zip the retained logs plus ``meta.txt``; return the archive path."""
    import state  # noqa: PLC0415

    if dest_dir is None:
        dest_dir = os.path.join(state.appdata, 'cache')
        if not os.path.isdir(dest_dir):
            os.makedirs(dest_dir)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    path = os.path.join(dest_dir, 'pybitmessage-logs-%s.zip' % stamp)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('meta.txt', describe_install())
        for log_path in log_files():
            archive.write(log_path, os.path.basename(log_path))
        # the last moments matter most; make them easy to read first
        archive.writestr('tail-400.txt', recent_text())
    return path


# ---------------------------------------------------------------------------
# sharing
# ---------------------------------------------------------------------------

def _android_context():
    if os.environ.get('ANDROID_ARGUMENT') is None:
        return None, None
    try:
        from jnius import autoclass, cast
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        activity = PythonActivity.mActivity
        if activity is None:
            return None, None
        return activity, cast(Context, activity)
    except Exception as exc:  # noqa: BLE001
        _log('no android context: %r' % (exc,))
        return None, None


def _publish_to_downloads(context, path, display_name, mime='application/zip'):
    """Copy *path* into the public Downloads collection; return its Uri.

    MediaStore needs no FileProvider and no androidx dependency, so this cannot
    break the APK build and it also leaves the user a copy they can find in
    Files/Downloads if the share sheet is unavailable.
    """
    from jnius import autoclass

    Build = autoclass('android.os.Build$VERSION')
    if Build.SDK_INT < 29:
        return None

    MediaStore = autoclass('android.provider.MediaStore')
    Downloads = autoclass('android.provider.MediaStore$Downloads')
    # nested classes need '$' in jnius (MediaStore$MediaColumns), otherwise
    # MediaStore.MediaColumns raises AttributeError at runtime -- exactly the
    # Android side of the "works on desktop, fails on device" trap.
    Columns = autoclass('android.provider.MediaStore$MediaColumns')
    ContentValues = autoclass('android.content.ContentValues')

    try:
        collection = Downloads.EXTERNAL_CONTENT_URI
    except AttributeError:
        collection = MediaStore.EXTERNAL_CONTENT_URI

    resolver = context.getContentResolver()
    # Only String values go into ContentValues. IS_PENDING would need a
    # java.lang.Integer/Boolean object: handing jnius a Python int makes the
    # overload resolver pick the wrong signature and raise
    # "No methods called put ... matching your arguments". The publish window
    # without IS_PENDING is milliseconds and a half-written log zip is
    # harmless, so it is not worth the extra failure mode.
    values = ContentValues()
    values.put(Columns.DISPLAY_NAME, display_name)
    values.put(Columns.MIME_TYPE, mime)
    values.put(Columns.RELATIVE_PATH, 'Download/PyBitmessage')
    uri = resolver.insert(collection, values)
    if uri is None:
        return None
    stream = resolver.openOutputStream(uri)
    try:
        with open(path, 'rb') as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                stream.write(bytearray(chunk))
    finally:
        try:
            stream.close()
        except Exception:  # noqa: BLE001
            pass
    return uri


def share_archive():
    """Build the zip and open the system share sheet.

    Returns ``(ok, message)``; *message* is shown to the user.
    """
    activity, context = _android_context()
    if context is None:
        return False, '仅安卓设备支持分享'

    try:
        archive_path = build_archive()
    except Exception as exc:  # noqa: BLE001
        _log('build archive failed: %r' % (exc,))
        return False, '打包日志失败：%r' % (exc,)

    display_name = os.path.basename(archive_path)
    try:
        from jnius import autoclass, cast
        Intent = autoclass('android.content.Intent')
        Parcelable = autoclass('android.os.Parcelable')

        uri = _publish_to_downloads(context, archive_path, display_name)
        intent = Intent(Intent.ACTION_SEND)
        if uri is not None:
            intent.setType(mime_type())
            # putExtra(String, ...) is overloaded; without the cast jnius picks
            # the String variant and raises TypeError("Invalid instance of
            # 'android/net/Uri' passed for a 'java/lang/String'").
            intent.putExtra(Intent.EXTRA_STREAM, cast(Parcelable, uri))
            intent.putExtra(
                Intent.EXTRA_SUBJECT,
                _java_string('PyBitmessage 诊断日志 ' + display_name))
        else:
            # API 28 and below: no MediaStore.Downloads, share the tail text
            intent.setType('text/plain')
            intent.putExtra(
                Intent.EXTRA_TEXT,
                _java_string(recent_text(max_lines=300)))
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        chooser = Intent.createChooser(
            intent, _java_string('分享诊断日志'))
        activity.startActivity(chooser)
        if uri is not None:
            return True, '日志已导出到 Download/PyBitmessage 并打开分享'
        return True, '已打开分享（纯文本，含最近 300 行）'
    except Exception as exc:  # noqa: BLE001
        _log('share failed: %r' % (exc,))
        return False, '打开分享失败：%r（日志在 %s）' % (exc, archive_path)


def _java_string(text):
    from jnius import autoclass
    return autoclass('java.lang.String')(text)


def mime_type():
    return 'application/zip'


def copy_recent_to_clipboard():
    """Last-resort export: put the log tail on the clipboard."""
    try:
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(recent_text())
        return True, '最近 400 行已复制到剪贴板'
    except Exception as exc:  # noqa: BLE001
        return False, '复制失败：%r' % (exc,)


def reset_for_tests():  # pragma: no cover - helper for the test suite
    global _installed, _log_dir, _current_date, _current_handle
    global _truncated_notice_written
    # Put the real streams back. Without this the tee survives into the next
    # test and writes into whatever state.appdata happens to be then, leaving
    # a surprise logs/ directory behind (it made an unrelated test fail).
    if isinstance(sys.stdout, _Tee):
        sys.stdout = sys.stdout._stream
    if isinstance(sys.stderr, _Tee):
        sys.stderr = sys.stderr._stream
    with _lock:
        if _current_handle is not None:
            try:
                _current_handle.close()
            except Exception:  # noqa: BLE001
                pass
        _current_handle = None
        _current_date = None
        _log_dir = None
        _installed = False
        _truncated_notice_written = False
