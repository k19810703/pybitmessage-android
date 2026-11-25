"""Android entry point: start the real PyBitmessage core with the Kivy UI.

This replaces the old mock entry point (kept as ``main_mock.py`` for the Kivy
UI tests). Ordering matters:

1. ``envprobe`` runs first so the ``PROBE`` lines are the first thing in
   logcat (milestone M2.1.1);
2. ``BITMESSAGE_HOME`` is pointed at Android app storage **before** importing
   anything that pulls in :mod:`debug` -- ``debug`` calls
   ``helper_startup.loadConfig()`` at import time, and without a writable home
   the config lookup would fail (milestone M2.4.1);
3. only then the core is imported and started with ``state.kivy = True`` so
   ``bitmessagemain`` skips the PyQt requirement and dispatches to Kivy
   (milestone M2.3).
"""

import os
import threading
import traceback

from envprobe import run as probe_environment  # noqa: E402


def _install_thread_excepthook():
    """Make daemon-thread crashes visible in logcat.

    Python kills a thread on an unhandled exception and only prints a one-line
    'Exception in thread ...' to stderr; several of those lines were missed
    while debugging, so route them through an explicit hook.
    """
    def hook(args):
        name = getattr(args.thread, 'name', '?')
        print('THREAD-CRASH %s: %r' % (name, args.exc_value), flush=True)
        traceback.print_exception(
            args.exc_type, args.exc_value, args.exc_traceback)

    threading.excepthook = hook


_install_thread_excepthook()



def prepare_home():
    """Point BITMESSAGE_HOME at a writable app-private directory."""
    if os.environ.get('BITMESSAGE_HOME'):
        return os.environ['BITMESSAGE_HOME']

    try:
        # python-for-android helper; absent on the desktop
        from android.storage import app_storage_path
        base = app_storage_path()
    except Exception:  # noqa: BLE001 - desktop run, or very old p4a
        base = os.path.dirname(os.path.abspath(__file__))

    target = os.path.join(base, 'bitmessage')
    try:
        if not os.path.isdir(target):
            os.makedirs(target)
    except OSError:
        target = base
    os.environ['BITMESSAGE_HOME'] = target
    print('BITMESSAGE_HOME=%s' % target)
    return target


CORE_MODULES = (
    'state', 'bmconfigparser', 'helper_sql', 'helper_startup', 'defaults',
    'queues', 'shared', 'addresses', 'protocol', 'inventory', 'debug',
    'l10n', 'network', 'storage', 'singleinstance', 'shutdown',
)


def alias_core_modules():
    """Bind the flattened ``pybitmessage.*`` names to the real modules.

    The APK ships a copy of every top-level ``*.py`` inside ``pybitmessage/``
    (buildozer needs that layout for the Kivy imports), which would otherwise
    give the UI a *second* ``state``/``config`` instance. Aliasing keeps one
    object per module, so things like ``networkConnections`` are shared.
    """
    import importlib
    import sys

    try:
        package = importlib.import_module('pybitmessage')
    except ImportError:
        return
    for name in CORE_MODULES:
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        sys.modules['pybitmessage.' + name] = module
        setattr(package, name, module)
    import state as _state
    print('ALIAS pybitmessage.state is state: %s' % (
        sys.modules.get('pybitmessage.state') is _state), flush=True)


SERVICE_ENTRYPOINT = 'core_service.py'
# p4a derives the Java class from buildozer's ``services = name:entry``:
# "pybitmessagesvc" becomes "<package>.ServicePybitmessagesvc" (verified with
# aapt2 on the built APK). Using org.kivy.android.PythonService instead makes
# ActivityManager fail with "Unable to start service Intent ... not found".
SERVICE_CLASS = 'at.bitmessage.pybitmessage.ServicePybitmessagesvc'


