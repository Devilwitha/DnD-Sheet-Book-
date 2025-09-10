import sys
from kivy.uix.screenmanager import Screen
from utils.helpers import (
    apply_styles_to_widget, apply_background
)

class OptionsScreen(Screen):
    """Main options screen, providing navigation to other sub-menus."""
    def __init__(self, **kwargs):
        super(OptionsScreen, self).__init__(**kwargs)

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def switch_to_info(self):
        self.manager.current = 'info'
