from kivy.uix.screenmanager import Screen
from kivy.app import App
from pathlib import Path
from utils.helpers import apply_background, apply_styles_to_widget, resource_path

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
        """Read the release version and bundled project attribution."""
        try:
            version_path = Path(resource_path("version.txt"))
            info = version_path.read_text(encoding="utf-8").strip()
            credits_path = version_path.with_name("CREDITS.txt")
            if credits_path.is_file():
                info += "\n\n" + credits_path.read_text(encoding="utf-8").strip()
            return info
        except FileNotFoundError:
            return "version.txt nicht gefunden"
        except Exception as e:
            return f"Fehler: {e}"

    def go_back(self):
        self.app.go_back_screen()

    def export_logs(self):
        from utils.diagnostics import export_diagnostics, record_error
        from utils.helpers import create_styled_popup
        from kivy.uix.label import Label
        from kivy.utils import platform
        try:
            path = export_diagnostics()
            if platform == 'android':
                from utils.android_export import save_document
                save_document(path, self._export_done)
            else:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy(path)
                self._export_done('Diagnose-ZIP erstellt. Der Dateipfad wurde kopiert:\n' + path)
        except Exception as error:
            record_error('export_logs', error)
            self._export_done('Diagnose konnte nicht exportiert werden.')

    def _export_done(self, message):
        from utils.helpers import create_styled_popup
        from kivy.uix.label import Label
        create_styled_popup('Diagnose', Label(text=message), size_hint=(0.9, 0.65)).open()
