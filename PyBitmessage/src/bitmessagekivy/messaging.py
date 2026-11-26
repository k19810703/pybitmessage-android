"""Minimal Chinese messaging screen: my address, compose, inbox.

This is the demo UI: it talks to the real core (config/helper_sent/queues and
the sqlite inbox), so messages sent here go through the normal encryption and
PoW pipeline, and anything received shows up without extra plumbing.
"""
import os
import threading

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

import helper_sent
import queues
from bmconfigparser import config
from helper_sql import sqlQuery

# Android ships a CJK font in a few possible places; Kivy's default (Roboto)
# renders Chinese as boxes.
_CJK_FONTS = (
    '/system/fonts/NotoSansCJK-Regular.ttc',
    '/system/fonts/NotoSansSC-Regular.otf',
    '/system/fonts/DroidSansFallback.ttf',
    '/system/fonts/NotoSansCJKsc-Regular.otf',
)
FONT = 'Roboto'


def _register_cjk_font():
    """Use a system font that can render Chinese, if one exists."""
    global FONT
    for path in _CJK_FONTS:
        if os.path.exists(path):
            try:
                LabelBase.register(name='CJK', fn_regular=path)
                # Also take over the name the Material widgets use for their
                # theme font. MDLabel/MDTabs ignore a per-widget font_name and
                # render CJK as tofu boxes unless "Roboto" itself points at a
                # font that has the glyphs (HANDOFF §6.2).
                LabelBase.register(name='Roboto', fn_regular=path)
                FONT = 'CJK'
                return
            except Exception:  # noqa: BLE001 - a missing font must not crash
                continue


def _text(value):
    """Normalise whatever sqlite hands back into str."""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode('utf-8', 'replace')
    return '' if value is None else str(value)


def my_address():
    """First enabled address, or None."""
    for addr in config.addresses():
        try:
            if config.safeGetBoolean(addr, 'enabled'):
                return addr
        except Exception:  # noqa: BLE001
            continue
    return None


def create_address(label='phone'):
    """Ask the address generator for a fresh random address (blocking)."""
    queues.apiAddressGeneratorReturnQueue.queue.clear()
    queues.addressGeneratorQueue.put((
        'createRandomAddress', 4, 1, label, 1, '', False, 0, 0))
    return queues.apiAddressGeneratorReturnQueue.get(timeout=120)


def send_message(to_address, body, subject='', from_address=None):
    """Queue a message exactly like the XML-RPC API does.

    *from_address* lets the composer honour its sender dropdown; the worker
    signs with whatever address the ``sent`` row carries.
    """
    me = from_address or my_address()
    if not me:
        raise RuntimeError('还没有地址')
    h = helper_sent.insert(
        toAddress=to_address.strip(), fromAddress=me, subject=subject,
        message=body, encoding=2, ttl=4 * 24 * 60 * 60)
    queues.workerQueue.put(('sendmessage', ''))
    # ackdata identifies this row in the ``sent`` table; following it turns
    # "it never arrived" into "it sat in doingmsgpow" or "it waited for a
    # pubkey that never came".
    try:
        import diag
        diag.watch_sent(h)
    except Exception:  # noqa: BLE001
        pass
    return h


def inbox(limit=50):
    """Newest first: (from, subject, body, received, msgid).

    msgid is the raw blob from sqlite -- keep it as bytes, a str will never
    match the row (M7.1.1).
    """
    rows = sqlQuery(
        'SELECT fromaddress, subject, message, received, msgid FROM inbox '
        "WHERE folder='inbox' ORDER BY received DESC LIMIT ?", limit)
    return [(_text(r[0]), _text(r[1]), _text(r[2]), r[3], r[4])
            for r in rows]


