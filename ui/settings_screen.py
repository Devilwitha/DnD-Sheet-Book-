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
from kivy.uix.colorpicker import ColorPicker
from kivy.clock import Clock

from utils.helpers import (
    load_settings, save_settings, apply_styles_to_widget, apply_background,
    create_styled_popup
)

class SettingsScreen(Screen):
    """Screen for detailed application settings."""
    def __init__(self, **kwargs):
        super(SettingsScreen, self).__init__(**kwargs)

    def on_pre_enter(self, *args):
        self.load_and_apply_settings()
        apply_background(self)
        apply_styles_to_widget(self)
        if not sys.platform.startswith('linux'):
            # Hide wifi button
            self.ids.wifi_button.size_hint_y = None
            self.ids.wifi_button.height = 0
            self.ids.wifi_button.opacity = 0
            self.ids.wifi_button.disabled = True
        else:
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
        self.ids.font_color_switch.active = settings.get('font_color_enabled', False)
        self.ids.popup_color_switch.active = settings.get('popup_color_enabled', False)
        self.ids.button_font_color_switch.active = settings.get('button_font_color_enabled', False)
        self.ids.button_bg_color_switch.active = settings.get('button_bg_color_enabled', False)


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

    def show_popup(self, title, message):
        popup = create_styled_popup(title=title, content=Label(text=message), size_hint=(0.7, 0.5))
        popup.open()

    def on_font_color_toggle(self, value):
        settings = load_settings()
        settings['font_color_enabled'] = value
        save_settings(settings)
        apply_styles_to_widget(self.manager)

    def on_popup_color_toggle(self, value):
        settings = load_settings()
        settings['popup_color_enabled'] = value
        save_settings(settings)
        # No immediate visual update needed, will apply on next popup

    def on_button_font_color_toggle(self, value):
        settings = load_settings()
        settings['button_font_color_enabled'] = value
        save_settings(settings)
        apply_styles_to_widget(self.manager)

    def on_button_bg_color_toggle(self, value):
        settings = load_settings()
        settings['button_bg_color_enabled'] = value
        save_settings(settings)
        apply_styles_to_widget(self.manager)

    def show_color_picker(self, setting_type):
        settings = load_settings()

        key = f'custom_{setting_type}_color'
        initial_color = settings.get(key, [1, 1, 1, 1])

        color_picker = ColorPicker(color=initial_color)

        content = BoxLayout(orientation='vertical', spacing=10)
        content.add_widget(color_picker)

        save_btn = Button(text="Speichern", size_hint_y=None, height=44)
        content.add_widget(save_btn)

        popup = create_styled_popup(title="Farbe auswählen", content=content, size_hint=(0.8, 0.8))

        def save_color(instance):
            new_color = color_picker.color
            settings[key] = new_color
            save_settings(settings)
            if setting_type in ['font', 'button_font', 'button_bg']:
                apply_styles_to_widget(self.manager)
            popup.dismiss()

        save_btn.bind(on_press=save_color)
        popup.open()

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
        except subprocess.CalledProcessError as e:
            self.show_popup("Error", f"Failed to connect to {ssid}.\n{e.stderr}")
        except FileNotFoundError:
            self.show_popup("Error", "Could not connect to WiFi.\nPlease ensure 'nmcli' is installed.")

    def show_background_options_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)

        main_bg_btn = Button(text="Allgemeiner Hintergrund", size_hint_y=None, height=50)
        creator_bg_btn = Button(text="Charaktererstellung Hintergrund", size_hint_y=None, height=50)
        sheet_bg_btn = Button(text="Charakterbogen Hintergrund", size_hint_y=None, height=50)

        content.add_widget(main_bg_btn)
        content.add_widget(creator_bg_btn)
        content.add_widget(sheet_bg_btn)

        popup = create_styled_popup(title="Hintergrund auswählen", content=content, size_hint=(0.8, 0.5))

        main_bg_btn.bind(on_press=lambda x: [self._show_background_chooser('background_path'), popup.dismiss()])
        creator_bg_btn.bind(on_press=lambda x: [self._show_background_chooser('cs_creator_background_path'), popup.dismiss()])
        sheet_bg_btn.bind(on_press=lambda x: [self._show_background_chooser('cs_sheet_background_path'), popup.dismiss()])

        popup.open()

    def _show_background_chooser(self, setting_key):
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

        popup = create_styled_popup(title="Hintergrundbild auswählen", content=content, size_hint=(0.9, 0.9))

        def select_file(instance):
            if filechooser.selection:
                selected_path = filechooser.selection[0]
                if os.path.isfile(selected_path):
                    settings = load_settings()
                    settings[setting_key] = selected_path
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
