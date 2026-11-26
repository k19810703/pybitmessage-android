# pylint: disable=unused-argument, consider-using-f-string, too-many-ancestors
# pylint: disable=no-member, no-name-in-module, too-few-public-methods, no-name-in-module
"""
    Message composer screen UI
"""

import logging

from kivy.app import App
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
)
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen

from kivymd.uix.textfield import MDTextField

from pybitmessage import state
from pybitmessage.bitmessagekivy.get_platform import platform
from pybitmessage.bitmessagekivy.baseclass.common import (
    toast, kivy_state_variables, composer_common_dialog
)

logger = logging.getLogger('default')


class Create(Screen):
    """Creates Screen class for kivy Ui"""

    def __init__(self, **kwargs):
        """Getting Labels and address from addressbook"""
        super(Create, self).__init__(**kwargs)
        self.kivy_running_app = App.get_running_app()
        self.kivy_state = kivy_state_variables()
        self.dropdown_widget = DropDownWidget()
        self.dropdown_widget.ids.txt_input.starting_no = 2
        self.add_widget(self.dropdown_widget)
        # 发件地址默认取第一个身份：以前是个空输入框，用户得手打自己地址
        # （M7.2.1）。下拉框仍然可以改。
        self._apply_defaults()
        self.children[0].ids.id_scroll.bind(scroll_y=self.check_scroll_y)

    def _apply_defaults(self, *_args):
        """Pick the sender once the identity list actually has entries.

        This screen is not a ScreenManager child, so ``on_pre_enter`` never
        fires (the dropdown stayed at "Select" on device). identity_list is
        filled asynchronously by the core, so poll briefly and also react to
        later changes.
        """
        try:
            app = App.get_running_app()
            if app is not None and not getattr(self, '_bound_identities', False):
                app.bind(identity_list=lambda *_: self._apply_defaults())
                self._bound_identities = True
        except Exception:  # noqa: BLE001
            pass
        tries = getattr(self, '_default_tries', 0)
        try:
            self.dropdown_widget.select_default_sender()
            self.dropdown_widget.refresh_candidates()
        except Exception as exc:  # noqa: BLE001
            print('COMPOSER defaults: %r' % (exc,), flush=True)
        if getattr(self, '_default_tries', 0) is not None:
            self._default_tries = tries + 1
        # keep trying for the first ~15s in case the core is still starting
        if self._default_tries < 30 and (
                (self.dropdown_widget.ids.composer_dropdown.text or 'Select')
                == 'Select'):
            Clock.schedule_once(self._apply_defaults, 0.5)

    def on_pre_enter(self, *args):
        """Apply the default sender every time the screen is shown.

        identity_list is filled by the core asynchronously, so doing this only
        in __init__ left the dropdown showing "Select" (seen on device).
        """
        try:
            self.dropdown_widget.select_default_sender()
            self.dropdown_widget.refresh_candidates()
        except Exception as exc:  # noqa: BLE001 - never block the screen
            print('COMPOSER on_pre_enter: %r' % (exc,), flush=True)

    def check_scroll_y(self, instance, somethingelse):  # pylint: disable=unused-argument
        """show data on scroll down"""
        if self.children[1].ids.composer_dropdown.is_open:
            self.children[1].ids.composer_dropdown.is_open = False


class RV(RecycleView):
    """Recycling View class for kivy Ui"""

    def __init__(self, **kwargs):
        """Recycling Method"""
        super(RV, self).__init__(**kwargs)


class SelectableRecycleBoxLayout(
    FocusBehavior, LayoutSelectionBehavior, RecycleBoxLayout
):
    """Adds selection and focus behaviour to the view"""
    # pylint: disable = duplicate-bases


