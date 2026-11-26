"""Shared message-list loading for the drawer screens (M6 follow-up).

Upstream's Sent / Draft / Trash / AllMails screens are empty shells: their
``load*()`` methods set the selected account and stop -- none of them ever
queries the database, so every folder looked empty even with messages in
it. (The drawer's Inbox had the identical defect and was fixed separately.)

Bitmessage keeps folders in a single pair of tables, selected by the
``folder`` column:
  * sent    : sent / draft / trash
  * inbox   : inbox / draft / trash
so one query helper covers all four screens.

Everything here degrades to an empty list plus a printed message instead of
raising: navigation must never die because a table is missing.
"""
import time

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

from helper_sql import sqlQuery

_CJK_FONTS = (
    '/system/fonts/NotoSansCJK-Regular.ttc',
    '/system/fonts/NotoSansSC-Regular.otf',
    '/system/fonts/DroidSansFallback.ttf',
    '/system/fonts/NotoSansCJKsc-Regular.otf',
)
_cjk_font = None


def cjk_font():
    """Register and return a CJK-capable font name (cached)."""
    global _cjk_font
    if _cjk_font:
        return _cjk_font
    import os
    from kivy.core.text import LabelBase

    for path in _CJK_FONTS:
        if os.path.exists(path):
            try:
                LabelBase.register(name='CJK', fn_regular=path)
                _cjk_font = 'CJK'
                return _cjk_font
            except Exception:  # noqa: BLE001
                continue
    _cjk_font = 'Roboto'
    return _cjk_font


def _text(value):
    """Normalise sqlite bytes/None into str."""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode('utf-8', 'replace')
    return '' if value is None else str(value)


def _unrepr(value):
    """Undo the b'\\x..' repr that older builds stored as subject/body."""
    if not isinstance(value, str) or not value.startswith(("b'", 'b"')):
        return value
    try:
        raw = value[2:-1].encode('latin-1', 'backslashreplace').decode(
            'unicode_escape').encode('latin-1')
        return raw.decode('utf-8')
    except Exception:  # noqa: BLE001
        return value


def _preview(body, limit=48):
    text = ' '.join((body or '').split())
    return text[:limit] + ('…' if len(text) > limit else '')


def load_folder(folder, limit=100):
    """Return [dict] for *folder*: sent / draft / trash / all / inbox.

    Each row carries: from, to, subject, body, time, status (sent only).
    """
    folders = {
        'sent': [('sent', ('sent',))],
        'draft': [('sent', ('draft',)), ('inbox', ('draft',))],
        'trash': [('sent', ('trash',)), ('inbox', ('trash',))],
        'inbox': [('inbox', ('inbox',))],
        'all': [('inbox', ('inbox', 'draft', 'trash')),
                ('sent', ('sent', 'draft', 'trash'))],
    }
    plan = folders.get(folder)
    if plan is None:
        print('LIST unknown folder %r' % (folder,), flush=True)
        return []

    rows = []
    for table, names in plan:
        placeholders = ','.join('?' * len(names))
        if table == 'sent':
            sql = ('SELECT toaddress, fromaddress, subject, message, '
                   'lastactiontime, status, msgid FROM sent '
                   'WHERE folder IN (%s)' % placeholders)
        else:
            sql = ('SELECT toaddress, fromaddress, subject, message, '
                   'received, NULL, msgid FROM inbox '
                   'WHERE folder IN (%s)' % placeholders)
        try:
            result = sqlQuery(sql, *names)
        except Exception as exc:  # noqa: BLE001 - a missing table is not fatal
            print('LIST query failed (%s/%s): %r' % (table, folder, exc),
                  flush=True)
            continue
        for to_addr, from_addr, subject, body, when, status, msgid in result:
            rows.append({
                'to': _text(to_addr),
                'from': _text(from_addr),
                'subject': _unrepr(_text(subject)),
                'body': _unrepr(_text(body)),
                'time': int(when or 0),
                'status': _text(status) if status else '',
                # bytes: keep it raw, sqlite matches the blob only that way
                'msgid': msgid,
                'table': table,
            })
    rows.sort(key=lambda r: r['time'], reverse=True)
    rows = rows[:limit]
    print('LIST %s: %d message(s)' % (folder, len(rows)), flush=True)
    return rows


def _text_label(text, font, size, colour):
    """Native Label (MDLabel would ignore the CJK font)."""
    lbl = Label(text=text, font_name=font, font_size=dp(size), color=colour,
                size_hint_y=None, halign='left', valign='middle',
                shorten=True, shorten_from='right')
    lbl.height = dp(size + 8)
    lbl.bind(size=lambda i, v: setattr(i, 'text_size', (v[0], None)))
    return lbl


