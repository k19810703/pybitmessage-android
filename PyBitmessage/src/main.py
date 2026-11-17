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

from envprobe import run as probe_environment  # noqa: E402

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


def main():
    """Start the core with the Kivy user interface."""
    prepare_home()

    import state
    import bitmessagemain

    state.kivy = True
    bitmessagemain.main()


if __name__ == '__main__':
    main()
