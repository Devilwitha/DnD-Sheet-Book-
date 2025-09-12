from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle
from utils.helpers import apply_background, apply_styles_to_widget
from kivy.app import App
from functools import partial

class PlayerMapScreen(Screen):
    """Screen for the player to view the game map."""
    def __init__(self, **kwargs):
        super(PlayerMapScreen, self).__init__(**kwargs)
        self.map_data = None
        self.selected_object = None
        self.highlighted_tiles = []
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        if self.map_data:
            self.update_map_view()

    def set_map_data(self, map_data):
        # The tiles come with string keys from JSON, convert them
        map_data['tiles'] = {eval(k): v for k, v in map_data['tiles'].items()}
        self.map_data = map_data
        self.update_map_view()

    def update_map_view(self):
        grid = self.ids.player_map_grid
        grid.clear_widgets()

        if not self.map_data: return

        rows, cols, tiles = self.map_data['rows'], self.map_data['cols'], self.map_data['tiles']
        grid.rows, grid.cols = rows, cols

        my_char_name = self.app.character.name if self.app.character else ""

        for r in range(rows):
            for c in range(cols):
                tile_button = Button()
                tile_button.bind(on_press=partial(self.on_tile_click, r, c))

                tile_data = tiles.get((r, c))
                if not tile_data: continue

                bg_color = [0.5, 0.5, 0.5, 1] # Floor
                if (r,c) in self.highlighted_tiles:
                    bg_color = [0.9, 0.9, 0.2, 1] # Highlight color
                elif tile_data.get('type') == 'Wall': bg_color = [0.2, 0.2, 0.2, 1]
                elif tile_data.get('type') == 'Door': bg_color = [0.6, 0.3, 0.1, 1]

                tile_button.background_color = bg_color

                obj = tile_data.get('object')
                if obj:
                    tile_button.text = obj[:3]
                    if obj == my_char_name:
                        tile_button.color = (0.5, 1, 0.5, 1) # Green for self
                    else:
                        # A simple way to differentiate players from enemies without full data
                        # This assumes player names don't typically contain '#'
                        if '#' in obj:
                            tile_button.color = (1, 0.5, 0.5, 1) # Red for enemies
                        else:
                            tile_button.color = (0.5, 0.5, 1, 1) # Blue for other players

                grid.add_widget(tile_button)

    def on_tile_click(self, row, col, instance):
        my_char_name = self.app.character.name

        if self.selected_object and (row, col) in self.highlighted_tiles:
            # Move action
            payload = {'name': my_char_name, 'to_pos': (row, col)}
            self.app.network_manager.send_to_dm("MOVE_OBJECT", payload)
            self.selected_object = None
            self.highlighted_tiles = []
            # Don't update view immediately, wait for server confirmation (MAP_DATA)
        else:
            self.highlighted_tiles = []
            tile_data = self.map_data['tiles'].get((row, col))
            if tile_data and tile_data.get('object') == my_char_name:
                self.selected_object = {'name': my_char_name, 'pos': (row, col)}
                self.highlight_movement_range(row, col)
            else:
                self.selected_object = None
            self.update_map_view()

    def highlight_movement_range(self, r_start, c_start):
        # Speed is 9m -> 6 squares
        speed = 6
        self.highlighted_tiles = []
        for r in range(self.map_data['rows']):
            for c in range(self.map_data['cols']):
                dist = abs(r - r_start) + abs(c - c_start)
                if 0 < dist <= speed:
                    tile_data = self.map_data['tiles'].get((r,c))
                    if tile_data and tile_data['type'] != 'Wall' and not tile_data.get('object'):
                        self.highlighted_tiles.append((r, c))

    def go_back(self):
        self.manager.current = 'player_sheet'
