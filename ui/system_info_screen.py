import os
import sys
import platform
import psutil
from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.core.window import Window
from utils.helpers import apply_background, apply_styles_to_widget

class SystemInfoScreen(Screen):
    """Bildschirm zur Anzeige von Systeminformationen."""

    def __init__(self, **kwargs):
        super(SystemInfoScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        """Wird beim Betreten des Bildschirms aufgerufen. Lädt und zeigt die Systeminfos an."""
        self.load_info()
        apply_background(self)
        apply_styles_to_widget(self)

    def load_info(self):
        """Sammelt die Systeminformationen und aktualisiert die Labels."""
        self.ids.raspberry_model.text = f"Modell: {self.get_model()}"
        self.ids.os_version.text = f"Betriebssystem: {self.get_os_version()}"
        self.ids.cpu_usage.text = f"CPU-Auslastung: {self.get_cpu_usage()}"
        self.ids.memory_usage.text = f"RAM-Nutzung: {self.get_memory_usage()}"
        self.ids.disk_usage.text = f"Festplattennutzung: {self.get_disk_usage()}"
        self.ids.resolution.text = f"Auflösung: {self.get_screen_resolution()}"
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

    def get_cpu_usage(self):
        """Gibt die aktuelle CPU-Auslastung in Prozent zurück."""
        return f"{psutil.cpu_percent(interval=1)}%"

    def get_memory_usage(self):
        """Gibt die RAM-Nutzung als 'genutzt / gesamt' in GB zurück."""
        memory = psutil.virtual_memory()
        total_gb = round(memory.total / (1024**3), 2)
        used_gb = round(memory.used / (1024**3), 2)
        return f"{used_gb} GB / {total_gb} GB ({memory.percent}%)"

    def get_disk_usage(self):
        """Gibt die Festplattennutzung als 'genutzt / gesamt' in GB zurück."""
        disk = psutil.disk_usage('/')
        total_gb = round(disk.total / (1024**3), 2)
        used_gb = round(disk.used / (1024**3), 2)
        return f"{used_gb} GB / {total_gb} GB ({disk.percent}%)"

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

    def go_back(self):
        self.app.go_back_screen()
