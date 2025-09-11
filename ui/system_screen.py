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

from utils.helpers import (
    apply_styles_to_widget, apply_background, create_styled_popup
)


class SystemScreen(Screen):
    """Screen for system-level actions like restart, shutdown, and updates."""

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

        if not sys.platform.startswith('linux'):
            # Hide shutdown button
            self.ids.shutdown_button.size_hint_y = None
            self.ids.shutdown_button.height = 0
            self.ids.shutdown_button.opacity = 0
            self.ids.shutdown_button.disabled = True
            # Hide restart button
            self.ids.restart_button.size_hint_y = None
            self.ids.restart_button.height = 0
            self.ids.restart_button.opacity = 0
            self.ids.restart_button.disabled = True
            # Hide update button
            self.ids.update_button.size_hint_y = None
            self.ids.update_button.height = 0
            self.ids.update_button.opacity = 0
            self.ids.update_button.disabled = True
        else:
            # Ensure buttons are visible on Linux
            self.ids.shutdown_button.size_hint_y = None
            self.ids.shutdown_button.height = 80
            self.ids.shutdown_button.opacity = 1
            self.ids.shutdown_button.disabled = False
            self.ids.restart_button.size_hint_y = None
            self.ids.restart_button.height = 80
            self.ids.restart_button.opacity = 1
            self.ids.restart_button.disabled = False
            self.ids.update_button.size_hint_y = None
            self.ids.update_button.height = 80
            self.ids.update_button.opacity = 1
            self.ids.update_button.disabled = False

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
        self.popup = create_styled_popup(title='Update', content=Label(text='Suche nach Updates...'), size_hint=(0.6, 0.4))
        self.popup.auto_dismiss = False
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
