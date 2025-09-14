import os
import sys
import subprocess

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

from utils.helpers import (
    apply_styles_to_widget, apply_background, create_styled_popup,
    load_settings, save_settings
)


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
        self.show_popup("Neustart erforderlich", "Die Änderung an der Bildschirmtastatur\nwird nach einem Neustart der Anwendung wirksam.")

    def shutdown_system(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Möchten Sie das System wirklich herunterfahren?'))
        btn_layout = BoxLayout(spacing=10)
        yes_btn = Button(text="Ja", on_press=self.do_shutdown, height=80, font_size='20sp')
        no_btn = Button(text="Nein", on_press=lambda x: self.confirmation_popup.dismiss(), height=80, font_size='20sp')
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
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Wählen Sie den Branch für das Update:', height=80, font_size='20sp'))
        btn_layout = BoxLayout(spacing=10)
        main_btn = Button(text="Main", on_press=lambda x: self._start_update('main'), height=80, font_size='20sp')
        beta_btn = Button(text="Beta", on_press=lambda x: self._start_update('beta'), height=80, font_size='20sp')
        btn_layout.add_widget(main_btn)
        btn_layout.add_widget(beta_btn)
        content.add_widget(btn_layout)
        cancel_btn = Button(text="Abbrechen", on_press=lambda x: self.branch_popup.dismiss(), height=80, font_size='20sp')
        content.add_widget(cancel_btn)
        apply_styles_to_widget(content)
        self.branch_popup = create_styled_popup(title="Update Branch wählen", content=content, size_hint=(0.6, 0.6))
        self.branch_popup.open()

    def _start_update(self, branch):
        self.branch_popup.dismiss()
        self.popup = create_styled_popup(title='Update', content=Label(text=f'Update für Branch "{branch}" wird gestartet...'), size_hint=(0.6, 0.4))
        self.popup.auto_dismiss = False
        self.popup.open()
        Clock.schedule_once(lambda dt: self._run_update_script(branch), 0.1)

    def _run_update_script(self, branch):
        try:
            self.popup.content.text = "Updater wird gestartet...\nDie Anwendung wird sich nun schließen."
            subprocess.Popen([sys.executable, "utils/updater.py", branch])
            Clock.schedule_once(lambda x: App.get_running_app().stop(), 0.5)
        except Exception as e:
            self.popup.content.text = f"Fehler beim Starten des Updaters:\n{e}"
            Clock.schedule_once(lambda x: self.popup.dismiss(), 5)

    def restart_app_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Möchten Sie die Anwendung wirklich neustarten?'))
        btn_layout = BoxLayout(spacing=10)
        yes_btn = Button(text="Ja", on_press=self.do_restart, height=80, font_size='20sp')
        no_btn = Button(text="Nein", on_press=lambda x: self.confirmation_popup.dismiss(), height=80, font_size='20sp')
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
        yes_btn = Button(text="Ja", on_press=self.do_restart_system, height=80, font_size='20sp')
        no_btn = Button(text="Nein", on_press=lambda x: self.confirmation_popup.dismiss(), height=80, font_size='20sp')
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

    def _get_wifi_status(self):
        if not sys.platform.startswith('linux'):
            return "N/A", "N/A"
        try:
            result = subprocess.check_output(['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL', 'dev', 'wifi'], encoding='utf-8')
            for line in result.strip().split('\n'):
                if line.startswith('yes:'):
                    parts = line.split(':')
                    return parts[1], f"{parts[2]}%"
        except Exception as e:
            print(f"Error getting wifi status with nmcli: {e}")
            try:
                result = subprocess.check_output(['iwconfig'], encoding='utf-8')
                ssid, signal = "Not Connected", "0"
                for line in result.split('\n'):
                    if "ESSID:" in line:
                        ssid = line.split('ESSID:"')[1].split('"')[0]
                    if "Signal level=" in line:
                        signal_dbm = int(line.split('Signal level=')[1].split(' dBm')[0])
                        signal = str(2 * (signal_dbm + 100)) if -100 <= signal_dbm <= -50 else "100" if signal_dbm > -50 else "0"
                return ssid, f"{signal}%"
            except Exception as e_iw:
                print(f"Error getting wifi status with iwconfig: {e_iw}")
                return "Error", "Error"
        return "Not Connected", "0%"

    def show_wifi_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Wifi Status'))
        ssid, signal = self._get_wifi_status()
        self.wifi_status_label = Label(text=f'SSID: {ssid}\nSignal: {signal}')
        content.add_widget(self.wifi_status_label)
        refresh_button = Button(text="Refresh Status", size_hint_y=None, height=50, on_press=self.refresh_wifi_status)
        content.add_widget(refresh_button)
        scan_button = Button(text="Scan for networks", size_hint_y=None, height=50, on_press=self.scan_for_wifi)
        content.add_widget(scan_button)
        close_button = Button(text="Close", size_hint_y=None, height=50)
        self.wifi_popup = create_styled_popup(title="Wifi Settings", content=content, size_hint=(0.8, 0.8))
        close_button.bind(on_press=self.wifi_popup.dismiss)
        content.add_widget(close_button)
        self.wifi_popup.open()

    def refresh_wifi_status(self, instance):
        ssid, signal = self._get_wifi_status()
        self.wifi_status_label.text = f'SSID: {ssid}\nSignal: {signal}'

    def scan_for_wifi(self, instance):
        if not sys.platform.startswith('linux'):
            self.show_popup("Error", "WiFi scanning is only available on Linux.")
            return
        try:
            result = subprocess.check_output(['nmcli', '-t', '-f', 'SSID,SIGNAL', 'dev', 'wifi', 'list', '--rescan', 'yes'], encoding='utf-8')
            networks = [line.split(':') for line in result.strip().split('\n')]
        except Exception as e:
            print(f"Error scanning for wifi: {e}")
            self.show_popup("Error", "Could not scan for WiFi networks.\nPlease ensure 'nmcli' is installed.")
            return
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for ssid, signal in networks:
            if ssid:
                btn = Button(text=f"{ssid} ({signal}%)", size_hint_y=None, height=40, on_press=lambda x, ssid=ssid: self._prompt_for_password(ssid))
                grid.add_widget(btn)
        scroll.add_widget(grid)
        content.add_widget(scroll)
        close_button = Button(text="Close", size_hint_y=None, height=50)
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
        button_layout = BoxLayout(spacing=10, size_hint_y=None, height=50)
        button_layout.add_widget(connect_button)
        button_layout.add_widget(cancel_button)
        content.add_widget(button_layout)
        password_popup = create_styled_popup(title="Password", content=content, size_hint=(0.7, 0.5))
        def connect(instance):
            password = password_input.text
            password_popup.dismiss()
            self._connect_to_wifi(ssid, password)
        connect_button.bind(on_press=connect)
        cancel_button.bind(on_press=password_popup.dismiss)
        password_popup.open()

    def _connect_to_wifi(self, ssid, password):
        try:
            command = ['nmcli', 'dev', 'wifi', 'connect', ssid]
            if password:
                command.extend(['password', password])
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            self.show_popup("Success", f"Successfully connected to {ssid}")
            self.refresh_wifi_status(None)
        except Exception as e:
            print(f"Error connecting to wifi: {e}")
            self.show_popup("Error", f"Failed to connect to {ssid}.\nSee console for details.")