def render(screen, folder, empty_text='（暂无消息）', on_tap=None, actions=None):
    """Fill ``screen.ids.ml`` with the rows of *folder*.

    Returns the list of rows so callers can keep them for detail views.
    """
    ml = screen.ids.get('ml') if screen.ids else None
    if ml is None:
        print('LIST no ml container on %s' % type(screen).__name__, flush=True)
        return []
    font = cjk_font()
    rows = load_folder(folder)
    ml.clear_widgets()
    print('LIST render %s by %s: rows=%d' % (
        folder, type(screen).__name__, len(rows)), flush=True)
    if not rows:
        ml.add_widget(Label(text=empty_text, font_name=font,
                            color=(.5, .5, .5, 1)))
        return []

    for row in rows:
        line = BoxLayout(orientation='horizontal', size_hint_y=None,
                         height=dp(76), spacing=dp(6))
        item = BoxLayout(orientation='vertical', padding=(dp(8), dp(6)),
                         spacing=dp(2))
        title = row['subject'] or _preview(row['body'], 32)
        item.add_widget(_text_label(title, font, 16, (0.1, 0.1, 0.1, 1)))
        who = row['to'] if folder == 'sent' else row['from']
        item.add_widget(_text_label('%s %s' % (
            '收件人' if folder == 'sent' else '来自', who), font, 12,
            (0.45, 0.45, 0.45, 1)))
        tail = _preview(row['body'])
        if row['status']:
            tail = '[%s] %s' % (_status_text(row['status']), tail)
        item.add_widget(_text_label(tail, font, 13, (0.25, 0.25, 0.25, 1)))
        if on_tap is not None:
            item.touch_args = row
            line.touch_args = row
        line.add_widget(item)
        for label, callback in (actions or []):
            btn = Button(text=label, font_name=font, font_size=dp(12),
                         size_hint=(None, 1), width=dp(66))
            btn.bind(on_release=(lambda cb, r: lambda *_: cb(r))(
                callback, row))
            line.add_widget(btn)
        ml.add_widget(line)

    print('LIST render %s by %s done: %d widget(s)' % (
        folder, type(screen).__name__, len(ml.children)), flush=True)
    if on_tap is not None:
        _install_taps(ml, on_tap)
    return rows


_STATUS_ZH = {
    'awaitingpubkey': '等待公钥',
    'doingpubkeypow': '计算公钥 PoW',
    'doingmsgpow': '计算消息 PoW',
    'msgsent': '已发送',
    'ackreceived': '对方已确认',
    'broadcastsent': '已广播',
    'awaitingpubkeyconfirmation': '等待公钥确认',
    'original': '原始',
}


def _status_text(status):
    """Chinese for a Bitmessage sent-status value (M3.9.4)."""
    return _STATUS_ZH.get(status, status)


def _install_taps(ml, on_tap):
    """Route taps on the list to the row that was hit.

    A BoxLayout inside MDList/ScrollView never receives touch itself, so the
    handler lives on the MDList and hit-tests its children in reverse order.
    """
    if getattr(ml, '_taps_installed', False):
        return
    ml._taps_installed = True

    def _on_down(_widget, touch):
        for child in ml.children:
            row = getattr(child, 'touch_args', None)
            if row is None:
                continue
            if child.collide_point(touch.x, touch.y):
                if getattr(touch, 'grab_current', None) is None:
                    try:
                        on_tap(row)
                    except Exception as exc:  # noqa: BLE001
                        print('LIST tap failed: %r' % (exc,), flush=True)
                return True
        return False

    ml.bind(on_touch_down=_on_down)


def show_detail(row):
    """MDDialog showing one message in full (subject/sender/time/body)."""
    from kivymd.uix.button import MDFlatButton
    from kivymd.uix.dialog import MDDialog

    font = cjk_font()
    root = BoxLayout(orientation='vertical', spacing=dp(6),
                     size_hint_y=None, height=dp(320))
    meta = [
        ('主题', row['subject'] or '（无主题）', (0.1, .1, .1, 1)),
        ('来自', row['from'], (.45, .45, .45, 1)),
        ('收件人', row['to'], (.45, .45, .45, 1)),
        ('时间', time.strftime('%Y-%m-%d %H:%M:%S',
                               time.localtime(row['time'] or 0)),
         (.45, .45, .45, 1)),
    ]
    for key, value, colour in meta:
        root.add_widget(_text_label('%s：%s' % (key, value), font, 13, colour))
    if row['status']:
        root.add_widget(_text_label('状态：%s' % _status_text(row['status']),
                                    font, 13, (0.1, 0.5, 0.1, 1)))

    from kivy.uix.scrollview import ScrollView
    scroll = ScrollView(size_hint=(1, None), height=dp(180))
    root.add_widget(scroll)
    box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
    box.bind(minimum_height=box.setter('height'))
    scroll.add_widget(box)
    body = Label(text=row['body'] or '（空消息）', font_name=font,
                 font_size=dp(15), color=(.1, .1, .1, 1),
                 size_hint_y=None, halign='left', valign='top',
                 text_size=(dp(260), None))
    body.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
    box.add_widget(body)

    dialog = MDDialog(title='Message', type='custom', content_cls=root,
                      buttons=[MDFlatButton(
                          text='Close',
                          on_release=lambda *_: dialog.dismiss())])
    dialog.open()
    print('LIST open detail from=%s len(body)=%d' % (
        row['from'], len(row['body'] or '')), flush=True)
