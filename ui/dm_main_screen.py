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
from core.game_manager import GameManager
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup, get_user_saves_dir
from utils.non_ui_helpers import roll_dice
from functools import partial
from utils.data_manager import ENEMY_DATA
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

class DMMainScreen(Screen):
    def add_offline_player_popup(self):
        # Popup für neuen Offline-Spieler mit AC, Angriffsbonus, Übungsbonus, Schaden
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        name_input = TextInput(hint_text="Name", multiline=False)
        ac_input = TextInput(hint_text="Rüstungsklasse (AC)", multiline=False, input_filter='int')
        attack_bonus_input = TextInput(hint_text="Angriffsbonus", multiline=False, input_filter='int')
        proficiency_input = TextInput(hint_text="Übungsbonus", multiline=False, input_filter='int')
        damage_input = TextInput(hint_text="Schaden (z.B. 2d4)", multiline=False)
        add_btn = Button(text="Hinzufügen")
        cancel_btn = Button(text="Abbrechen")
        btn_box = BoxLayout(orientation='horizontal', spacing=10)
        btn_box.add_widget(add_btn)
        btn_box.add_widget(cancel_btn)
        content.add_widget(Label(text="Neuen Offline-Spieler anlegen:"))
        content.add_widget(name_input)
        content.add_widget(ac_input)
        content.add_widget(attack_bonus_input)
        content.add_widget(proficiency_input)
        content.add_widget(damage_input)
        content.add_widget(btn_box)
        popup = create_styled_popup(title="Offline-Spieler hinzufügen", content=content, size_hint=(0.5, 0.7))

        def on_add(instance):
            name = name_input.text.strip()
            try:
                ac = int(ac_input.text.strip())
            except Exception:
                ac = 10
            try:
                attack_bonus = int(attack_bonus_input.text.strip())
            except Exception:
                attack_bonus = 0
            try:
                proficiency = int(proficiency_input.text.strip())
            except Exception:
                proficiency = 2
            damage = damage_input.text.strip() or "1d8"
            if not name:
                self.log_message("Name darf nicht leer sein!")
                return
            char = Character(name, race="", char_class="")
            char.armor_class = ac
            char.attack_bonus = attack_bonus
            char.proficiency = proficiency
            char.attacks = [{"name": "Angriff", "damage": damage}]
            if not hasattr(self.game_manager, 'offline_players'):
                self.game_manager.offline_players = []
            self.game_manager.offline_players.append(char)
            self.update_offline_players_list()
            popup.dismiss()

        add_btn.bind(on_press=on_add)
        cancel_btn.bind(on_press=popup.dismiss)
        popup.open()
    def update_offline_players_list(self):
        offline_players_widget = self.ids.offline_players_list
        offline_players_widget.clear_widgets()
        for char in self.game_manager.offline_players:
            box = BoxLayout(orientation='horizontal', size_hint_y=None, height=30)
            label = Label(text=char.name, size_hint_x=0.7)
            remove_btn = Button(text="Entfernen", size_hint_x=0.3, size_hint_y=None, height=30)
            def make_remove_callback(c):
                return lambda instance: self.remove_offline_player(c)
            remove_btn.bind(on_press=make_remove_callback(char))
            box.add_widget(label)
            box.add_widget(remove_btn)
            offline_players_widget.add_widget(box)

    def remove_offline_player(self, char):
        if char in self.game_manager.offline_players:
            self.game_manager.offline_players.remove(char)
            self.update_offline_players_list()
    """The main screen for the Dungeon Master to manage the game."""
    def __init__(self, **kwargs):
        super(DMMainScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.network_manager = self.app.network_manager
        self.game_manager = GameManager(logger_func=self.log_message)
        self.update_event = None
        self.selected_object = None
        self.highlighted_tiles = []
        self._map_widget_bound = False
        self.dm_selected_attacker = None  # Stores attacker name (player or enemy)

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def on_enter(self, *args):
        if not self._map_widget_bound:
            self.ids.dm_map_grid.bind(on_tile_click=self.handle_tile_click)
            self._map_widget_bound = True

        if self.app.edited_map_data:
            self.game_manager.map_data = self.app.edited_map_data
            self.app.edited_map_data = None
            self.log_message("Zuletzt bearbeitete Karte geladen.")
            self.update_map_widget()
            self.broadcast_map_data()
        else:
            self.network_manager.broadcast_message("GAME_START", "Das Spiel beginnt!")
            self.load_state_from_manager()

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
            from core.character import Character
            offline_players_raw = session.get('offline_players', [])
            offline_players = []
            for p in offline_players_raw:
                if isinstance(p, Character):
                    offline_players.append(p)
                elif isinstance(p, dict):
                    offline_players.append(Character.from_dict(p))
            self.game_manager.offline_players = offline_players

            # online_players from session are now just a list of character dicts
            # The real online players are managed by NetworkManager
            self.game_manager.online_players = {} # Will be populated by NetworkManager joins

            self.game_manager.map_data = session.get('map_data', None)

            if self.game_manager.map_data and 'enemies' in self.game_manager.map_data:
                self.game_manager.enemies.clear()
                for enemy_name in self.game_manager.map_data['enemies']:
                    base_name = enemy_name.split('#')[0].strip()
                    if base_name in ENEMY_DATA:
                        enemy_stats = ENEMY_DATA[base_name]
                        new_enemy = Enemy(name=enemy_name, hp=enemy_stats['hp'], armor_class=enemy_stats.get('ac', 10), attacks=enemy_stats['attacks'])
                        self.game_manager.enemies.append(new_enemy)
                self.log_message("Feindliste automatisch von der Karte geladen.")
            else:
                self.game_manager.enemies = [Enemy.from_dict(e) for e in session.get('enemies', [])]

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
            if source == 'PLAYER_JOINED':
                char = message['char']
                # Falls char ein dict ist, in Character umwandeln
                if isinstance(char, dict):
                    from core.character import Character
                    char = Character.from_dict(char)
                self.game_manager.online_players[char.name] = char
                self.update_ui()
                return
            if source == 'PLAYER_LEFT':
                char_name = message['name']
                if char_name in self.game_manager.online_players:
                    del self.game_manager.online_players[char_name]
                self.update_ui()
                return

            msg_type = message.get('type')
            payload = message.get('payload')
            player_char = self.network_manager.clients[source]['character']

            if msg_type == 'MOVE_OBJECT':
                success, reason = self.game_manager.move_object(payload['name'], tuple(payload['to_pos']))
                if success:
                    self.update_ui()
                    self.broadcast_map_data()
                    self.check_for_trigger(payload['name'], tuple(payload['to_pos']))
                else:
                    self.network_manager.send_message(source, "ERROR", reason)

            elif msg_type == 'PLAYER_ATTACK':
                result = self.game_manager.handle_attack(
                    attacker_name=player_char.name,
                    target_name=payload.get('enemy_name'),
                    attack_roll=payload.get('attack_roll'),
                    damage_roll=payload.get('damage')
                )
                if result.get('success'):
                    self.update_ui()
                    self.broadcast_game_state()
                else:
                    self.network_manager.send_message(source, "ERROR", result.get('reason'))

            elif msg_type == 'END_TURN':
                current_turn_name = self.game_manager.get_current_turn_info()['name']
                if current_turn_name == player_char.name:
                    self.end_turn()
                else:
                    self.log_message(f"Warning: {player_char.name} tried to end turn, but it's not their turn.")

            elif msg_type == 'INTERACT_WITH_OBJECT':
                self.handle_interaction(player_char.name, tuple(payload['pos']))
        except Empty:
            pass

    def get_character_or_enemy_by_name(self, name):
        return self.game_manager.get_character_or_enemy_by_name(name)

    def handle_character_death(self, character_name):
        # This method is now fully handled by the game manager
        # The UI update and broadcast calls will happen in the calling method
        outcome = self.game_manager.handle_character_death(character_name)
        if outcome == "VICTORY":
             self.network_manager.broadcast_message("VICTORY", "Alle Feinde wurden besiegt!")
        self.update_ui()
        self.broadcast_map_data()
        self.broadcast_game_state()

    def handle_player_attack(self, player_name, payload):
        # This is now handled in check_for_updates
        pass

    def handle_interaction(self, player_name, pos):
        if not self.game_manager.map_data or pos not in self.game_manager.map_data['tiles']:
            return
        tile = self.game_manager.map_data['tiles'][pos]
        furniture = tile.get('furniture')
        if not furniture: return
        furn_type = furniture['type']
        if furniture.get('is_mimic'):
            self.log_message(f"MIMIC! Die {furn_type} bei {pos} entpuppt sich als Mimic, als {player_name} interagiert!")
            tile['furniture'] = None
            mimic_data = ENEMY_DATA.get('Mimic', {'hp': 30, 'ac': 12, 'attacks': [{'name': 'Biss', 'damage': '1d8+3'}]})
            count = 1
            for enemy in self.game_manager.enemies:
                if enemy.name.startswith('Mimic'):
                    try:
                        num = int(enemy.name.split('#')[-1])
                        if num >= count: count = num + 1
                    except (ValueError, IndexError): continue
            unique_name = f"Mimic #{count}"
            new_enemy = Enemy(name=unique_name, hp=mimic_data['hp'], armor_class=mimic_data['ac'], attacks=mimic_data['attacks'])
            self.game_manager.enemies.append(new_enemy)
            tile['object'] = new_enemy.name
            self.update_ui()
            self.broadcast_map_data()
        else:
            self.log_message(f"{player_name} interagiert mit {furn_type} bei {pos}.")

    def update_ui(self):
        self.update_online_players_list()
        self.update_offline_players_list()
        self.update_enemies_list_ui()
        self.update_initiative_ui()
        if self.game_manager.map_data:
            self.update_objects_list_ui()
            self.update_map_widget()

    def update_map_widget(self):
        if self.game_manager.map_data:
            current_turn_info = self.game_manager.get_current_turn_info()
            map_widget = self.ids.dm_map_grid
            map_widget.set_data(
                map_data=self.game_manager.map_data,
                highlighted_tiles=self.highlighted_tiles,
                current_turn_pos=current_turn_info['pos']
            )

    def log_message(self, message):
        # A check to prevent errors during __init__
        if hasattr(self, 'ids') and self.ids.get('log_output'):
            self.ids.log_output.text += f"{message}\n"
        else:
            print(f"LOG: {message}")

    def roll_initiative_for_all(self):
        # Update game manager with current combatants
        with self.network_manager.lock:
            self.game_manager.online_players = {c['character'].name: c['character'] for c in self.network_manager.clients.values()}

        # Füge offline Spieler zur Initiative hinzu
        all_online = list(self.game_manager.online_players.values())
        all_offline = getattr(self.game_manager, 'offline_players', [])
        self.game_manager._initiative_override_players = all_online + all_offline

        # Patch: roll_initiative_for_all nimmt jetzt alle Spieler (online+offline)
        initiative_order = self.game_manager.roll_initiative_for_all(players=all_online + all_offline)

        log_msg = "Initiativereihenfolge:\n" + "\n".join([f"{roll}: {name}" for roll, name in initiative_order])
        self.log_message(log_msg)

        self.update_initiative_ui()
        self.broadcast_game_state()

    def end_turn(self):
        self.game_manager.end_turn()
        self.update_ui()
        self.broadcast_game_state()

    def start_next_turn(self):
        # This is now handled internally by game_manager on roll_initiative and end_turn
        pass

    def broadcast_game_state(self):
        current_turn_info = self.game_manager.get_current_turn_info()
        state = {
            'players': list(self.game_manager.online_players.keys()),
            'initiative': self.game_manager.initiative_order,
            'current_turn': current_turn_info['name'],
            'current_turn_pos': current_turn_info['pos'],
            'turn_action_state': current_turn_info['state']
        }
        self.network_manager.broadcast_message("GAME_STATE_UPDATE", state)

    def update_initiative_ui(self):
        initiative_list_widget = self.ids.initiative_list
        initiative_list_widget.clear_widgets()
        current_turn_name = self.game_manager.get_current_turn_info()['name']

        for i, (roll, name) in enumerate(self.game_manager.initiative_order):
            text = f"{roll}: {name}"
            label = Label(text=text, size_hint_y=None, height=30)
            if name == current_turn_name:
                label.color = (0.2, 1, 0.2, 1)
                label.bold = True
            initiative_list_widget.add_widget(label)
        self.ids.current_turn_label.text = f"Am Zug: {current_turn_name or 'Niemand'}"

    def create_enemy_instance(self, name, data, instance):
        count = 1
        for enemy in self.game_manager.enemies:
            if enemy.name.startswith(name):
                try:
                    num = int(enemy.name.split('#')[-1])
                    if num >= count: count = num + 1
                except (ValueError, IndexError): continue
        unique_name = f"{name} #{count}"
        new_enemy = Enemy(name=unique_name, hp=data['hp'], armor_class=data['ac'], attacks=data['attacks'])
        self.game_manager.enemies.append(new_enemy)
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
        maps_dir = get_user_saves_dir("maps")
        filepath = os.path.join(maps_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            self.game_manager.map_data = loaded_data
            self.game_manager.map_data['tiles'] = {eval(k): v for k, v in loaded_data['tiles'].items()}
            self.log_message(f"Map '{filename}' geladen.")
            # Feinde laden
            if 'enemies' in loaded_data:
                self.game_manager.enemies.clear()
                for enemy_name in loaded_data['enemies']:
                    base_name = enemy_name.split('#')[0].strip()
                    if base_name in ENEMY_DATA:
                        enemy_stats = ENEMY_DATA[base_name]
                        new_enemy = Enemy(name=enemy_name, hp=enemy_stats['hp'], armor_class=enemy_stats['ac'], attacks=enemy_stats['attacks'])
                        self.game_manager.enemies.append(new_enemy)
                self.log_message(f"Feindliste automatisch von der Karte geladen.")
            # Offline-Spieler laden
            if 'offline_players' in loaded_data:
                offline_players = []
                for p in loaded_data['offline_players']:
                    if isinstance(p, dict):
                        offline_players.append(Character.from_dict(p))
                self.game_manager.offline_players = offline_players
            # UI nur einmal am Ende aktualisieren
            self.update_ui()
            self.broadcast_map_data()
            if hasattr(self, 'load_map_popup_widget'):
                self.load_map_popup_widget.dismiss()
        except Exception as e:
            create_styled_popup(title="Load Error", content=Label(text=f"Error loading map:\n{e}"), size_hint=(0.7, 0.5)).open()

    def broadcast_map_data(self):
        if self.game_manager.map_data:
            map_data = self.game_manager.map_data
            player_map_data = {
                'rows': map_data.get('rows'),
                'cols': map_data.get('cols'),
                'enemies': map_data.get('enemies', []),
                'tiles': {}
            }
            for pos, tile_data in map_data['tiles'].items():
                tile_copy = tile_data.copy()
                if 'furniture' in tile_copy and tile_copy['furniture']:
                    tile_copy['furniture'] = tile_copy['furniture'].copy()
                    tile_copy['furniture'].pop('is_mimic', None)
                if tile_copy.get('type') == 'Trigger':
                    tile_copy['type'] = 'Floor'
                    tile_copy.pop('trigger_message', None)
                player_map_data['tiles'][str(pos)] = tile_copy
            self.network_manager.broadcast_message("MAP_DATA", player_map_data)

    def handle_tile_click(self, instance, touch, row, col):
        if not self.ids.dm_map_grid.collide_point(*touch.pos):
            return False
        if not touch.is_mouse_scrolling:
            if touch.button == 'left':
                self.handle_left_click(row, col)
            elif touch.button == 'right':
                self.handle_right_click(row, col)

    def handle_left_click(self, row, col):
        # DM selects and moves player or enemy with left click
        if not self.game_manager.map_data:
            return
        tile_data = self.game_manager.map_data['tiles'].get((row, col))
        # 1. Wenn ein Objekt ausgewählt ist und das Feld leer & im Bewegungsbereich ist: bewegen
        if self.selected_object and not (tile_data and tile_data.get('object')):
            obj_name = self.selected_object['name']
            # Prüfe, ob das Feld im Bewegungsbereich ist
            if (row, col) in self.highlighted_tiles:
                self.move_object(obj_name, (row, col))
                self.selected_object = None
                self.dm_selected_attacker = None
                self.highlighted_tiles = []
                self.update_map_widget()
                return
        # 2. Wenn ein Objekt (Spieler oder Gegner) angeklickt wird: auswählen und Bewegungsreichweite anzeigen
        if tile_data and tile_data.get('object'):
            obj_name = tile_data['object']
            self.selected_object = {'name': obj_name, 'pos': (row, col)}
            self.dm_selected_attacker = obj_name
            self.log_message(f"Ausgewählt: {obj_name}. Linksklick auf ein freies Feld zum Bewegen, Rechtsklick auf Ziel für Angriff.")
            self.highlight_movement_range(obj_name, row, col)
        else:
            self.selected_object = None
            self.dm_selected_attacker = None
            self.highlighted_tiles = []
        self.update_map_widget()

    def handle_right_click(self, row, col):
        # DM right-clicks a target to attack with selected attacker
        if not self.dm_selected_attacker:
            self.log_message("Aktion: Wähle zuerst einen Angreifer mit Linksklick.")
            return
        if not self.game_manager.map_data:
            return
        tile_data = self.game_manager.map_data['tiles'].get((row, col))
        if not tile_data or not tile_data.get('object'):
            self.log_message("Aktion: Du musst auf ein Feld mit einem Ziel klicken.")
            return
        attacker_name = self.dm_selected_attacker
        target_name = tile_data.get('object')
        if attacker_name == target_name:
            self.log_message("Aktion: Ein Charakter kann sich nicht selbst angreifen.")
            return
        self.dm_attack(attacker_name, target_name)
        # Reset selection after attack
        self.dm_selected_attacker = None
        self.selected_object = None
        self.update_map_widget()

    def dm_attack(self, attacker_name, target_name):
        current_turn_name = self.game_manager.get_current_turn_info()['name']
        if not current_turn_name:
            self.log_message("FEHLER: Der Kampf hat noch nicht begonnen. Würfle zuerst Initiative.")
            return
        if attacker_name != current_turn_name:
            self.log_message(f"FEHLER: {attacker_name} kann nicht angreifen, weil {current_turn_name} am Zug ist.")
            return

        attacker = self.game_manager.get_character_or_enemy_by_name(attacker_name)
        # DM kann jetzt auch offline Spieler (Character) angreifen lassen
        if isinstance(attacker, Enemy):
            attacks = attacker.attacks
            if not attacks:
                self.log_message(f"FEHLER: {attacker_name} hat keine Angriffe definiert.")
                return
            if len(attacks) == 1:
                self._execute_dm_attack(attacker, target_name, attacks[0])
            else:
                # Attack choice popup
                content = BoxLayout(orientation='vertical', spacing=10)
                scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
                scroll_content.bind(minimum_height=scroll_content.setter('height'))
                popup = create_styled_popup(title=f"Wähle einen Angriff für {attacker_name}", content=content, size_hint=(0.8, 0.6))
                for attack in attacks:
                    btn_text = f"{attack['name']} ({attack.get('damage', 'N/A')})"
                    btn = Button(text=btn_text, size_hint_y=None, height=44)
                    def on_attack_chosen(instance, chosen_attack=attack):
                        popup.dismiss()
                        self._execute_dm_attack(attacker, target_name, chosen_attack)
                    btn.bind(on_press=on_attack_chosen)
                    scroll_content.add_widget(btn)
                scroll_view = ScrollView()
                scroll_view.add_widget(scroll_content)
                content.add_widget(scroll_view)
                popup.open()
        elif isinstance(attacker, Character):
            # Standardangriff für Spieler: 1d20+Angriffsbonus, 1d8 Schaden (oder aus Attacks-Liste falls vorhanden)
            if hasattr(attacker, 'attacks') and attacker.attacks:
                attack = attacker.attacks[0]
                # Simpler Angriff: 1d20+to_hit, Schaden aus Attack
                import random
                from utils.non_ui_helpers import roll_dice
                attack_roll = random.randint(1, 20) + getattr(attack, 'to_hit', 0)
                damage = roll_dice(attack.get('damage', '1d8'))
            else:
                import random
                attack_roll = random.randint(1, 20) + getattr(attacker, 'attack_bonus', 0)
                damage = random.randint(1, 8)
            result = self.game_manager.handle_attack(attacker.name, target_name, attack_roll=attack_roll, damage_roll=damage)
            if result.get('success'):
                self.update_ui()
                self.broadcast_game_state()
            else:
                self.log_message(f"ERROR: {result.get('reason')}")
        else:
            self.log_message("FEHLER: Unbekannter Angreifer-Typ.")
            return

    def _execute_dm_attack(self, attacker, target_name, attack):
        result = self.game_manager.handle_attack(attacker.name, target_name)
        if result.get('success'):
            self.update_ui()
            self.broadcast_game_state()
        else:
            self.log_message(f"ERROR: {result.get('reason')}")

    def highlight_movement_range(self, obj_name, r_start, c_start):
        turn_state = self.game_manager.get_current_turn_info()['state']
        movement_left = turn_state.get('movement_left', 0)
        self.highlighted_tiles = []
        if movement_left <= 0 or not self.game_manager.map_data: return

        for r in range(self.game_manager.map_data['rows']):
            for c in range(self.game_manager.map_data['cols']):
                dist = abs(r - r_start) + abs(c - c_start)
                if 0 < dist <= movement_left:
                    tile_data = self.game_manager.map_data['tiles'].get((r,c))
                    if tile_data and tile_data['type'] != 'Wall' and not tile_data.get('object'):
                        self.highlighted_tiles.append((r, c))

    def move_object(self, obj_name, to_pos):
        success, reason = self.game_manager.move_object(obj_name, to_pos)
        if success:
            self.selected_object = None
            self.highlighted_tiles = []
            self.update_ui()
            self.broadcast_map_data()
            self.check_for_trigger(obj_name, to_pos)
        else:
            self.log_message(f"FEHLER: {reason}")

    def update_online_players_list(self):
        online_players_widget = self.ids.online_players_list
        online_players_widget.clear_widgets()
        def get_name(p):
            return p.name if hasattr(p, 'name') else str(p)
        sorted_players = sorted(self.game_manager.online_players.values(), key=get_name)
        for char in sorted_players:
            label = Label(text=get_name(char), size_hint_y=None, height=30)
            online_players_widget.add_widget(label)

    def update_offline_players_list(self):
        offline_players_widget = self.ids.offline_players_list
        offline_players_widget.clear_widgets()
        def get_name(p):
            return p.name if hasattr(p, 'name') else str(p)
        for player in sorted(self.game_manager.offline_players, key=get_name):
            name = get_name(player)
            player_entry = BoxLayout(size_hint_y=None, height=40, spacing=5)
            label = Label(text=name)
            remove_button = Button(text="Entfernen", size_hint_x=0.4)
            remove_button.bind(on_press=partial(self.remove_offline_player, player))
            player_entry.add_widget(label)
            player_entry.add_widget(remove_button)
            offline_players_widget.add_widget(player_entry)

    def remove_offline_player(self, player, instance=None):
        if player in self.game_manager.offline_players:
            self.game_manager.offline_players.remove(player)
            self.update_offline_players_list()
            name = player.name if hasattr(player, 'name') else str(player)
            self.log_message(f"Offline-Spieler '{name}' entfernt.")

    def add_offline_player(self):
        self.add_offline_player_popup()

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
            if not filename: return
            filename = f"{filename}.json"
            saves_dir = get_user_saves_dir("sessions")
            filepath = os.path.join(saves_dir, filename)

            map_data_to_save = None
            if self.game_manager.map_data:
                map_data_to_save = self.game_manager.map_data.copy()
                map_data_to_save['tiles'] = {str(k): v for k, v in self.game_manager.map_data['tiles'].items()}

            session_data = {
                'online_players': [p.to_dict() for p in self.game_manager.online_players.values()],
                'offline_players': [p.to_dict() for p in self.game_manager.offline_players],
                'enemies': [e.to_dict() for e in self.game_manager.enemies],
                'map_data': map_data_to_save,
                'log': self.ids.log_output.text,
                'initiative_order': self.game_manager.initiative_order,
                'current_turn_index': self.game_manager.current_turn_index,
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
        maps_dir = get_user_saves_dir("maps")
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
        for enemy in self.game_manager.enemies:
            enemy_entry = BoxLayout(size_hint_y=None, height=40)
            name_button = Button(text=enemy.name)
            name_button.bind(on_press=partial(self.show_enemy_stats, enemy))
            remove_button = Button(text="Entfernen", size_hint_x=0.3, on_press=partial(self.remove_enemy, enemy))
            enemy_entry.add_widget(name_button)
            enemy_entry.add_widget(remove_button)
            enemy_list_widget.add_widget(enemy_entry)

    def remove_enemy(self, enemy, instance):
        if enemy in self.game_manager.enemies:
            self.game_manager.enemies.remove(enemy)
            self.update_enemies_list_ui()
            self.log_message(f"Gegner '{enemy.name}' entfernt.")

    def update_objects_list_ui(self):
        objects_list_widget = self.ids.objects_list
        objects_list_widget.clear_widgets()
        if not self.game_manager.map_data or not self.game_manager.map_data.get('tiles'):
            return
        for pos, tile_data in self.game_manager.map_data['tiles'].items():
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
        if not self.game_manager.map_data: return
        tile = self.game_manager.map_data['tiles'].get(pos)
        if not tile or tile.get('type') != 'Trigger':
            return
        message = tile.get('trigger_message')
        if not message:
            return

        player_char = self.game_manager.get_character_or_enemy_by_name(obj_name)
        if player_char and isinstance(player_char, Character):
            player_addr = self.network_manager.get_client_addr_by_name(obj_name)
            if player_addr:
                self.log_message(f"Trigger ausgelöst bei {pos} von {obj_name}. Sende Nachricht.")
                self.network_manager.send_message(player_addr, "TRIGGER_MESSAGE", {'message': message})

    def _editor_callback(self, instance, map_data=None):
        # Kopiere offline_players und online_players ins App-Objekt für den Map-Editor
        from core.character import Character
        offline_players = []
        for p in getattr(self.game_manager, 'offline_players', []):
            if isinstance(p, Character):
                offline_players.append(p)
            elif isinstance(p, dict):
                offline_players.append(Character.from_dict(p))
        self.app.game_manager.offline_players = offline_players
        self.app.game_manager.online_players = dict(getattr(self.game_manager, 'online_players', {}))
        editor_screen = self.manager.get_screen('map_editor')
        if not isinstance(map_data, dict):
            map_data = None
        editor_screen.preloaded_map_data = map_data or self.game_manager.map_data
        self.app.change_screen('map_editor')

    def create_new_map(self):
        self._editor_callback(None, map_data=None)

    def edit_existing_map(self):
        self.select_map_to_edit_popup(self._editor_callback)

    def select_map_to_edit_popup(self, callback):
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))
        saves_dir = get_user_saves_dir("maps")
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
        maps_dir = get_user_saves_dir("maps")
        filepath = os.path.join(maps_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            if hasattr(self, 'edit_map_popup'):
                self.edit_map_popup.dismiss()
            callback(None, map_data=loaded_data)
        except Exception as e:
            create_styled_popup(title="Load Error", content=Label(text=f"Error loading map for editing:\n{e}"), size_hint=(0.7, 0.5)).open()
