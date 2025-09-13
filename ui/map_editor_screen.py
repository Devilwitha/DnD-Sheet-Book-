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
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup
from utils.data_manager import ENEMY_DATA
from kivy.app import App

class MapEditorScreen(Screen):
    """Screen for creating and editing maps."""
    def __init__(self, **kwargs):
        super(MapEditorScreen, self).__init__(**kwargs)
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
        self.map_data = map_data
        if self.map_data and self.map_data.get('tiles'):
            first_key = next(iter(self.map_data['tiles']), None)
            if isinstance(first_key, str):
                self.map_data['tiles'] = {eval(k): v for k, v in self.map_data['tiles'].items()}
        self.ids.rows_input.text = str(self.map_data.get('rows', 10))
        self.ids.cols_input.text = str(self.map_data.get('cols', 10))
        self.recreate_grid_from_data()

    def populate_spinners(self):
        enemy_names = self.custom_enemy_list or list(ENEMY_DATA.keys())
        self.ids.enemy_spinner.values = ["None"] + sorted(enemy_names)

        player_names = []
        try:
            if self.app.network_manager and self.app.network_manager.mode == 'dm':
                with self.app.network_manager.lock:
                    player_names = [client['character'].name for client in self.app.network_manager.clients.values()]
        except Exception as e:
            print(f"[WARN] Could not get player list for map editor: {e}")
        self.ids.player_spinner.values = ["None"] + sorted(player_names)

    def create_grid(self):
        try:
            rows = int(self.ids.rows_input.text)
            cols = int(self.ids.cols_input.text)
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
                tile_button.bind(on_press=partial(self.on_tile_click, r, c))
                grid.add_widget(tile_button)
        self.update_grid_visuals()

    def on_tile_click(self, row, col, instance):
        paint_tool = self.ids.tile_type_spinner.text
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
                for r in range(self.map_data['rows']):
                    for c in range(self.map_data['cols']):
                        if self.map_data['tiles'].get((r,c),{}).get('object') == object_to_place:
                            self.map_data['tiles'][(r,c)]['object'] = None
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

    def do_save(self, filename):
        if not filename.endswith('.json'): filename += '.json'
        saves_dir = "utils/data/maps"
        os.makedirs(saves_dir, exist_ok=True)
        filepath = os.path.join(saves_dir, filename)
        try:
            enemies = [obj for tile in self.map_data.get('tiles',{}).values() if (obj := tile.get('object')) and obj.split('#')[0].strip() in ENEMY_DATA]
            with open(filepath, 'w', encoding='utf-8') as f:
                save_data = self.map_data.copy()
                save_data['tiles'] = {str(k): v for k, v in self.map_data['tiles'].items()}
                save_data['enemies'] = enemies
                json.dump(save_data, f, indent=4)
            self.app.edited_map_data = self.map_data
            self.current_map_filename = filename
        except Exception as e:
            create_styled_popup(title="Error", content=Label(text=f"Error saving map:\n{e}"), size_hint=(0.6, 0.4)).open()

    def save_map(self):
        if self.current_map_filename:
            self.do_save(self.current_map_filename)
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
            if filename: self.do_save(filename)
            popup.dismiss()
        save_btn.bind(on_press=save_action)
        popup.open()

    def load_map_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        saves = "utils/data/maps"
        os.makedirs(saves, exist_ok=True)
        for f in [f for f in os.listdir(saves) if f.endswith('.json')]:
            btn = Button(text=f, size_hint_y=None, height=44)
            btn.bind(on_press=partial(self.do_load_map, f))
            grid.add_widget(btn)
        scroll.add_widget(grid)
        content.add_widget(scroll)
        self.load_popup = create_styled_popup(title="Load Map", content=content, size_hint=(0.8, 0.8))
        self.load_popup.open()

    def do_load_map(self, filename, instance):
        filepath = os.path.join("utils/data/maps", filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
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
        for f in [f for f in os.listdir() if f.endswith('.enemies')]:
            btn = Button(text=f, size_hint_y=None, height=44)
            btn.bind(on_press=partial(self.do_load_enemy_list, f))
            grid.add_widget(btn)
        scroll.add_widget(grid)
        content.add_widget(scroll)
        self.enemy_list_popup = create_styled_popup(title="Load Enemy List", content=content, size_hint=(0.8, 0.8))
        self.enemy_list_popup.open()

    def do_load_enemy_list(self, filename, instance):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
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
             self.app.edited_map_data = self.map_data
        if self.app.source_screen:
            self.app.change_screen(self.app.source_screen)
        else:
            self.app.change_screen('dm_prep')
