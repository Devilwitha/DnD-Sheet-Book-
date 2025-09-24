from kivy.utils import platform
from kivy.uix.screenmanager import Screen
from kivy.app import App
from utils.helpers import apply_background, apply_styles_to_widget

class InfoMenuScreen(Screen):
    """Screen with buttons to navigate to Model, Version, and System info screens."""
    def __init__(self, **kwargs):
        super(InfoMenuScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        if platform == 'android':
            if self.ids.system_info_button.parent:
                self.ids.button_layout.remove_widget(self.ids.system_info_button)

    def go_to_screen(self, screen_name):
        self.app.change_screen(screen_name)

    def go_back(self):
        self.app.go_back_screen()
