import os
import sys
import json
import socket
import random
import math
from copy import deepcopy
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle
from kivy.utils import platform
# Delay importing Window until runtime in functions so Config can be set
# early (e.g. in main.py) before Window initializes.

from utils.paths import resource_path, get_user_saves_dir, user_data_dir

DATA_DIR = resource_path("utils/data")
SETTINGS_FILE = os.path.join(user_data_dir(), "settings.json")

def validated_settings(defaults, loaded):
    result = deepcopy(defaults)
    if not isinstance(loaded, dict):
        return result
    for key, value in loaded.items():
        if key not in defaults and key != 'lobby_background_path':
            continue
        default = defaults.get(key, '')
        valid = False
        if type(default) is bool:
            valid = type(value) is bool
        elif isinstance(default, list):
            valid = (isinstance(value, list) and len(value) == 4 and
                     all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in value))
        elif key in ('window_width', 'window_height'):
            valid = type(value) in (int, float) and math.isfinite(value) and 320 <= value <= 8192
            if valid:
                value = int(value)
        elif key == 'button_transparency':
            valid = type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
        elif isinstance(default, str):
            valid = isinstance(value, str) and len(value) <= 4096 and '\x00' not in value
        if valid:
            result[key] = deepcopy(value)
    return result

def load_settings():
    """Lädt die Einstellungen aus der JSON-Datei."""
    # Standardeinstellung für die Tastatur basierend auf dem Betriebssystem
    keyboard_default = platform == 'linux'

    defaults = {
        'button_transparency': 0.25,
        'transparency_enabled': False,
        'background_enabled': False,
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
    if not os.path.exists(SETTINGS_FILE):
        return defaults
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            loaded_settings = json.load(f)
        return validated_settings(defaults, loaded_settings)
    except (IOError, UnicodeError, json.JSONDecodeError):
        return defaults

def save_settings(settings):
    """Speichert die Einstellungen in der JSON-Datei."""
    from utils.storage import atomic_write_json
    atomic_write_json(SETTINGS_FILE, settings)

def apply_styles_to_widget(widget):
    """Durchläuft ein Widget und seine Kinder und wendet Stile an."""
    settings = load_settings()
    use_transparency = settings.get('transparency_enabled', False)
    font_color_enabled = settings.get('font_color_enabled', False)
    custom_font_color = settings.get('custom_font_color', [1, 1, 1, 1])
    button_font_color_enabled = settings.get('button_font_color_enabled', False)
    custom_button_font_color = settings.get('custom_button_font_color', [1, 1, 1, 1])
    button_bg_color_enabled = settings.get('button_bg_color_enabled', False)
    custom_button_bg_color = settings.get('custom_button_bg_color', [1, 1, 1, 1])

    def apply_to_children(w):
        # Some test runs replace kivy classes with MagicMocks, which makes
        # isinstance checks raise TypeError. We'll handle that by trying
        # isinstance first and falling back to duck-typing checks.
        is_button = False
        try:
            is_button = isinstance(w, Button)
        except TypeError:
            # Fallback: consider it a button-like object if it has common attrs
            is_button = all(hasattr(w, attr) for attr in ('background_normal', 'background_down', 'background_color'))

        if is_button:
            if button_font_color_enabled:
                try:
                    w.color = custom_button_font_color
                except Exception:
                    pass
            else:
                try:
                    w.color = [1, 1, 1, 1]
                except Exception:
                    pass

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

        else:
            # Label handling: also robust to MagicMock replacements
            is_label = False
            try:
                is_label = isinstance(w, Label)
            except TypeError:
                is_label = hasattr(w, 'text') and hasattr(w, 'texture_size')

            if is_label:
                try:
                    if font_color_enabled:
                        w.color = custom_font_color
                    else:
                        w.color = [1, 1, 1, 1]
                except Exception:
                    pass

        # Styling preserves layout constraints and scroll extents.

        if hasattr(w, 'children'):
            for child in w.children:
                apply_to_children(child)

    apply_to_children(widget)

def create_styled_popup(title, content, size_hint=(0.85, 0.75), **kwargs):
    settings = load_settings()
    popup_color_enabled = settings.get('popup_color_enabled', False)
    custom_popup_color = settings.get('custom_popup_color', [0.1, 0.1, 0.1, 0.9])

    # If the content is a long label, wrap it in a ScrollView
    is_label = False
    try:
        is_label = isinstance(content, Label)
    except TypeError:
        # In tests, Kivy classes may be replaced by MagicMock which makes
        # isinstance() raise TypeError. Fall back to duck-typing: treat it
        # as a label-like object if it has a 'text' attribute and a 'bind'
        # method. This avoids trying to assign tuple values to height.
        is_label = hasattr(content, 'text') and callable(getattr(content, 'bind', None))

    if is_label:
        try:
            content.size_hint_y = None
        except Exception:
            pass
        # Bind the label's height to the texture height only (texture_size is (width, height)).
        # Avoid assigning the full tuple to height which causes a ValueError.
        try:
            content.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1] if value and len(value) > 1 else 0))
        except Exception:
            # If binding fails (e.g. MagicMock), ignore and proceed.
            pass
        # Enable text wrapping
        try:
            content.bind(width=lambda *x: content.setter('text_size')(content, (content.width, None)))
        except Exception:
            pass
        scroll_view = ScrollView(size_hint=(1, 1))
        try:
            scroll_view.add_widget(content)
            final_content = scroll_view
        except Exception:
            final_content = content
    else:
        final_content = content

    # On Android, use size_hint for proportional sizing.
    # On desktop, calculate a fixed size from the hint to prevent overly large popups.
    if platform == 'android':
        popup = Popup(title=title, content=final_content, size_hint=size_hint, **kwargs)
    else:
        # Use a fixed size on desktop platforms
        # Import Window here to avoid importing it at module import time
        from kivy.core.window import Window
        # A None hint means an explicit pixel dimension, as in name/text
        # dialogs. Preserve width/height/size kwargs without multiplying None
        # or passing the same argument twice to Popup.
        dimensions = kwargs.pop('size', (Window.width * .85, Window.height * .75))
        fixed_width = kwargs.pop('width', dimensions[0] if size_hint[0] is None else Window.width * size_hint[0])
        fixed_height = kwargs.pop('height', dimensions[1] if size_hint[1] is None else Window.height * size_hint[1])
        popup = Popup(title=title, content=final_content, size_hint=(None, None),
                      size=(fixed_width, fixed_height), **kwargs)

    if popup_color_enabled:
        popup.background_color = custom_popup_color
        popup.background = ''

    apply_styles_to_widget(final_content)

    return popup

from kivy.graphics import Rectangle

def apply_background(screen):
    settings = load_settings()

    # Remove the old background if it exists
    old_bg_rect = getattr(screen, '_background_rect', None)
    if old_bg_rect:
        screen.canvas.before.remove(old_bg_rect)
        screen._background_rect = None

    if settings.get('background_enabled', False):
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
    from utils.wire import get_local_ipv4s
    addresses = get_local_ipv4s()
    if not addresses:
        raise OSError('Keine aktive lokale IPv4-Netzwerkschnittstelle gefunden.')
    return addresses[0]


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
