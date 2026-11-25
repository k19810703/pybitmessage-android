# pylint: disable=too-many-public-methods, unused-variable, too-many-ancestors
# pylint: disable=too-few-public-methods, unused-argument
# pylint: disable=attribute-defined-outside-init, too-many-instance-attributes
# pylint: disable=broad-exception-caught, no-self-use

"""
Bitmessage android(mobile) interface
"""

import logging
import os
import sys
import time
from functools import partial

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivymd.app import MDApp
from kivymd.uix.bottomsheet import MDCustomBottomSheet
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.filemanager import MDFileManager
from kivymd.uix.label import MDLabel
from kivymd.uix.list import IRightBodyTouch
from PIL import Image as PilImage

from pybitmessage.bitmessagekivy import identiconGeneration
from pybitmessage.bitmessagekivy.base_navigation import (
    BaseContentNavigationDrawer, BaseIdentitySpinner, BaseLanguage,
    BaseNavigationDrawerDivider, BaseNavigationDrawerSubheader,
    BaseNavigationItem)
from pybitmessage.bitmessagekivy.baseclass.common import (get_identity_list,
                                                          load_image_path,
                                                          toast)
from pybitmessage.bitmessagekivy.baseclass.popup import (AddAddressPopup,
                                                         AddressChangingLoader,
                                                         AppClosingPopup)
from pybitmessage.bitmessagekivy.get_platform import platform
from pybitmessage.bitmessagekivy.kivy_state import KivyStateVariables
from pybitmessage.bitmessagekivy.load_kivy_screens_data import load_screen_json
from pybitmessage.bitmessagekivy.uikivysignaler import UIkivySignaler
from pybitmessage.bmconfigparser import config  # noqa: F401
from pybitmessage.helper_startup import loadConfig

logger = logging.getLogger('default')

# Define constants for magic numbers
DIALOG_WIDTH_ANDROID = 0.85
DIALOG_WIDTH_OTHER = 0.8
DIALOG_HEIGHT = 0.23
LOADER_DELAY = 1
IMAGE_SIZE = (300, 300)
MAX_LABEL_LENGTH = 15
TRUNCATE_STRING = '...'


# Android ships a CJK font in a few possible places; KivyMD's theme font
# (Roboto) has no Chinese glyphs, so every translated label rendered as a
# tofu box until we swapped the theme font.
_CJK_FONT_CANDIDATES = (
    '/system/fonts/NotoSansCJK-Regular.ttc',
    '/system/fonts/NotoSansSC-Regular.otf',
    '/system/fonts/DroidSansFallback.ttf',
    '/system/fonts/NotoSansCJKsc-Regular.otf',
)
_CJK_FONT_NAME = None


def cjk_font_name():
    """Register and return a CJK-capable font name (cached)."""
    global _CJK_FONT_NAME
    if _CJK_FONT_NAME:
        return _CJK_FONT_NAME
    from kivy.core.text import LabelBase
    for path in _CJK_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                LabelBase.register(name='CJK', fn_regular=path)
                _CJK_FONT_NAME = 'CJK'
                return _CJK_FONT_NAME
            except Exception:  # noqa: BLE001
                continue
    _CJK_FONT_NAME = 'Roboto'
    return _CJK_FONT_NAME


def apply_cjk_theme_font(app):
    """Point KivyMD's whole theme at the CJK font.

    KivyMD widgets (NavigationItem, MDLabel, MDTextField, dialogs...) resolve
    their font through ``theme_cls.font_styles``, entries of the form
    ``[font_name, size, bold, letter_spacing]``. Rewriting element 0 of every
    style makes all MD widgets Chinese-capable at once.

    ``app`` is passed in because MDApp.get_running_app() is not reliably set
    yet while build() runs.
    """
    name = cjk_font_name()
    print('CJK font resolved: %r' % (name,), flush=True)
    try:
        styles = app.theme_cls.font_styles
        changed = 0
        for style in list(styles.keys()):
            # Never touch the icon style: it is ["Icons", 24, ...] and every
            # IconLeftWidget/MDIconButton renders a private-use codepoint from
            # that font. Rewriting it turned all drawer icons into tofu boxes
            # (MDLabel.update_font_style() assigns font_name unconditionally).
            if style == 'Icon':
                continue
            value = styles[style]
            if isinstance(value, (list, tuple)) and value:
                styles[style] = [name] + list(value[1:])
                changed += 1
        print('CJK theme font applied to %d text styles (Icon kept as %r)' % (
            changed, styles.get('Icon', ['?'])[0]), flush=True)
        return True
    except Exception as exc:  # noqa: BLE001 - never block startup
        print('CJK theme font failed: %r' % (exc,), flush=True)
        return False


