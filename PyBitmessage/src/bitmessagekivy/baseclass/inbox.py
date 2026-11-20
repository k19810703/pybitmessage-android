# pylint: disable=unused-import, too-many-public-methods, unused-variable, too-many-ancestors
# pylint: disable=no-name-in-module, too-few-public-methods, import-error, unused-argument, too-many-arguments
# pylint: disable=attribute-defined-outside-init, global-variable-not-assigned, too-many-instance-attributes

"""
Kivy UI for inbox screen
"""
from kivy.clock import Clock
from kivy.properties import ListProperty, StringProperty
from kivy.app import App
from kivy.uix.screenmanager import Screen
from pybitmessage.bitmessagekivy.baseclass.common import kivy_state_variables, load_image_path


class Inbox(Screen):
    """Inbox Screen class for Kivy UI"""

    queryreturn = ListProperty()
    has_refreshed = True
    account = StringProperty()
    no_search_res_found = "No search result found"
    label_str = "Yet no message for this account!"

    def __init__(self, *args, **kwargs):
        """Initialize Kivy variables and set up the UI"""
        super().__init__(*args, **kwargs)  # pylint: disable=missing-super-argument
        self.kivy_running_app = App.get_running_app()
        self.kivy_state = kivy_state_variables()
        self.image_dir = load_image_path()
        Clock.schedule_once(self.init_ui, 0)

    def set_default_address(self):
        """Set the default address if none is selected"""
        if not self.kivy_state.selected_address and self.kivy_running_app.identity_list:
            self.kivy_state.selected_address = self.kivy_running_app.identity_list[0]

    def init_ui(self, dt=0):
        """Initialize UI and load message list"""
        self.loadMessagelist()

    def on_pre_enter(self, *args):
        """Reload whenever the screen is opened.

        The list used to be filled once at construction, so anything that
        arrived after startup never appeared in the drawer's Inbox.
        """
        try:
            self._repair_legacy_rows()
            self.loadMessagelist()
        except Exception as exc:  # noqa: BLE001
            print('INBOX refresh failed: %r' % (exc,), flush=True)

    def loadMessagelist(self, where="", what=""):
        """Load inbox messages into the list.

        Until now this only recorded the selected account and never queried
        anything, which is why the drawer's Inbox screen stayed empty even
        though messages had arrived (the demo screen did show them -- it
        queries directly). Read the same rows the demo screen reads so the
        two places always agree.
        """
        self.set_default_address()
        self.account = self.kivy_state.selected_address
        try:
            from pybitmessage.bitmessagekivy.messaging import inbox
            messages = inbox()
        except Exception as exc:  # noqa: BLE001 - never break navigation
            print('INBOX load failed: %r' % (exc,), flush=True)
            messages = []
        self.queryreturn = messages
        print('INBOX loadMessagelist: %d message(s)' % len(messages),
              flush=True)
        self._render(messages)

    @staticmethod
    def _repair_legacy_rows():
        """One-off migration for rows written before the api.py bytes fix.

        Those rows hold a literal "b'\\xe5\\x85\\xac...'" instead of text. Rewrite
        them in place so the database stops carrying escape soup; idempotent,
        and skipped entirely when there is nothing to fix.
        """
        from pybitmessage.helper_sql import sqlExecute, sqlQuery

        try:
            rows = sqlQuery(
                'SELECT msgid, subject, message FROM inbox '
                "WHERE subject LIKE 'b''%' OR message LIKE 'b''%'")
        except Exception as exc:  # noqa: BLE001
            print('INBOX migration query failed: %r' % (exc,), flush=True)
            return 0

        def _as_text(value):
            if isinstance(value, (bytes, bytearray)):
                return bytes(value).decode('utf-8', 'replace')
            return '' if value is None else str(value)

        fixed = 0
        for msgid, subject, message in rows:
            old_subject, old_message = _as_text(subject), _as_text(message)
            new_subject = _bidi_safe_text(old_subject)
            new_message = _bidi_safe_text(old_message)
            if new_subject == old_subject and new_message == old_message:
                continue
            try:
                sqlExecute(
                    'UPDATE inbox SET subject=?, message=? WHERE msgid=?',
                    new_subject, new_message, msgid)
                fixed += 1
            except Exception as exc:  # noqa: BLE001
                print('INBOX migration update failed: %r' % (exc,), flush=True)
        if fixed:
            print('INBOX migrated %d legacy row(s)' % fixed, flush=True)
        return fixed

    def _render(self, messages):
        """Fill the list: a tappable card per message, no icon font needed.

        Deliberately not TwoLineListItem: its built-in leading glyph comes
        from the KivyMD icon font, which is not fully bundled here, so every
        row showed two tofu boxes (□) before the sender address. A plain
        BoxLayout of MDLabels renders predictably and lets us bind a tap.
        """
        ml = self.ids.get('ml') if self.ids else None
        if ml is None:
            return
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivymd.uix.label import MDLabel
        from pybitmessage.bitmessagekivy.messaging import FONT

        ml.clear_widgets()
        if not messages:
            ml.add_widget(MDLabel(
                text=self.label_str, halign='center',
                theme_text_color='Secondary'))
            return
        for from_addr, subject, body, received in messages:
            title = subject or (body[:32] + ('…' if len(body) > 32 else ''))
            row = BoxLayout(
                orientation='vertical', size_hint_y=None, height=dp(72),
                padding=(dp(8), dp(6)), spacing=dp(2))
            row.add_widget(MDLabel(
                text=str(title), font_name=FONT, font_size='16sp',
                size_hint_y=None, height=dp(26),
                shorten=True, shorten_from='right'))
            row.add_widget(MDLabel(
                text='来自 %s' % from_addr, font_name=FONT,
                font_size='12sp', size_hint_y=None, height=dp(20),
                theme_text_color='Secondary'))
            row.add_widget(MDLabel(
                text=_preview(body), font_name=FONT, font_size='13sp',
                size_hint_y=None, height=dp(18),
                theme_text_color='Primary', shorten=True,
                shorten_from='right'))
            _bind_tap(row, self._open_detail, from_addr, subject, body,
                      received)
            ml.add_widget(row)

    def _open_detail(self, from_addr, subject, body, received):
        """Show the whole message (the list only ever showed a preview)."""
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.dialog import MDDialog

        content = _detail_content(from_addr, subject, body, received)
        dialog = MDDialog(
            title='消息详情', type='custom', content_cls=content,
            buttons=[MDFlatButton(
                text='关闭', on_release=lambda *_: dialog.dismiss())])
        dialog.open()
        print('INBOX open detail from=%s len(body)=%d' % (
            from_addr, len(body or '')), flush=True)

    def refresh_callback(self, *args):
        """Refresh the inbox messages while showing a loading spinner"""

        def refresh_on_scroll_down(interval):
            """Reset search fields and reload data on scroll"""
            self.kivy_state.searching_text = ""
            self.children[2].children[1].ids.search_field.text = ""
            self.ids.ml.clear_widgets()
            self.loadMessagelist(self.kivy_state.selected_address)
            self.has_refreshed = True
            self.ids.refresh_layout.refresh_done()
            self.tick = 0

        Clock.schedule_once(refresh_on_scroll_down, 1)


