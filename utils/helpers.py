import os
import sys
import json
import socket
import random
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_settings_file():
    """Gets the path to the settings file, ensuring it's in a writable location."""
    app = App.get_running_app()
    # Use Kivy's user_data_dir for settings
    user_data_path = app.user_data_dir
    if not os.path.exists(user_data_path):
        os.makedirs(user_data_path)
    return os.path.join(user_data_path, 'settings.json')

def get_user_saves_dir(folder_name="saves"):
    """Gets the path to a user-specific saves folder (characters, maps, etc.)."""
    app = App.get_running_app()
    saves_path = os.path.join(app.user_data_dir, folder_name)
    if not os.path.exists(saves_path):
        os.makedirs(saves_path)
    return saves_path

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
        'keyboard_enabled': keyboard_default,
        'window_width': 1280,
        'window_height': 720,
        'font_color_enabled': False,
        'custom_font_color': [1, 1, 1, 1],
        'popup_color_enabled': False,
        'custom_popup_color': [0.1, 0.1, 0.1, 0.9],
        'button_font_color_enabled': False,
        'custom_button_font_color': [1, 1, 1, 1],
        'button_bg_color_enabled': False,
        'custom_button_bg_color': [1, 1, 1, 1]
    }
    settings_file = get_settings_file()
    if not os.path.exists(settings_file):
        return defaults
    try:
        with open(settings_file, 'r') as f:
            loaded_settings = json.load(f)
        defaults.update(loaded_settings)
        return defaults
    except (IOError, json.JSONDecodeError):
        return defaults

def save_settings(settings):
    """Speichert die Einstellungen in der JSON-Datei."""
    settings_file = get_settings_file()
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=4)

def apply_styles_to_widget(widget):
    """Durchläuft ein Widget und seine Kinder und wendet Stile an."""
    settings = load_settings()
    use_transparency = settings.get('transparency_enabled', True)
    font_color_enabled = settings.get('font_color_enabled', False)
    custom_font_color = settings.get('custom_font_color', [1, 1, 1, 1])
    button_font_color_enabled = settings.get('button_font_color_enabled', False)
    custom_button_font_color = settings.get('custom_button_font_color', [1, 1, 1, 1])
    button_bg_color_enabled = settings.get('button_bg_color_enabled', False)
    custom_button_bg_color = settings.get('custom_button_bg_color', [1, 1, 1, 1])

    def apply_to_children(w):
        if isinstance(w, Button):
            if button_font_color_enabled:
                w.color = custom_button_font_color
            else:
                w.color = [1, 1, 1, 1]

            if hasattr(w, '_update_canvas_transparent'):
                w.unbind(pos=w._update_canvas_transparent, size=w._update_canvas_transparent, state=w._update_canvas_transparent)
                del w._update_canvas_transparent

            if use_transparency:
                transparency = settings.get('button_transparency', 1.0)
                base_color = custom_button_bg_color if button_bg_color_enabled else [1, 1, 1, 1]

                if len(base_color) == 3:
                    base_color.append(1)

                final_alpha = base_color[3] * transparency

                normal_color = (base_color[0], base_color[1], base_color[2], final_alpha)
                down_color = (base_color[0] * 0.8, base_color[1] * 0.8, base_color[2] * 0.8, final_alpha)
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
                w.canvas.before.clear()
                w.background_normal = 'atlas://data/images/defaulttheme/button'
                w.background_down = 'atlas://data/images/defaulttheme/button_pressed'
                w.background_color = (1, 1, 1, 1)

        elif isinstance(w, Label):
            if font_color_enabled:
                w.color = custom_font_color
            else:
                w.color = [1, 1, 1, 1]

        if hasattr(w, 'children'):
            for child in w.children:
                apply_to_children(child)

    apply_to_children(widget)

def create_styled_popup(title, content, size_hint, **kwargs):
    settings = load_settings()
    popup_color_enabled = settings.get('popup_color_enabled', False)
    custom_popup_color = settings.get('custom_popup_color', [0.1, 0.1, 0.1, 0.9])

    popup = Popup(title=title, content=content, size_hint=size_hint, **kwargs)
    if popup_color_enabled:
        popup.background_color = custom_popup_color
        popup.background = ''

    apply_styles_to_widget(content)

    return popup

from kivy.graphics import Rectangle

def apply_background(screen):
    settings = load_settings()

    # Remove the old background if it exists
    old_bg_rect = getattr(screen, '_background_rect', None)
    if old_bg_rect:
        screen.canvas.before.remove(old_bg_rect)
        screen._background_rect = None

    if settings.get('background_enabled', True):
        bg_path = settings.get('background_path', 'osbackground/hmbg.png')
        if screen.name == 'creator':
            bg_path = settings.get('cs_creator_background_path', bg_path)
        elif screen.name == 'sheet':
            bg_path = settings.get('cs_sheet_background_path', bg_path)
        elif screen.name == 'dm_lobby' or screen.name == 'player_waiting':
            bg_path = settings.get('lobby_background_path', bg_path)

        bg_path = resource_path(bg_path)
        if os.path.exists(bg_path):
            try:
                with screen.canvas.before:
                    screen._background_rect = Rectangle(source=bg_path, size=screen.size, pos=screen.pos)

                def update_rect(instance, value):
                    if hasattr(instance, '_background_rect') and instance._background_rect:
                        instance._background_rect.pos = instance.pos
                        instance._background_rect.size = instance.size

                screen.bind(pos=update_rect, size=update_rect)

            except Exception as e:
                print(f"Fehler beim Laden des Hintergrundbildes: {e}")

def get_local_ip():
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        try:
            IP = socket.gethostbyname(socket.gethostname())
        except Exception:
            IP = '127.0.0.1'
    finally:
        if s:
            s.close()
    return IP

def ensure_character_attributes(character):
    """Adds missing attributes to older character objects for forward compatibility."""
    if not hasattr(character, 'max_spell_slots'):
        character.max_spell_slots = {}

    if isinstance(character.max_spell_slots, list):
        new_slots = {str(i+1): val for i, val in enumerate(character.max_spell_slots)}
        character.max_spell_slots = new_slots

    if not hasattr(character, 'current_spell_slots') or isinstance(character.current_spell_slots, list):
        character.current_spell_slots = {k: v for k, v in character.max_spell_slots.items()}

    if not hasattr(character, 'fighting_style'):
        character.fighting_style = None

    if hasattr(character, 'spell_slots'):
        del character.spell_slots

    return character
