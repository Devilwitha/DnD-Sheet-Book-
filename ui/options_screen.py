
import sys
import logging
from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.properties import StringProperty
from utils.helpers import (
    apply_styles_to_widget, apply_background
)

logger = logging.getLogger(__name__)

class OptionsScreen(Screen):
    """Main options screen, providing navigation to other sub-menus."""
    status_message = StringProperty("")

    def __init__(self, **kwargs):
        super(OptionsScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        logger.debug("OptionsScreen initialized")

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        logger.debug("OptionsScreen entered")

    def go_to_screen(self, screen_name):
        logger.info(f"Navigating to screen: {screen_name}")
        self.app.change_screen(screen_name)

    def go_back(self):
        logger.info("Going back from OptionsScreen")
        self.app.go_back_screen()
