from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup
from kivy.app import App
from functools import partial
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.textinput import TextInput
import random

class PlayerMapScreen(Screen):
    """Screen for the player to view the game map."""
    def __init__(self, **kwargs):
        super(PlayerMapScreen, self).__init__(**kwargs)
        self.map_data = None
        self.selected_object = None
        self.highlighted_tiles = []
        self.app = App.get_running_app()
        self.interactable_pos = None
        self.is_my_turn = False
        self.current_turn_name = ""
        self.current_turn_pos = None
        # self.tile_widgets is no longer needed
        self.turn_action_state = {}
        self._map_widget_bound = False

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        if not self._map_widget_bound:
            self.ids.player_map_grid.bind(on_tile_click=self.handle_tile_click)
            self._map_widget_bound = True
        self.update_ui()

    def set_map_data(self, map_data):
        if not map_data or not map_data.get('tiles'):
            self.map_data = map_data
            self.ids.player_map_grid.set_data(None, [], None)
            return

        tiles = map_data.get('tiles')
        if tiles:
            first_key = next(iter(tiles), None)
            if isinstance(first_key, str):
                map_data['tiles'] = {eval(k): v for k, v in tiles.items()}

        self.map_data = map_data
        self.update_ui()

    # create_map_grid and update_map_view are now handled by MapGridWidget

    def update_ui(self):
        self.update_turn_status_ui()
        if self.map_data:
            self.update_map_widget()
            self.update_interact_button()

    def update_map_widget(self):
        if self.map_data:
            self.ids.player_map_grid.set_data(
                map_data=self.map_data,
                highlighted_tiles=self.highlighted_tiles,
                current_turn_pos=self.current_turn_pos
            )

    def update_interact_button(self):
        my_char_name = self.app.character.name if self.app.character else ""
        my_pos = None
        for pos, tile in self.map_data['tiles'].items():
            if tile.get('object') == my_char_name:
                my_pos = pos
                break

        self.interactable_pos = None
        if my_pos:
            r_my, c_my = my_pos
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                check_pos = (r_my + dr, c_my + dc)
                if check_pos in self.map_data['tiles'] and self.map_data['tiles'][check_pos].get('furniture'):
                    self.interactable_pos = check_pos
                    break

        interact_btn = self.ids.interact_button
        if self.interactable_pos and self.is_my_turn:
            furn_type = self.map_data['tiles'][self.interactable_pos]['furniture']['type']
            interact_btn.text = f"Interagiere mit {furn_type}"
            interact_btn.height = 44
            interact_btn.opacity = 1
            interact_btn.disabled = False
        else:
            interact_btn.height = 0
            interact_btn.opacity = 0
            interact_btn.disabled = True

    def update_game_state(self, game_state):
        my_name = self.app.character.name if self.app.character else ""
        self.current_turn_name = game_state.get('current_turn', '')
        self.turn_action_state = game_state.get('turn_action_state', {})

        pos_list = game_state.get('current_turn_pos')
        self.current_turn_pos = tuple(pos_list) if pos_list else None

        was_my_turn = self.is_my_turn
        self.is_my_turn = (self.current_turn_name == my_name)

        if self.is_my_turn and not was_my_turn:
            self.show_turn_popup()

        if not self.is_my_turn:
            self.selected_object = None
            self.highlighted_tiles = []

        self.update_ui()

    def show_turn_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(text="Du bist am Zug!", font_size='20sp'))

        dismiss_button = Button(text="OK", size_hint_y=None, height=44)
        content.add_widget(dismiss_button)

        popup = create_styled_popup(title="Dein Zug", content=content, size_hint=(0.5, 0.4), auto_dismiss=False)
        dismiss_button.bind(on_press=popup.dismiss)

        popup.open()

    def update_turn_status_ui(self):
        if not hasattr(self.ids, 'turn_status_label'): return
        self.ids.turn_status_label.text = f"Am Zug: {self.current_turn_name}"
        if self.is_my_turn:
            self.ids.turn_status_label.color = (0.2, 1, 0.2, 1)
            self.ids.end_turn_button.disabled = False
            self.ids.end_turn_button.opacity = 1
        else:
            self.ids.turn_status_label.color = (1, 1, 1, 1)
            self.ids.end_turn_button.disabled = True
            self.ids.end_turn_button.opacity = 0.5

    def handle_tile_click(self, instance, touch, row, col):
        if self.ids.player_map_grid.collide_point(*touch.pos):
            if touch.button == 'left':
                self.on_tile_click(row, col)

    def on_tile_click(self, row, col):
        if not self.is_my_turn:
            print("Cannot perform actions, it's not your turn.")
            return

        my_char_name = self.app.character.name

        if self.selected_object and (row, col) in self.highlighted_tiles:
            payload = {'name': my_char_name, 'to_pos': [row, col]}
            print(f"[CLIENT-MOVE] Sending MOVE_OBJECT: {payload}") # Using print as client has no log widget
            self.app.network_manager.send_to_dm("MOVE_OBJECT", payload)
            # DO NOT update UI here. Wait for server confirmation.
            # For better UX, we can give some feedback that the action is sent.
            self.selected_object = None
            self.highlighted_tiles = []
            self.update_map_widget() # Redraw to remove highlights
        else:
            self.highlighted_tiles = []
            tile_data = self.map_data['tiles'].get((row, col), {})

            if self.selected_object and tile_data.get('object') and tile_data.get('object') != my_char_name:
                self.try_attack_enemy(self.selected_object['pos'], (row, col), tile_data['object'])

            elif tile_data.get('object') == my_char_name:
                self.selected_object = {'name': my_char_name, 'pos': (row, col)}
                self.highlight_movement_range(row, col)

            else:
                self.selected_object = None

            self.update_map_widget()

    def try_attack_enemy(self, from_pos, to_pos, enemy_name):
        if not self.is_my_turn: return
        if self.turn_action_state.get('attacks_left', 0) <= 0:
            print("Client: No attacks left.")
            return

        from utils.data_manager import WEAPON_DATA
        weapon_name = self.app.character.equipped_weapon
        weapon_info = WEAPON_DATA.get(weapon_name, {})

        dist = max(abs(from_pos[0] - to_pos[0]), abs(from_pos[1] - to_pos[1]))
        weapon_range = weapon_info.get('range', 1)
        if weapon_range is None:
            weapon_range = 1

        if dist <= weapon_range:
            self.open_attack_popup(enemy_name, from_pos, to_pos)
        else:
            print(f"Attack on {enemy_name} is out of range.")

    def open_attack_popup(self, enemy_name, player_pos, enemy_pos):
        content = BoxLayout(orientation='vertical', padding=10, spacing=20)

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

            attack_die_roll = random.randint(1, 20)
            attack_roll = attack_die_roll + ability_mod

            damage_str = weapon.get('damage', '1d4')
            num_dice, dice_type = map(int, damage_str.split('d'))
            damage_die_roll = sum(random.randint(1, dice_type) for _ in range(num_dice))
            damage = damage_die_roll + ability_mod

            result_label.text = f"Attack: {attack_die_roll} + {ability_mod} = {attack_roll}\nDamage: {damage_die_roll} + {ability_mod} = {damage}"

            payload = {'type': 'auto', 'enemy_name': enemy_name, 'attack_roll': attack_roll, 'damage': damage, 'details': result_label.text}
            self.app.network_manager.send_to_dm("PLAYER_ATTACK", payload)

            manual_button.disabled = True
            auto_button.disabled = True
            auto_button.text = "Attack Sent!"

        manual_button.bind(on_press=send_manual)
        auto_button.bind(on_press=roll_automatic)

        popup.open()

    def highlight_movement_range(self, r_start, c_start):
        movement_left = self.turn_action_state.get('movement_left', 0)
        self.highlighted_tiles = []
        if movement_left <= 0:
            return

        for r in range(self.map_data['rows']):
            for c in range(self.map_data['cols']):
                dist = abs(r - r_start) + abs(c - c_start)
                if 0 < dist <= movement_left:
                    tile_data = self.map_data['tiles'].get((r,c))
                    if tile_data and tile_data['type'] != 'Wall' and not tile_data.get('object'):
                        self.highlighted_tiles.append((r, c))

    def end_turn(self):
        if self.is_my_turn:
            self.app.network_manager.send_to_dm("END_TURN", {})
            print("Sent end turn request to DM.")
        else:
            print("Cannot end turn, it's not your turn.")

    def go_back(self):
        self.manager.current = 'player_sheet'

    def interact(self):
        if not self.is_my_turn:
            print("Cannot interact, it's not your turn.")
            return

        if self.interactable_pos:
            self.app.network_manager.send_to_dm("INTERACT_WITH_OBJECT", {'pos': self.interactable_pos})

            self.ids.interact_button.height = 0
            self.ids.interact_button.opacity = 0
            self.ids.interact_button.disabled = True
            self.interactable_pos = None