def start_keepalive_service():
    """Start the foreground service that keeps the node alive (M4.1e).

    python-for-android *declares* the service in AndroidManifest.xml from
    ``services =`` in buildozer.spec, but nothing ever starts it -- that is
    why M4.1d found no ``:service_pybitmessagesvc`` process on the device.

    We start it from here, after BITMESSAGE_HOME is set, so the service
    process inherits the same environment. It runs ``core_service.py``,
    which only keeps the process up and posts a notification; the
    Bitmessage core stays in this (UI) process on purpose -- two processes
    running the core would fight over the single-instance lock and the
    same data files.
    """
    if os.environ.get('ANDROID_ARGUMENT') is None:
        return  # desktop run

    try:
        from jnius import autoclass, cast

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        Context = autoclass('android.content.Context')
        Build = autoclass('android.os.Build$VERSION')
        ServiceClass = autoclass(SERVICE_CLASS)

        activity = PythonActivity.mActivity
        if activity is None:
            print('SERVICE start skipped: no activity', flush=True)
            return
        context = cast(Context, activity)
        # p4a unpacks the python bundle into <files>/app
        app_root = context.getFilesDir().getPath() + '/app'

        intent = Intent(context, ServiceClass)
        # jnius resolves putExtra() overloads by Python type; a plain str may
        # bind to putExtra(String, CharSequence) instead of (String, String),
        # and Bundle.getString() then returns null. Wrapping in a real
        # java.lang.String makes the (String, String) overload win.
        JavaString = autoclass('java.lang.String')

        def put(key, value):
            intent.putExtra(JavaString(key), JavaString(value))

        put('serviceEntrypoint', SERVICE_ENTRYPOINT)
        put('androidPrivate', context.getFilesDir().getPath())
        # PythonService.run() -> nativeStart(files, argument, entrypoint,
        # name, home, path, serviceArgument) calls GetStringUTFChars() on
        # every one of them; a single null aborts the process with
        # "JNI DETECTED ERROR ... GetStringUTFChars received NULL jstring".
        # So pass the same environment the UI process uses.
        put('androidArgument', os.environ.get('ANDROID_ARGUMENT', ''))
        put('pythonName', os.environ.get('PYTHON_NAME', 'python'))
        put('pythonHome', os.environ.get('PYTHONHOME', '') or str(app_root))
        put('pythonPath', os.environ.get('PYTHONPATH', '') or str(app_root))
        # PythonService.onStartCommand() (p4a v2024.01.21, lines 75-84) also
        # calls .equals() on some of these, so a missing key throws
        #   NullPointerException: String.equals(...) on a null object
        # at PythonService.java:82. serviceStartAsForeground must literally
        # be "true" for doStartForeground() to run.
        put('serviceStartAsForeground', 'true')
        put('serviceTitle', 'PyBitmessage')
        put('smallIconName', '')
        put('contentTitle', 'PyBitmessage')
        put('contentText', '正在运行')
        put('pythonServiceArgument', '')

        if Build.SDK_INT >= 26:
            context.startForegroundService(intent)
        else:
            context.startService(intent)
        print('SERVICE startForegroundService(%s -> %s) issued, API %d' % (
            SERVICE_CLASS, SERVICE_ENTRYPOINT, Build.SDK_INT), flush=True)
    except Exception as exc:  # noqa: BLE001 - never block startup
        print('SERVICE start failed: %r' % (exc,), flush=True)


