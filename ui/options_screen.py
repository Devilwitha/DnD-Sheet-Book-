import os
import sys
import subprocess
import json

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.switch import Switch
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.clock import Clock

from utils.helpers import (
    load_settings, save_settings, apply_styles_to_widget, apply_background
)

class OptionsScreen(Screen):
    """Bildschirm für Optionen, Updates und Versionsanzeige."""
    def __init__(self, **kwargs):
        super(OptionsScreen, self).__init__(**kwargs)

    def on_pre_enter(self, *args):
        self.load_and_apply_settings()
        apply_background(self)
        apply_styles_to_widget(self)

        if not sys.platform.startswith('linux'):
            # Hide shutdown button
            self.ids.shutdown_button.size_hint_y = None
            self.ids.shutdown_button.height = 0
            self.ids.shutdown_button.opacity = 0
            self.ids.shutdown_button.disabled = True
            # Hide update button
            self.ids.update_button.size_hint_y = None
            self.ids.update_button.height = 0
            self.ids.update_button.opacity = 0
            self.ids.update_button.disabled = True
            # Hide wifi button
            self.ids.wifi_button.size_hint_y = None
            self.ids.wifi_button.height = 0
            self.ids.wifi_button.opacity = 0
            self.ids.wifi_button.disabled = True
        else:
            # Ensure buttons are visible on Linux
            self.ids.shutdown_button.size_hint_y = None
            self.ids.shutdown_button.height = 80
            self.ids.shutdown_button.opacity = 1
            self.ids.shutdown_button.disabled = False
            self.ids.update_button.size_hint_y = None
            self.ids.update_button.height = 80
            self.ids.update_button.opacity = 1
            self.ids.update_button.disabled = False
            # Ensure wifi button is visible on Linux
            self.ids.wifi_button.size_hint_y = None
            self.ids.wifi_button.height = 80
            self.ids.wifi_button.opacity = 1
            self.ids.wifi_button.disabled = False


    def load_and_apply_settings(self):
        settings = load_settings()
        self.ids.transparency_slider.value = settings.get('button_transparency', 1.0)
        self.ids.transparency_label.text = f"Button Transparenz: {int(self.ids.transparency_slider.value * 100)}%"
        self.ids.transparency_switch.active = settings.get('transparency_enabled', True)
        self.ids.background_switch.active = settings.get('background_enabled', True)
        self.ids.keyboard_switch.active = settings.get('keyboard_enabled', sys.platform.startswith('linux'))

    def on_transparency_change(self, value):
        settings = load_settings()
        settings['button_transparency'] = value
        save_settings(settings)
        self.ids.transparency_label.text = f"Button Transparenz: {int(value * 100)}%"
        apply_styles_to_widget(self.manager)

    def on_transparency_toggle(self, value):
        settings = load_settings()
        settings['transparency_enabled'] = value
        save_settings(settings)
        apply_styles_to_widget(self.manager)

    def on_background_toggle(self, value):
        settings = load_settings()
        settings['background_enabled'] = value
        save_settings(settings)
        for screen in self.manager.screens:
            apply_background(screen)

    def on_keyboard_toggle(self, value):
        settings = load_settings()
        settings['keyboard_enabled'] = value
        save_settings(settings)
        self.show_popup("Neustart erforderlich", "Die Änderung an der Bildschirmtastatur\nwird nach einem Neustart der Anwendung wirksam.")

    def show_background_chooser_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10)

        initial_path = os.path.abspath(".")

        filechooser = FileChooserListView(path=initial_path, filters=['*.png', '*.jpg', '*.jpeg', '*.bmp'])
        content.add_widget(filechooser)

        button_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)
        select_btn = Button(text="Auswählen")
        cancel_btn = Button(text="Abbrechen")
        button_layout.add_widget(select_btn)
        button_layout.add_widget(cancel_btn)
        content.add_widget(button_layout)

        popup = Popup(title="Hintergrundbild auswählen", content=content, size_hint=(0.9, 0.9))

        def select_file(instance):
            if filechooser.selection:
                selected_path = filechooser.selection[0]
                if os.path.isfile(selected_path):
                    settings = load_settings()
                    settings['background_path'] = selected_path
                    save_settings(settings)
                    popup.dismiss()
                    for screen in self.manager.screens:
                        apply_background(screen)
                else:
                    self.show_popup("Fehler", "Bitte eine Datei auswählen.")
            else:
                self.show_popup("Fehler", "Keine Datei ausgewählt.")

        select_btn.bind(on_press=select_file)
        cancel_btn.bind(on_press=popup.dismiss)

        popup.open()

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
        self.confirmation_popup = Popup(title="Herunterfahren bestätigen", content=content, size_hint=(0.6, 0.5))
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
        popup = Popup(title=title, content=Label(text=message), size_hint=(0.7, 0.5))
        popup.open()

    def update_app(self):
        self.popup = Popup(title='Update', content=Label(text='Suche nach Updates...'), size_hint=(0.6, 0.4), auto_dismiss=False)
        self.popup.open()
        Clock.schedule_once(self._update_task, 0.1)

    def _update_task(self, dt):
        try:
            self.popup.content.text = "Updater wird gestartet...\nDie Anwendung wird sich nun schließen."
            subprocess.Popen([sys.executable, "updater.py"])
            Clock.schedule_once(lambda x: App.get_running_app().stop(), 0.5)
        except Exception as e:
            self.popup.content.text = f"Fehler beim Starten des Updaters:\n{e}"
            Clock.schedule_once(lambda x: self.popup.dismiss(), 5)

    def switch_to_info(self):
        self.manager.current = 'info'

    def _get_wifi_status(self):
        if not sys.platform.startswith('linux'):
            return "N/A", "N/A"

        try:
            # Try with nmcli first
            result = subprocess.check_output(['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL', 'dev', 'wifi'], encoding='utf-8')
            for line in result.strip().split('\n'):
                if line.startswith('yes:'):
                    parts = line.split(':')
                    ssid = parts[1]
                    signal = parts[2]
                    return ssid, f"{signal}%"
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to iwconfig
            try:
                result = subprocess.check_output(['iwconfig'], encoding='utf-8')
                ssid, signal = "Not Connected", "0"
                for line in result.split('\n'):
                    if "ESSID:" in line:
                        ssid = line.split('ESSID:"')[1].split('"')[0]
                    if "Signal level=" in line:
                        # This can be in dBm, need to convert to percentage.
                        # This is a rough approximation.
                        signal_dbm = int(line.split('Signal level=')[1].split(' dBm')[0])
                        if signal_dbm <= -100:
                            signal = "0"
                        elif signal_dbm >= -50:
                            signal = "100"
                        else:
                            signal = str(2 * (signal_dbm + 100))
                return ssid, f"{signal}%"
            except (subprocess.CalledProcessError, FileNotFoundError):
                return "Error", "Error"
        return "Not Connected", "0%"

    def show_wifi_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Wifi Status'))

        ssid, signal = self._get_wifi_status()
        self.wifi_status_label = Label(text=f'SSID: {ssid}\nSignal: {signal}')
        content.add_widget(self.wifi_status_label)

        refresh_button = Button(text="Refresh Status", size_hint_y=None, height=50)
        refresh_button.bind(on_press=self.refresh_wifi_status)
        content.add_widget(refresh_button)

        scan_button = Button(text="Scan for networks", size_hint_y=None, height=50)
        scan_button.bind(on_press=self.scan_for_wifi)
        content.add_widget(scan_button)

        close_button = Button(text="Close", size_hint_y=None, height=50)

        self.wifi_popup = Popup(title="Wifi Settings", content=content, size_hint=(0.8, 0.8))
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
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.show_popup("Error", "Could not scan for WiFi networks.\nPlease ensure 'nmcli' is installed.")
            return

        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        for ssid, signal in networks:
            if ssid: # a ssid can be empty
                btn = Button(text=f"{ssid} ({signal}%)", size_hint_y=None, height=40)
                btn.bind(on_press=lambda x, ssid=ssid: self._prompt_for_password(ssid))
                scroll_content.add_widget(btn)

        scroll_view = ScrollView(size_hint=(1, 1))
        scroll_view.add_widget(scroll_content)
        content.add_widget(scroll_view)

        close_button = Button(text="Close", size_hint_y=None, height=50)

        scan_popup = Popup(title="Available Networks", content=content, size_hint=(0.8, 0.8))
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

        password_popup = Popup(title="Password", content=content, size_hint=(0.7, 0.5))

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
        except subprocess.CalledProcessError as e:
            self.show_popup("Error", f"Failed to connect to {ssid}.\n{e.stderr}")
        except FileNotFoundError:
            self.show_popup("Error", "Could not connect to WiFi.\nPlease ensure 'nmcli' is installed.")

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
        self.confirmation_popup = Popup(title="Neustart bestätigen", content=content, size_hint=(0.6, 0.5))
        self.confirmation_popup.open()

    def do_restart(self, instance):
        self.confirmation_popup.dismiss()
        # Nehmen wir an, die App wird mit "python main.py" gestartet
        os.execv(sys.executable, ['python'] + sys.argv)
