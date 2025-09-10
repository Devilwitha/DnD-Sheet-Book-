import os
import sys
import json
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle

SETTINGS_FILE = 'settings.json'

def load_settings():
    """Lädt die Einstellungen aus der JSON-Datei."""
    # Standardeinstellung für die Tastatur basierend auf dem Betriebssystem
    keyboard_default = sys.platform.startswith('linux')

    defaults = {
        'button_transparency': 0.25,
        'transparency_enabled': True,
        'background_enabled': True,
        'background_path': 'osbackground/hmbg.png',
        'cs_creator_background_path': 'osbackground/csbg.png',
        'cs_sheet_background_path': 'osbackground/csbg.png',
        'keyboard_enabled': keyboard_default
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

    def apply_to_children(w):
        if isinstance(w, Button):
            # Unbind any previously bound canvas update functions to prevent conflicts
            if hasattr(w, '_update_canvas_transparent'):
                w.unbind(pos=w._update_canvas_transparent, size=w._update_canvas_transparent, state=w._update_canvas_transparent)
                del w._update_canvas_transparent

            if use_transparency:
                transparency = settings.get('button_transparency', 1.0)
                base_color = (1, 1, 1)
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

                w._update_canvas_transparent = update_canvas
                w.bind(pos=w._update_canvas_transparent, size=w._update_canvas_transparent, state=w._update_canvas_transparent)
                update_canvas(w, None)
            else:
                # Restore default button appearance
                w.canvas.before.clear()
                w.background_normal = 'atlas://data/images/defaulttheme/button'
                w.background_down = 'atlas://data/images/defaulttheme/button_pressed'
                w.background_color = (1, 1, 1, 1)

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
        bg_path = settings.get('background_path', 'osbackground/hmbg.png') # Fallback
        if screen.name == 'creator':
            bg_path = settings.get('cs_creator_background_path', bg_path)
        elif screen.name == 'sheet':
            bg_path = settings.get('cs_sheet_background_path', bg_path)

        if os.path.exists(bg_path):
            try:
                background = Image(source=bg_path, allow_stretch=True, keep_ratio=False)
                screen._background_image = background
                screen.add_widget(background, index=len(screen.children))
            except Exception as e:
                print(f"Fehler beim Laden des Hintergrundbildes: {e}")
