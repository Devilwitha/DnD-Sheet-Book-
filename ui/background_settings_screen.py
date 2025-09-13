import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from utils.helpers import (
    load_settings, save_settings, apply_background, apply_styles_to_widget,
    create_styled_popup
)

class BackgroundSettingsScreen(Screen):
    """
    Screen for managing background settings.
    """
    def __init__(self, **kwargs):
        super(BackgroundSettingsScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        self.load_and_apply_settings()

    def load_and_apply_settings(self):
        settings = load_settings()
        self.ids.background_switch.active = settings.get('background_enabled', True)

    def on_background_toggle(self, value):
        settings = load_settings()
        settings['background_enabled'] = value
        save_settings(settings)
        for screen in self.manager.screens:
            apply_background(screen)

    def show_background_chooser(self, setting_key):
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

    def show_popup(self, title, message):
        # This is a helper method that might be needed.
        # It can be removed if not used.
        popup = create_styled_popup(title=title, content=Label(text=message), size_hint=(0.7, 0.5))
        popup.open()

    def go_back(self):
        self.manager.current = 'settings'
