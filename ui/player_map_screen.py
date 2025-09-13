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
        self.interactable_pos = None

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        if self.map_data:
            self.update_map_view()

    def set_map_data(self, map_data):
        # This function needs to be robust against None or empty map_data.
        if not map_data or not map_data.get('tiles'):
            self.map_data = map_data
            self.update_map_view()
            return

        tiles = map_data.get('tiles')
        # If the dictionary is not empty, check the type of the first key.
        if tiles:
            first_key = next(iter(tiles), None)
            if isinstance(first_key, str):
                # Keys are strings that need to be evaluated to tuples.
                map_data['tiles'] = {eval(k): v for k, v in tiles.items()}

        self.map_data = map_data
        self.update_map_view()

    def update_map_view(self):
        grid = self.ids.player_map_grid
        grid.clear_widgets()

        if not self.map_data: return

        rows, cols, tiles = self.map_data['rows'], self.map_data['cols'], self.map_data['tiles']
        grid.rows, grid.cols = rows, cols

        my_char_name = self.app.character.name if self.app.character else ""
        my_pos = None
        # First, find the player's character position
        for pos, tile in tiles.items():
            if tile.get('object') == my_char_name:
                my_pos = pos
                break

        # Now, check for adjacent interactable furniture
        self.interactable_pos = None
        if my_pos:
            r, c = my_pos
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                check_pos = (r + dr, c + dc)
                if check_pos in tiles and tiles[check_pos].get('furniture'):
                    self.interactable_pos = check_pos
                    break # Found one, that's enough

        # Update the interact button's visibility and text
        interact_btn = self.ids.interact_button
        if self.interactable_pos:
            furn_type = tiles[self.interactable_pos]['furniture']['type']
            interact_btn.text = f"Interagiere mit {furn_type}"
            interact_btn.height = 44
            interact_btn.opacity = 1
            interact_btn.disabled = False
        else:
            interact_btn.height = 0
            interact_btn.opacity = 0
            interact_btn.disabled = True

        # Finally, draw the grid
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
                tile_button.text = "" # Clear text

                obj = tile_data.get('object')
                furniture = tile_data.get('furniture')

                if obj:
                    tile_button.text = obj[:3]
                    if obj == my_char_name:
                        tile_button.color = (0.5, 1, 0.5, 1) # Green for self
                    elif '#' in obj:
                        tile_button.color = (1, 0.5, 0.5, 1) # Red for enemies
                    else:
                        tile_button.color = (0.5, 0.5, 1, 1) # Blue for other players
                elif furniture:
                    tile_button.text = furniture['type'][:2]
                    tile_button.color = (0.7, 0.7, 0.7, 1) # Grey for furniture

                grid.add_widget(tile_button)

    def on_tile_click(self, row, col, instance):
        my_char_name = self.app.character.name

        if self.selected_object and (row, col) in self.highlighted_tiles:
            # Move action
            # Convert tuple to list for JSON serialization
            payload = {'name': my_char_name, 'to_pos': [row, col]}
            self.app.network_manager.send_to_dm("MOVE_OBJECT", payload)
            self.selected_object = None
            self.highlighted_tiles = []
            # Don't update view immediately, wait for server confirmation (MAP_DATA)
        else:
            self.highlighted_tiles = []
            tile_data = self.map_data['tiles'].get((row, col))
            # Check if clicking on an enemy to attack
            if self.selected_object and tile_data and tile_data.get('object') and tile_data.get('object') != my_char_name:
                self.try_attack_enemy(self.selected_object['pos'], (row, col), tile_data['object'])
            # Check if clicking on self to select
            elif tile_data and tile_data.get('object') == my_char_name:
                self.selected_object = {'name': my_char_name, 'pos': (row, col)}
                self.highlight_movement_range(row, col)
            else:
                self.selected_object = None
            self.update_map_view()

    def try_attack_enemy(self, from_pos, to_pos, enemy_name):
        from utils.data_manager import WEAPON_DATA

        weapon_name = self.app.character.equipped_weapon
        weapon_info = WEAPON_DATA.get(weapon_name)
        if not weapon_info:
            print(f"[ATTACK] Weapon '{weapon_name}' not found in data.")
            return

        # Chebyshev distance for grid
        dist = max(abs(from_pos[0] - to_pos[0]), abs(from_pos[1] - to_pos[1]))

        weapon_type = weapon_info.get('type', 'Melee')
        weapon_range = weapon_info.get('range', 1)

        attack_valid = False
        if weapon_type == 'Melee' and dist <= weapon_range:
            attack_valid = True
        elif weapon_type == 'Ranged' and dist > 0: # Can't shoot self
            # For now, we ignore disadvantage at close range for simplicity
            attack_valid = True

        if attack_valid:
            print(f"Attack on {enemy_name} is valid. Opening attack popup...")
            # TODO: Implement attack popup
            self.open_attack_popup(enemy_name, from_pos, to_pos)
        else:
            print(f"Attack on {enemy_name} is out of range. Dist: {dist}, WeapRange: {weapon_range}")

    def open_attack_popup(self, enemy_name, player_pos, enemy_pos):
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.textinput import TextInput
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from utils.helpers import create_styled_popup
        import random

        content = BoxLayout(orientation='vertical', padding=10, spacing=20)

        # --- Manual Section ---
        manual_layout = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None, height=150)
        manual_layout.add_widget(Label(text="Manual Attack", font_size='18sp'))

        inputs_layout = GridLayout(cols=2, spacing=10, size_hint_y=None, height=50)
        attack_roll_input = TextInput(hint_text="Attack Roll (e.g. 15)", input_filter='int')
        damage_input = TextInput(hint_text="Total Damage", input_filter='int')
        inputs_layout.add_widget(Label(text="Attack Roll:"))
        inputs_layout.add_widget(attack_roll_input)
        inputs_layout.add_widget(Label(text="Damage:"))
        inputs_layout.add_widget(damage_input)
        manual_layout.add_widget(inputs_layout)

        manual_button = Button(text="Send Manual Attack")
        manual_layout.add_widget(manual_button)
        content.add_widget(manual_layout)

        # --- Automatic Section ---
        auto_layout = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None, height=150)
        auto_layout.add_widget(Label(text="Automatic Attack", font_size='18sp'))

        auto_button = Button(text="Roll Attack Automatically")
        result_label = Label(text="")
        auto_layout.add_widget(auto_button)
        auto_layout.add_widget(result_label)
        content.add_widget(auto_layout)

        popup = create_styled_popup(title=f"Attack {enemy_name}", content=content, size_hint=(0.8, 0.7))

        def send_manual(instance):
            try:
                attack_roll = int(attack_roll_input.text)
                damage = int(damage_input.text)
                payload = {'type': 'manual', 'enemy_name': enemy_name, 'attack_roll': attack_roll, 'damage': damage}
                self.app.network_manager.send_to_dm("PLAYER_ATTACK", payload)
                popup.dismiss()
            except ValueError:
                result_label.text = "Invalid input for manual attack."

        def roll_automatic(instance):
            from utils.data_manager import WEAPON_DATA
            char = self.app.character
            weapon = WEAPON_DATA.get(char.equipped_weapon, {})
            ability_mod = (char.abilities.get(weapon.get('ability', 'Stärke'), 10) - 10) // 2

            # Attack Roll
            attack_die_roll = random.randint(1, 20)
            attack_roll = attack_die_roll + ability_mod

            # Damage Roll
            damage_str = weapon.get('damage', '1d4')
            num_dice, dice_type = map(int, damage_str.split('d'))
            damage_die_roll = sum(random.randint(1, dice_type) for _ in range(num_dice))
            damage = damage_die_roll + ability_mod

            result_label.text = f"Attack: {attack_die_roll} + {ability_mod} = {attack_roll}\nDamage: {damage_die_roll} + {ability_mod} = {damage}"

            payload = {'type': 'auto', 'enemy_name': enemy_name, 'attack_roll': attack_roll, 'damage': damage, 'details': result_label.text}
            self.app.network_manager.send_to_dm("PLAYER_ATTACK", payload)

            # Disable buttons after action
            manual_button.disabled = True
            auto_button.disabled = True
            auto_button.text = "Attack Sent!"


        manual_button.bind(on_press=send_manual)
        auto_button.bind(on_press=roll_automatic)

        popup.open()

    def highlight_movement_range(self, r_start, c_start):
        # Speed is 9m -> 6 squares
        speed = 6
        self.highlighted_tiles = []
        for r in range(self.map_data['rows']):
            for c in range(self.map_data['cols']):
                dist = abs(r - r_start) + abs(c - c_start)
                if 0 < dist <= speed:
                    tile_data = self.map_data['tiles'].get((r,c))
                    if tile_data and tile_data['type'] not in ['Wall', 'Empty'] and not tile_data.get('object'):
                        self.highlighted_tiles.append((r, c))

    def go_back(self):
        self.manager.current = 'player_sheet'

    def interact(self):
        if self.interactable_pos:
            self.app.network_manager.send_to_dm("INTERACT_WITH_OBJECT", {'pos': self.interactable_pos})

            # Hide button immediately for responsiveness
            self.ids.interact_button.height = 0
            self.ids.interact_button.opacity = 0
            self.ids.interact_button.disabled = True
            self.interactable_pos = None
