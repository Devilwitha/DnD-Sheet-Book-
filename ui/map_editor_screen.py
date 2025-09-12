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
from kivy.app import App

class MapEditorScreen(Screen):
    """Screen for creating and editing maps."""
    def __init__(self, **kwargs):
        super(MapEditorScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.map_data = {}
        self.preloaded_map_data = None

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        self.populate_object_spinner()

        if self.preloaded_map_data:
            self.load_existing_map(self.preloaded_map_data)
            self.preloaded_map_data = None # Clear after loading
        else:
            # Clear grid if not loading a map
            self.ids.map_grid.clear_widgets()
            self.ids.rows_input.text = "10"
            self.ids.cols_input.text = "10"
            self.map_data = {}


    def load_existing_map(self, map_data):
        """Loads map data passed from another screen."""
        self.map_data = map_data
        self.map_data['tiles'] = {eval(k): v for k, v in self.map_data['tiles'].items()}
        self.ids.rows_input.text = str(self.map_data.get('rows', 10))
        self.ids.cols_input.text = str(self.map_data.get('cols', 10))
        self.recreate_grid_from_data()

    def populate_object_spinner(self):
        enemy_names = []
        player_names = []
        try:
            if self.manager.has_screen('dm_prep'):
                dm_prep_screen = self.manager.get_screen('dm_prep')
                if hasattr(dm_prep_screen, 'enemy_list'):
                    enemy_names = [enemy.name for enemy in dm_prep_screen.enemy_list]
        except Exception as e:
            print(f"[WARN] Could not get enemy list for map editor: {e}")
        try:
            if self.app.network_manager and self.app.network_manager.mode == 'dm':
                with self.app.network_manager.lock:
                    player_names = [client['character'].name for client in self.app.network_manager.clients.values()]
        except Exception as e:
            print(f"[WARN] Could not get player list for map editor: {e}")
        self.ids.object_spinner.values = ["None"] + enemy_names + player_names

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
                self.map_data['tiles'][(r, c)] = {'type': 'Floor', 'object': None}
        self.recreate_grid_from_data()

    def recreate_grid_from_data(self):
        grid = self.ids.map_grid
        grid.clear_widgets()
        if not self.map_data: return

        rows = self.map_data.get('rows', 10)
        cols = self.map_data.get('cols', 10)
        grid.rows, grid.cols = rows, cols

        for r in range(rows):
            for c in range(cols):
                tile_button = Button()
                tile_button.bind(on_press=partial(self.on_tile_click, r, c))
                grid.add_widget(tile_button)
        self.update_grid_visuals()

    def on_tile_click(self, row, col, instance):
        paint_tool = self.ids.tile_type_spinner.text
        object_to_place = self.ids.object_spinner.text
        tile_data = self.map_data['tiles'].get((row, col))
        if not tile_data: return

        if object_to_place != "None":
            for r_idx in range(self.map_data['rows']):
                for c_idx in range(self.map_data['cols']):
                    if self.map_data['tiles'].get((r_idx, c_idx), {}).get('object') == object_to_place:
                        self.map_data['tiles'][(r_idx, c_idx)]['object'] = None
            tile_data['object'] = object_to_place
            self.ids.object_spinner.text = "None"
        else:
            tile_data['type'] = paint_tool
        self.update_grid_visuals()

    def update_grid_visuals(self):
        grid = self.ids.map_grid
        if not grid.children or not self.map_data: return
        rows, cols = self.map_data['rows'], self.map_data['cols']
        for i, child in enumerate(reversed(grid.children)):
            row, col = i // cols, i % cols
            tile_data = self.map_data['tiles'].get((row, col))
            if not tile_data: continue
            child.text = ""
            bg_color = [0.5, 0.5, 0.5, 1]
            if tile_data.get('type') == 'Wall': bg_color = [0.2, 0.2, 0.2, 1]
            elif tile_data.get('type') == 'Door': bg_color = [0.6, 0.3, 0.1, 1]
            obj = tile_data.get('object')
            if obj:
                child.text = obj[:3]
                dm_prep_screen = self.manager.get_screen('dm_prep')
                if hasattr(dm_prep_screen, 'enemy_list') and obj in [e.name for e in dm_prep_screen.enemy_list]:
                    child.color = (1, 0.5, 0.5, 1)
                else:
                    child.color = (0.5, 1, 0.5, 1)
            child.background_color = bg_color

    def save_map_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        filename_input = TextInput(hint_text="map_name", multiline=False)
        save_btn = Button(text="Save")
        content.add_widget(filename_input)
        content.add_widget(save_btn)
        popup = create_styled_popup(title="Save Map", content=content, size_hint=(0.7, 0.4))
        def do_save(instance):
            filename = filename_input.text.strip()
            if not filename: return
            if not filename.endswith('.json'): filename += '.json'
            saves_dir = "utils/data/maps"
            os.makedirs(saves_dir, exist_ok=True)
            filepath = os.path.join(saves_dir, filename)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    save_data = self.map_data.copy()
                    save_data['tiles'] = {str(k): v for k, v in self.map_data['tiles'].items()}
                    json.dump(save_data, f, indent=4)
                popup.dismiss()
            except Exception as e:
                create_styled_popup(title="Error", content=Label(text=f"Error saving map:\n{e}"), size_hint=(0.6, 0.4)).open()
        save_btn.bind(on_press=do_save)
        popup.open()

    def load_map_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))
        saves_dir = "utils/data/maps"
        os.makedirs(saves_dir, exist_ok=True)
        map_files = [f for f in os.listdir(saves_dir) if f.endswith('.json')]
        if not map_files:
            create_styled_popup(title="No Maps", content=Label(text="No saved maps found."), size_hint=(0.6, 0.4)).open()
            return
        for filename in map_files:
            btn = Button(text=filename, size_hint_y=None, height=44)
            btn.bind(on_press=partial(self.do_load_map, filename))
            scroll_content.add_widget(btn)
        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        content.add_widget(scroll_view)
        self.load_popup = create_styled_popup(title="Load Map", content=content, size_hint=(0.8, 0.8))
        self.load_popup.open()

    def do_load_map(self, filename, instance):
        filepath = os.path.join("utils/data/maps", filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            self.load_existing_map(loaded_data)
            if hasattr(self, 'load_popup'):
                self.load_popup.dismiss()
        except Exception as e:
            create_styled_popup(title="Load Error", content=Label(text=f"Error loading map:\n{e}"), size_hint=(0.7, 0.5)).open()

    def go_back(self):
        if self.app.source_screen:
            self.app.change_screen(self.app.source_screen)
        else:
            self.app.change_screen('dm_prep') # Fallback
