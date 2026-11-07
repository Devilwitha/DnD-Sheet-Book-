from kivy.metrics import dp
import os
import sys

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

from utils.helpers import (
    apply_styles_to_widget, apply_background, create_styled_popup,
    load_settings, save_settings
)
from utils import wifi


class SystemScreen(Screen):
    """Screen for system-level actions like restart, shutdown, and updates."""
    def __init__(self, **kwargs):
        super(SystemScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        settings = load_settings()
        self.ids.keyboard_switch.active = settings.get('keyboard_enabled', sys.platform.startswith('linux'))

        is_linux = sys.platform.startswith('linux')

        linux_only_buttons = ['shutdown_button', 'restart_button', 'update_button', 'wifi_button']

        for btn_id in linux_only_buttons:
            button = self.ids.get(btn_id)
            if button:
                if is_linux:
                    button.size_hint_y = None
                    button.height = 80
                    button.opacity = 1
                    button.disabled = False
                else:
                    button.size_hint_y = None
                    button.height = 0
                    button.opacity = 0
                    button.disabled = True

    def go_to_screen(self, screen_name):
        self.app.change_screen(screen_name)

    def go_back(self):
        self.app.go_back_screen()

    def open_wifi_settings(self):
        self.show_wifi_popup()

    def toggle_keyboard(self, value):
        settings = load_settings()
        settings['keyboard_enabled'] = value
        save_settings(settings)
        try:
            from kivy.config import Config
            from kivy.core.window import Window
            if value:
                Config.set('kivy', 'keyboard_mode', 'dock')
                Config.set('kivy', 'keyboard_height', '600')
            else:
                Config.set('kivy', 'keyboard_mode', '')
            try:
                Window.release_all_keyboards()
            except Exception:
                pass
        except Exception:
            pass

        self.show_popup("Hinweis", "Die Änderung an der Bildschirmtastatur wurde angewendet (falls unterstützt).")

    def shutdown_system(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Möchten Sie das System wirklich herunterfahren?'))
        btn_layout = BoxLayout(spacing=10)
        yes_btn = Button(text="Ja", on_press=self.do_shutdown, height=dp(80), font_size='20sp')
        no_btn = Button(text="Nein", on_press=lambda x: self.confirmation_popup.dismiss(), height=dp(80), font_size='20sp')
        btn_layout.add_widget(yes_btn)
        btn_layout.add_widget(no_btn)
        content.add_widget(btn_layout)
        apply_styles_to_widget(content)
        self.confirmation_popup = create_styled_popup(title="Herunterfahren bestätigen", content=content, size_hint=(0.6, 0.5))
        self.confirmation_popup.open()

    def do_shutdown(self, instance):
        self.confirmation_popup.dismiss()
        try:
            if sys.platform == "win32":
                os.system("shutdown /s /t 1")
            elif sys.platform.startswith('linux'):
                os.system("shutdown now")
            else:
                self.show_popup("Nicht unterstützt", f"Herunterfahren wird auf '{sys.platform}' nicht unterstützt.")
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Herunterfahren:\n{e}")

    def show_popup(self, title, message):
        popup = create_styled_popup(title=title, content=Label(text=message), size_hint=(0.7, 0.5))
        popup.open()

    def update_app(self):
        """Local builds are updated manually; never stop the app or spawn git."""
        message = (
            "Dies ist ein lokaler Build.\n"
            "Updates müssen manuell mit dem Installer durchgeführt werden\n"
            "(install_on_pi.sh bzw. install_on_Linux_Debian.sh).\n"
            "Die Anwendung wird nicht automatisch aktualisiert."
        )
        self.show_popup("Update", message)

    def restart_app_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Möchten Sie die Anwendung wirklich neustarten?'))
        btn_layout = BoxLayout(spacing=10)
        yes_btn = Button(text="Ja", on_press=self.do_restart, height=dp(80), font_size='20sp')
        no_btn = Button(text="Nein", on_press=lambda x: self.confirmation_popup.dismiss(), height=dp(80), font_size='20sp')
        btn_layout.add_widget(yes_btn)
        btn_layout.add_widget(no_btn)
        content.add_widget(btn_layout)
        apply_styles_to_widget(content)
        self.confirmation_popup = create_styled_popup(title="Neustart bestätigen", content=content, size_hint=(0.6, 0.5))
        self.confirmation_popup.open()

    def do_restart(self, instance):
        self.confirmation_popup.dismiss()
        os.execv(sys.executable, ['python'] + sys.argv)

    def restart_system(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Möchten Sie das System wirklich neustarten?'))
        btn_layout = BoxLayout(spacing=10)
        yes_btn = Button(text="Ja", on_press=self.do_restart_system, height=dp(80), font_size='20sp')
        no_btn = Button(text="Nein", on_press=lambda x: self.confirmation_popup.dismiss(), height=dp(80), font_size='20sp')
        btn_layout.add_widget(yes_btn)
        btn_layout.add_widget(no_btn)
        content.add_widget(btn_layout)
        apply_styles_to_widget(content)
        self.confirmation_popup = create_styled_popup(title="Neustart bestätigen", content=content, size_hint=(0.6, 0.5))
        self.confirmation_popup.open()

    def do_restart_system(self, instance):
        self.confirmation_popup.dismiss()
        try:
            if sys.platform.startswith('linux'):
                os.system("sudo reboot now")
            else:
                self.show_popup("Nicht unterstützt", f"Neustart wird auf '{sys.platform}' nicht unterstützt.")
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Neustarten:\n{e}")

    # ------------------------------------------------------------------
    # WiFi (all nmcli work runs in background threads; UI updates are
    # scheduled onto the main thread with Clock.schedule_once)
    # ------------------------------------------------------------------
    def _to_ui(self, func, *args):
        Clock.schedule_once(lambda dt: func(*args), 0)

    def show_wifi_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Wifi Status'))
        self.wifi_status_label = Label(text='SSID: ...\nSignal: ...')
        content.add_widget(self.wifi_status_label)
        refresh_button = Button(text="Refresh Status", size_hint_y=None, height=dp(50), on_press=self.refresh_wifi_status)
        content.add_widget(refresh_button)
        scan_button = Button(text="Scan for networks", size_hint_y=None, height=dp(50), on_press=self.scan_for_wifi)
        content.add_widget(scan_button)
        close_button = Button(text="Close", size_hint_y=None, height=dp(50))
        self.wifi_popup = create_styled_popup(title="Wifi Settings", content=content, size_hint=(0.8, 0.8))
        close_button.bind(on_press=self.wifi_popup.dismiss)
        content.add_widget(close_button)
        self.wifi_popup.open()
        self.refresh_wifi_status(None)

    def refresh_wifi_status(self, instance):
        if hasattr(self, 'wifi_status_label'):
            self.wifi_status_label.text = 'SSID: ...\nSignal: ...'
        wifi.run_in_background(
            wifi.get_status,
            lambda result, error: self._to_ui(self._apply_wifi_status, result, error))

    def _apply_wifi_status(self, result, error):
        label = getattr(self, 'wifi_status_label', None)
        if label is None:
            return
        if error:
            label.text = f'SSID: -\nSignal: {error}'
            return
        ssid, signal = result
        if ssid is None:
            label.text = 'SSID: Not Connected\nSignal: 0%'
        elif signal is None:
            label.text = f'SSID: {ssid}\nSignal: N/A'
        else:
            label.text = f'SSID: {ssid}\nSignal: {signal}%'

    def scan_for_wifi(self, instance):
        if not sys.platform.startswith('linux'):
            self.show_popup("Error", "WiFi scanning is only available on Linux.")
            return
        self._scan_progress = create_styled_popup(
            title="WiFi", content=Label(text="Scanning..."), size_hint=(0.6, 0.4))
        self._scan_progress.open()
        wifi.run_in_background(
            wifi.scan,
            lambda result, error: self._to_ui(self._show_scan_results, result, error))

    def _show_scan_results(self, networks, error):
        progress = getattr(self, '_scan_progress', None)
        if progress is not None:
            progress.dismiss()
        if error:
            self.show_popup("Error", f"Could not scan for WiFi networks.\n{error}")
            return
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for ssid, signal in networks:
            btn = Button(text=f"{ssid} ({signal}%)", size_hint_y=None, height=dp(48),
                         on_press=lambda x, ssid=ssid: self._prompt_for_password(ssid))
            grid.add_widget(btn)
        scroll.add_widget(grid)
        content.add_widget(scroll)
        close_button = Button(text="Close", size_hint_y=None, height=dp(50))
        scan_popup = create_styled_popup(title="Available Networks", content=content, size_hint=(0.8, 0.8))
        close_button.bind(on_press=scan_popup.dismiss)
        content.add_widget(close_button)
        scan_popup.open()

    def _prompt_for_password(self, ssid):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=f"Enter password for {ssid}"))
        password_input = TextInput(multiline=False, password=True)
        content.add_widget(password_input)
        connect_button = Button(text="Connect")
        cancel_button = Button(text="Cancel")
        button_layout = BoxLayout(spacing=10, size_hint_y=None, height=dp(50))
        button_layout.add_widget(connect_button)
        button_layout.add_widget(cancel_button)
        content.add_widget(button_layout)
        password_popup = create_styled_popup(title="Password", content=content, size_hint=(0.7, 0.5))

        def connect(instance):
            password = password_input.text
            password_input.text = ''
            password_popup.dismiss()
            self._connect_to_wifi(ssid, password)

        connect_button.bind(on_press=connect)
        cancel_button.bind(on_press=password_popup.dismiss)
        password_popup.open()

    def _connect_to_wifi(self, ssid, password):
        wifi.run_in_background(
            wifi.connect,
            lambda result, error: self._to_ui(self._on_wifi_connected, ssid, error),
            ssid, password)

    def _on_wifi_connected(self, ssid, error):
        if error:
            self.show_popup("Error", f"Failed to connect to {ssid}.\n{error}")
            return
        self.show_popup("Success", f"Successfully connected to {ssid}")
        self.refresh_wifi_status(None)
