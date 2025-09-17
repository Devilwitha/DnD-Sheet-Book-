import os
import sys
import platform
import subprocess
from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.core.window import Window
from utils.helpers import apply_background, apply_styles_to_widget

class ModelScreen(Screen):
    """Screen to display model and other static system information."""
    def __init__(self, **kwargs):
        super(ModelScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        self.load_info()

    def load_info(self):
        self.ids.model.text = f"Modell: {self.get_model()}"
        self.ids.os_version.text = f"Betriebssystem: {self.get_os_version()}"
        self.ids.resolution.text = f"Auflösung: {self.get_screen_resolution()}"
        self.ids.git_branch.text = f"Aktueller Branch: {self.get_git_branch()}"
        self.ids.folder_size.text = f"Größe des App-Ordners: {self.get_folder_size()} MB"

    def get_model(self):
        """Liest das Modell des Systems."""
        if sys.platform.startswith('linux'):
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if line.startswith('Model'):
                            return line.split(':')[1].strip()
            except FileNotFoundError:
                return platform.processor()
        return platform.processor()

    def get_os_version(self):
        """Gibt die Betriebssystemversion zurück."""
        return f"{platform.system()} {platform.release()}"

    def get_screen_resolution(self):
        """Gibt die Bildschirmauflösung zurück."""
        return f"{Window.width}x{Window.height}"

    def get_git_branch(self):
        """Gibt den aktuellen Git-Branch zurück."""
        try:
            return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode('utf-8')
        except Exception:
            return "N/A"

    def get_folder_size(self):
        """Berechnet die Größe des aktuellen Ordners."""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk('.'):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        return round(total_size / (1024 * 1024), 2)  # Umrechnung in MB

    def go_back(self):
        self.app.go_back_screen()
