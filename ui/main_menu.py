from kivy.uix.screenmanager import Screen
from kivy.app import App
from utils.helpers import apply_background, apply_styles_to_widget

class MainMenu(Screen):
    """Hauptmenü-Bildschirm."""
    def __init__(self, **kwargs):
        super(MainMenu, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        """Wird ausgeführt, bevor der Bildschirm angezeigt wird."""
        apply_background(self)
        apply_styles_to_widget(self)

    def go_to_screen(self, screen_name):
        self.app.change_screen(screen_name)