class Lang(BaseLanguage):
    """UI Language.

    M6: Chinese translation for the whole navigation drawer and the
    dialogs. Upstream never shipped a Kivy translation mechanism (the
    BaseLanguage._() stub returns the text unchanged), so this is a plain
    dictionary lookup -- every string the UI actually renders through
    app.tr._() is listed here. Unmatched strings fall back to English.
    """

    ZH = {
        # --- navigation drawer (main.kv) ---
        'Accounts': '账户',
        'Inbox': '收件箱',
        'Sent': '已发送',
        'Draft': '草稿',
        'Trash': '回收站',
        'All Mails': '全部邮件',
        'Chat': '聊天',
        'All labels': '全部标签',
        'Address Book': '通讯录',
        'Settings': '设置',
        'Payment plan': '付费方案',
        'New address': '新建地址',
        'Network status': '网络状态',
        'My addresses': '我的地址',
        # --- dialogs and forms ---
        'My Addresses': '我的地址',
        'Apply': '应用',
        'Cancel': '取消',
        'OK': '确定',
        'Yes': '是',
        'No': '否',
        'Send': '发送',
        'Send message from': '发件人',
        'Show QR code': '显示二维码',
        'Type or Scan QR code for recipients address': '输入或扫描收件人地址',
        'Enter a label to:generate address for:': '输入标签以生成地址：',
        'Enter a label to generate address for:': '输入标签以生成地址：',
        'Select method to make an address:': '选择生成地址的方式：',
        'Passphrase (deterministic) Generator': '口令（确定性）生成器',
        'Pseudorandom Generator': '伪随机生成器',
        'Proceed Next': '下一步',
        'From :': '发件人：',
        'First message': '第一条消息',
        'No Chat': '暂无聊天',
        'Chats': '聊天',
        'Contacts': '联系人',
        'Reply below Quote': '在引用下方回复',
        'Label': '标签',
        'Address': '地址',
        'Authentication': '身份验证',
        'Username:': '用户名：',
        'Password:': '密码：',
        'Pass:': '密码：',
        'Type:': '类型：',
        'Port:': '端口：',
        'hostname:': '主机名：',
        'Server hostname:': '服务器主机名：',
        'Connect to:': '连接到：',
        'Listening port': '监听端口',
        'Listen for connections on port:': '监听连接的端口：',
        'Listen for incoming connections when using proxy': '使用代理时监听入站连接',
        'Proxy server / Tor': '代理服务器 / Tor',
        'Only connect to onion services(*.onion)': '仅连接洋葱服务（*.onion）',
        'User Interface': '用户界面',
        'Interface Language': '界面语言',
        'Close to tray': '关闭到托盘',
        'Minimize to tray': '最小化到托盘',
        'Tray': '托盘',
        'Start-on-login not yet supported on your OS': '您的操作系统暂不支持开机自启',
        'Show notification when message received': '收到消息时显示通知',
        'Hide connection notifications': '隐藏连接通知',
        'Use identicons': '使用抽象头像',
        'Hardware GPU acceleration (OpenCL):': '硬件 GPU 加速（OpenCL）：',
        'Maximum acceptable total difficulty:': '最大接受总难度：',
        'Total difficulty:': '总难度：',
        'Small message difficulty:': '小消息难度：',
        'Maximum download rate (kB/s):[0:unlimited]': '最大下载速度 (kB/s)：[0：不限]',
        'Maximum upload rate (kB/s):[0:unlimited]': '最大上传速度 (kB/s)：[0：不限]',
        'Maximum outbound connections:[0:none]': '最大出站连接数：[0：无]',
        'Bandwidth limit': '带宽限制',
        'Give up after': '放弃于',
        'days and': '天',
        'objects': '个对象',
        'publickeys': '公钥',
        'Extra-Messages': '额外消息',
        'Total connections': '总连接数',
        'Total Connections': '总连接数',
        'Processes': '进程',
        'Payment': '支付',
        'Available Credits': '可用额度',
        '+Add more credits': '+充值',
        'Brodcast': '广播',
        'person-to-person': '点对点',
        'Namecoind': 'Namecoind',
        'NMControl': 'NMControl',
        'UPnP': 'UPnP',
        'Willingly include unencrypted destination address when sending to a '
        'mobile device': '向移动设备发送时包含未加密的目标地址',
        'In portable Mode, messages and config files are stored in the same '
        'directory as the program rather then the normal application-data '
        'folder. This makes it convenient to run Bitmessage from a USB '
        'thumb drive.': '便携模式下，消息和配置文件与程序存放在同一目录，而非系统'
        '的应用数据目录。这便于从 U 盘运行 Bitmessage。',
        'Leave these input fields blank for the default behavior.': '留空则使用默认行为。',
        # input hints (M6.2.1) -- these were plain English literals in the .kv
        'Search': '搜索',
        'Empty field': '（空）',
        'Subject': '主题',
        'Body': '内容',
        'Type or Select sender address': '输入或选择发件地址',
        'Type or Scan QR code for recipients address': '输入或扫描二维码获取收件地址',
        'Add contact': '添加联系人',
        'Save': '保存',
        'Cancel': '取消',
        'Scan QR code': '扫描二维码',
        'System Setting': '系统设置',
        'Network Settings': '网络设置',
        'Demanded Difficulty': '要求的难度',
        'Max acceptable Difficulty': '可接受的最大难度',
        'Resends Expire': '重发截止',
        'Share logs': '分享日志',
        'Namecoin Integration': 'Namecoin 集成',
        'please enter your text': '请输入内容',
        'To :': '收件人：',
        "Start Bitmessage in the tray(don't show main window)":
            '启动时最小化到托盘（不显示主窗口）',
        "Bitmessage isn't connected to the network.\n If you quit now, it may"
        " cause delivery delays.\n Wait until connected and the"
        " synchronisation finishes?":
            'Bitmessage 还没连上网络。\n现在退出可能导致消息投递延迟。\n'
            '要等连接成功并完成同步吗？',
    }

    def _(self, text):
        """Translate *text* into Chinese; fall back to the original."""
        return self.ZH.get(text, text)


