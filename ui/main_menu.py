from kivy.uix.screenmanager import Screen
from utils.helpers import apply_background, apply_styles_to_widget

class MainMenu(Screen):
    """Hauptmenü-Bildschirm."""
    def __init__(self, **kwargs):
        super(MainMenu, self).__init__(**kwargs)

    def on_pre_enter(self, *args):
        """Wird ausgeführt, bevor der Bildschirm angezeigt wird."""
        apply_background(self)
        apply_styles_to_widget(self)

    def switch_to_options(self):
        self.manager.current = 'options'
