from kivy.uix.screenmanager import Screen
from kivy.app import App
from utils.helpers import apply_background, apply_styles_to_widget

class VersionScreen(Screen):
    """Screen to display version information."""
    def __init__(self, **kwargs):
        super(VersionScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        self.ids.version_label.text = self.get_version_info()

    def get_version_info(self):
        """Reads version information from version.txt."""
        try:
            with open("version.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return "version.txt nicht gefunden"
        except Exception as e:
            return f"Fehler: {e}"

    def go_back(self):
        self.app.go_back_screen()
