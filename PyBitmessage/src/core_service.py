"""Foreground service entry point (milestone M4.1).

python-for-android starts this file in a **separate Android process**
(``<package>:service``) when ``services=`` is declared in buildozer.spec.
That process is kept alive by the platform and by our foreground
notification, independently of the Kivy UI process.

Scope of this milestone: prove the mechanism works end to end -- the
process starts, posts a persistent notification on a proper channel,
survives the UI being backgrounded/killed, and stops cleanly. The
Bitmessage core is **not** moved in here yet (M4.3+): two processes
running the core would fight over the single-instance lock and the same
data files.

Context note: a p4a ``Service`` has no ``mActivity``; we resolve the
application context from the service handle instead, and fall back to
``android.app.ActivityThread`` when even that is unavailable.
"""

import os
import time

SERVICE_NAME = 'PyBitmessage'
CHANNEL_ID = 'pybitmessage_service'
NOTIFICATION_ID = 1


def _log(message):
    """print() is forwarded to logcat under the python tag."""
    print('SERVICE %s' % message, flush=True)


def _app_context():
    """Best-effort Android Context for posting notifications."""
    from jnius import autoclass, cast  # noqa: PLC0415 - android only

    Context = autoclass('android.content.Context')

    # 1) the p4a PythonService instance, when the runtime sets it up
    try:
        PythonService = autoclass('org.kivy.android.PythonService')
        if getattr(PythonService, 'mService', None) is not None:
            return cast(Context, PythonService.mService)
    except Exception:  # noqa: BLE001
        pass

    # 2) the application context via ActivityThread
    try:
        ActivityThread = autoclass('android.app.ActivityThread')
        app = ActivityThread.currentApplication()
        if app is not None:
            return cast(Context, app)
    except Exception:  # noqa: BLE001
        pass

    raise RuntimeError('no Android context available')


def _build_notification(context):
    """Create a channel-aware persistent notification."""
    from jnius import autoclass, cast  # noqa: PLC0415

    Context = autoclass('android.content.Context')
    PendingIntent = autoclass('android.app.PendingIntent')
    NotificationManager = autoclass('android.app.NotificationManager')
    Build = autoclass('android.os.Build$VERSION')
    sdk = Build.SDK_INT

    if sdk >= 26:
        NotificationChannel = autoclass('android.app.NotificationChannel')
        nm = cast(NotificationManager,
                  context.getSystemService(Context.NOTIFICATION_SERVICE))
        channel = NotificationChannel(
            CHANNEL_ID, SERVICE_NAME, NotificationManager.IMPORTANCE_LOW)
        channel.setDescription('Keeps the Bitmessage node online')
        nm.createNotificationChannel(channel)

    # tapping the notification brings the UI back
    launch = context.getPackageManager().getLaunchIntentForPackage(
        context.getPackageName())
    flags = PendingIntent.FLAG_UPDATE_CURRENT
    if sdk >= 23:
        flags |= PendingIntent.FLAG_IMMUTABLE
    pending = PendingIntent.getActivity(context, 0, launch, flags)

    Builder = autoclass('android.app.Notification$Builder')
    RDrawable = autoclass('android.R$drawable')
    builder = Builder(context, CHANNEL_ID) if sdk >= 26 else Builder(context)
    builder.setContentTitle(SERVICE_NAME)
    builder.setContentText('正在运行')
    builder.setSmallIcon(RDrawable.stat_notify_sync)
    builder.setOngoing(True)
    builder.setContentIntent(pending)
    return builder.build(), nm if sdk >= 26 else cast(
        NotificationManager,
        context.getSystemService(Context.NOTIFICATION_SERVICE)), sdk


def _post_notification():
    """Post the persistent notification; returns True on success."""
    try:
        from jnius import autoclass  # noqa: PLC0415
        from jnius import cast  # noqa: F401  (re-exported for clarity)
        Context = autoclass('android.content.Context')
        NotificationManager = autoclass('android.app.NotificationManager')
        context = _app_context()
        notification, nm, sdk = _build_notification(context)
        nm.notify(NOTIFICATION_ID, notification)
        _log('notification posted (API %d)' % sdk)
        return True
    except Exception as exc:  # noqa: BLE001 - never crash the service
        _log('notification failed: %r' % (exc,))
        return False


def main():
    """Service loop: keep the process alive, refresh the notification."""
    _log('started, pid=%s' % os.getpid())
    ok = _post_notification()
    beat = 0
    posted = ok
    while True:
        beat += 1
        # Retry once a minute until the notification is actually up
        # (the context may not be ready in the very first second).
        if not posted and beat % 10 == 0:
            posted = _post_notification()
        if beat % 10 == 1:
            _log('heartbeat %d (notification=%s)' % (beat, posted))
        time.sleep(6)


if __name__ == '__main__':
    main()