def schedule_android_keepalive(delay=8.0):
    """Set up wake lock + start the keep-alive service, shortly after the UI.

    Two constraints learned the hard way on the device:

    * Running this inline before ``bitmessagemain.main()`` crashed the app
      with "JNI DETECTED ERROR ... jclass is an invalid JNI transition frame
      reference ... from SDLActivity.nativeRunMain" -- the service process
      was forked while the main process was still initialising SDL.
    * Running it in a worker *thread* then failed differently: autoclass()
      could not resolve our service class ("ClassNotFoundException") because
      the thread had no valid JNI class loader.

    So: schedule through Kivy's Clock, which fires on the main thread once
    the event loop is running. Everything is best-effort and logged.
    """
    if os.environ.get('ANDROID_ARGUMENT') is None:
        return

    def _setup(_dt):
        # M4.2.1: ask for POST_NOTIFICATIONS (API 33+) before anything is
        # posted; without it both this and the new-message note are silent
        # no-ops. The hook turns inbox signals into notifications.
        try:
            import android_notify
            android_notify.request_permission_once()
            android_notify.ensure_channel()
            android_notify.install_message_hook()
        except Exception as exc:  # noqa: BLE001
            print('NOTIFY setup failed: %r' % (exc,), flush=True)
        try:
            import android_keepalive
            if android_keepalive.install():
                print('KEEPALIVE active: %s' % android_keepalive.status(),
                      flush=True)
            else:
                print('KEEPALIVE: not active', flush=True)
        except Exception as exc:  # noqa: BLE001
            print('KEEPALIVE setup failed: %r' % (exc,), flush=True)
        try:
            start_keepalive_service()
        except Exception as exc:  # noqa: BLE001
            print('SERVICE delayed start failed: %r' % (exc,), flush=True)

    try:
        from kivy.clock import Clock
        Clock.schedule_once(_setup, delay)
        print('KEEPALIVE scheduled in %ss (main thread)' % delay, flush=True)
    except Exception as exc:  # noqa: BLE001 - no Kivy: try once inline
        print('KEEPALIVE: Clock unavailable (%r), running inline'
              % (exc,), flush=True)
        _setup(0)


def main():
    """Start the core with the Kivy user interface."""
    prepare_home()

    import logging

    import state
    import bitmessagemain

    # Diagnostic log file (3-day retention) *before* anything interesting
    # happens: from here on every print() -- PROBE matrix, handshake, inv,
    # decrypt, notifications -- also lands in a file the user can share.
    try:
        import applog
        applog.install()
    except Exception as exc:  # noqa: BLE001 - never block startup
        print('APPLOG install failed: %r' % (exc,), flush=True)

    # Runs now (not at import time) so the PROBE lines are captured in the log
    # file above; they are the first thing a supporter needs to see.
    probe_environment()

    # Diagnostic switch; must run after debug.py configured logging.
    if os.environ.get('BITMESSAGE_LOG_DEBUG'):
        logging.getLogger('default').setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)

    state.kivy = True
    # The APK does not ship src/sslkeys (the shared self-signed node certs are
    # excluded from the repo), so a TLS handshake with peers that advertise
    # NODE_SSL would fail before the connection is ever marked established.
    # Plaintext peer links are allowed by the protocol; messages stay E2E
    # encrypted. Re-enable once the certs are generated at build time.
    # Allow the TLS upgrade: public peers may drop plaintext links.
    state.disable_tls = os.environ.get('BITMESSAGE_DISABLE_TLS') == '1'

    # The C PoW library (libbitmsghash.so) makes protocol-default difficulty
    # fast enough (~4s per object), so do not lower it: public peers clamp the
    # difficulty up and would drop low-PoW objects.
    from bmconfigparser import config
    if config.safeGetBoolean('bitmessagesettings', 'extralowdifficulty'):
        print('POW: extralowdifficulty is on; messages may be dropped by '
              'public peers', flush=True)

    # M4.5.2: report which vault protects keys.dat, so the device log alone
    # answers "is the private key encrypted, and by what?".
    try:
        import keystore
        print('KEYSTORE enabled=%s backend=%s' % (
            keystore.enabled(), keystore.backend()), flush=True)
    except Exception as exc:  # noqa: BLE001 - never block startup
        print('KEYSTORE probe failed: %r' % (exc,), flush=True)

    alias_core_modules()
    schedule_android_keepalive()
    bitmessagemain.main()


if __name__ == '__main__':
    main()
