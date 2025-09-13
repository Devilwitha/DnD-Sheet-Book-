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
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def go_back(self):
        if self.app.source_screen:
            self.app.change_screen(self.app.source_screen)
        else:
            self.app.change_screen('options') # Fallback

    def open_background_settings(self):
        self.manager.current = 'background_settings'

    def open_customization_settings(self):
        self.manager.current = 'customization_settings'

    def show_popup(self, title, message):
        popup = create_styled_popup(title=title, content=Label(text=message), size_hint=(0.7, 0.5))
        popup.open()
