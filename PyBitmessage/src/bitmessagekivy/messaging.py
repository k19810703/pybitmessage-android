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


def send_message(to_address, body, subject=''):
    """Queue a message exactly like the XML-RPC API does."""
    me = my_address()
    if not me:
        raise RuntimeError('还没有地址')
    helper_sent.insert(
        toAddress=to_address.strip(), fromAddress=me, subject=subject,
        message=body, encoding=2, ttl=4 * 24 * 60 * 60)
    queues.workerQueue.put(('sendmessage', ''))


def inbox(limit=50):
    """Newest first: (from, subject, body, received)."""
    rows = sqlQuery(
        'SELECT fromaddress, subject, message, received FROM inbox '
        'ORDER BY received DESC LIMIT ?', limit)
    return [(_text(r[0]), _text(r[1]), _text(r[2]), r[3]) for r in rows]


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

    def _build_ui(self):
        root = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))

        # header: my address
        header = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        self.addr_label = self._label('我的地址：加载中…', size=14, bold=True)
        copy_btn = Button(text='复制', font_name=FONT, font_size=dp(13),
                          size_hint=(None, 1), width=dp(64))
        copy_btn.bind(on_release=lambda *_: self._copy_address())
        header.add_widget(self.addr_label)
        header.add_widget(copy_btn)
        root.add_widget(header)

        # inbox
        root.add_widget(self._label('收件箱', size=13, color=(.4, .4, .4, 1),
                                    height=dp(22)))
        self.inbox_box = BoxLayout(orientation='vertical', size_hint_y=None,
                                   spacing=dp(4))
        self.inbox_box.bind(minimum_height=self.inbox_box.setter('height'))
        scroll = ScrollView(size_hint=(1, .45))
        scroll.add_widget(self.inbox_box)
        root.add_widget(scroll)

        # compose
        root.add_widget(self._label('收件人地址', size=13,
                                    color=(.4, .4, .4, 1), height=dp(22)))
        self.to_input = TextInput(
            hint_text='BM-2c…', multiline=False, font_name=FONT,
            font_size=dp(14), size_hint_y=None, height=dp(42))
        root.add_widget(self.to_input)

        root.add_widget(self._label('内容', size=13, color=(.4, .4, .4, 1),
                                    height=dp(22)))
        self.body_input = TextInput(
            hint_text='输入要发送的内容…', multiline=True, font_name=FONT,
            font_size=dp(15))
        root.add_widget(self.body_input)

        self.send_btn = Button(text='发送', font_name=FONT, font_size=dp(16),
                               size_hint_y=None, height=dp(46))
        self.send_btn.bind(on_release=lambda *_: self._on_send())
        root.add_widget(self.send_btn)

        self.status = self._label('', size=13, color=(.1, .5, .1, 1),
                                  height=dp(24))
        root.add_widget(self.status)

        self.add_widget(root)

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
        if addr:
            Clipboard.copy(addr)
            self._set_status('地址已复制')

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

        def worker():
            try:
                send_message(to_addr, body)
            except Exception as exc:  # noqa: BLE001
                Clock.schedule_once(
                    lambda *_: self._after_send('发送失败：%s' % exc), 0)
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
        for from_addr, subject, body, _received in messages:
            item = BoxLayout(orientation='vertical', size_hint_y=None,
                             height=dp(66), spacing=dp(2))
            title = subject or (body[:24] + ('…' if len(body) > 24 else ''))
            item.add_widget(self._label(title, size=14, bold=True,
                                        height=dp(24)))
            item.add_widget(self._label('来自 %s' % from_addr, size=11,
                                        color=(.45, .45, .45, 1),
                                        height=dp(18)))
            item.add_widget(self._label(body[:120], size=12, height=dp(20)))
            self.inbox_box.add_widget(item)
