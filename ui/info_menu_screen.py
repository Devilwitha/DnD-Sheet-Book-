
import sys
import os
import logging
from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.properties import StringProperty
from utils.helpers import apply_background, apply_styles_to_widget

logger = logging.getLogger(__name__)

class InfoMenuScreen(Screen):
    """Screen with buttons to navigate to Model, Version, and System info screens."""
    status_message = StringProperty("")

    def __init__(self, **kwargs):
        super(InfoMenuScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        logger.debug("InfoMenuScreen initialized")

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        logger.debug("InfoMenuScreen entered")
        if sys.platform == 'linux' and os.environ.get('ANDROID_ARGUMENT'):
            if self.ids.system_info_button.parent:
                self.ids.button_layout.remove_widget(self.ids.system_info_button)

    def go_to_screen(self, screen_name):
        logger.info(f"Navigating to screen: {screen_name}")
        self.app.change_screen(screen_name)

    def go_back(self):
        logger.info("Going back from InfoMenuScreen")
        self.app.go_back_screen()