class DropDownWidget(BoxLayout):
    """DropDownWidget class for kivy Ui"""

    # pylint: disable=too-many-statements

    txt_input = ObjectProperty()
    rv = ObjectProperty()

    def __init__(self, **kwargs):
        super(DropDownWidget, self).__init__(**kwargs)
        self.kivy_running_app = App.get_running_app()
        self.kivy_state = kivy_state_variables()

    @staticmethod
    def callback_for_msgsend(dt=0):  # pylint: disable=unused-argument
        """Callback method for messagesend"""
        state.kivyapp.root.ids.id_create.children[0].active = False
        state.in_sent_method = True
        state.kivyapp.back_press()
        toast("sent")

    def select_default_sender(self):
        """Point the sender at the first enabled identity (no typing needed)."""
        identities = list(getattr(self.kivy_running_app, 'identity_list', []) or [])
        if not identities:
            try:
                try:
                    from bmconfigparser import config
                except ImportError:      # package-style import inside the APK
                    from pybitmessage.bmconfigparser import config
                identities = [str(addr) for addr in config.addresses()
                              if config.getboolean(str(addr), 'enabled')]
            except Exception as exc:  # noqa: BLE001
                print('COMPOSER fallback failed: %r' % (exc,), flush=True)
                identities = []
        if not identities:
            self.ids.ti.text = ''
            return
        current = (self.ids.composer_dropdown.text or '').strip()
        chosen = current if current in identities else identities[0]
        self.ids.composer_dropdown.text = chosen
        self.ids.ti.text = chosen
        print('COMPOSER sender=%s (of %d)' % (chosen, len(identities)),
              flush=True)

    def pick_contact(self):
        """Pick a recipient from the address book (M7.6).

        The button to the right of the recipient field used to paste; the user
        asked for it to open the address book instead, and to leave pasting to
        the system long-press menu.
        """
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.popup import Popup
        from kivy.uix.scrollview import ScrollView

        self.refresh_candidates()
        entries = list(getattr(self, 'candidates', []))
        try:
            from pybitmessage.bitmessagekivy.baseclass.mail_list import cjk_font
            font = cjk_font()
        except Exception:  # noqa: BLE001
            font = 'Roboto'

        box = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(6))
        popup = Popup(title='从通讯录选择收件人', title_font=font, content=box,
                      size_hint=(.92, .75))
        scroll = ScrollView()
        listing = BoxLayout(orientation='vertical', size_hint_y=None,
                            spacing=dp(2))
        listing.bind(minimum_height=listing.setter('height'))

        if not entries:
            listing.add_widget(Label(
                text='通讯录是空的，先用右上角「添加联系人」加一个',
                font_name=font, size_hint_y=None, height=dp(48)))
        for item in entries:
            btn = Button(text=item['text'], font_name=font, font_size=dp(13),
                         size_hint_y=None, height=dp(46),
                         halign='left', valign='middle')
            btn.bind(size=lambda w, *_a: setattr(
                w, 'text_size', (w.width - dp(12), None)))
            btn.bind(on_release=(lambda addr, pop: (
                lambda *_: (self._set_recipient(addr), pop.dismiss())))(
                    item['address'], popup))
            listing.add_widget(btn)

        scroll.add_widget(listing)
        box.add_widget(scroll)
        close = Button(text='取消', font_name=font, font_size=dp(14),
                       size_hint_y=None, height=dp(44))
        close.bind(on_release=lambda *_: popup.dismiss())
        box.add_widget(close)
        popup.open()

    def _set_recipient(self, address):
        """Fill the recipient field with a bare address."""
        self.ids.txt_input.text = address
        print('COMPOSER picked %s' % address, flush=True)
        try:
            self.ids.txt_input.focus = True
        except Exception:  # noqa: BLE001
            pass

    def paste_recipient(self):
        """Paste the clipboard into the recipient field.

        Long-press bubble paste is unreliable with the on-device keyboard
        (reported M7.2.2), so the field gets an explicit button.
        """
        try:
            # Kivy's clipboard is empty on this device; go through Android's
            # ClipboardManager first (see clipbridge.py).
            try:
                from clipbridge import get_text
            except ImportError:
                from pybitmessage.clipbridge import get_text
            text = (get_text() or '').strip()
            print('COMPOSER paste: %d chars' % len(text), flush=True)
        except Exception as exc:  # noqa: BLE001 - clipboard may be unavailable
            toast('读取剪贴板失败：%s' % exc)
            return
        if not text:
            toast('剪贴板是空的')
            return
        # A pasted share text may be "address" or "label <address>": keep the
        # first token that looks like an address.
        for token in text.replace('\n', ' ').split():
            if token.startswith('BM-'):
                self.ids.txt_input.text = token
                break
        else:
            self.ids.txt_input.text = text.split()[0] if text.split() else text
        self.ids.txt_input.focus = True

    def refresh_candidates(self):
        """Build the recipient picker: address book first, then our addresses.

        The old version stuffed "label address" strings into word_list and
        matched them by *prefix of the whole string*, so typing "BM-2c" filtered
        every address-book entry out and only our own addresses survived --
        which is why the list looked useless (reported 2026-11-26).
        """
        candidates = []
        try:
            from helper_sql import sqlQuery
            for label, address in sqlQuery(
                    'SELECT label, address FROM addressbook'):
                label = label.decode('utf-8', 'replace') if isinstance(
                    label, (bytes, bytearray)) else str(label or '')
                address = address.decode('utf-8', 'replace') if isinstance(
                    address, (bytes, bytearray)) else str(address or '')
                if not address:
                    continue
                short = '%s…%s' % (address[:8], address[-4:]) \
                    if len(address) > 16 else address
                text = '%s   %s' % (label or '（无标签）', short)
                candidates.append({
                    'text': text, 'address': address, 'label': label})
        except Exception as exc:  # noqa: BLE001 - empty book is fine
            print('COMPOSER addressbook: %r' % (exc,), flush=True)
        for address in (getattr(self.kivy_running_app, 'identity_list', []) or []):
            if any(item['address'] == address for item in candidates):
                continue
            candidates.append({
                'text': '（我的地址）   %s' % (
                    '%s…%s' % (address[:8], address[-4:])
                    if len(address) > 16 else address),
                'address': address, 'label': ''})
        self.candidates = candidates
        self.ids.txt_input.word_list = [item['text'] for item in candidates]
        print('COMPOSER candidates=%d' % len(candidates), flush=True)

    def send(self, *args):
        """Send the composed message from the toolbar paper-plane.

        ``send`` used to be defined on SelectableLabel (the suggestion list
        row), so the toolbar's ``DropDownWidget.send`` call raised
        AttributeError and the button did nothing at all (user report
        2026-11-26). It lives here now, where the toolbar actually looks.
        """
        to_addr = (self.ids.txt_input.text or '').strip()
        sender = (self.ids.ti.text or '').strip()
        subject = (self.ids.subject.text or '').strip()
        body = (self.ids.body.text or '').strip()
        if not to_addr.startswith('BM-'):
            self._notify('收件人地址应以 BM- 开头')
            return False
        if not body:
            self._notify('内容不能为空')
            return False
        try:
            from pybitmessage.bitmessagekivy.messaging import send_message
            send_message(to_addr, body, subject, from_address=sender or None)
        except Exception as exc:  # noqa: BLE001 - report, never crash
            print('COMPOSER send failed: %r' % (exc,), flush=True)
            self._notify('发送失败：%s' % (exc,))
            return False
        print('COMPOSER send to=%s from=%s len(body)=%d' % (
            to_addr, sender or 'primary', len(body)), flush=True)
        self._notify('已提交，正在广播…')
        # leave the composer so the user can see it is gone
        try:
            from kivy.app import App
            from kivy.clock import Clock
            Clock.schedule_once(
                lambda *_a: App.get_running_app().back_press(), 1.2)
        except Exception:  # noqa: BLE001
            pass
        return True

    @staticmethod
    def _notify(text):
        """Toast if available; a failure here must not break sending."""
        try:
            from pybitmessage.bitmessagekivy.baseclass.common import toast
            toast(text)
        except Exception:  # noqa: BLE001
            print('COMPOSER notify: %s' % text, flush=True)

    def reset_composer(self):
        """Method will reset composer"""
        self.ids.ti.text = ""
        self.select_default_sender()
        self.ids.txt_input.text = ""
        self.ids.subject.text = ""
        self.ids.body.text = ""
        toast("Reset message")

    def auto_fill_fromaddr(self):
        """Mirror the chosen sender into the read-only display."""
        self.ids.ti.text = self.ids.composer_dropdown.text

    def is_camara_attached(self):
        """Checks the camera availability in device"""
        self.parent.parent.parent.ids.id_scanscreen.check_camera()
        is_available = self.parent.parent.parent.ids.id_scanscreen.camera_available
        return is_available

    @staticmethod
    def camera_alert():
        """Show camera availability alert message"""
        feature_unavailable = 'Currently this feature is not available!'
        cam_not_available = 'Camera is not available!'
        alert_text = feature_unavailable if platform == 'android' else cam_not_available
        composer_common_dialog(alert_text)


