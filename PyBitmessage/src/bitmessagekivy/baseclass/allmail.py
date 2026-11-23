# pylint: disable=import-error, no-name-in-module
# pylint: disable=unused-argument, no-member, attribute-defined-outside-init

"""
allmail.py
==============

All mails are managed in allmail screen
"""

import logging

from kivy.clock import Clock
from kivy.properties import ListProperty, StringProperty
from kivy.uix.screenmanager import Screen
from kivy.app import App

from pybitmessage.bitmessagekivy.baseclass.common import (
    show_limited_cnt, empty_screen_label, kivy_state_variables,
)

logger = logging.getLogger('default')


class AllMails(Screen):
    """AllMails Screen for Kivy UI"""
    data = ListProperty()
    has_refreshed = True
    all_mails = ListProperty()
    account = StringProperty()
    label_str = 'No messages for this account.'

    def __init__(self, *args, **kwargs):
        """Initialize the AllMails screen."""
        super().__init__(*args, **kwargs)  # pylint: disable=missing-super-argument
        self.kivy_state = kivy_state_variables()
        self._initialize_selected_address()
        Clock.schedule_once(self.init_ui, 0)

    def _initialize_selected_address(self):
        """Initialize the selected address from the identity list."""
        if not self.kivy_state.selected_address and App.get_running_app().identity_list:
            self.kivy_state.selected_address = App.get_running_app().identity_list[0]

    def init_ui(self, dt=0):
        """Initialize the UI by loading the message list."""
        self.load_message_list()
        logger.debug("UI initialized after %s seconds.", dt)

    def load_message_list(self):
        """Load every folder (inbox + sent + draft + trash) into the list."""
        self.account = self.kivy_state.selected_address
        from pybitmessage.bitmessagekivy.baseclass.mail_list import (
            render, show_detail)
        # render() returns the rows, so all_mails reflects reality (it used to
        # stay an empty ListProperty, which made _update_mail_count() take the
        # empty branch and paint "暂无消息" over the rows we had just added).
        self.all_mails = render(self, 'all', on_tap=show_detail)
        self.queryreturn = self.all_mails
        self.ids.tag_label.text = '全部邮件' if self.all_mails else ''
        self._update_mail_count()

    def _update_mail_count(self):
        """Update the badge with the real row count.

        The empty state is drawn by render(), so nothing is added here -- the
        old code appended an empty-screen label straight into ids.ml, which
        hid the messages.
        """
        count = len(self.all_mails or [])
        self.kivy_state.all_count = str(count)
        self.set_all_mail_count(count)

    def on_pre_enter(self, *args):
        """Reload whenever the screen is opened."""
        try:
            self.load_message_list()
        except Exception as exc:  # noqa: BLE001
            print('ALLMAIL refresh failed: %r' % (exc,), flush=True)

    @staticmethod
    def set_all_mail_count(count):
        """Set the message count for all mails."""
        allmail_count_widget = App.get_running_app().root.ids.content_drawer.ids.allmail_cnt
        allmail_count_widget.ids.badge_txt.text = show_limited_cnt(int(count))
