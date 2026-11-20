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

probe_environment()



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
        PythonService = autoclass('org.kivy.android.PythonService')
        Intent = autoclass('android.content.Intent')
        Context = autoclass('android.content.Context')
        Build = autoclass('android.os.Build$VERSION')

        activity = PythonActivity.mActivity
        if activity is None:
            print('SERVICE start skipped: no activity', flush=True)
            return
        context = cast(Context, activity)

        intent = Intent(context, PythonService)
        intent.putExtra('serviceEntrypoint', SERVICE_ENTRYPOINT)
        # p4a reads these when building the foreground notification.
        intent.putExtra('androidPrivate', context.getFilesDir().getPath())
        intent.putExtra('contentTitle', 'PyBitmessage')
        intent.putExtra('contentText', '正在运行')

        if Build.SDK_INT >= 26:
            context.startForegroundService(intent)
        else:
            context.startService(intent)
        print('SERVICE startForegroundService(%s) issued, API %d' % (
            SERVICE_ENTRYPOINT, Build.SDK_INT), flush=True)
    except Exception as exc:  # noqa: BLE001 - never block startup
        print('SERVICE start failed: %r' % (exc,), flush=True)


def main():
    """Start the core with the Kivy user interface."""
    prepare_home()

    import logging

    import state
    import bitmessagemain

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

    alias_core_modules()
    start_keepalive_service()
    bitmessagemain.main()


if __name__ == '__main__':
    main()