class MessagingScreen(Screen):
    """One screen with everything the demo needs."""

    def __init__(self, **kwargs):
        super(MessagingScreen, self).__init__(**kwargs)
        _register_cjk_font()
        self._build_ui()
        Clock.schedule_once(lambda _dt: self._ensure_address(), 1)
        Clock.schedule_once(lambda _dt: self._prefill_from_intent(), 2)
        Clock.schedule_interval(self.refresh_inbox, 5)

    def _prefill_from_intent(self):
        """Let other apps share an address straight into the composer.

        `adb shell am start -n ... --es to BM-2c...` or any ACTION_SEND with
        the address as an extra pre-fills the recipient field.
        """
        try:
            from jnius import autoclass
            activity = autoclass(
                'org.kivy.android.PythonActivity').mActivity
            intent = activity.getIntent()
            extra = intent.getStringExtra('to')
            if extra:
                self.to_input.text = extra.strip()
                self._set_status('已填入收件人地址')
        except Exception:  # noqa: BLE001 - desktop/tests have no jnius
            pass

    # ---- ui -------------------------------------------------------------
    def _label(self, text, size=15, bold=False, color=(.1, .1, .1, 1),
               height=None, halign='left'):
        lbl = Label(
            text=text, font_name=FONT, font_size=dp(size), bold=bold,
            color=color, halign=halign, valign='middle',
            size_hint_y=None, height=height or dp(28))
        lbl.bind(size=lambda w, *_: setattr(w, 'text_size', (w.width, None)))
        return lbl

    # ---- layout ---------------------------------------------------------
    #: Wider than this and taller than the second value -> two columns.
    #: A tablet in landscape is ~1280x800 dp, a phone in landscape ~800x360 dp:
    #: the height test keeps phones on the single-column layout.
    WIDE_WIDTH = dp(720)
    WIDE_HEIGHT = dp(480)

    def _build_ui(self):
        self._make_widgets()
        self.root_layout = BoxLayout(padding=dp(10), spacing=dp(8))
        self.add_widget(self.root_layout)
        self._wide = None
        self._apply_layout()
        Window.bind(size=self._on_window_resize)

    def _make_widgets(self):
        """Create the widgets once; :meth:`_apply_layout` decides the parents.

        Widgets belong to exactly one parent, so the layout switch reparents
        three *groups* instead of moving individual widgets around.
        """
        # header: my address
        self.header = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        self.addr_label = self._label('我的地址：加载中…', size=14, bold=True)
        copy_btn = Button(text='复制', font_name=FONT, font_size=dp(13),
                          size_hint=(None, 1), width=dp(64))
        copy_btn.bind(on_release=lambda *_: self._copy_address())
        self.header.add_widget(self.addr_label)
        self.header.add_widget(copy_btn)

        # inbox
        self.inbox_group = BoxLayout(orientation='vertical', spacing=dp(4))
        self.inbox_group.add_widget(
            self._label('收件箱', size=13, color=(.4, .4, .4, 1),
                        height=dp(22)))
        self.inbox_box = BoxLayout(orientation='vertical', size_hint_y=None,
                                   spacing=dp(4))
        self.inbox_box.bind(minimum_height=self.inbox_box.setter('height'))
        self.inbox_scroll = ScrollView()
        self.inbox_scroll.add_widget(self.inbox_box)
        self.inbox_group.add_widget(self.inbox_scroll)

        # compose
        self.compose_group = BoxLayout(orientation='vertical', spacing=dp(6))
        self.compose_group.add_widget(
            self._label('收件人地址', size=13, color=(.4, .4, .4, 1),
                        height=dp(22)))
        self.to_input = TextInput(
            hint_text='BM-2c…', multiline=False, font_name=FONT,
            font_size=dp(14), size_hint_y=None, height=dp(42))
        self.compose_group.add_widget(self.to_input)
        self.compose_group.add_widget(
            self._label('内容', size=13, color=(.4, .4, .4, 1), height=dp(22)))
        self.body_input = TextInput(
            hint_text='输入要发送的内容…', multiline=True, font_name=FONT,
            font_size=dp(15))
        self.compose_group.add_widget(self.body_input)
        self.send_btn = Button(text='发送', font_name=FONT, font_size=dp(16),
                               size_hint_y=None, height=dp(46))
        self.send_btn.bind(on_release=lambda *_: self._on_send())
        self.compose_group.add_widget(self.send_btn)
        self.status = self._label('', size=13, color=(.1, .5, .1, 1),
                                  height=dp(24))
        self.compose_group.add_widget(self.status)

    def _on_window_resize(self, _window, _size):
        # Kivy fires several resize events per rotation; coalesce them so the
        # tree is rebuilt once, after the final size is known.
        if getattr(self, '_resize_event', None) is not None:
            self._resize_event.cancel()
        self._resize_event = Clock.schedule_once(self._apply_layout, 0.15)

    def _apply_layout(self, *_args):
        wide = (Window.width >= self.WIDE_WIDTH
                and Window.height >= self.WIDE_HEIGHT)
        if wide == self._wide:
            return
        self._wide = wide

        for group in (self.header, self.inbox_group, self.compose_group):
            if group.parent is not None:
                group.parent.remove_widget(group)
        self.root_layout.clear_widgets()

        if wide:
            # list on the left, composer on the right (M6.3.2)
            self.root_layout.orientation = 'horizontal'
            self.inbox_scroll.size_hint_y = 1
            left = BoxLayout(orientation='vertical', spacing=dp(8),
                             size_hint_x=.44)
            right = BoxLayout(orientation='vertical', spacing=dp(6),
                              size_hint_x=.56)
            left.add_widget(self.header)
            left.add_widget(self.inbox_group)
            right.add_widget(self.compose_group)
            self.root_layout.add_widget(left)
            self.root_layout.add_widget(right)
        else:
            self.root_layout.orientation = 'vertical'
            self.inbox_scroll.size_hint_y = .45
            self.root_layout.add_widget(self.header)
            self.root_layout.add_widget(self.inbox_group)
            self.root_layout.add_widget(self.compose_group)

    # ---- behaviour ------------------------------------------------------
    def _ensure_address(self):
        addr = my_address()
        if addr:
            self.addr_label.text = '我的地址：%s' % addr
            return
        self.addr_label.text = '正在生成地址（首次约需几秒）…'

        def worker():
            try:
                addr = create_address()
            except Exception as exc:  # noqa: BLE001
                self._set_status('地址生成失败：%s' % exc)
                return
            Clock.schedule_once(
                lambda *_: self._on_address_ready(addr), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _on_address_ready(self, addr):
        self.addr_label.text = '我的地址：%s' % addr
        self._set_status('地址已生成，可以发送消息了')

    def _copy_address(self):
        addr = my_address()
        if not addr:
            return
        try:
            # Write to the *system* clipboard too: Kivy's store alone is not
            # visible to WeChat or the browser (and was not even readable by
            # our own paste button, see clipbridge.py).
            from clipbridge import set_text
            set_text(addr)
        except Exception:  # noqa: BLE001
            Clipboard.copy(addr)
        self._set_status('地址已复制')

    def _confirm_delete(self, msgid):
        """Ask before trashing a message, then move it to 回收站 (M7.1.2)."""
        from kivy.uix.popup import Popup

        box = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        box.add_widget(Label(text='移到回收站？', font_name=FONT,
                             font_size=dp(14)))
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        popup = Popup(title='删除消息', title_font=FONT, content=box,
                      size_hint=(.8, .35))

        def do_delete(*_args):
            try:
                import helper_inbox
                helper_inbox.trash(msgid)
                self._set_status('已移到回收站')
                print('INBOX trash msgid=%r' % (msgid[:4],), flush=True)
            except Exception as exc:  # noqa: BLE001
                self._set_status('删除失败：%s' % exc)
                print('INBOX trash failed: %r' % (exc,), flush=True)
            popup.dismiss()
            self.refresh_inbox()

        cancel = Button(text='取消', font_name=FONT, font_size=dp(14))
        ok = Button(text='删除', font_name=FONT, font_size=dp(14))
        cancel.bind(on_release=lambda *_: popup.dismiss())
        ok.bind(on_release=do_delete)
        buttons.add_widget(cancel)
        buttons.add_widget(ok)
        box.add_widget(buttons)
        popup.open()

    def _set_status(self, text):
        self.status.text = text

    def _on_send(self):
        to_addr = self.to_input.text.strip()
        body = self.body_input.text.strip()
        if not to_addr.startswith('BM-'):
            self._set_status('收件人地址格式不对（应以 BM- 开头）')
            return
        if not body:
            self._set_status('内容不能为空')
            return
        self.send_btn.disabled = True
        self._set_status('正在加密并计算 PoW，请稍候…')

        try:
            import diag
            diag.describe_send(to_addr, my_address())
        except Exception:  # noqa: BLE001
            pass

        def worker():
            try:
                send_message(to_addr, body)
            except Exception as exc:  # noqa: BLE001
                # Bind the text now: `exc` is deleted when the except block
                # ends, so a lambda that closed over it would raise NameError
                # instead of showing the reason.
                text = '发送失败：%s' % exc
                Clock.schedule_once(
                    lambda *_: self._after_send(text), 0)
                return
            Clock.schedule_once(
                lambda *_: self._after_send('已提交，正在广播…'), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _after_send(self, message):
        self.send_btn.disabled = False
        self._set_status(message)
        self.body_input.text = ''

    def refresh_inbox(self, _dt=None):
        """Re-render the inbox (called every 5s)."""
        try:
            messages = inbox()
        except Exception as exc:  # noqa: BLE001
            self._set_status('读取收件箱失败：%s' % exc)
            return
        self.inbox_box.clear_widgets()
        if not messages:
            self.inbox_box.add_widget(
                self._label('（暂无消息）', size=13,
                            color=(.6, .6, .6, 1), height=dp(40)))
            return
        for from_addr, subject, body, _received, msgid in messages:
            line = BoxLayout(orientation='horizontal', size_hint_y=None,
                             height=dp(66), spacing=dp(6))
            item = BoxLayout(orientation='vertical', spacing=dp(2))
            title = subject or (body[:24] + ('…' if len(body) > 24 else ''))
            item.add_widget(self._label(title, size=14, bold=True,
                                        height=dp(24)))
            item.add_widget(self._label('来自 %s' % from_addr, size=11,
                                        color=(.45, .45, .45, 1),
                                        height=dp(18)))
            item.add_widget(self._label(body[:120], size=12, height=dp(20)))
            line.add_widget(item)
            delete_btn = Button(text='删除', font_name=FONT, font_size=dp(12),
                                size_hint=(None, 1), width=dp(58))
            delete_btn.bind(on_release=(lambda mid: lambda *_: (
                self._confirm_delete(mid)))(msgid))
            line.add_widget(delete_btn)
            self.inbox_box.add_widget(line)
