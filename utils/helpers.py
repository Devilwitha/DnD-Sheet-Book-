import os
import json
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle

SETTINGS_FILE = 'settings.json'

def load_settings():
    """Lädt die Einstellungen aus der JSON-Datei."""
    defaults = {
        'button_transparency': 0.25,
        'transparency_enabled': True,
        'background_enabled': True,
        'background_path': 'osbackground/hmbg.png'
    }
    if not os.path.exists(SETTINGS_FILE):
        return defaults
    try:
        with open(SETTINGS_FILE, 'r') as f:
            loaded_settings = json.load(f)
        defaults.update(loaded_settings)
        return defaults
    except (IOError, json.JSONDecodeError):
        return defaults

def save_settings(settings):
    """Speichert die Einstellungen in der JSON-Datei."""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

def apply_styles_to_widget(widget):
    """Durchläuft ein Widget und seine Kinder und wendet Transparenz und abgerundete Ecken auf Buttons an."""
    settings = load_settings()

    use_transparency = settings.get('transparency_enabled', True)
    transparency = settings.get('button_transparency', 1.0) if use_transparency else 1.0

    base_color = (1, 1, 1)

    def apply_to_children(w):
        if isinstance(w, Button):
            normal_color = (*base_color, transparency)
            down_color = (base_color[0] * 0.8, base_color[1] * 0.8, base_color[2] * 0.8, transparency)

            w.background_normal = ''
            w.background_down = ''
            w.background_color = (0, 0, 0, 0)

            def update_canvas(instance, value):
                instance.canvas.before.clear()
                with instance.canvas.before:
                    Color(rgba=(down_color if instance.state == 'down' else normal_color))
                    RoundedRectangle(pos=instance.pos, size=instance.size, radius=[15])

            w.bind(pos=update_canvas, size=update_canvas, state=update_canvas)
            update_canvas(w, None)

        elif hasattr(w, 'children'):
            for child in w.children:
                apply_to_children(child)

    apply_to_children(widget)

def apply_background(screen):
    """Fügt den Hintergrund zu einem Bildschirm hinzu oder entfernt ihn, basierend auf den Einstellungen."""
    settings = load_settings()

    old_bg = getattr(screen, '_background_image', None)
    if old_bg and old_bg.parent:
        screen.remove_widget(old_bg)

    if settings.get('background_enabled', True):
        bg_path = settings.get('background_path', 'osbackground/hmbg.png')
        if os.path.exists(bg_path):
            try:
                background = Image(source=bg_path, allow_stretch=True, keep_ratio=False)
                screen._background_image = background
                screen.add_widget(background, index=len(screen.children))
            except Exception as e:
                print(f"Fehler beim Laden des Hintergrundbildes: {e}")
