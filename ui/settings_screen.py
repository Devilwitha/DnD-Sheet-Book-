import sys
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from utils.helpers import (
    load_settings, save_settings, apply_styles_to_widget, apply_background,
    create_styled_popup
)

class SettingsScreen(Screen):
    """Screen for detailed application settings."""
    def __init__(self, **kwargs):
        super(SettingsScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        self.load_and_apply_settings()
        apply_background(self)
        apply_styles_to_widget(self)
        if not sys.platform.startswith('linux'):
            self.ids.wifi_button.size_hint_y = None
            self.ids.wifi_button.height = 0
            self.ids.wifi_button.opacity = 0
            self.ids.wifi_button.disabled = True
        else:
            self.ids.wifi_button.size_hint_y = None
            self.ids.wifi_button.height = 80
            self.ids.wifi_button.opacity = 1
            self.ids.wifi_button.disabled = False

    def go_back(self):
        # source_screen is not reliably set, so we go back to options
        self.app.change_screen('options')

    def load_and_apply_settings(self):
        settings = load_settings()
        self.ids.background_switch.active = settings.get('background_enabled', True)
        self.ids.keyboard_switch.active = settings.get('keyboard_enabled', sys.platform.startswith('linux'))

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
        create_styled_popup(
            title="Neustart erforderlich",
            content=Label(text="Die Änderung an der Bildschirmtastatur\nwird nach einem Neustart der Anwendung wirksam."),
            size_hint=(0.7, 0.5)
        ).open()