class NavigationItem(BaseNavigationItem):
    """NavigationItem class for kivy Ui"""


class NavigationDrawerDivider(BaseNavigationDrawerDivider):
    """
    A small full-width divider that can be placed
    in the :class:`MDNavigationDrawer`
    """


class NavigationDrawerSubheader(BaseNavigationDrawerSubheader):
    """
    A subheader for separating content in :class:`MDNavigationDrawer`

    Works well alongside :class:`NavigationDrawerDivider`
    """


class ContentNavigationDrawer(BaseContentNavigationDrawer):
    """ContentNavigationDrawer class for kivy Uir"""


class BadgeText(IRightBodyTouch, MDLabel):
    """BadgeText class for kivy Ui"""


class IdentitySpinner(BaseIdentitySpinner):
    """Identity Dropdown in Side Navigation bar"""


def _messages_last_month():
    """Count inbox messages received in the last 30 days (real data)."""
    try:
        from pybitmessage.helper_sql import sqlQuery
        since = int(time.time()) - 30 * 24 * 3600
        rows = sqlQuery(
            'SELECT COUNT(*) FROM inbox WHERE received >= ?', since)
        return int(rows[0][0]) if rows else 0
    except Exception:  # noqa: BLE001 - a dashboard counter must not crash
        return 0


