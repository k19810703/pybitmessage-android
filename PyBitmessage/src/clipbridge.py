"""Clipboard that actually works on Android.

Kivy's own clipboard provider returns an empty string on this device: the
"copy" in the messaging screen wrote only to Kivy's in-process store, so
pasting into the recipient field produced nothing (reported by the user as
"收件地址无法黏贴").

This module talks to Android's ClipboardManager through jnius instead, and
falls back to Kivy's clipboard on the desktop (and if anything goes wrong).
Both directions are supported so text copied inside the app is also visible to
WeChat, the browser, and so on.
"""

import os

_KIVY = 'kivy'
_ANDROID = 'android'


def _android_clipboard(activity=None):
    """Return the system ClipboardManager, or None off-device."""
    if os.environ.get('ANDROID_ARGUMENT') is None:
        return None
    try:
        from jnius import autoclass, cast
        if activity is None:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
        if activity is None:
            return None
        Context = autoclass('android.content.Context')
        ClipboardManager = autoclass('android.content.ClipboardManager')
        service = activity.getSystemService(Context.CLIPBOARD_SERVICE)
        return cast(ClipboardManager, service)
    except Exception as exc:  # noqa: BLE001 - never break the caller
        print('CLIP android clipboard unavailable: %r' % (exc,), flush=True)
        return None


def get_text(activity=None):
    """Read the clipboard as str; '' when there is nothing to read."""
    manager = _android_clipboard(activity)
    if manager is not None:
        try:
            clip = manager.getPrimaryClip()
            if clip is not None and clip.getItemCount() > 0:
                item = clip.getItemAt(0)
                coerced = item.coerceToText(
                    activity or
                    _current_activity())
                if coerced is not None:
                    return str(coerced.toString())
        except Exception as exc:  # noqa: BLE001
            print('CLIP android read failed: %r' % (exc,), flush=True)
    try:
        from kivy.core.clipboard import Clipboard
        return Clipboard.paste() or ''
    except Exception as exc:  # noqa: BLE001
        print('CLIP kivy read failed: %r' % (exc,), flush=True)
        return ''


def set_text(text, activity=None):
    """Put *text* on both the system clipboard and Kivy's store."""
    text = '' if text is None else str(text)
    manager = _android_clipboard(activity)
    if manager is not None:
        try:
            from jnius import autoclass
            ClipData = autoclass('android.content.ClipData')
            ClipData.newPlainText = ClipData.newPlainText  # noqa: B018
            clip = ClipData.newPlainText('PyBitmessage', _java_str(text))
            manager.setPrimaryClip(clip)
        except Exception as exc:  # noqa: BLE001
            print('CLIP android write failed: %r' % (exc,), flush=True)
    try:
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(text)
        return True
    except Exception as exc:  # noqa: BLE001
        print('CLIP kivy write failed: %r' % (exc,), flush=True)
        return manager is not None


def _java_str(text):
    from jnius import autoclass
    return autoclass('java.lang.String')(text)


def _current_activity():
    try:
        from jnius import autoclass
        return autoclass('org.kivy.android.PythonActivity').mActivity
    except Exception:  # noqa: BLE001
        return None
