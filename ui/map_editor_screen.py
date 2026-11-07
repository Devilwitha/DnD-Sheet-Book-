from kivy.metrics import dp
import json
import os
from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from functools import partial
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup, get_user_saves_dir
from utils.data_manager import ENEMY_DATA
from kivy.app import App
from kivy.uix.checkbox import CheckBox
from utils.formats import decode_map, encode_map
from utils.storage import read_json, atomic_write_json, safe_save_path

class LegacyMapEditorScreen(Screen):
    """Screen for creating and editing maps."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.map_data = {}
        self.preloaded_map_data = None
        self.custom_enemy_list = None
        self.current_map_filename = None

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        self.populate_spinners()

        if self.preloaded_map_data:
            self.load_existing_map(self.preloaded_map_data)
            self.preloaded_map_data = None
        else:
            self.ids.map_grid.clear_widgets()
            self.ids.rows_input.text = "10"
            self.ids.cols_input.text = "10"
            self.map_data = {}
            self.current_map_filename = None

    def load_existing_map(self, map_data):
        self.map_data = decode_map(map_data)
        map_data = self.map_data
        # Lade offline_players aus map_data falls vorhanden und setze sie im GameManager
        offline_players_raw = map_data.get('offline_players', [])
        offline_players = []
        from core.character import Character
        for p in offline_players_raw:
            if isinstance(p, Character):
                offline_players.append(p)
            elif isinstance(p, dict):
                offline_players.append(Character.from_dict(p))
        if hasattr(self.app, 'game_manager'):
            known = {c.name for c in self.app.game_manager.offline_players}
            self.app.game_manager.offline_players.extend(c for c in offline_players if c.name not in known)
            # Versuche, die Offline-Spieler-Liste im DM-Screen zu aktualisieren
            try:
                if hasattr(self.app, 'root') and hasattr(self.app.root, 'get_screen'):
                    dm_screen = self.app.root.get_screen('dm_main')
                    if hasattr(dm_screen, 'update_offline_players_list'):
                        dm_screen.update_offline_players_list()
            except Exception as e:
                print(f"[WARN] Konnte Offline-Spieler-Liste im DM-Screen nicht aktualisieren: {e}")
        self.ids.rows_input.text = str(self.map_data.get('rows', 10))
        self.ids.cols_input.text = str(self.map_data.get('cols', 10))
        self.recreate_grid_from_data()

    def populate_spinners(self):
        enemy_names = self.custom_enemy_list or list(ENEMY_DATA.keys())
        self.ids.enemy_spinner.values = ["None"] + sorted(enemy_names)

        player_names = []
        # Online Spieler
        try:
            if self.app.network_manager and self.app.network_manager.mode == 'dm':
                with self.app.network_manager.lock:
                    player_names = [client['character'].name for client in self.app.network_manager.clients.values()]
        except Exception as e:
            print(f"[WARN] Could not get player list for map editor: {e}")
        # Offline Spieler aus GameManager ergänzen
        try:
            offline_names = []
            if hasattr(self.app, 'game_manager'):
                offline_names = [char.name for char in getattr(self.app.game_manager, 'offline_players', [])]
                offline_names += list(self.app.game_manager.disconnected_players)
            for name in offline_names:
                if name not in player_names:
                    player_names.append(name)
        except Exception as e:
            print(f"[WARN] Could not get offline player list: {e}")
        self.ids.player_spinner.values = ["None"] + sorted(player_names)

        furniture_items = ["None", "Table", "Chair", "Chest", "Bed", "Barrel", "Bookcase"]
        self.ids.furniture_spinner.values = sorted(furniture_items)

    def create_grid(self):
        try:
            rows = int(self.ids.rows_input.text)
            cols = int(self.ids.cols_input.text)
            if not (1 <= rows <= 100 and 1 <= cols <= 100):
                raise ValueError('Kartengröße muss zwischen 1 und 100 liegen.')
        except ValueError:
            create_styled_popup(title="Error", content=Label(text="Invalid number of rows/cols."), size_hint=(0.5, 0.3)).open()
            return
        self.map_data = {'rows': rows, 'cols': cols, 'tiles': {}}
        for r in range(rows):
            for c in range(cols):
                self.map_data['tiles'][(r, c)] = {'type': 'Floor', 'object': None, 'furniture': None, 'trigger_message': None}
        self.current_map_filename = None
        self.recreate_grid_from_data()

    def recreate_grid_from_data(self):
        grid = self.ids.map_grid
        grid.clear_widgets()
        if not self.map_data: return
        rows, cols = self.map_data.get('rows', 10), self.map_data.get('cols', 10)
        grid.rows, grid.cols = rows, cols
        for r in range(rows):
            for c in range(cols):
                tile_button = Button()
                tile_button.bind(on_touch_down=partial(self.on_tile_touch_down, r, c))
                grid.add_widget(tile_button)
        self.update_grid_visuals()

    def on_tile_touch_down(self, row, col, instance, touch):
        if instance.collide_point(*touch.pos):
            if getattr(touch, 'button', 'left') == 'right' or self.ids.tile_type_spinner.text == 'Optionen':
                self.show_tile_context_menu(row, col)
                return

            # If it's not a right-click, proceed with the normal logic
            paint_tool = self.ids.tile_type_spinner.text
            paint_tool = {'Boden': 'Floor', 'Wand': 'Wall', 'Tür': 'Door', 'Auslöser': 'Trigger'}.get(paint_tool, paint_tool)
            enemy_to_place = self.ids.enemy_spinner.text
            player_to_place = self.ids.player_spinner.text
            furniture_to_place = self.ids.furniture_spinner.text

            tile_data = self.map_data['tiles'].get((row, col))
            if not tile_data: return

            object_to_place, is_enemy = (player_to_place, False) if player_to_place != "None" else (enemy_to_place, True) if enemy_to_place != "None" else (None, False)

            self.ids.enemy_spinner.text = "None"
            self.ids.player_spinner.text = "None"
            self.ids.furniture_spinner.text = "None"

            if object_to_place:
                if is_enemy:
                    base_name, highest_num = object_to_place, 0
                    for r in range(self.map_data['rows']):
                        for c in range(self.map_data['cols']):
                            obj = self.map_data['tiles'].get((r, c), {}).get('object')
                            if obj and obj.startswith(base_name):
                                try:
                                    num = int(obj.split('#')[-1])
                                    if num > highest_num: highest_num = num
                                except (ValueError, IndexError):
                                    if obj == base_name and highest_num == 0: highest_num = 1
                    tile_data['object'], tile_data['furniture'] = f"{base_name} #{highest_num + 1}", None
                else: # Player
                    # Prüfe, ob der Spieler schon irgendwo platziert ist
                    already_placed = False
                    for r in range(self.map_data['rows']):
                        for c in range(self.map_data['cols']):
                            if self.map_data['tiles'].get((r,c),{}).get('object') == object_to_place:
                                already_placed = True
                                break
                        if already_placed:
                            break
                    if already_placed:
                        create_styled_popup(title="Fehler", content=Label(text=f"{object_to_place} ist bereits auf der Karte!"), size_hint=(0.5, 0.3)).open()
                        return
                    tile_data['object'], tile_data['furniture'] = object_to_place, None
            elif furniture_to_place != "None":
                tile_data['object'], tile_data['furniture'] = None, {'type': furniture_to_place, 'is_mimic': self.ids.mimic_checkbox.active}
            else:
                if paint_tool == 'Trigger': self.prompt_for_trigger_message(tile_data)
                else:
                    tile_data['type'] = paint_tool
                    tile_data.pop('trigger_message', None)
                    if paint_tool == 'Wall': tile_data['object'], tile_data['furniture'] = None, None
            self.update_grid_visuals()

    def prompt_for_trigger_message(self, tile_data):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        message_input = TextInput(hint_text="Enter trigger message...", text=tile_data.get('trigger_message') or '', multiline=True)
        save_btn = Button(text="Save Trigger")
        content.add_widget(message_input)
        content.add_widget(save_btn)
        popup = create_styled_popup(title="Set Trigger Message", content=content, size_hint=(0.7, 0.5))
        def save_action(instance):
            tile_data['type'], tile_data['trigger_message'] = 'Trigger', message_input.text
            self.update_grid_visuals()
            popup.dismiss()
        save_btn.bind(on_press=save_action)
        popup.open()

    def update_grid_visuals(self):
        grid = self.ids.map_grid
        if not grid.children or not self.map_data: return
        rows, cols = self.map_data['rows'], self.map_data['cols']
        for i, child in enumerate(reversed(grid.children)):
            r, c = i // cols, i % cols
            tile = self.map_data['tiles'].get((r, c), {})
            child.text, obj, furn = "", tile.get('object'), tile.get('furniture')
            bg = {'Wall': [0.2,0.2,0.2,1], 'Door': [0.6,0.3,0.1,1], 'Trigger': [1,1,0,0.5]}.get(tile.get('type'), [0.5,0.5,0.5,1])
            if obj:
                child.text, child.color = obj[:3], (1,0.5,0.5,1) if '#' in obj and obj.split('#')[0].strip() in ENEMY_DATA else (0.5,1,0.5,1)
            elif furn:
                child.text, child.color = furn['type'][:2], (1,0.5,1,1) if furn.get('is_mimic') else (0.7,0.7,0.7,1)
            child.background_color = bg

    def map_with_characters(self):
        """Carry character definitions both on disk and when returning to the DM."""
        data = dict(self.map_data)
        gm = self.app.game_manager
        data['offline_players'] = [p.to_dict() for p in gm.offline_players]
        data['online_players'] = [p.to_dict() for p in
                                  {**gm.disconnected_players, **gm.online_players}.values()]
        return data

    def do_save(self, filename):
        if not filename.endswith('.json'): filename += '.json'
        saves_dir = get_user_saves_dir("maps")
        try:
            filepath = safe_save_path(saves_dir, filename)
            enemies = [obj for tile in self.map_data.get('tiles',{}).values() if (obj := tile.get('object')) and obj.split('#')[0].strip() in ENEMY_DATA]
            save_data = self.map_with_characters()
            save_data['enemies'] = enemies
            if hasattr(self.app.game_manager, 'offline_players'):
                save_data['offline_players'] = [c.to_dict() for c in self.app.game_manager.offline_players]
            atomic_write_json(filepath, encode_map(save_data))
            self.app.edited_map_data = save_data
            self.current_map_filename = filename
            return True
        except Exception as e:
            create_styled_popup(title="Error", content=Label(text=f"Error saving map:\n{e}"), size_hint=(0.6, 0.4)).open()
            return False

    def save_map(self):
        if self.current_map_filename:
            if self.do_save(self.current_map_filename):
                create_styled_popup(title="Gespeichert", content=Label(text=f"Map '{self.current_map_filename}' gespeichert."), size_hint=(0.6, 0.4)).open()
        else:
            self.save_map_as_popup()

    def save_map_as_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        filename_input = TextInput(hint_text="map_name", multiline=False)
        save_btn = Button(text="Save")
        content.add_widget(filename_input)
        content.add_widget(save_btn)
        popup = create_styled_popup(title="Save Map As...", content=content, size_hint=(0.7, 0.4))
        def save_action(instance):
            filename = filename_input.text.strip()
            if filename and self.do_save(filename):
                popup.dismiss()
        save_btn.bind(on_press=save_action)
        popup.open()

    def load_map_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        saves = get_user_saves_dir("maps")
        for f in [f for f in os.listdir(saves) if f.endswith('.json')]:
            btn = Button(text=f, size_hint_y=None, height=dp(48))
            btn.bind(on_press=partial(self.do_load_map, f))
            grid.add_widget(btn)
        scroll.add_widget(grid)
        content.add_widget(scroll)
        self.load_popup = create_styled_popup(title="Load Map", content=content, size_hint=(0.8, 0.8))
        self.load_popup.open()

    def do_load_map(self, filename, instance):
        maps_dir = get_user_saves_dir("maps")
        try:
            filepath = safe_save_path(maps_dir, filename)
            loaded_data = read_json(filepath)
            self.load_existing_map(loaded_data)
            self.current_map_filename = filename
            if hasattr(self, 'load_popup'): self.load_popup.dismiss()
        except Exception as e:
            create_styled_popup(title="Load Error", content=Label(text=f"Error loading map:\n{e}"), size_hint=(0.7, 0.5)).open()

    def load_enemy_list_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        saves_dir = get_user_saves_dir("enemies")
        for f in [f for f in os.listdir(saves_dir) if f.endswith('.enemies')]:
            btn = Button(text=f, size_hint_y=None, height=dp(48))
            btn.bind(on_press=partial(self.do_load_enemy_list, f))
            grid.add_widget(btn)
        scroll.add_widget(grid)
        content.add_widget(scroll)
        self.enemy_list_popup = create_styled_popup(title="Load Enemy List", content=content, size_hint=(0.8, 0.8))
        self.enemy_list_popup.open()

    def do_load_enemy_list(self, filename, instance):
        saves_dir = get_user_saves_dir("enemies")
        try:
            filepath = safe_save_path(saves_dir, filename)
            data = read_json(filepath)
            self.custom_enemy_list = [e.get('name') for e in data if e.get('name')]
            self.populate_spinners()
            self.enemy_list_popup.dismiss()
        except Exception as e:
            create_styled_popup(title="Load Error", content=Label(text=f"Error loading enemy list:\n{e}"), size_hint=(0.7, 0.5)).open()

    def reset_enemy_list(self):
        self.custom_enemy_list = None
        self.populate_spinners()

    def go_back(self):
        if self.map_data.get('tiles'):
             self.app.edited_map_data = self.map_with_characters()
        self.app.go_back_screen()

    def show_info_popup(self):
        info_text = (
            "[b]Map Editor Bedienung[/b]\n\n"
            "- [b]Grid erstellen:[/b] Geben Sie die gewünschte Anzahl an Zeilen und Spalten ein und klicken Sie auf 'Create Grid'.\n\n"
            "- [b]Malen:[/b] Wählen Sie einen Kacheltyp (Floor, Wall, Door) aus dem 'Paint Tool' Dropdown-Menü und klicken Sie auf die Kacheln, um sie zu malen.\n\n"
            "- [b]Gegner/Spieler platzieren:[/b] Wählen Sie einen Gegner oder Spieler aus den entsprechenden Dropdown-Menüs aus. Klicken Sie dann auf eine Kachel, um ihn zu platzieren.\n\n"
            "- [b]Rechtsklick:[/b] Öffnet ein Kontextmenü für die ausgewählte Kachel.\n\n"
            "- [b]Speichern/Laden:[/b] Verwenden Sie die 'Save Map' und 'Load Map' Buttons, um Ihren Fortschritt zu speichern und zu laden.\n\n"
            "- [b]Gegnerlisten:[/b] Sie können benutzerdefinierte Gegnerlisten laden, um die 'Place Enemy' Auswahl zu füllen."
        )
        content = ScrollView()
        label = Label(text=info_text, markup=True, size_hint_y=None, padding=(10, 10))
        label.bind(
            width=lambda *x: label.setter('text_size')(label, (label.width, None)),
            texture_size=lambda *x: label.setter('height')(label, label.texture_size[1])
        )
        content.add_widget(label)
        create_styled_popup(title="Map Editor Info", content=content, size_hint=(0.8, 0.8)).open()

    def show_tile_context_menu(self, row, col):
        tile_data = self.map_data['tiles'].get((row, col))
        if not tile_data:
            return

        content = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))

        reset_button = Button(text="Reset Tile", size_hint_y=None, height=dp(48))

        popup = create_styled_popup(title=f"Options for Tile ({row}, {col})", content=content, size_hint=(0.5, 0.5))

        def reset_action(instance):
            self.reset_tile(row, col)
            popup.dismiss()

        reset_button.bind(on_press=reset_action)
        content.add_widget(reset_button)

        if tile_data.get('furniture'):
            is_mimic = tile_data['furniture'].get('is_mimic', False)
            mimic_button_text = "Remove Mimic Flag" if is_mimic else "Flag as Mimic"
            mimic_button = Button(text=mimic_button_text, size_hint_y=None, height=dp(48))

            def mimic_action(instance):
                self.toggle_mimic(row, col)
                popup.dismiss()

            mimic_button.bind(on_press=mimic_action)
            content.add_widget(mimic_button)

        popup.open()

    def toggle_mimic(self, row, col):
        tile_data = self.map_data['tiles'].get((row, col))
        if tile_data and tile_data.get('furniture'):
            is_mimic = tile_data['furniture'].get('is_mimic', False)
            tile_data['furniture']['is_mimic'] = not is_mimic
            self.update_grid_visuals()

    def reset_tile(self, row, col):
        tile_data = self.map_data['tiles'].get((row, col))
        if tile_data:
            tile_data['type'] = 'Floor'
            tile_data['object'] = None
            tile_data['furniture'] = None
            tile_data.pop('trigger_message', None)
            self.update_grid_visuals()


from ui.map_editor_tools import MapEditorTools


class MapEditorScreen(MapEditorTools, LegacyMapEditorScreen):
    """Integrated atlas editor with existing game-tile placement."""
    pass
