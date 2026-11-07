import os
import sys
import subprocess
import json

from kivy.app import App
from kivy.uix.screenmanager import Screen
from utils.helpers import apply_background, apply_styles_to_widget

class SettingsScreen(Screen):
    """Screen for detailed application settings."""
    def __init__(self, **kwargs):
        super(SettingsScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def go_back(self):
        self.app.go_back_screen()

    def open_background_settings(self):
        self.app.change_screen('background_settings')

    def open_customization_settings(self):
        self.app.change_screen('customization_settings')