class MyTextInput(MDTextField):
    """MyTextInput class for kivy Ui"""

    txt_input = ObjectProperty()
    flt_list = ObjectProperty()
    rv = ObjectProperty(None)
    word_list = ListProperty()
    starting_no = NumericProperty(3)
    suggestion_text = ''

    def __init__(self, **kwargs):
        """Getting Text Input."""
        super(MyTextInput, self).__init__(**kwargs)
        self.__lineBreak__ = 0

    def on_text(self, instance, value):  # pylint: disable=unused-argument
        """Filter the recipient suggestions as the user types."""
        self._render_suggestions(value)

    def on_focus(self, _instance, focused):
        """Refresh the candidate list whenever the field is entered.

        The address book can change while the app runs, and an empty list used
        to leave the suggestion box on screen doing nothing.
        """
        if not focused:
            return
        try:
            self.parent.parent  # noqa: B018 - ensure we are in the tree
            app = App.get_running_app()
            create = app.root.ids.id_create
            create.children[0].refresh_candidates()
        except Exception:  # noqa: BLE001 - never break typing
            pass
        self._render_suggestions(self.text or '')

    def _render_suggestions(self, value):
        """Keep the inline suggestion box collapsed.

        Recipients are picked from the address-book dialog now; the inline list
        only confused people, so it stays hidden.
        """
        rv = self.rv
        if rv is not None:
            rv.data = []
            rv.height = 0
            rv.opacity = 0
            rv.disabled = True
        return
        """Show matching candidates, or collapse the box when there are none."""
        rv = self.rv
        if rv is None:
            return
        value = (value or '').strip()
        try:
            owner = App.get_running_app().root.ids.id_create.children[0]
            candidates = getattr(owner, 'candidates', [])
        except Exception:  # noqa: BLE001
            candidates = []
        from kivy.metrics import dp as _dp
        max_rows = 6
        row_height = _dp(30)
        if not candidates:
            matches = [{'text': t, 'address': t} for t in (self.word_list or [])]
        elif not value:
            # nothing typed yet: offer the whole address book
            matches = candidates[:max_rows]
        else:
            lowered = value.lower()
            matches = [
                item for item in candidates
                if item['address'].lower().startswith(lowered)
                or lowered in (item.get('label') or '').lower()
            ][:max_rows]
        rv.data = matches
        if not matches:
            rv.height = 0
            rv.opacity = 0
            rv.disabled = True
            return
        rv.height = row_height * len(matches)
        rv.opacity = 1
        rv.disabled = False

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        """Keyboard on key Down"""
        if self.suggestion_text and keycode[1] == 'tab' and modifiers is None:
            self.insert_text(self.suggestion_text + ' ')
            return True
        return super(MyTextInput, self).keyboard_on_key_down(
            window, keycode, text, modifiers)


class SelectableLabel(RecycleDataViewBehavior, Label):
    """Add selection support to the Label"""

    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)

    def refresh_view_attrs(self, rv, index, data):
        """Catch and handle the view changes"""
        self.index = index
        return super(SelectableLabel, self).refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):  # pylint: disable=inconsistent-return-statements
        """Add selection on touch down"""
        if super(SelectableLabel, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        """Respond to the selection of items in the view"""
        self.selected = is_selected
        if is_selected:
            logger.debug("selection changed to %s", rv.data[index])
            entry = rv.data[index]
            # insert the bare address, never the "label  address" display text
            value = entry.get('address') or entry.get('text', '')
            rv.parent.txt_input.text = value
            rv.parent.txt_input.focus = True