class NavigateApp(MDApp):
    """Navigation Layout of class"""

    kivy_state = KivyStateVariables()
    title = "PyBitmessage"
    identity_list = get_identity_list()
    image_path = load_image_path()
    app_platform = platform
    encrypted_messages_per_month = _messages_last_month()
    tr = Lang("zh")  # M6: Chinese UI (drawer + dialogs)

    def __init__(self):
        super(NavigateApp, self).__init__()
        # workaround for relative imports
        sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
        self.data_screens, self.all_data, self.data_screen_dict, response = load_screen_json()
        self.kivy_state_obj = KivyStateVariables()
        self.image_dir = load_image_path()
        self.kivy_state_obj.screen_density = Window.size
        self.window_size = self.kivy_state_obj.screen_density

    def build(self):
        """Method builds the widget"""
        # M6: swap KivyMD's theme font for a CJK one before any widget is
        # built, otherwise every translated label renders as a tofu box.
        apply_cjk_theme_font(self)
        for kv in self.data_screens:
            Builder.load_file(
                os.path.join(
                    os.path.dirname(__file__),
                    'kv',
                    '{0}.kv'.format(self.all_data[kv]["kv_string"]),
                )
            )
        Window.bind(on_request_close=self.on_request_close)
        root = Builder.load_file(
            os.path.join(os.path.dirname(__file__), 'main.kv'))
        print('BUILD root=%r ids=%r' % (type(root).__name__,
                                        list(root.ids.keys())), flush=True)
        # Demo entry point: the simple Chinese messaging screen is what the
        # Android build shows on start. The original screens stay registered.
        try:
            from bitmessagekivy.messaging import MessagingScreen
            manager = root.ids.scr_mngr
            manager.add_widget(MessagingScreen(name='messaging'))
            manager.current = 'messaging'
        except Exception as exc:  # noqa: BLE001 - never block startup
            print('MESSAGING screen failed to load: %r' % (exc,), flush=True)
        return root

    def set_screen(self, screen_name):
        """Set the screen name when navigate to other screens"""
        manager = self.root.ids.scr_mngr
        print(
            'SETSCREEN: %r available=%r' % (
                screen_name, manager.screen_names), flush=True)
        manager.current = screen_name

    def run(self):
        """Running the widgets"""
        loadConfig()
        kivysignalthread = UIkivySignaler()
        kivysignalthread.daemon = True
        kivysignalthread.start()
        self.kivy_state_obj.kivyui_ready.set()
        super(NavigateApp, self).run()

    def share_logs(self):
        """把打包好的诊断日志交给系统分享（抽屉菜单 → 分享日志）。

        Lives on the app (not on the messaging screen) so it is reachable from
        every page -- the drawer is the only navigation that always exists.
        """
        try:
            import applog
            applog.install()          # idempotent; main.py already did it
        except Exception as exc:      # noqa: BLE001
            toast('日志模块不可用：%s' % exc)
            return

        # A snapshot right before sharing is worth more than the periodic one:
        # it records what the user was seeing when they decided to report.
        try:
            import diag
            diag.log_network('before share')
        except Exception:             # noqa: BLE001
            pass

        try:
            ok, message = applog.share_archive()
        except Exception as exc:      # noqa: BLE001
            ok, message = False, '分享失败：%r' % (exc,)
        if not ok:
            copied, copy_msg = applog.copy_recent_to_clipboard()
            message = '%s；%s' % (message, copy_msg if copied else '')
        toast(message)

    def addingtoaddressbook(self):
        """Dialog for saving address"""
        width = DIALOG_WIDTH_ANDROID if platform == 'android' else DIALOG_WIDTH_OTHER
        self.add_popup = MDDialog(
            title=self.tr._('Add contact'),
            type="custom",
            size_hint=(width, DIALOG_HEIGHT),
            content_cls=AddAddressPopup(),
            buttons=[
                MDRaisedButton(
                    text=self.tr._("Save"),
                    on_release=self.savecontact,
                ),
                MDRaisedButton(
                    text=self.tr._("Cancel"),
                    on_release=self.close_pop,
                ),
                MDRaisedButton(
                    text=self.tr._("Scan QR code"),
                    on_release=self.scan_qr_code,
                ),
            ],
        )
        self.add_popup.auto_dismiss = False
        self.add_popup.open()

    def scan_qr_code(self, instance):
        """this method is used for showing QR code scanner"""
        if self.is_camara_attached():
            self.add_popup.dismiss()
            self.root.ids.id_scanscreen.get_screen(self.root.ids.scr_mngr.current, self.add_popup)
            self.root.ids.scr_mngr.current = 'scanscreen'
        else:
            alert_text = (
                'Currently this feature is not available!'
                if platform == 'android'
                else 'Camera is not available!')
            self.add_popup.dismiss()
            toast(alert_text)

    def is_camara_attached(self):
        """This method is for checking the camera is available or not"""
        self.root.ids.id_scanscreen.check_camera()
        is_available = self.root.ids.id_scanscreen.camera_available
        return is_available

    def savecontact(self, instance):
        """Method is used for saving contacts"""
        popup_obj = self.add_popup.content_cls
        label = popup_obj.ids.label.text.strip()
        address = popup_obj.ids.address.text.strip()
        popup_obj.ids.label.focus = not label
        # default focus on address field
        popup_obj.ids.address.focus = label or not address

    def close_pop(self, instance):
        """Close the popup"""
        self.add_popup.dismiss()
        toast('Canceled')

    def load_my_address_screen(self, action):
        """load_my_address_screen method spin the loader"""
        if len(self.root.ids.id_myaddress.children) <= 2:
            self.root.ids.id_myaddress.children[0].active = action
        else:
            self.root.ids.id_myaddress.children[1].active = action

    def load_screen(self, instance):
        """This method is used for loading screen on every click"""
        if instance.text == 'Inbox':
            self.root.ids.scr_mngr.current = 'inbox'
            self.root.ids.id_inbox.children[1].active = True
        elif instance.text == 'Trash':
            self.root.ids.scr_mngr.current = 'trash'
            try:
                self.root.ids.id_trash.children[1].active = True
            except Exception as e:
                self.root.ids.id_trash.children[0].children[1].active = True
        Clock.schedule_once(partial(self.load_screen_callback, instance), LOADER_DELAY)

    def load_screen_callback(self, instance, dt=0):
        """This method is rotating loader for few seconds"""
        if instance.text == 'Inbox':
            self.root.ids.id_inbox.ids.ml.clear_widgets()
            self.root.ids.id_inbox.loadMessagelist(self.kivy_state_obj.selected_address)
            self.root.ids.id_inbox.children[1].active = False
        elif instance.text == 'Trash':
            self.root.ids.id_trash.clear_widgets()
            self.root.ids.id_trash.add_widget(self.data_screen_dict['Trash'].Trash())
            try:
                self.root.ids.id_trash.children[1].active = False
            except Exception as e:
                self.root.ids.id_trash.children[0].children[1].active = False

    @staticmethod
    def get_enabled_addresses():
        """Getting list of all the enabled addresses"""
        addresses = [addr for addr in config.addresses()
                     if config.getboolean(str(addr), 'enabled')]
        return addresses

    @staticmethod
    def format_address(address):
        """Formatting address"""
        return " ({0})".format(address)

    @staticmethod
    def format_label(label):
        """Formatting label"""
        if label:
            f_name = label.split()
            formatted_label = f_name[0][:MAX_LABEL_LENGTH - 1].capitalize() + TRUNCATE_STRING if len(
                f_name[0]) > MAX_LABEL_LENGTH else f_name[0].capitalize()
            return formatted_label
        return ''

    @staticmethod
    def format_address_and_label(address=None):
        """Getting formatted address information"""
        if not address:
            try:
                address = NavigateApp.get_enabled_addresses()[0]
            except IndexError:
                return ''
        return "{0}{1}".format(
            NavigateApp.format_label(config.get(address, "label")),
            NavigateApp.format_address(address)
        )

    def get_default_account_data(self, instance):
        """Getting Default Account Data"""
        if self.identity_list:
            self.kivy_state_obj.selected_address = first_addr = self.identity_list[0]
            return first_addr
        return 'Select Address'

    def get_current_account_data(self, text):
        """Get Current Address Account Data"""
        if text != '':
            if os.path.exists(os.path.join(
                    self.image_dir, 'default_identicon', '{}.png'.format(text))
            ):
                self.load_selected_image(text)
            else:
                self.set_identicon(text)
                self.root.ids.content_drawer.ids.reset_image.opacity = 0
                self.root.ids.content_drawer.ids.reset_image.disabled = True
            address_label = self.format_address_and_label(text)
            self.root_window.children[1].ids.toolbar.title = address_label
            self.kivy_state_obj.selected_address = text
            AddressChangingLoader().open()
            for nav_obj in self.root.ids.content_drawer.children[
                    0].children[0].children[0].children:
                nav_obj.active = True if nav_obj.text == 'Inbox' else False
            self.file_manager_setting()
            Clock.schedule_once(self.set_current_account_data, 0.5)

    def set_current_account_data(self, dt=0):
        """This method set the current accout data on all the screens"""
        self.root.ids.id_inbox.ids.ml.clear_widgets()
        self.root.ids.id_inbox.loadMessagelist(self.kivy_state_obj.selected_address)

        self.root.ids.id_sent.ids.ml.clear_widgets()
        self.root.ids.id_sent.children[2].children[2].ids.search_field.text = ''
        self.root.ids.id_sent.loadSent(self.kivy_state_obj.selected_address)

    def file_manager_setting(self):
        """This method is for file manager setting"""
        if not self.root.ids.content_drawer.ids.file_manager.opacity and \
                self.root.ids.content_drawer.ids.file_manager.disabled:
            self.root.ids.content_drawer.ids.file_manager.opacity = 1
            self.root.ids.content_drawer.ids.file_manager.disabled = False

    def on_request_close(self, *args):
        """This method is for app closing request"""
        AppClosingPopup().open()
        return True

    def clear_composer(self):
        """If slow down, the new composer edit screen"""
        self.set_navbar_for_composer()
        composer_obj = self.root.ids.id_create.children[1].ids
        composer_obj.ti.text = ''
        composer_obj.composer_dropdown.text = 'Select'
        composer_obj.txt_input.text = ''
        composer_obj.subject.text = ''
        composer_obj.body.text = ''
        self.kivy_state_obj.in_composer = True
        self.kivy_state_obj = False

    def set_navbar_for_composer(self):
        """Clearing toolbar data when composer open"""
        self.root.ids.toolbar.left_action_items = [
            ['arrow-left', lambda x: self.back_press()]]
        self.root.ids.toolbar.right_action_items = [
            ['refresh', self._composer_action('reset_composer')],
            ['send', self._composer_action('send')]]

    def _composer_action(self, method_name):
        """Call a method on the composer, reporting instead of crashing.

        The toolbar used to call ``...children[1].send(self)`` and the
        composer had no ``send`` at all; the AttributeError escaped into
        Kivy's event loop and froze the whole UI. Any failure is now logged
        and swallowed.
        """
        def _action(*_args):
            try:
                composer = self.root.ids.id_create.children[1]
                getattr(composer, method_name)()
            except Exception as exc:  # noqa: BLE001
                print('COMPOSER %s failed: %r' % (method_name, exc),
                      flush=True)
        return _action

    def set_identicon(self, text):
        """Show identicon in address spinner"""
        img = identiconGeneration.generate(text)
        self.root.ids.content_drawer.ids.top_box.children[0].texture = img.texture

    # pylint: disable=import-outside-toplevel
    def file_manager_open(self):
        """This method open the file manager of local system"""
        if not self.kivy_state_obj.file_manager:
            self.file_manager = MDFileManager(
                exit_manager=self.exit_manager,
                select_path=self.select_path,
                ext=['.png', '.jpg']
            )
        self.file_manager.previous = False
        self.file_manager.current_path = '/'
        if platform == 'android':
            # pylint: disable=import-error
            from android.permissions import (Permission, check_permission,
                                             request_permissions)
            if check_permission(Permission.WRITE_EXTERNAL_STORAGE) and \
                    check_permission(Permission.READ_EXTERNAL_STORAGE):
                self.file_manager.show(os.getenv('EXTERNAL_STORAGE'))
                self.kivy_state_obj.manager_open = True
            else:
                request_permissions([
                    Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE
                ])
        else:
            self.file_manager.show(os.environ["HOME"])
            self.kivy_state_obj.manager_open = True

    def select_path(self, path):
        """This method is used to set the select image"""
        try:
            new_image = PilImage.open(path).resize(IMAGE_SIZE)
            if platform == 'android':
                android_path = os.path.join(
                    os.path.join(os.environ['ANDROID_PRIVATE'], 'app', 'images', 'kivy')
                )
                if not os.path.exists(os.path.join(android_path, 'default_identicon')):
                    os.makedirs(os.path.join(android_path, 'default_identicon'))
                new_image.save(os.path.join(android_path, 'default_identicon', '{}.png'.format(
                    self.kivy_state_obj.selected_address))
                )
            else:
                if not os.path.exists(os.path.join(self.image_dir, 'default_identicon')):
                    os.makedirs(os.path.join(self.image_dir, 'default_identicon'))
                new_image.save(os.path.join(self.image_dir, 'default_identicon', '{0}.png'.format(
                    self.kivy_state_obj.selected_address))
                )
            self.load_selected_image(self.kivy_state_obj.selected_address)
            toast('Image changed')
        except Exception:
            toast('Exit')
        self.exit_manager()

    def exit_manager(self, *args):
        """Called when the user reaches the root of the directory tree."""
        self.kivy_state_obj.manager_open = False
        self.file_manager.close()

    def load_selected_image(self, curerent_addr):
        """This method load the selected image on screen"""
        top_box_obj = self.root.ids.content_drawer.ids.top_box.children[0]
        top_box_obj.source = os.path.join(
            self.image_dir,
            'default_identicon',
            '{0}.png'.format(curerent_addr)
        )
        self.root.ids.content_drawer.ids.reset_image.opacity = 1
        self.root.ids.content_drawer.ids.reset_image.disabled = False
        top_box_obj.reload()

    def rest_default_avatar_img(self):
        """set default avatar generated image"""
        self.set_identicon(self.kivy_state_obj.selected_address)
        img_path = os.path.join(
            self.image_dir, 'default_identicon',
            '{}.png'.format(self.kivy_state_obj.selected_address)
        )
        if os.path.exists(img_path):
            os.remove(img_path)
        self.root.ids.content_drawer.ids.reset_image.opacity = 0
        self.root.ids.content_drawer.ids.reset_image.disabled = True
        toast('Avatar reset')

    def get_default_logo(self, instance):
        """Getting default logo image"""
        if self.identity_list:
            first_addr = self.identity_list[0]
            if config.getboolean(str(first_addr), 'enabled'):
                if os.path.exists(
                    os.path.join(
                        self.image_dir, 'default_identicon', '{}.png'.format(first_addr)
                    )
                ):
                    return os.path.join(
                        self.image_dir, 'default_identicon', '{}.png'.format(first_addr)
                    )
                else:
                    img = identiconGeneration.generate(first_addr)
                    instance.texture = img.texture
                    return None
        return os.path.join(self.image_dir, 'drawer_logo1.png')

    @staticmethod
    def have_any_address():
        """Checking existance of any address"""
        if config.addresses():
            return True
        return False

    def reset_login_screen(self):
        """This method is used for clearing the widgets of random screen"""
        if self.root.ids.id_newidentity.ids.add_random_bx.children:
            self.root.ids.id_newidentity.ids.add_random_bx.clear_widgets()

    def reset(self, *args):
        """Set transition direction"""
        self.root.ids.scr_mngr.transition.direction = 'left'
        self.root.ids.scr_mngr.transition.unbind(on_complete=self.reset)

    def back_press(self):
        """Method for, reverting composer to previous page"""
        if self.root.ids.scr_mngr.current == 'showqrcode':
            self.set_common_header()
            self.root.ids.scr_mngr.current = 'myaddress'
        self.root.ids.scr_mngr.transition.bind(on_complete=self.reset)
        self.kivy_state.in_composer = False

    def set_toolbar_for_qr_code(self):
        """This method is use for setting Qr code toolbar."""
        self.root.ids.toolbar.left_action_items = [
            ['arrow-left', lambda x: self.back_press()]]
        self.root.ids.toolbar.right_action_items = []

    def set_common_header(self):
        """Common header for all the Screens"""
        self.root.ids.toolbar.right_action_items = [
            ['account-plus', lambda x: self.addingtoaddressbook()]]
        self.root.ids.toolbar.left_action_items = [
            ['menu', lambda x: self.root.ids.nav_drawer.set_state("toggle")]]
        return

    def open_payment_layout(self, sku):
        """It basically open up a payment layout for kivy UI"""
        pml = PaymentMethodLayout()
        self.product_id = sku
        self.custom_sheet = MDCustomBottomSheet(screen=pml)
        self.custom_sheet.open()

    def initiate_purchase(self, method_name):
        """initiate_purchase module"""
        logger.debug("Purchasing %s through %s", self.product_id, method_name)

    def copy_composer_text(self, text):
        """Copy text to clipboard"""
        Clipboard.copy(text)


class PaymentMethodLayout(BoxLayout):
    """PaymentMethodLayout class for kivy Ui"""


if __name__ == '__main__':
    NavigateApp().run()
