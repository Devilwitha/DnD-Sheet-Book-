import os
import sys
import platform
from kivy.uix.screenmanager import Screen
from kivy.core.window import Window
from utils.helpers import apply_background, apply_styles_to_widget

class InfoScreen(Screen):
    """Bildschirm zur Anzeige von Systeminformationen."""

    def on_pre_enter(self, *args):
        """Wird beim Betreten des Bildschirms aufgerufen. Lädt und zeigt die Systeminfos an."""
        self.load_info()
        apply_background(self)
        apply_styles_to_widget(self)

    def load_info(self):
        """Sammelt die Systeminformationen und aktualisiert die Labels."""
        self.ids.raspberry_model.text = f"Raspberry Pi Modell: {self.get_raspberry_pi_model()}"
        self.ids.os_version.text = f"Betriebssystem: {self.get_os_version()}"
        self.ids.resolution.text = f"Auflösung: {self.get_screen_resolution()}"
        self.ids.folder_size.text = f"Größe des App-Ordners: {self.get_folder_size()} MB"
        self.ids.version_info.text = self.get_version_info()

    def get_version_info(self):
        """Liest die Versionsinformationen aus der version.txt-Datei."""
        try:
            with open("version.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return "version.txt nicht gefunden"
        except Exception as e:
            return f"Fehler: {e}"

    def get_raspberry_pi_model(self):
        """Liest das Raspberry Pi Modell aus /proc/cpuinfo."""
        if sys.platform.startswith('linux'):
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if line.startswith('Model'):
                            return line.split(':')[1].strip()
            except FileNotFoundError:
                return "N/A (nicht auf Raspberry Pi)"
        return "N/A (nicht auf Linux)"

    def get_os_version(self):
        """Gibt die Betriebssystemversion zurück."""
        return f"{platform.system()} {platform.release()}"

    def get_screen_resolution(self):
        """Gibt die Bildschirmauflösung zurück."""
        return f"{Window.width}x{Window.height}"

    def get_folder_size(self):
        """Berechnet die Größe des aktuellen Ordners."""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk('.'):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        return round(total_size / (1024 * 1024), 2)  # Umrechnung in MB
