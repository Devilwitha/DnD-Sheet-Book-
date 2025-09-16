import json
import random
import os
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from queue import Empty

from core.character import Character
from core.enemy import Enemy
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup, roll_dice
from functools import partial
from utils.data_manager import ENEMY_DATA
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

class DMMainScreen(Screen):
    """The main screen for the Dungeon Master to manage the game."""
    def __init__(self, **kwargs):
        super(DMMainScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.network_manager = self.app.network_manager
        self.update_event = None
        self.offline_players = []
        self.enemies = []
        self.initiative_order = []
        self.map_data = None
        self.selected_object = None
        self.highlighted_tiles = []
        self.session_players = {}
        # New attributes for combat
        self.current_turn_index = -1
        self.current_turn_pos = None
        self.turn_action_state = {}
        self._map_widget_bound = False

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def on_enter(self, *args):
        if not self._map_widget_bound:
            self.ids.dm_map_grid.bind(on_tile_click=self.handle_tile_click)
            self._map_widget_bound = True

        if self.app.edited_map_data:
            self.map_data = self.app.edited_map_data
            self.app.edited_map_data = None
            self.log_message("Zuletzt bearbeitete Karte geladen.")
            self.update_map_widget()
            self.broadcast_map_data()
        else:
            self.network_manager.broadcast_message("GAME_START", "Das Spiel beginnt!")
            self.load_state_from_manager()

        # This will trigger the first full UI update including the map
        self.update_ui()
        self.update_event = Clock.schedule_interval(self.check_for_updates, 0.2)

    def on_leave(self, *args):
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None

    def load_state_from_manager(self):
        session = None
        if self.app.loaded_session_data:
            session = self.app.loaded_session_data
            self.app.loaded_session_data = None
        elif hasattr(self.app, 'prepared_session_data') and self.app.prepared_session_data:
            session = self.app.prepared_session_data
            self.app.prepared_session_data = None

        if session:
            self.offline_players = session.get('offline_players', [])
            self.session_players = session.get('online_players', {})
            self.map_data = session.get('map_data', None)
            # create_map_grid is no longer needed, update_ui will handle the map widget
            if self.map_data and 'enemies' in self.map_data:
                self.enemies.clear()
                for enemy_name in self.map_data['enemies']:
                    base_name = enemy_name.split('#')[0].strip()
                    if base_name in ENEMY_DATA:
                        enemy_stats = ENEMY_DATA[base_name]
                        new_enemy = Enemy(
                            name=enemy_name,
                            hp=enemy_stats['hp'],
                            armor_class=enemy_stats.get('ac', 10),
                            attacks=enemy_stats['attacks']
                        )
                        self.enemies.append(new_enemy)
                self.log_message("Feindliste automatisch von der Karte geladen.")
            else:
                self.enemies = [Enemy.from_dict(e) for e in session.get('enemies', [])]
            log_text = session.get('log', "Neue Sitzung gestartet.\n")
            if session.get('type') == 'prepared':
                log_text += f"Notizen: {session.get('notes', '')}\n"
            self.ids.log_output.text = log_text
        else:
            self.ids.log_output.text = "Neue Sitzung gestartet.\n"

    def check_for_updates(self, dt):
        try:
            item = self.network_manager.incoming_messages.get_nowait()
            if not isinstance(item, tuple) or len(item) != 2: return

            source, message = item
            if source in ['PLAYER_JOINED', 'PLAYER_LEFT']:
                # ... (original logic remains)
                return

            msg_type = message.get('type')
            payload = message.get('payload')

            if msg_type == 'MOVE_OBJECT':
                self.move_object(payload['name'], tuple(payload['to_pos']))
            elif msg_type == 'PLAYER_ATTACK':
                player_name = self.network_manager.clients[source]['character'].name
                self.handle_player_attack(player_name, payload)
            elif msg_type == 'END_TURN':
                player_name = self.network_manager.clients[source]['character'].name
                current_char_name = "N/A"
                if self.initiative_order and self.current_turn_index < len(self.initiative_order):
                    current_char_name = self.initiative_order[self.current_turn_index][1]
                self.log_message(f"[DEBUG] End turn request from '{player_name}'. Current turn is '{current_char_name}'.")
                if current_char_name == player_name:
                    self.end_turn()
                else:
                    self.log_message(f"Warning: {player_name} tried to end turn, but it's not their turn.")
            elif msg_type == 'INTERACT_WITH_OBJECT':
                player_name = self.network_manager.clients[source]['character'].name
                self.handle_interaction(player_name, tuple(payload['pos']))
        except Empty:
            pass

    def get_character_or_enemy_by_name(self, name):
        with self.network_manager.lock:
            for client in self.network_manager.clients.values():
                if client['character'].name == name:
                    return client['character']
        for enemy in self.enemies:
            if enemy.name == name:
                return enemy
        return None

    def handle_character_death(self, character_name):
        self.log_message(f"{character_name} wurde besiegt!")

        defeated_index = -1
        for i, (_, name) in enumerate(self.initiative_order):
            if name == character_name:
                defeated_index = i
                break

        char_or_enemy = self.get_character_or_enemy_by_name(character_name)
        if isinstance(char_or_enemy, Enemy):
            self.enemies.remove(char_or_enemy)

        self.initiative_order = [item for item in self.initiative_order if item[1] != character_name]

        if defeated_index != -1 and defeated_index <= self.current_turn_index:
            self.current_turn_index -= 1

        for pos, tile in self.map_data['tiles'].items():
            if tile.get('object') == character_name:
                tile['object'] = None
                break

        if not any(isinstance(self.get_character_or_enemy_by_name(name), Enemy) for _, name in self.initiative_order):
            self.log_message("SIEG! Alle Feinde wurden besiegt!")
            self.network_manager.broadcast_message("VICTORY", "Alle Feinde wurden besiegt!")
            self.current_turn_index = -1

        self.update_ui()
        self.broadcast_map_data()
        self.broadcast_game_state()

    def handle_player_attack(self, player_name, payload):
        if not self.initiative_order or self.current_turn_index < 0 or self.initiative_order[self.current_turn_index][1] != player_name:
            client_addr = self.network_manager.get_client_addr_by_name(player_name)
            if client_addr: self.network_manager.send_message(client_addr, "ERROR", "Du kannst nicht außerhalb deiner Runde angreifen.")
            return

        if self.turn_action_state.get('attacks_left', 0) <= 0:
            client_addr = self.network_manager.get_client_addr_by_name(player_name)
            if client_addr: self.network_manager.send_message(client_addr, "ERROR", "Du hast keine Angriffe mehr.")
            return

        enemy_name = payload.get('enemy_name')
        target_enemy = self.get_character_or_enemy_by_name(enemy_name)
        if not target_enemy: return

        attack_roll = payload.get('attack_roll')
        damage = payload.get('damage')

        self.log_message(f"{player_name} greift {enemy_name} an...")
        if attack_roll >= target_enemy.armor_class:
            target_enemy.hp -= damage
            self.log_message(f"GETROFFEN! {enemy_name} erleidet {damage} Schaden. Verbleibende HP: {target_enemy.hp}")
            if target_enemy.hp <= 0:
                self.handle_character_death(enemy_name)
        else:
            self.log_message("VERFEHLT!")

        self.turn_action_state['attacks_left'] -= 1
        self.update_ui()

    def handle_interaction(self, player_name, pos):
        # (Restoring original handle_interaction method)
        if not self.map_data or pos not in self.map_data['tiles']:
            return
        tile = self.map_data['tiles'][pos]
        furniture = tile.get('furniture')
        if not furniture: return
        furn_type = furniture['type']
        if furniture.get('is_mimic'):
            self.log_message(f"MIMIC! Die {furn_type} bei {pos} entpuppt sich als Mimic, als {player_name} interagiert!")
            tile['furniture'] = None
            mimic_data = ENEMY_DATA.get('Mimic', {'hp': 30, 'ac': 12, 'attacks': [{'name': 'Biss', 'damage': '1d8+3'}]})
            count = 1
            for enemy in self.enemies:
                if enemy.name.startswith('Mimic'):
                    try:
                        num = int(enemy.name.split('#')[-1])
                        if num >= count: count = num + 1
                    except (ValueError, IndexError): continue
            unique_name = f"Mimic #{count}"
            new_enemy = Enemy(name=unique_name, hp=mimic_data['hp'], armor_class=mimic_data['ac'], attacks=mimic_data['attacks'])
            self.enemies.append(new_enemy)
            tile['object'] = new_enemy.name
            self.update_ui()
            self.broadcast_map_data()
        else:
            self.log_message(f"{player_name} interagiert mit {furn_type} bei {pos}.")

    def update_ui(self):
        # This updates non-map related UI parts
        self.update_online_players_list()
        self.update_offline_players_list()
        self.update_enemies_list_ui()
        self.update_initiative_ui()
        if self.map_data:
            self.update_objects_list_ui()
            self.update_map_widget() # And also update the map widget

    def update_map_widget(self):
        if self.map_data:
            map_widget = self.ids.dm_map_grid
            map_widget.set_data(
                map_data=self.map_data,
                highlighted_tiles=self.highlighted_tiles,
                current_turn_pos=self.current_turn_pos
            )

    def log_message(self, message):
        self.ids.log_output.text += f"{message}\n"

    def roll_initiative_for_all(self):
        self.initiative_order = []
        with self.network_manager.lock:
            for client_info in self.network_manager.clients.values():
                char = client_info['character']
                roll = random.randint(1, 20) + char.initiative
                self.initiative_order.append((roll, char.name))
        for enemy in self.enemies:
            roll = random.randint(1, 20)
            self.initiative_order.append((roll, enemy.name))

        self.initiative_order.sort(key=lambda x: x[0], reverse=True)
        log_msg = "Initiativereihenfolge:\n" + "\n".join([f"{roll}: {name}" for roll, name in self.initiative_order])
        self.log_message(log_msg)

        if self.initiative_order:
            self.current_turn_index = 0
            self.start_next_turn()
        else:
            self.current_turn_index = -1
        self.update_initiative_ui()
        self.broadcast_game_state()

    def end_turn(self):
        if not self.initiative_order: return
        self.current_turn_index = (self.current_turn_index + 1) % len(self.initiative_order)
        self.start_next_turn()

    def start_next_turn(self):
        if not self.initiative_order or self.current_turn_index == -1:
            self.current_turn_pos = None
            self.update_map_widget()
            return

        _, current_char_name = self.initiative_order[self.current_turn_index]
        self.current_turn_pos = None
        if self.map_data and self.map_data.get('tiles'):
            for pos, tile in self.map_data['tiles'].items():
                if tile.get('object') == current_char_name:
                    self.current_turn_pos = pos
                    break

        character = self.get_character_or_enemy_by_name(current_char_name)
        if character:
            self.turn_action_state = {
                'movement_left': character.speed,
                'attacks_left': character.actions_per_turn
            }

        self.log_message(f"Nächster Zug: {current_char_name} at {self.current_turn_pos}")
        self.update_ui()
        self.broadcast_game_state()

    def broadcast_game_state(self):
        with self.network_manager.lock:
            player_names = [c['character'].name for c in self.network_manager.clients.values()]

        current_turn_name = None
        if self.current_turn_index != -1 and self.initiative_order:
            current_turn_name = self.initiative_order[self.current_turn_index][1]
        state = {
            'players': player_names,
            'initiative': self.initiative_order,
            'current_turn': current_turn_name,
            'current_turn_pos': self.current_turn_pos,
            'turn_action_state': self.turn_action_state
        }
        self.network_manager.broadcast_message("GAME_STATE_UPDATE", state)

    def update_initiative_ui(self):
        initiative_list_widget = self.ids.initiative_list
        initiative_list_widget.clear_widgets()
        current_turn_name = None
        if self.current_turn_index != -1 and self.initiative_order:
            current_turn_name = self.initiative_order[self.current_turn_index][1]

        for i, (roll, name) in enumerate(self.initiative_order):
            text = f"{roll}: {name}"
            label = Label(text=text, size_hint_y=None, height=30)
            if name == current_turn_name:
                label.color = (0.2, 1, 0.2, 1)
                label.bold = True
            initiative_list_widget.add_widget(label)
        self.ids.current_turn_label.text = f"Am Zug: {current_turn_name or 'Niemand'}"

    def create_enemy_instance(self, name, data, instance):
        count = 1
        for enemy in self.enemies:
            if enemy.name.startswith(name):
                try:
                    num = int(enemy.name.split('#')[-1])
                    if num >= count: count = num + 1
                except (ValueError, IndexError): continue
        unique_name = f"{name} #{count}"
        new_enemy = Enemy(name=unique_name, hp=data['hp'], armor_class=data['ac'], attacks=data['attacks'])
        self.enemies.append(new_enemy)
        self.update_enemies_list_ui()
        self.log_message(f"Gegner '{unique_name}' hinzugefügt.")
        if hasattr(self, 'enemy_popup'): self.enemy_popup.dismiss()

    def show_enemy_stats(self, enemy, instance):
        content = BoxLayout(orientation='vertical', spacing=5, padding=10)
        content.add_widget(Label(text=f"Name: {enemy.name}"))
        content.add_widget(Label(text=f"HP: {enemy.hp}"))
        content.add_widget(Label(text=f"AC: {enemy.armor_class}"))
        attacks_str = ", ".join([f"{a['name']} ({a['damage']})" for a in enemy.attacks])
        content.add_widget(Label(text=f"Angriffe: {attacks_str}"))
        create_styled_popup(title="Gegner-Statistiken", content=content, size_hint=(0.6, 0.5)).open()

    def do_load_map(self, filename, instance):
        filepath = os.path.join("utils/data/maps", filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            self.map_data = loaded_data
            self.map_data['tiles'] = {eval(k): v for k, v in loaded_data['tiles'].items()}
            self.log_message(f"Map '{filename}' geladen.")
            # create_map_grid is no longer needed, update_ui will handle the map widget
            if 'enemies' in loaded_data:
                self.enemies.clear()
                for enemy_name in loaded_data['enemies']:
                    base_name = enemy_name.split('#')[0].strip()
                    if base_name in ENEMY_DATA:
                        enemy_stats = ENEMY_DATA[base_name]
                        new_enemy = Enemy(name=enemy_name, hp=enemy_stats['hp'], armor_class=enemy_stats['ac'], attacks=enemy_stats['attacks'])
                        self.enemies.append(new_enemy)
                self.log_message(f"Feindliste automatisch von der Karte geladen.")
            self.update_ui()
            self.broadcast_map_data()
            if hasattr(self, 'load_map_popup_widget'):
                self.load_map_popup_widget.dismiss()
        except Exception as e:
            create_styled_popup(title="Load Error", content=Label(text=f"Error loading map:\n{e}"), size_hint=(0.7, 0.5)).open()

    def broadcast_map_data(self):
        if self.map_data:
            player_map_data = {
                'rows': self.map_data.get('rows'),
                'cols': self.map_data.get('cols'),
                'enemies': self.map_data.get('enemies', []),
                'tiles': {}
            }
            for pos, tile_data in self.map_data['tiles'].items():
                tile_copy = tile_data.copy()
                if 'furniture' in tile_copy and tile_copy['furniture']:
                    tile_copy['furniture'] = tile_copy['furniture'].copy()
                    tile_copy['furniture'].pop('is_mimic', None)
                if tile_copy.get('type') == 'Trigger':
                    tile_copy['type'] = 'Floor'
                    tile_copy.pop('trigger_message', None)
                player_map_data['tiles'][str(pos)] = tile_copy
            self.network_manager.broadcast_message("MAP_DATA", player_map_data)

    # create_map_grid and update_map_view are now handled by MapGridWidget

    def handle_tile_click(self, instance, touch, row, col):
        """Callback for the custom on_tile_click event from MapGridWidget."""
        if not self.ids.dm_map_grid.collide_point(*touch.pos):
            return False

        if not touch.is_mouse_scrolling:
            if touch.button == 'left':
                self.handle_left_click(row, col)
            elif touch.button == 'right':
                self.handle_right_click(row, col)

    def handle_left_click(self, row, col):
        if self.selected_object and (row, col) in self.highlighted_tiles:
            self.move_object(self.selected_object['name'], (row, col))
        else:
            self.highlighted_tiles = []
            tile_data = self.map_data['tiles'].get((row, col))
            if tile_data and tile_data.get('object'):
                obj_name = tile_data['object']
                self.selected_object = {'name': obj_name, 'pos': (row, col)}
                self.highlight_movement_range(obj_name, row, col)
            else:
                self.selected_object = None
            self.update_map_widget()

    def handle_right_click(self, row, col):
        if not self.selected_object:
            self.log_message("Aktion: Wähle zuerst einen Charakter aus, der angreifen soll (Linksklick).")
            return
        tile_data = self.map_data['tiles'].get((row, col))
        if not tile_data or not tile_data.get('object'):
            self.log_message("Aktion: Du musst auf ein Feld mit einem Ziel klicken.")
            return
        attacker_name = self.selected_object['name']
        target_name = tile_data.get('object')
        if attacker_name == target_name:
            self.log_message("Aktion: Ein Charakter kann sich nicht selbst angreifen.")
            return
        self.dm_attack(attacker_name, target_name)

    def dm_attack(self, attacker_name, target_name):
        if not self.initiative_order:
            self.log_message("FEHLER: Der Kampf hat noch nicht begonnen. Würfle zuerst Initiative.")
            return
        if self.initiative_order and self.current_turn_index >= 0:
            current_turn_name = self.initiative_order[self.current_turn_index][1]
            if attacker_name != current_turn_name:
                self.log_message(f"FEHLER: {attacker_name} kann nicht angreifen, weil {current_turn_name} am Zug ist.")
                return

        if self.turn_action_state.get('attacks_left', 0) <= 0:
            self.log_message(f"AKTION: {attacker_name} hat keine Angriffe mehr in dieser Runde.")
            return

        attacker = self.get_character_or_enemy_by_name(attacker_name)
        target = self.get_character_or_enemy_by_name(target_name)
        if not attacker or not target: return

        if not isinstance(attacker, Enemy):
            self.log_message("FEHLER: Nur Gegner können vom DM zu Angriffen befehligt werden.")
            return

        attacks = attacker.attacks
        if not attacks:
            self.log_message(f"FEHLER: {attacker_name} hat keine Angriffe definiert.")
            return

        if len(attacks) == 1:
            self._execute_dm_attack(attacker, target, attacks[0])
        else:
            content = BoxLayout(orientation='vertical', spacing=10)
            scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
            scroll_content.bind(minimum_height=scroll_content.setter('height'))
            popup = create_styled_popup(title=f"Wähle einen Angriff für {attacker_name}", content=content, size_hint=(0.8, 0.6))
            for attack in attacks:
                btn_text = f"{attack['name']} ({attack.get('damage', 'N/A')})"
                btn = Button(text=btn_text, size_hint_y=None, height=44)
                def on_attack_chosen(instance, chosen_attack=attack):
                    popup.dismiss()
                    self._execute_dm_attack(attacker, target, chosen_attack)
                btn.bind(on_press=on_attack_chosen)
                scroll_content.add_widget(btn)
            scroll_view = ScrollView()
            scroll_view.add_widget(scroll_content)
            content.add_widget(scroll_view)
            popup.open()

    def _execute_dm_attack(self, attacker, target, attack):
        attack_roll = random.randint(1, 20)
        total_attack = attack_roll + attack.get('to_hit', 0)
        self.log_message(f"{attacker.name} greift {target.name} mit {attack['name']} an! Wurf: {attack_roll} + {attack.get('to_hit', 0)} = {total_attack}")
        if total_attack >= target.armor_class:
            damage = roll_dice(attack.get('damage', '1d4'))

            remaining_hp = 0
            if isinstance(target, Character):
                target.hit_points -= damage
                remaining_hp = target.hit_points
            else: # It's an Enemy
                target.hp -= damage
                remaining_hp = target.hp

            self.log_message(f"GETROFFEN! {target.name} erleidet {damage} Schaden. Verbleibende HP: {remaining_hp}")

            if isinstance(target, Character):
                client_addr = self.network_manager.get_client_addr_by_name(target.name)
                if client_addr:
                    self.network_manager.send_message(client_addr, "SET_CHARACTER_DATA", target.to_dict())

            if remaining_hp <= 0:
                self.handle_character_death(target.name)
        else:
            self.log_message("VERFEHLT!")
        self.turn_action_state['attacks_left'] -= 1
        self.update_ui()
        self.broadcast_map_data()
        self.broadcast_game_state()

    def highlight_movement_range(self, obj_name, r_start, c_start):
        movement_left = self.turn_action_state.get('movement_left', 0)
        self.highlighted_tiles = []
        if movement_left <= 0: return
        for r in range(self.map_data['rows']):
            for c in range(self.map_data['cols']):
                dist = abs(r - r_start) + abs(c - c_start)
                if 0 < dist <= movement_left:
                    tile_data = self.map_data['tiles'].get((r,c))
                    if tile_data and tile_data['type'] != 'Wall' and not tile_data.get('object'):
                        self.highlighted_tiles.append((r, c))

    def move_object(self, obj_name, to_pos):
        if self.initiative_order and self.current_turn_index >= 0:
            current_turn_name = self.initiative_order[self.current_turn_index][1]
            if obj_name != current_turn_name:
                self.log_message(f"FEHLER: {obj_name} hat versucht, sich außerhalb der Reihe zu bewegen.")
                return
        elif self.initiative_order:
             self.log_message(f"FEHLER: {obj_name} hat versucht sich zu bewegen, aber niemand ist am Zug.")
             return

        from_pos = None
        for pos, tile in self.map_data['tiles'].items():
            if tile.get('object') == obj_name:
                from_pos = pos
                break

        if from_pos:
            dist = abs(to_pos[0] - from_pos[0]) + abs(to_pos[1] - from_pos[1])
            movement_left = self.turn_action_state.get('movement_left', 0)
            if dist > movement_left:
                self.log_message(f"FEHLER: {obj_name} hat versucht, sich zu weit zu bewegen ({dist} > {movement_left}).")
                return

            self.map_data['tiles'][from_pos]['object'] = None
            self.map_data['tiles'][to_pos]['object'] = obj_name
            self.turn_action_state['movement_left'] -= dist
            self.current_turn_pos = to_pos
            self.log_message(f"{obj_name} von {from_pos} nach {to_pos} bewegt. Verbleibende Bewegung: {self.turn_action_state['movement_left']}")

            self.selected_object = None
            self.highlighted_tiles = []

            self.update_ui()
            self.broadcast_map_data()
            self.check_for_trigger(obj_name, to_pos)

    # (Keep all original helper functions like add_offline_player, save_session, etc.)
    def update_online_players_list(self):
        online_players_widget = self.ids.online_players_list
        online_players_widget.clear_widgets()
        with self.network_manager.lock:
            sorted_clients = sorted(self.network_manager.clients.values(), key=lambda item: item['character'].name)
            for client_info in sorted_clients:
                char_name = client_info['character'].name
                label = Label(text=char_name, size_hint_y=None, height=30)
                online_players_widget.add_widget(label)

    def update_offline_players_list(self):
        offline_players_widget = self.ids.offline_players_list
        offline_players_widget.clear_widgets()
        for player_name in sorted(self.offline_players):
            player_entry = BoxLayout(size_hint_y=None, height=40, spacing=5)
            label = Label(text=player_name)
            remove_button = Button(text="Entfernen", size_hint_x=0.4)
            remove_button.bind(on_press=partial(self.remove_offline_player, player_name))
            player_entry.add_widget(label)
            player_entry.add_widget(remove_button)
            offline_players_widget.add_widget(player_entry)

    def remove_offline_player(self, player_name, instance):
        if player_name in self.offline_players:
            self.offline_players.remove(player_name)
            self.update_offline_players_list()
            self.log_message(f"Offline-Spieler '{player_name}' entfernt.")

    def add_offline_player(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        text_input = TextInput(hint_text="Name des Offline-Spielers", multiline=False)
        content.add_widget(text_input)
        add_button = Button(text="Hinzufügen")
        popup = create_styled_popup(title="Offline-Spieler hinzufügen", content=content, size_hint=(0.6, 0.4))
        def do_add(instance):
            player_name = text_input.text.strip()
            if player_name and player_name not in self.offline_players:
                self.offline_players.append(player_name)
                self.update_offline_players_list()
                self.log_message(f"Offline-Spieler '{player_name}' hinzugefügt.")
                popup.dismiss()
        add_button.bind(on_press=do_add)
        content.add_widget(add_button)
        popup.open()

    def add_enemy(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))
        for name, data in sorted(ENEMY_DATA.items()):
            btn = Button(text=name, size_hint_y=None, height=44)
            btn.bind(on_press=partial(self.create_enemy_instance, name, data))
            scroll_content.add_widget(btn)
        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        content.add_widget(scroll_view)
        self.enemy_popup = create_styled_popup(title="Gegner hinzufügen", content=content, size_hint=(0.8, 0.8))
        self.enemy_popup.open()

    def save_session(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        text_input = TextInput(hint_text="Sitzungsname (ohne .json)", multiline=False)
        content.add_widget(text_input)
        save_button = Button(text="Speichern")
        popup = create_styled_popup(title="Sitzung speichern", content=content, size_hint=(0.7, 0.4))
        def do_save(instance):
            filename = text_input.text.strip()
            if not filename:
                return
            filename = f"{filename}.json"
            saves_dir = "utils/data/sessions"
            os.makedirs(saves_dir, exist_ok=True)
            filepath = os.path.join(saves_dir, filename)
            with self.network_manager.lock:
                online_players = [client['character'].to_dict() for client in self.network_manager.clients.values()]
            map_data_to_save = None
            if self.map_data:
                map_data_to_save = self.map_data.copy()
                map_data_to_save['tiles'] = {str(k): v for k, v in self.map_data['tiles'].items()}
            session_data = {
                'online_players': online_players,
                'offline_players': self.offline_players,
                'enemies': [enemy.to_dict() for enemy in self.enemies],
                'map_data': map_data_to_save,
                'log': self.ids.log_output.text,
                'initiative_order': self.initiative_order,
                'current_turn_index': self.current_turn_index,
            }
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, indent=4, ensure_ascii=False)
                self.log_message(f"Sitzung in '{filename}' gespeichert.")
                popup.dismiss()
            except Exception as e:
                create_styled_popup(title="Speicherfehler", content=Label(text=f"Fehler:\\n{e}"), size_hint=(0.7,0.5)).open()
        save_button.bind(on_press=do_save)
        content.add_widget(save_button)
        popup.open()

    def load_map_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))
        maps_dir = "utils/data/maps"
        os.makedirs(maps_dir, exist_ok=True)
        map_files = [f for f in os.listdir(maps_dir) if f.endswith('.json')]
        if not map_files:
            create_styled_popup(title="Keine Karten", content=Label(text="Keine Karten zum Laden gefunden."), size_hint=(0.6, 0.4)).open()
            return
        for filename in sorted(map_files):
            btn = Button(text=filename, size_hint_y=None, height=44)
            btn.bind(on_press=partial(self.do_load_map, filename))
            scroll_content.add_widget(btn)
        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        content.add_widget(scroll_view)
        self.load_map_popup_widget = create_styled_popup(title="Karte laden", content=content, size_hint=(0.8, 0.8))
        self.load_map_popup_widget.open()

    def update_enemies_list_ui(self):
        enemy_list_widget = self.ids.enemies_list
        enemy_list_widget.clear_widgets()
        for enemy in self.enemies:
            enemy_entry = BoxLayout(size_hint_y=None, height=40)
            name_button = Button(text=enemy.name)
            name_button.bind(on_press=partial(self.show_enemy_stats, enemy))
            remove_button = Button(text="Entfernen", size_hint_x=0.3, on_press=partial(self.remove_enemy, enemy))
            enemy_entry.add_widget(name_button)
            enemy_entry.add_widget(remove_button)
            enemy_list_widget.add_widget(enemy_entry)

    def remove_enemy(self, enemy, instance):
        if enemy in self.enemies:
            self.enemies.remove(enemy)
            self.update_enemies_list_ui()
            self.log_message(f"Gegner '{enemy.name}' entfernt.")

    def update_objects_list_ui(self):
        objects_list_widget = self.ids.objects_list
        objects_list_widget.clear_widgets()
        if not self.map_data or not self.map_data.get('tiles'):
            return
        for pos, tile_data in self.map_data['tiles'].items():
            if tile_data.get('furniture'):
                furn = tile_data['furniture']
                furn_type = furn['type']
                is_mimic = furn.get('is_mimic', False)
                text = f"{furn_type} at {pos}"
                if is_mimic:
                    text += " (Mimic!)"
                label = Label(text=text, size_hint_y=None, height=30)
                if is_mimic:
                    label.color = (1, 0.5, 1, 1)
                objects_list_widget.add_widget(label)

    def check_for_trigger(self, obj_name, pos):
        tile = self.map_data['tiles'].get(pos)
        if not tile or tile.get('type') != 'Trigger':
            return
        message = tile.get('trigger_message')
        if not message:
            return
        player_addr = None
        with self.network_manager.lock:
            for addr, client_info in self.network_manager.clients.items():
                if client_info['character'].name == obj_name:
                    player_addr = addr
                    break
        if player_addr:
            self.log_message(f"Trigger ausgelöst bei {pos} von {obj_name}. Sende Nachricht.")
            self.network_manager.send_message(player_addr, "TRIGGER_MESSAGE", {'message': message})

    def _editor_callback(self, instance, map_data=None):
        editor_screen = self.manager.get_screen('map_editor')
        if not isinstance(map_data, dict):
            map_data = None
        if map_data:
            editor_screen.preloaded_map_data = map_data
        else:
            editor_screen.preloaded_map_data = None
        self.app.change_screen('map_editor')

    def create_new_map(self):
        self._editor_callback(None, map_data=None)

    def edit_existing_map(self):
        self.select_map_to_edit_popup(self._editor_callback)

    def select_map_to_edit_popup(self, callback):
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))
        saves_dir = "utils/data/maps"
        os.makedirs(saves_dir, exist_ok=True)
        map_files = [f for f in os.listdir(saves_dir) if f.endswith('.json')]
        if not map_files:
            create_styled_popup(title="No Maps", content=Label(text="No saved maps found to edit."), size_hint=(0.6, 0.4)).open()
            return
        for filename in map_files:
            btn = Button(text=filename, size_hint_y=None, height=44)
            btn.bind(on_press=lambda x, f=filename: self.load_and_pass_map_to_editor(f, callback))
            scroll_content.add_widget(btn)
        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        content.add_widget(scroll_view)
        self.edit_map_popup = create_styled_popup(title="Select Map to Edit", content=content, size_hint=(0.8, 0.8))
        self.edit_map_popup.open()

    def load_and_pass_map_to_editor(self, filename, callback):
        filepath = os.path.join("utils/data/maps", filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            if hasattr(self, 'edit_map_popup'):
                self.edit_map_popup.dismiss()
            callback(None, map_data=loaded_data)
        except Exception as e:
            create_styled_popup(title="Load Error", content=Label(text=f"Error loading map for editing:\n{e}"), size_hint=(0.7, 0.5)).open()
