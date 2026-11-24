"""Android notifications: runtime permission + "new message" notice (M4.2.1).

Two separate jobs, both no-ops off-device:

1. **Runtime permission** (Android 13 / API 33+). The manifest already
   declares ``POST_NOTIFICATIONS`` (M4.1c), but on API 33+ a declared
   permission is *not* granted: without the prompt ``NotificationManager.
   notify()`` is a silent no-op, so neither the foreground-service note nor
   the new-message note would ever appear. Decline must not crash the app --
   the node keeps running, it just cannot show anything.

2. **New message notification**. The core already emits
   ``displayNewInboxMessage`` on ``queues.UISignalQueue`` for every message
   that is stored in the inbox (class_objectProcessor.processmsg), but only
   the PyQt UI consumed it -- on Kivy the queue item was simply thrown
   away. ``install_message_hook()`` peeks into the same queue from a small
   daemon thread and posts a notification. It *peeks* (``get_nowait`` then
   ``put`` back) instead of consuming, because ``UIkivySignaler`` owns the
   consumer side of that queue.

Accepted trade-off: while the notification shade is expanded the OS also
shows the subject on the lock screen. The subject is the first line of the
E2E-decrypted message, i.e. the same thing the app shows in its inbox; the
body is never put in a notification. Pass ``privacy=True`` to
``notify_message`` to show only the sender address.
"""

import os
import threading
import time

CHANNEL_ID = 'pybitmessage_messages'
CHANNEL_NAME = '新消息'
MESSAGE_ID_BASE = 2000
REQUEST_CODE_PERMISSION = 0x424D  # arbitrary but stable ("BM")

_permission_asked = False
_hook_thread = None


def _android_context():
    """Return a Context usable for notification APIs, or None off-device."""
    if os.environ.get('ANDROID_ARGUMENT') is None:
        return None
    try:
        from jnius import autoclass, cast

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        activity = PythonActivity.mActivity
        if activity is None:
            return None
        return cast(Context, activity)
    except Exception as exc:  # noqa: BLE001
        print('NOTIFY: no android context: %r' % (exc,), flush=True)
        return None


# --------------------------------------------------------------------------
# 1. runtime permission
# --------------------------------------------------------------------------

def has_permission():
    """True when notifications can be posted (always True below API 33)."""
    context = _android_context()
    if context is None:
        return True
    try:
        from jnius import autoclass

        Build = autoclass('android.os.Build$VERSION')
        if Build.SDK_INT < 33:
            return True
        PackageManager = autoclass(
            'android.content.pm.PackageManager')
        granted = context.checkSelfPermission('android.permission.'
                                              'POST_NOTIFICATIONS')
        return granted == PackageManager.PERMISSION_GRANTED
    except Exception as exc:  # noqa: BLE001
        print('NOTIFY: permission check failed: %r' % (exc,), flush=True)
        return False


def request_permission_once():
    """Ask for POST_NOTIFICATIONS at most once per process (API 33+).

    Uses the plain ``requestPermissions()`` path (no result callback): the
    callback needs a subclassed activity or a Java-side receiver, and the
    latter crashed this app before (see android_keepalive.install()).
    Whether the user allowed or denied it is logged on the next startup by
    ``has_permission()``.
    """
    global _permission_asked
    if _permission_asked:
        return False
    context = _android_context()
    if context is None:
        return False
    try:
        from jnius import autoclass

        Build = autoclass('android.os.Build$VERSION')
        if Build.SDK_INT < 33:
            print('NOTIFY: API %d, POST_NOTIFICATIONS not needed'
                  % Build.SDK_INT, flush=True)
            _permission_asked = True
            return False
        if has_permission():
            print('NOTIFY: POST_NOTIFICATIONS already granted', flush=True)
            _permission_asked = True
            return False
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity = PythonActivity.mActivity
        java_str = autoclass('java.lang.String')
        String = autoclass('[Ljava.lang.String;')
        perms = String(1)
        perms[0] = java_str('android.permission.POST_NOTIFICATIONS')
        _permission_asked = True
        activity.requestPermissions(perms, REQUEST_CODE_PERMISSION)
        print('NOTIFY: POST_NOTIFICATIONS requested', flush=True)
        return True
    except Exception as exc:  # noqa: BLE001 - never block startup
        _permission_asked = True
        print('NOTIFY: request failed: %r' % (exc,), flush=True)
        return False


# --------------------------------------------------------------------------
# 2. notification channel + posting
# --------------------------------------------------------------------------

