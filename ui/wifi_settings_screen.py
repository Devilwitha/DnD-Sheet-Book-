from kivy.uix.screenmanager import Screen
from kivy.app import App
from utils.helpers import apply_background, apply_styles_to_widget

import sys
import subprocess
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from utils.helpers import create_styled_popup

class WifiSettingsScreen(Screen):
    """Screen for wifi settings."""
    def __init__(self, **kwargs):
        super(WifiSettingsScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.wifi_status_label = Label()
        self.wifi_popup = None
        self.scan_popup = None
        self.password_popup = None


    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        self.refresh_wifi_status(None)

    def go_back(self):
        self.app.change_screen('settings')

    def _get_wifi_status(self):
        if not sys.platform.startswith('linux'):
            return "N/A", "N/A"
        try:
            result = subprocess.check_output(['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL', 'dev', 'wifi'], encoding='utf-8')
            for line in result.strip().split('\n'):
                if line.startswith('yes:'):
                    return line.split(':')[1], f"{line.split(':')[2]}%"
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "Error", "Error"
        return "Not Connected", "0%"

    def refresh_wifi_status(self, instance):
        ssid, signal = self._get_wifi_status()
        self.ids.wifi_status_label.text = f'SSID: {ssid}\nSignal: {signal}'

    def scan_for_wifi(self, instance):
        if not sys.platform.startswith('linux'):
            create_styled_popup(title="Error", content=Label(text="WiFi scanning is only available on Linux."), size_hint=(0.6, 0.4)).open()
            return
        try:
            result = subprocess.check_output(['nmcli', '-t', '-f', 'SSID,SIGNAL', 'dev', 'wifi', 'list', '--rescan', 'yes'], encoding='utf-8')
            networks = [line.split(':') for line in result.strip().split('\n')]
        except (subprocess.CalledProcessError, FileNotFoundError):
            create_styled_popup(title="Error", content=Label(text="Could not scan for WiFi networks.\nPlease ensure 'nmcli' is installed."), size_hint=(0.6, 0.4)).open()
            return

        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))
        for ssid, signal in networks:
            if ssid:
                btn = Button(text=f"{ssid} ({signal}%)", size_hint_y=None, height=40)
                btn.bind(on_press=lambda x, ssid=ssid: self._prompt_for_password(ssid))
                scroll_content.add_widget(btn)
        scroll_view = ScrollView(size_hint=(1, 1))
        scroll_view.add_widget(scroll_content)
        content.add_widget(scroll_view)
        close_button = Button(text="Close", size_hint_y=None, height=50)
        self.scan_popup = create_styled_popup(title="Available Networks", content=content, size_hint=(0.8, 0.8))
        close_button.bind(on_press=self.scan_popup.dismiss)
        content.add_widget(close_button)
        self.scan_popup.open()

    def _prompt_for_password(self, ssid):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=f"Enter password for {ssid}"))
        password_input = TextInput(multiline=False, password=True)
        content.add_widget(password_input)
        connect_button = Button(text="Connect")
        cancel_button = Button(text="Cancel")
        button_layout = BoxLayout(spacing=10, size_hint_y=None, height=50)
        button_layout.add_widget(connect_button)
        button_layout.add_widget(cancel_button)
        content.add_widget(button_layout)
        self.password_popup = create_styled_popup(title="Password", content=content, size_hint=(0.7, 0.5))
        def connect(instance):
            password = password_input.text
            self.password_popup.dismiss()
            self._connect_to_wifi(ssid, password)
        connect_button.bind(on_press=connect)
        cancel_button.bind(on_press=self.password_popup.dismiss)
        self.password_popup.open()

    def _connect_to_wifi(self, ssid, password):
        try:
            command = ['nmcli', 'dev', 'wifi', 'connect', ssid]
            if password:
                command.extend(['password', password])
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            create_styled_popup(title="Success", content=Label(text=f"Successfully connected to {ssid}")).open()
            self.refresh_wifi_status(None)
        except subprocess.CalledProcessError as e:
            create_styled_popup(title="Error", content=Label(text=f"Failed to connect to {ssid}.\n{e.stderr}")).open()
        except FileNotFoundError:
            create_styled_popup(title="Error", content=Label(text="Could not connect to WiFi.\nPlease ensure 'nmcli' is installed.")).open()
