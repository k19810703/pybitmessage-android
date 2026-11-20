"""Keep the node alive while the screen is off (milestone M4.3).

Two independent mechanisms, because Android and vendor ROMs each take a
bite out of background execution:

1. **Partial wake lock** -- keeps the CPU awake so the socket threads (which
   live in the UI process) can still be scheduled. Released as soon as the
   app is foregrounded again, and re-acquired on screen-off. Without it the
   device dozes within minutes and every peer connection times out.
2. **Battery-optimisation exemption prompt** -- Doze and, on Xiaomi/HyperOS,
   the "app battery saver" can still kill or freeze us even with a wake
   lock. There is no silent way to get the exemption, so this module asks
   the system to show the user the "no restrictions / allow background
   activity" screen, at most once per process.

Both are no-ops on desktop so the same code runs everywhere.
Accepted trade-off: a held wake lock costs battery. M4.7.1 (energy policy)
is where that gets measured (acceptance C3: <= 8 % / hour).
"""

import os
import time

WAKE_LOCK_TAG = 'pybitmessage:node'
# Do not re-prompt the user for the battery exemption more than once per
# app launch; the setting lives in the system UI and is sticky once granted.
_prompted_battery_optimisation = False

_wake_lock = None


def _android():
    """Return (activity, context) or (None, None) off-device."""
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
        print('KEEPALIVE: no android context: %r' % (exc,), flush=True)
        return None, None


def acquire_wake_lock():
    """Take a partial wake lock (CPU stays on; the screen may still sleep)."""
    global _wake_lock
    activity, context = _android()
    if context is None or _wake_lock is not None:
        return False
    try:
        from jnius import autoclass, cast

        Context = autoclass('android.content.Context')
        PowerManager = autoclass('android.os.PowerManager')
        pm = cast(PowerManager, context.getSystemService(Context.POWER_SERVICE))
        _wake_lock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,
                                    WAKE_LOCK_TAG)
        _wake_lock.setReferenceCounted(False)
        _wake_lock.acquire()
        print('KEEPALIVE: partial wake lock acquired', flush=True)
        return True
    except Exception as exc:  # noqa: BLE001
        print('KEEPALIVE: wake lock failed: %r' % (exc,), flush=True)
        _wake_lock = None
        return False


def release_wake_lock():
    """Drop the wake lock (call when the UI is in the foreground again)."""
    global _wake_lock
    if _wake_lock is None:
        return False
    try:
        if _wake_lock.isHeld():
            _wake_lock.release()
        _wake_lock = None
        print('KEEPALIVE: partial wake lock released', flush=True)
        return True
    except Exception as exc:  # noqa: BLE001
        print('KEEPALIVE: release failed: %r' % (exc,), flush=True)
        _wake_lock = None
        return False


def is_battery_optimisation_ignored():
    """True when the OS already exempts us from battery optimisations."""
    _, context = _android()
    if context is None:
        return True
    try:
        from jnius import autoclass, cast

        Context = autoclass('android.content.Context')
        PowerManager = autoclass('android.os.PowerManager')
        pm = cast(PowerManager, context.getSystemService(Context.POWER_SERVICE))
        package = context.getPackageName()
        mode = pm.isIgnoringBatteryOptimizations(package)
        print('KEEPALIVE: ignoring battery optimizations = %s' % mode,
              flush=True)
        return bool(mode)
    except Exception as exc:  # noqa: BLE001
        print('KEEPALIVE: battery check failed: %r' % (exc,), flush=True)
        return False


def request_battery_optimisation_exemption(force=False):
    """Show the system's "allow background activity" screen, once per launch.

    Deliberately conservative: we never call ACTION_REQUEST_IGNORE_BATTERY_
    OPTIMIZATIONS silently in a loop, and we skip the prompt entirely when
    the user (or the ROM) already exempted us.
    """
    global _prompted_battery_optimisation
    if _prompted_battery_optimisation and not force:
        return False
    activity, context = _android()
    if activity is None:
        return False
    if is_battery_optimisation_ignored():
        _prompted_battery_optimisation = True
        return False
    try:
        from jnius import autoclass

        Intent = autoclass('android.content.Intent')
        Uri = autoclass('android.net.Uri')
        Settings = autoclass('android.provider.Settings')
        Build = autoclass('android.os.Build$VERSION')

        _prompted_battery_optimisation = True
        if Build.SDK_INT >= 23:
            intent = Intent()
            intent.setAction(
                Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
            intent.setData(Uri.parse('package:' + context.getPackageName()))
            activity.startActivity(intent)
            print('KEEPALIVE: battery exemption prompt shown', flush=True)
            return True
        intent = Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
        activity.startActivity(intent)
        return True
    except Exception as exc:  # noqa: BLE001
        print('KEEPALIVE: exemption prompt failed: %r' % (exc,), flush=True)
        return False


def install():
    """Wire the wake lock to screen on/off; call once at startup."""
    activity, _ = _android()
    if activity is None:
        return False
    if not acquire_wake_lock():
        return False
    try:
        from jnius import JavaClass, autoclass, java_method

        # BroadcastReceiver is an abstract *class* in Android, not an
        # interface: declaring it in __javainterfaces__ is rejected with
        # "android.content.BroadcastReceiver is not an interface". JavaClass
        # (class inheritance) is the correct wrapper. A plain Python func
        # cannot be a receiver without pyjnius' activity-broadcast helpers,
        # so this is best-effort: the wake lock above already does the
        # heavy lifting and is held for the whole app lifetime.
        class ScreenReceiver(JavaClass):
            __javaclass__ = 'android/content/BroadcastReceiver'

            @java_method('(Landroid/content/Context;Landroid/content/Intent;)V')
            def onReceive(self, context, intent):
                action = intent.getAction()
                if action == 'android.intent.action.SCREEN_OFF':
                    acquire_wake_lock()
                elif action == 'android.intent.action.SCREEN_ON':
                    release_wake_lock()

        IntentFilter = autoclass('android.content.IntentFilter')
        filter_ = IntentFilter()
        filter_.addAction('android.intent.action.SCREEN_OFF')
        filter_.addAction('android.intent.action.SCREEN_ON')
        activity.registerReceiver(ScreenReceiver(), filter_)
        print('KEEPALIVE: screen receiver registered', flush=True)
        return True
    except Exception as exc:  # noqa: BLE001
        # The wake lock alone is what keeps us alive; a receiver that cannot
        # be registered must not take the app down with it.
        print('KEEPALIVE: screen receiver unavailable (%r); wake lock stays '
              'held for the process lifetime' % (exc,), flush=True)
        return True


_last_touch = time.time()


def _touch_keepalive():
    global _last_touch
    _last_touch = time.time()


def status():
    """Human-readable state for the UI / logcat."""
    activity, context = _android()
    if context is None:
        return 'desktop'
    held = _wake_lock is not None and _wake_lock.isHeld()
    return 'wakeLock=%s batteryExempt=%s' % (
        held, is_battery_optimisation_ignored())
