# pylint: disable=unused-argument, consider-using-f-string, import-error, attribute-defined-outside-init
# pylint: disable=unnecessary-comprehension, no-member, no-name-in-module, too-few-public-methods

"""
    Trash screen
"""

from kivy.properties import (
    ListProperty,
    StringProperty
)
from kivy.uix.screenmanager import Screen
from kivy.app import App

from pybitmessage.bitmessagekivy.baseclass.common import kivy_state_variables


class Trash(Screen):
    """Trash Screen class for kivy Ui"""

    trash_messages = ListProperty()
    has_refreshed = True
    delete_index = None
    table_name = StringProperty()
    no_msg_found_str = "Yet no trashed message for this account!"

    def on_pre_enter(self, *args):
        """Load the Trash folder whenever the screen is opened.

        Upstream never loaded anything here at all -- the screen had no query
        and no render path.
        """
        from pybitmessage.bitmessagekivy.baseclass.mail_list import (
            render, show_detail)
        try:
            self.trash_messages = render(
                self, 'trash', on_tap=show_detail,
                actions=[('恢复', self._undelete), ('彻底删除', self._purge)])
        except Exception as exc:  # noqa: BLE001
            print('TRASH refresh failed: %r' % (exc,), flush=True)

    def _undelete(self, row):
        """Put a trashed message back into the inbox (M7.1.3)."""
        try:
            from pybitmessage.helper_inbox import undeleteMessage
            undeleteMessage(row['msgid'])
            print('TRASH undelete %s' % (row.get('table'),), flush=True)
        except Exception as exc:  # noqa: BLE001
            print('TRASH undelete failed: %r' % (exc,), flush=True)
        self.on_pre_enter()

    def _purge(self, row):
        """Delete a trashed message for good, after confirmation."""
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.popup import Popup
        from kivy.metrics import dp
        from pybitmessage.bitmessagekivy.baseclass.mail_list import cjk_font

        font = cjk_font()
        box = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        box.add_widget(Label(
            text='彻底删除后无法恢复，确定吗？', font_name=font,
            font_size=dp(14)))
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        popup = Popup(title='彻底删除', title_font=font, content=box,
                      size_hint=(.8, .35))

        def do_delete(*_args):
            try:
                from pybitmessage.helper_inbox import delete
                delete(row['msgid'])
                print('TRASH purge %s' % (row.get('table'),), flush=True)
            except Exception as exc:  # noqa: BLE001
                print('TRASH purge failed: %r' % (exc,), flush=True)
            popup.dismiss()
            self.on_pre_enter()

        cancel = Button(text='取消', font_name=font, font_size=dp(14))
        ok = Button(text='彻底删除', font_name=font, font_size=dp(14))
        cancel.bind(on_release=lambda *_: popup.dismiss())
        ok.bind(on_release=do_delete)
        buttons.add_widget(cancel)
        buttons.add_widget(ok)
        box.add_widget(buttons)
        popup.open()

    def __init__(self, *args, **kwargs):
        """Trash method, delete sent message and add in Trash"""
        super(Trash, self).__init__(*args, **kwargs)
        self.kivy_state = kivy_state_variables()
        if self.kivy_state.selected_address == '':
            if App.get_running_app().identity_list:
                self.kivy_state.selected_address = App.get_running_app().identity_list[0]