def ensure_channel():
    """Create the dedicated channel so the user can mute messages alone."""
    context = _android_context()
    if context is None:
        return False
    try:
        from jnius import autoclass, cast

        Build = autoclass('android.os.Build$VERSION')
        if Build.SDK_INT < 26:
            return True
        Context = autoclass('android.content.Context')
        NotificationManager = autoclass('android.app.NotificationManager')
        NotificationChannel = autoclass('android.app.NotificationChannel')
        nm = cast(NotificationManager,
                  context.getSystemService(Context.NOTIFICATION_SERVICE))
        channel = NotificationChannel(
            CHANNEL_ID, CHANNEL_NAME,
            NotificationManager.IMPORTANCE_HIGH)
        channel.setDescription('收到新的 Bitmessage 加密消息')
        nm.createNotificationChannel(channel)
        return True
    except Exception as exc:  # noqa: BLE001
        print('NOTIFY: channel failed: %r' % (exc,), flush=True)
        return False


def _short(text, limit):
    text = (text or '').strip().replace('\n', ' ')
    return text if len(text) <= limit else text[:limit - 1] + '…'


def notify_message(from_address, subject, body='', privacy=False):
    """Post (or update) the "new message" notification.

    All arguments are plain Python ``str``; ``subject``/``body`` come from
    the decrypted message, so they may be any Unicode. The body is never
    copied into the notification (only its length is used for the summary
    line) -- notification content leaks to the lock screen.
    """
    context = _android_context()
    if context is None:
        return False
    if not has_permission():
        print('NOTIFY: skipped, POST_NOTIFICATIONS not granted', flush=True)
        return False
    try:
        from jnius import autoclass, cast

        Build = autoclass('android.os.Build$VERSION')
        sdk = int(Build.SDK_INT)
        Context = autoclass('android.content.Context')
        NotificationManager = autoclass('android.app.NotificationManager')
        java_str = autoclass('java.lang.String')
        nm = cast(NotificationManager,
                  context.getSystemService(Context.NOTIFICATION_SERVICE))
        ensure_channel()

        builder_cls = autoclass('android.app.Notification$Builder')
        builder = builder_cls(context, CHANNEL_ID) if sdk >= 26 \
            else builder_cls(context)
        title = '新消息'
        if privacy:
            text = '来自 %s' % _short(from_address, 18)
        else:
            text = _short(subject, 40) or '（无标题）'
        builder.setContentTitle(java_str(title))
        builder.setContentText(java_str(text))
        builder.setSmallIcon(context.getApplicationInfo().icon)
        builder.setAutoCancel(True)
        builder.setOnlyAlertOnce(False)
        if sdk >= 26:
            builder.setCategory(java_str('msg'))
            if sdk >= 31:
                builder.setShortCriticalText(java_str(text))
        else:
            builder.setDefaults(
                autoclass('android.app.Notification').DEFAULT_ALL)

        # Tap opens the app (single activity; Kivy shows the inbox).
        PendingIntent = autoclass('android.app.PendingIntent')
        AndroidIntent = autoclass('android.content.Intent')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        intent = AndroidIntent(context, PythonActivity)
        intent.setFlags(
            AndroidIntent.FLAG_ACTIVITY_NEW_TASK
            | AndroidIntent.FLAG_ACTIVITY_SINGLE_TOP)
        flags = PendingIntent.FLAG_UPDATE_CURRENT
        if sdk >= 23:
            flags |= PendingIntent.FLAG_IMMUTABLE
        pending = PendingIntent.getActivity(context, 0, intent, flags)
        builder.setContentIntent(pending)

        # Stable id per app (not per sender): newer messages replace older
        # ones instead of stacking, which keeps the shade readable.
        nm.notify(MESSAGE_ID_BASE, builder.build())
        print('NOTIFY: message from %s posted (%s)'
              % (from_address, 'privacy' if privacy else 'subject'),
              flush=True)
        return True
    except Exception as exc:  # noqa: BLE001 - notifications are best effort
        print('NOTIFY: message notification failed: %r' % (exc,), flush=True)
        return False


# --------------------------------------------------------------------------
# 3. bridge to the core's UISignalQueue
# --------------------------------------------------------------------------

def _hook_loop():
    import queue as _queue

    from queues import UISignalQueue  # noqa: PLC0415

    while True:
        try:
            item = UISignalQueue.get_nowait()
        except _queue.Empty:
            time.sleep(2.0)
            continue
        except Exception:  # noqa: BLE001
            time.sleep(5.0)
            continue
        try:
            UISignalQueue.put(item)  # hand it back to the real consumer
        except Exception:  # noqa: BLE001
            pass
        try:
            command, data = item
            if command == 'displayNewInboxMessage' and len(data) >= 5:
                _inv, _to, from_address, subject, body = data[:5]
                notify_message(from_address, subject, body)
        except Exception as exc:  # noqa: BLE001
            print('NOTIFY: hook failed: %r' % (exc,), flush=True)


def install_message_hook():
    """Start the daemon thread that turns inbox signals into notifications."""
    global _hook_thread
    if os.environ.get('ANDROID_ARGUMENT') is None:
        return False
    if _hook_thread is not None and _hook_thread.is_alive():
        return True
    _hook_thread = threading.Thread(
        target=_hook_loop, name='notify-hook', daemon=True)
    _hook_thread.start()
    print('NOTIFY: message hook started', flush=True)
    return True