def _preview(body, limit=48):
    """One-line preview of the body (the list never showed the full text)."""
    text = ' '.join((body or '').split())
    return text[:limit] + ('…' if len(text) > limit else '')


def _bidi_safe_text(value):
    """Undo the b'\\x..' repr that older builds stored as the subject.

    Until 2026-11-19 the API path decoded base64 into bytes and stored
    str(bytes), so some rows hold a literal "b'\\xe5\\x85\\xac...'". Turn those
    back into real text instead of showing the escape soup.
    """
    if not isinstance(value, str) or not value.startswith(("b'", 'b"')):
        return value
    try:
        inner = value[2:-1]
        raw = inner.encode('latin-1', 'backslashreplace').decode(
            'unicode_escape').encode('latin-1')
        return raw.decode('utf-8')
    except Exception:  # noqa: BLE001 - keep the original on any surprise
        return value


def _bind_tap(widget, callback, *args):
    """Call ``callback(*args)`` on a short tap of ``widget``.

    Kivy BoxLayout has no on_press; touch_down/up within a small distance is
    the usual idiom and avoids firing on scroll gestures.
    """
    state = {'x': 0, 'y': 0, 'inside': False}

    def on_touch_down(_w, touch):
        if not widget.collide_point(*touch.pos):
            return False
        state['x'], state['y'] = touch.pos
        state['inside'] = True
        return False

    def on_touch_up(_w, touch):
        if not state['inside'] or not widget.collide_point(*touch.pos):
            state['inside'] = False
            return False
        state['inside'] = False
        dx, dy = abs(touch.pos[0] - state['x']), abs(touch.pos[1] - state['y'])
        if dx < 20 and dy < 20:  # a tap, not a drag/scroll
            try:
                callback(*args)
            except Exception as exc:  # noqa: BLE001
                print('INBOX tap handler failed: %r' % (exc,), flush=True)
        return False

    widget.bind(on_touch_down=on_touch_down, on_touch_up=on_touch_up)


def _detail_content(from_addr, subject, body, received):
    """Scrollable detail body: subject, sender, time and the full message."""
    import time

    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.scrollview import ScrollView
    from kivymd.uix.label import MDLabel
    from pybitmessage.bitmessagekivy.messaging import FONT

    root = BoxLayout(orientation='vertical', spacing=dp(6),
                     size_hint_y=None, height=dp(320))
    meta = [
        ('主题', _bidi_safe_text(subject or '（无主题）')),
        ('来自', from_addr),
        ('时间', time.strftime('%Y-%m-%d %H:%M:%S',
                               time.localtime(int(received or 0)))),
    ]
    for key, value in meta:
        root.add_widget(MDLabel(
            text='%s：%s' % (key, value), font_name=FONT, font_size='13sp',
            size_hint_y=None, height=dp(22),
            theme_text_color='Secondary' if key != '主题' else 'Primary'))
    scroll = ScrollView(size_hint=(1, None), height=dp(200))
    root.add_widget(scroll)
    msg_box = BoxLayout(orientation='vertical', size_hint_y=None,
                        spacing=dp(4))
    msg_box.bind(minimum_height=msg_box.setter('height'))
    scroll.add_widget(msg_box)
    msg_box.add_widget(MDLabel(
        text=_bidi_safe_text(body or '（空消息）'), font_name=FONT,
        font_size='15sp', size_hint_y=None,
        text_size=(dp(260), None), valign='top'))
    return root
