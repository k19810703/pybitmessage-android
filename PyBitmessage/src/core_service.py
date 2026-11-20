"""Foreground service entry point (milestone M4.1).

python-for-android starts this file in a separate Android process
(``<package>:service_pybitmessagesvc``) because buildozer.spec declares
``services = pybitmessagesvc:core_service.py``.

What p4a already gives us (v2024.01.21, PythonService.java):
  * the process is created and ``onStartCommand`` calls
    ``startForeground(id, notification)`` -- so the process is protected
    from low-memory kills without extra work from Python;
  * the channel it creates uses ``IMPORTANCE_NONE``, i.e. the notification
    is *silent and hidden from the shade*. That is fine for keep-alive but
    it means we cannot "see" it in a screenshot, so this module **re-posts
    a visible, low-importance notification on its own channel** to make the
    foreground state observable (acceptance: notification visible, M4.1c).

What this module does NOT do: run the Bitmessage core. Two processes
running the core would fight over the single-instance lock and the same
data files. Moving the core here is deferred to M4.3+ after the keep-alive
baseline is proven.
"""
import os
import time

SERVICE_NAME = 'PyBitmessage'
CHANNEL_ID = 'pybitmessage_service'
CHANNEL_NAME = '后台服务'
NOTIFICATION_ID = 1001
HEARTBEAT_EVERY_S = 60


def _log(message):
    """print() is forwarded to logcat under the python tag."""
    print('SERVICE %s' % message, flush=True)


def _ctx():
    """Resolve an Android Context usable for posting notifications."""
    from jnius import autoclass, cast  # noqa: PLC0415

    Context = autoclass('android.content.Context')

    # 1) the running p4a service instance
    try:
        PythonService = autoclass('org.kivy.android.PythonService')
        svc = getattr(PythonService, 'mService', None)
        if svc is not None:
            return cast(Context, svc)
    except Exception:  # noqa: BLE001
        pass

    # 2) application context fallback
    ActivityThread = autoclass('android.app.ActivityThread')
    app = ActivityThread.currentApplication()
    if app is None:
        raise RuntimeError('no Android context')
    return cast(Context, app)


def post_visible_notification():
    """Create a VISIBLE low-importance channel and post an ongoing note.

    p4a's own channel is IMPORTANCE_NONE (invisible in the shade), so this
    is what makes the service observable to a human / to a screenshot.
    """
    try:
        from jnius import autoclass, cast  # noqa: PLC0415

        Context = autoclass('android.content.Context')
        Build = autoclass('android.os.Build$VERSION')
        sdk = Build.SDK_INT
        ctx = _ctx()

        NotificationManager = autoclass('android.app.NotificationManager')
        nm = cast(NotificationManager,
                  ctx.getSystemService(Context.NOTIFICATION_SERVICE))

        # --- channel (API 26+) ---
        if sdk >= 26:
            NotificationChannel = autoclass(
                'android.app.NotificationChannel')
            channel = NotificationChannel(
                CHANNEL_ID, CHANNEL_NAME,
                NotificationManager.IMPORTANCE_LOW)
            channel.setDescription('保持 Bitmessage 节点在线')
            nm.createNotificationChannel(channel)

        # --- tap target: relaunch the UI activity ---
        PendingIntent = autoclass('android.app.PendingIntent')
        AndroidIntent = autoclass('android.content.Intent')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        intent = AndroidIntent(ctx, PythonActivity)
        flags = PendingIntent.FLAG_UPDATE_CURRENT
        if sdk >= 23:
            flags |= PendingIntent.FLAG_IMMUTABLE
        pending = PendingIntent.getActivity(ctx, 0, intent, flags)

        # --- build + post ---
        Builder = autoclass('android.app.Notification$Builder')
        builder = Builder(ctx, CHANNEL_ID) if sdk >= 26 else Builder(ctx)
        builder.setContentTitle(SERVICE_NAME)
        builder.setContentText('正在运行')
        builder.setSmallIcon(ctx.getApplicationInfo().icon)
        builder.setOngoing(True)
        builder.setContentIntent(pending)
        nm.notify(NOTIFICATION_ID, builder.build())
        _log('visible notification posted (API %d)' % sdk)
        return True
    except Exception as exc:  # noqa: BLE001 - never kill the service
        _log('notification failed: %r' % (exc,))
        return False


def main():
    """Keep the process alive; the heartbeat is what CI/devices assert on."""
    _log('started pid=%s' % os.getpid())
    ok = post_visible_notification()
    started = time.time()
    while True:
        time.sleep(HEARTBEAT_EVERY_S)
        _log('heartbeat uptime=%ds notification=%s' % (
            int(time.time() - started), ok))
        if not ok:
            ok = post_visible_notification()


if __name__ == '__main__':
    main()
