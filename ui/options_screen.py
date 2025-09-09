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

    def load_and_apply_settings(self):
        settings = load_settings()
        self.ids.transparency_slider.value = settings.get('button_transparency', 1.0)
        self.ids.transparency_label.text = f"Button Transparenz: {int(self.ids.transparency_slider.value * 100)}%"
        self.ids.transparency_switch.active = settings.get('transparency_enabled', True)
        self.ids.background_switch.active = settings.get('background_enabled', True)

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

    def show_version_popup(self):
        try:
            with open("version.txt", "r", encoding="utf-8") as f:
                version_info = f.read()
        except FileNotFoundError:
            version_info = "version.txt nicht gefunden."
        except Exception as e:
            version_info = f"Fehler beim Lesen der Version:\n{e}"
        popup = Popup(title="Version", content=Label(text=version_info), size_hint=(0.7, 0.5))
        popup.open()
