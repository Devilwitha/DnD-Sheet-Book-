import sys
from kivy.uix.screenmanager import Screen
from kivy.app import App
from utils.helpers import (
    apply_styles_to_widget, apply_background
)

class OptionsScreen(Screen):
    """Main options screen, providing navigation to other sub-menus."""
    def __init__(self, **kwargs):
        super(OptionsScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def go_to_screen(self, screen_name):
        self.app.change_screen(screen_name)

    def go_back(self):
        self.app.go_back_screen()
