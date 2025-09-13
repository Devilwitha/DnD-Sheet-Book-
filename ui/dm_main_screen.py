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
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup
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

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def on_enter(self, *args):
        # Check if we are returning from the map editor with a newly saved map
        if self.app.edited_map_data:
            self.map_data = self.app.edited_map_data
            self.app.edited_map_data = None # Clear it so it's not reloaded
            self.log_message("Zuletzt bearbeitete Karte geladen.")
            self.broadcast_map_data()
        else:
            # Normal on_enter logic
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
            self.app.loaded_session_data = None # Clear after use
        elif hasattr(self.app, 'prepared_session_data') and self.app.prepared_session_data:
            session = self.app.prepared_session_data
            self.app.prepared_session_data = None # Clear after use

        if session:
            self.offline_players = session.get('offline_players', [])
            self.map_data = session.get('map_data', None)

            # Prioritize loading enemies from the map data if it exists and has an enemy list
            if self.map_data and 'enemies' in self.map_data:
                self.enemies.clear()
                for enemy_name in self.map_data['enemies']:
                    base_name = enemy_name.split('#')[0].strip()
                    if base_name in ENEMY_DATA:
                        enemy_stats = ENEMY_DATA[base_name]
                        new_enemy = Enemy(
                            name=enemy_name,
                            hp=enemy_stats['hp'],
                            ac=enemy_stats['ac'],
                            attacks=enemy_stats['attacks']
                        )
                        self.enemies.append(new_enemy)
                self.log_message("Feindliste automatisch von der Karte geladen.")
            else:
                # Fallback to the session's enemy list
                self.enemies = [Enemy.from_dict(e) for e in session.get('enemies', [])]

            log_text = session.get('log', "Neue Sitzung gestartet.\n")
            if session.get('type') == 'prepared':
                log_text += f"Notizen: {session.get('notes', '')}\n"
            self.ids.log_output.text = log_text
        else:
            self.ids.log_output.text = "Neue Sitzung gestartet.\n"

    def check_for_updates(self, dt):
        try:
            # Process one message per frame to avoid freezing
            item = self.network_manager.incoming_messages.get_nowait()
            if not isinstance(item, tuple) or len(item) != 2: return

            source, message = item
            if source in ['PLAYER_JOINED', 'PLAYER_LEFT']:
                self.log_message(f"System: {source} - {message.get('name', 'Unknown')}")
                self.update_online_players_list()
                self.broadcast_game_state()
                if self.map_data: self.broadcast_map_data()
                return

            msg_type = message.get('type')
            payload = message.get('payload')

            if msg_type == 'LOG':
                player_name = self.network_manager.clients[source]['character'].name
                self.log_message(f"{player_name}: {payload}")
            elif msg_type == 'SET_CHARACTER_DATA':
                with self.network_manager.lock:
                    if source in self.network_manager.clients:
                        new_char = Character.from_dict(payload)
                        self.network_manager.clients[source]['character'] = new_char
                        self.log_message(f"System: {new_char.name}'s data has been updated.")
                # Call UI update outside the lock
                self.update_online_players_list()
            elif msg_type == 'MOVE_OBJECT':
                to_pos_tuple = tuple(payload['to_pos'])
                self.log_message(f"Processing MOVE_OBJECT for {payload['name']} to {to_pos_tuple}")
                self.move_object(payload['name'], to_pos_tuple)
                # The move_object function already logs the move.
                # Now, broadcast the entire updated map state.
                self.log_message(f"Broadcasting updated map data after move.")
                self.broadcast_map_data()
            elif msg_type == 'INTERACT_WITH_OBJECT':
                pos = tuple(payload['pos'])
                player_name = self.network_manager.clients[source]['character'].name
                self.handle_interaction(player_name, pos)
            elif msg_type == 'PLAYER_ATTACK':
                player_name = self.network_manager.clients[source]['character'].name
                self.handle_player_attack(player_name, payload)

        except Empty:
            pass

    def handle_player_attack(self, player_name, payload):
        enemy_name = payload.get('enemy_name')
        attack_roll = payload.get('attack_roll')
        damage = payload.get('damage')
        details = payload.get('details', '') # For auto-roll logging

        target_enemy = None
        for enemy in self.enemies:
            if enemy.name == enemy_name:
                target_enemy = enemy
                break

        if not target_enemy:
            self.log_message(f"[ERROR] {player_name} attacked {enemy_name}, but it could not be found.")
            return

        # Log the attack attempt
        if payload['type'] == 'auto':
            self.log_message(f"{player_name} greift {enemy_name} an... ({details})")
        else:
            self.log_message(f"{player_name} greift {enemy_name} an... (Manuelle Eingabe: {attack_roll})")

        # Check if the attack hits
        if attack_roll >= target_enemy.ac:
            target_enemy.hp -= damage
            self.log_message(f"GETROFFEN! {enemy_name} erleidet {damage} Schaden. Verbleibende HP: {target_enemy.hp}")

            if target_enemy.hp <= 0:
                self.log_message(f"{enemy_name} wurde besiegt!")
                self.enemies.remove(target_enemy)

                # Remove from map
                for pos, tile in self.map_data['tiles'].items():
                    if tile.get('object') == enemy_name:
                        tile['object'] = None
                        break

                self.broadcast_map_data()
        else:
            self.log_message(f"VERFEHLT! Der Angriff auf {enemy_name} geht daneben.")

        # Update the UI for the DM
        self.update_enemies_list_ui()

    def handle_interaction(self, player_name, pos):
        if not self.map_data or pos not in self.map_data['tiles']:
            return

        tile = self.map_data['tiles'][pos]
        furniture = tile.get('furniture')

        if not furniture:
            return

        furn_type = furniture['type']

        if furniture.get('is_mimic'):
            self.log_message(f"MIMIC! Die {furn_type} bei {pos} entpuppt sich als Mimic, als {player_name} interagiert!")

            # Remove furniture
            tile['furniture'] = None

            # Create and add mimic enemy
            mimic_data = ENEMY_DATA.get('Mimic', {'hp': 30, 'ac': 12, 'attacks': [{'name': 'Biss', 'damage': '1d8+3'}]})

            count = 1
            for enemy in self.enemies:
                if enemy.name.startswith('Mimic'):
                    try:
                        num = int(enemy.name.split('#')[-1])
                        if num >= count: count = num + 1
                    except (ValueError, IndexError): continue

            unique_name = f"Mimic #{count}"
            new_enemy = Enemy(name=unique_name, hp=mimic_data['hp'], ac=mimic_data['ac'], attacks=mimic_data['attacks'])
            self.enemies.append(new_enemy)

            # Place mimic on map
            tile['object'] = new_enemy.name

            self.broadcast_map_data()
            self.update_ui()
        elif furniture.get('is_enchanted'):
            self.log_message(f"{player_name} interagiert mit dem verzauberten {furn_type} bei {pos}!")
            # Here you could add logic for enchanted items.
            # For now, just a log message and maybe sending a message to the player.
            player_addr = self.network_manager.get_client_addr_by_name(player_name)
            if player_addr:
                self.network_manager.send_message(player_addr, "TRIGGER_MESSAGE", {'message': f"The {furn_type} hums with a faint magical energy."})
        else:
            self.log_message(f"{player_name} interagiert mit {furn_type} bei {pos}.")

    def update_ui(self):
        self.update_online_players_list()
        self.update_offline_players_list()
        self.update_enemies_list_ui()
        if self.map_data:
            self.update_map_view()
            self.update_objects_list_ui()

    def update_online_players_list(self):
        player_list_widget = self.ids.online_players_list
        player_list_widget.clear_widgets()
        with self.network_manager.lock:
            clients = list(self.network_manager.clients.items())
        for addr, player_info in clients:
            char = player_info['character']
            player_entry = BoxLayout(size_hint_y=None, height=40)
            hp_text = f"HP: {char.hit_points}/{char.max_hit_points}"
            name_button = Button(text=f"{char.name} ({char.char_class}) - {hp_text}")
            name_button.bind(on_press=lambda x, c=char: self.view_player_sheet(c))
            kick_button = Button(text="Kicken", size_hint_x=0.3)
            kick_button.bind(on_press=lambda x, a=addr: self.kick_player(a))
            player_entry.add_widget(name_button)
            player_entry.add_widget(kick_button)
            player_list_widget.add_widget(player_entry)

    def view_player_sheet(self, character):
        self.app.source_screen = self.name
        sheet_screen = self.manager.get_screen('sheet')
        sheet_screen.load_character(character)
        self.manager.current = 'sheet'

    def kick_player(self, player_address):
        player_name = "Ein Spieler"
        with self.network_manager.lock:
            if player_address in self.network_manager.clients:
                player_name = self.network_manager.clients[player_address]['character'].name
        self.log_message(f"Spieler '{player_name}' wird gekickt.")
        self.network_manager.kick_player(player_address)

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
        self.update_initiative_ui()
        log_msg = "Initiativereihenfolge:\n" + "\n".join([f"{roll}: {name}" for roll, name in self.initiative_order])
        self.log_message(log_msg)
        self.broadcast_game_state()

    def broadcast_game_state(self):
        with self.network_manager.lock:
            player_names = [c['character'].name for c in self.network_manager.clients.values()]
        state = {'players': player_names, 'initiative': self.initiative_order}
        self.network_manager.broadcast_message("GAME_STATE_UPDATE", state)

    def update_initiative_ui(self):
        initiative_list_widget = self.ids.initiative_list
        initiative_list_widget.clear_widgets()
        for roll, name in self.initiative_order:
            label = Label(text=f"{roll}: {name}", size_hint_y=None, height=30)
            initiative_list_widget.add_widget(label)

    def add_offline_player(self):
        """Opens a popup to add a new offline player."""
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        name_input = TextInput(hint_text="Name des Spielers", multiline=False)
        save_button = Button(text="Speichern")

        content.add_widget(name_input)
        content.add_widget(save_button)

        popup = create_styled_popup(title="Offline Spieler hinzufügen", content=content, size_hint=(0.6, 0.4))

        def save_and_dismiss(instance):
            player_name = name_input.text.strip()
            if player_name:
                self.offline_players.append(player_name)
                self.update_offline_players_list()
                self.log_message(f"Offline Spieler '{player_name}' hinzugefügt.")
                popup.dismiss()

        save_button.bind(on_press=save_and_dismiss)
        popup.open()

    def update_offline_players_list(self):
        """Updates the UI list of offline players."""
        player_list_widget = self.ids.offline_players_list
        player_list_widget.clear_widgets()
        for player_name in self.offline_players:
            player_entry = BoxLayout(size_hint_y=None, height=40)
            name_label = Label(text=player_name)
            remove_button = Button(text="Entfernen", size_hint_x=0.3)
            remove_button.bind(on_press=partial(self.remove_offline_player, player_name))
            player_entry.add_widget(name_label)
            player_entry.add_widget(remove_button)
            player_list_widget.add_widget(player_entry)

    def remove_offline_player(self, player_name, instance):
        """Removes an offline player from the list."""
        if player_name in self.offline_players:
            self.offline_players.remove(player_name)
            self.update_offline_players_list()
            self.log_message(f"Offline Spieler '{player_name}' entfernt.")

    def add_enemy(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))
        for enemy_name, enemy_data in ENEMY_DATA.items():
            btn = Button(text=enemy_name, size_hint_y=None, height=44)
            btn.bind(on_press=partial(self.create_enemy_instance, enemy_name, enemy_data))
            scroll_content.add_widget(btn)
        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        content.add_widget(scroll_view)
        self.enemy_popup = create_styled_popup(title="Gegner hinzufügen", content=content, size_hint=(0.7, 0.8))
        self.enemy_popup.open()

    def create_enemy_instance(self, name, data, instance):
        count = 1
        for enemy in self.enemies:
            if enemy.name.startswith(name):
                try:
                    num = int(enemy.name.split('#')[-1])
                    if num >= count: count = num + 1
                except (ValueError, IndexError): continue
        unique_name = f"{name} #{count}"
        new_enemy = Enemy(name=unique_name, hp=data['hp'], ac=data['ac'], attacks=data['attacks'])
        self.enemies.append(new_enemy)
        self.update_enemies_list_ui()
        self.log_message(f"Gegner '{unique_name}' hinzugefügt.")
        if hasattr(self, 'enemy_popup'): self.enemy_popup.dismiss()

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

    def show_enemy_stats(self, enemy, instance):
        content = BoxLayout(orientation='vertical', spacing=5, padding=10)
        content.add_widget(Label(text=f"Name: {enemy.name}"))
        content.add_widget(Label(text=f"HP: {enemy.hp}"))
        content.add_widget(Label(text=f"AC: {enemy.ac}"))
        attacks_str = ", ".join([f"{a['name']} ({a['damage']})" for a in enemy.attacks])
        content.add_widget(Label(text=f"Angriffe: {attacks_str}"))
        create_styled_popup(title="Gegner-Statistiken", content=content, size_hint=(0.6, 0.5)).open()

    def save_session(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        summary_input = TextInput(hint_text="Kurze Zusammenfassung für Spieler", multiline=True, size_hint_y=None, height=100)
        filename_input = TextInput(hint_text="Dateiname (ohne .session)", multiline=False)
        save_button = Button(text="Speichern")
        content.add_widget(Label(text="Sitzung speichern"))
        content.add_widget(summary_input)
        content.add_widget(filename_input)
        content.add_widget(save_button)
        popup = create_styled_popup(title="Sitzung speichern", content=content, size_hint=(0.8, 0.6))
        def do_save(instance):
            filename = filename_input.text.strip()
            if not filename: return
            online_players_data = {}
            with self.network_manager.lock:
                for addr, client_info in self.network_manager.clients.items():
                    char_name = client_info['character'].name
                    online_players_data[char_name] = {'character': client_info['character'].to_dict()}
            session_data = {
                'online_players': online_players_data,
                'offline_players': self.offline_players,
                'enemies': [e.to_dict() for e in self.enemies],
                'log': self.ids.log_output.text,
                'summary': summary_input.text.strip()
            }
            saves_dir = "saves"
            os.makedirs(saves_dir, exist_ok=True)
            filepath = os.path.join(saves_dir, f"{filename}.session")
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, indent=4)
                self.log_message(f"Sitzung '{filepath}' gespeichert.")
                self.network_manager.broadcast_message("SAVE_YOUR_CHARACTER", "")
                popup.dismiss()
            except Exception as e:
                self.log_message(f"Fehler beim Speichern der Sitzung: {e}")
        save_button.bind(on_press=do_save)
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
        self.load_map_popup_widget = create_styled_popup(title="Load Map", content=content, size_hint=(0.8, 0.8))
        self.load_map_popup_widget.open()

    def do_load_map(self, filename, instance):
        filepath = os.path.join("utils/data/maps", filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)

            self.map_data = loaded_data
            self.map_data['tiles'] = {eval(k): v for k, v in loaded_data['tiles'].items()}
            self.log_message(f"Map '{filename}' loaded.")

            # Auto-load enemies from map file
            if 'enemies' in loaded_data:
                self.enemies.clear()
                for enemy_name in loaded_data['enemies']:
                    base_name = enemy_name.split('#')[0].strip()
                    if base_name in ENEMY_DATA:
                        enemy_stats = ENEMY_DATA[base_name]
                        new_enemy = Enemy(
                            name=enemy_name,
                            hp=enemy_stats['hp'],
                            ac=enemy_stats['ac'],
                            attacks=enemy_stats['attacks']
                        )
                        self.enemies.append(new_enemy)
                self.log_message(f"Feindliste automatisch von der Karte geladen.")
                self.update_enemies_list_ui()

            self.broadcast_map_data()
            if hasattr(self, 'load_map_popup_widget'): self.load_map_popup_widget.dismiss()
        except Exception as e:
            create_styled_popup(title="Load Error", content=Label(text=f"Error loading map:\n{e}"), size_hint=(0.7, 0.5)).open()

    def broadcast_map_data(self):
        if self.map_data:
            # Manually create a deep copy that is safe for players and JSON
            player_map_data = {
                'rows': self.map_data.get('rows'),
                'cols': self.map_data.get('cols'),
                'enemies': self.map_data.get('enemies', []), # Pass enemy list
                'tiles': {}
            }

            for pos, tile_data in self.map_data['tiles'].items():
                # Copy the tile data
                tile_copy = tile_data.copy()

                # Hide mimics by making a copy of the furniture dict
                if 'furniture' in tile_copy and tile_copy['furniture']:
                    tile_copy['furniture'] = tile_copy['furniture'].copy()
                    tile_copy['furniture'].pop('is_mimic', None)
                    tile_copy['furniture'].pop('is_enchanted', None)

                # Hide triggers
                if tile_copy.get('type') == 'Trigger':
                    tile_copy['type'] = 'Floor'
                    tile_copy.pop('trigger_message', None)

                # Use a string key for the new dictionary
                player_map_data['tiles'][str(pos)] = tile_copy

            self.network_manager.broadcast_message("MAP_DATA", player_map_data)
            self.update_map_view()
            self.update_objects_list_ui()

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
                    label.color = (1, 0.5, 1, 1) # Purple
                objects_list_widget.add_widget(label)

    def update_map_view(self):
        grid = self.ids.dm_map_grid
        grid.clear_widgets()
        if not self.map_data: return
        rows, cols, tiles = self.map_data['rows'], self.map_data['cols'], self.map_data['tiles']
        grid.rows, grid.cols = rows, cols
        for r in range(rows):
            for c in range(cols):
                tile_button = Button()
                tile_button.bind(on_press=partial(self.on_tile_click, r, c))
                tile_data = tiles.get((r, c))
                if not tile_data: continue
                bg_color = [0.5, 0.5, 0.5, 1]
                if (r,c) in self.highlighted_tiles:
                    bg_color = [0.9, 0.9, 0.2, 1] # Highlight color
                elif tile_data.get('type') == 'Wall': bg_color = [0.2, 0.2, 0.2, 1]
                elif tile_data.get('type') == 'Door': bg_color = [0.6, 0.3, 0.1, 1]
                elif tile_data.get('type') == 'Trigger': bg_color = [1, 1, 0, 0.5] # Visible to DM
                tile_button.background_color = bg_color
                obj = tile_data.get('object')
                furn = tile_data.get('furniture')
                if obj:
                    tile_button.text = obj[:3]
                    if obj in [e.name for e in self.enemies]: tile_button.color = (1, 0.5, 0.5, 1)
                    else: tile_button.color = (0.5, 1, 0.5, 1)
                elif furn:
                    tile_button.text = furn['type'][:2]
                    if furn.get('is_mimic'):
                        tile_button.color = (1, 0.5, 1, 1) # Purple
                    elif furn.get('is_enchanted'):
                        tile_button.color = (0.5, 1, 1, 1) # Cyan
                    else:
                        tile_button.color = (0.7, 0.7, 0.7, 1)
                grid.add_widget(tile_button)

    def on_tile_click(self, row, col, instance):
        if self.selected_object and (row, col) in self.highlighted_tiles:
            # This is a confirmed move action
            self.move_object(self.selected_object['name'], (row, col))
            self.broadcast_map_data()
            self.selected_object = None
            self.highlighted_tiles = []
            self.update_map_view()
            return

        self.highlighted_tiles = []
        tile_data = self.map_data['tiles'].get((row, col))
        clicked_object_name = tile_data.get('object') if tile_data else None

        # Case 1: An enemy is selected, and a player is clicked -> ATTACK
        if self.selected_object and self.selected_object['name'] in [e.name for e in self.enemies] and \
           clicked_object_name and clicked_object_name in [c['character'].name for c in self.network_manager.clients.values()]:
            self.try_attack_player(self.selected_object, clicked_object_name, (row, col))

        # Case 2: Any object is clicked -> SELECT it
        elif clicked_object_name:
            self.selected_object = {'name': clicked_object_name, 'pos': (row, col)}
            self.highlight_movement_range(clicked_object_name, row, col)

        # Case 3: An empty tile is clicked -> DESELECT
        else:
            self.selected_object = None

        self.update_map_view()

    def highlight_movement_range(self, obj_name, r_start, c_start):
        # Determine movement speed (e.g., 6 squares for 9m)
        speed = 6
        self.highlighted_tiles = []
        for r in range(self.map_data['rows']):
            for c in range(self.map_data['cols']):
                dist = abs(r - r_start) + abs(c - c_start)
                if 0 < dist <= speed:
                    tile_data = self.map_data['tiles'].get((r,c))
                    if tile_data and tile_data['type'] not in ['Wall', 'Empty'] and not tile_data.get('object'):
                        self.highlighted_tiles.append((r, c))

    def move_object(self, obj_name, to_pos):
        from_pos = None
        for pos, tile in self.map_data['tiles'].items():
            if tile.get('object') == obj_name:
                from_pos = pos
                break
        if from_pos:
            self.map_data['tiles'][from_pos]['object'] = None
            self.map_data['tiles'][to_pos]['object'] = obj_name
            self.log_message(f"{obj_name} moved from {from_pos} to {to_pos}")

            # Check for trigger after the move is complete
            self.check_for_trigger(obj_name, to_pos)

    def check_for_trigger(self, obj_name, pos):
        print(f"[TRIGGER_DEBUG] Checking for trigger at {pos} for object: {obj_name}")
        tile = self.map_data['tiles'].get(pos)

        if not tile:
            print("[TRIGGER_DEBUG] No tile data found.")
            return

        print(f"[TRIGGER_DEBUG] Tile data is: {tile}")
        tile_type = tile.get('type')
        print(f"[TRIGGER_DEBUG] Tile type is: {tile_type}")

        if tile_type != 'Trigger':
            return

        # Find the player's address to send them a direct message
        player_addr = None
        with self.network_manager.lock:
            for addr, client_info in self.network_manager.clients.items():
                if client_info['character'].name == obj_name:
                    player_addr = addr
                    break

        if not player_addr:
            print(f"[TRIGGER_DEBUG] Trigger not fired because '{obj_name}' is not a connected player.")
            return

        self.log_message(f"Trigger ausgelöst bei {pos} von {obj_name}.")

        # Send trigger message if it exists
        message = tile.get('trigger_message')
        if message:
            self.network_manager.send_message(player_addr, "TRIGGER_MESSAGE", {'message': message})

        # Grant items and currency if they exist
        items_to_grant = tile.get('trigger_items', [])
        currency_to_grant = tile.get('trigger_currency', {})

        if items_to_grant or currency_to_grant:
            granted_items_str_list = []
            with self.network_manager.lock:
                char = self.network_manager.clients[player_addr]['character']

                for item in items_to_grant:
                    char.add_item(item['name'], item['quantity'])
                    granted_items_str_list.append(f"{item['quantity']}x {item['name']}")

                for code, amount in currency_to_grant.items():
                    char.add_item(code, amount)
                    granted_items_str_list.append(f"{amount} {code}")

            if granted_items_str_list:
                granted_items_str = ", ".join(granted_items_str_list)
                self.log_message(f"{obj_name} erhält: {granted_items_str}.")

            self.network_manager.send_message(player_addr, 'SET_CHARACTER_DATA', char.to_dict())

    def show_map_options_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)

        load_button = Button(text="Load Map")
        open_editor_button = Button(text="Open Map Editor (Current Map)")

        content.add_widget(load_button)
        content.add_widget(open_editor_button)

        popup = create_styled_popup(title="Map Options", content=content, size_hint=(0.6, 0.4))

        def go_to_editor(instance):
            editor_screen = self.manager.get_screen('map_editor')
            # Pass the current map to the editor so it can be edited
            editor_screen.preloaded_map_data = self.map_data
            self.app.change_screen('map_editor', source_screen=self.name)
            popup.dismiss()

        load_button.bind(on_press=lambda x: (self.load_map_popup(), popup.dismiss()))
        open_editor_button.bind(on_press=go_to_editor)

        popup.open()

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
            # This lambda will load the file content and then call the callback
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

    def try_attack_player(self, enemy_obj, player_name, player_pos):
        enemy_name = enemy_obj['name']
        enemy_pos = enemy_obj['pos']

        # Find the full enemy object to get its attack data
        enemy_data = None
        for e in self.enemies:
            if e.name == enemy_name:
                enemy_data = e
                break
        if not enemy_data or not enemy_data.attacks:
            self.log_message(f"[ERROR] No attack data found for {enemy_name}.")
            return

        # For now, use the first attack
        attack = enemy_data.attacks[0]
        attack_type = attack.get('type', 'Melee')
        attack_range = attack.get('range', 1)

        dist = max(abs(enemy_pos[0] - player_pos[0]), abs(enemy_pos[1] - player_pos[1]))

        attack_valid = False
        if attack_type == 'Melee' and dist <= attack_range:
            attack_valid = True
        elif attack_type == 'Ranged' and dist > 0:
            attack_valid = True

        if attack_valid:
            self.open_dm_attack_popup(enemy_data, player_name, attack)
        else:
            self.log_message(f"Angriff von {enemy_name} auf {player_name} außer Reichweite.")

    def open_dm_attack_popup(self, enemy, player_name, attack):
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.textinput import TextInput
        from kivy.uix.button import Button
        from kivy.uix.label import Label

        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=f"Angriff: {enemy.name} -> {player_name}", font_size='18sp'))

        # Manual Attack
        manual_layout = GridLayout(cols=2, spacing=10, size_hint_y=None, height=50)
        attack_roll_input = TextInput(hint_text="Attack Roll", input_filter='int')
        damage_input = TextInput(hint_text="Damage", input_filter='int')
        manual_layout.add_widget(Label(text="Attack Roll:"))
        manual_layout.add_widget(attack_roll_input)
        manual_layout.add_widget(Label(text="Damage:"))
        manual_layout.add_widget(damage_input)
        manual_button = Button(text="Execute Manual Attack")
        content.add_widget(manual_layout)
        content.add_widget(manual_button)

        # Auto Attack
        auto_button = Button(text=f"Roll {attack['name']} ({attack['to_hit']:+}, {attack['damage']})")
        result_label = Label()
        content.add_widget(auto_button)
        content.add_widget(result_label)

        popup = create_styled_popup(title="DM Attack", content=content, size_hint=(0.8, 0.7))

        def execute_attack(attack_roll, damage, details=""):
            # Find player character object
            player_char = None
            player_addr = self.network_manager.get_client_addr_by_name(player_name)
            if player_addr:
                player_char = self.network_manager.clients[player_addr]['character']

            if not player_char:
                self.log_message(f"[ERROR] Player {player_name} not found for attack.")
                return

            log_msg = f"{enemy.name} greift {player_name} an. {details}"
            self.log_message(log_msg)

            if attack_roll >= player_char.armor_class:
                player_char.hit_points -= damage
                self.log_message(f"GETROFFEN! {player_name} erleidet {damage} Schaden. Verbleibende HP: {player_char.hit_points}")
                if player_char.hit_points <= 0:
                    self.log_message(f"{player_name} ist bewusstlos!")
                # Send update to the specific player
                self.network_manager.send_message(player_addr, 'SET_CHARACTER_DATA', player_char.to_dict())
            else:
                self.log_message(f"VERFEHLT! Der Angriff auf {player_name} geht daneben.")

            self.update_online_players_list() # Refresh DM's view of player HP
            popup.dismiss()

        def manual_action(instance):
            try:
                execute_attack(int(attack_roll_input.text), int(damage_input.text))
            except ValueError:
                result_label.text = "Invalid input."

        def auto_action(instance):
            attack_roll = random.randint(1, 20) + attack['to_hit']

            damage_parts = attack['damage'].split('+')
            dice_part = damage_parts[0]
            bonus_damage = int(damage_parts[1]) if len(damage_parts) > 1 else 0
            num_dice, dice_type = map(int, dice_part.split('d'))
            damage_roll = sum(random.randint(1, dice_type) for _ in range(num_dice))
            total_damage = damage_roll + bonus_damage

            details = f"Roll: {attack_roll}, Damage: {total_damage}"
            result_label.text = details
            execute_attack(attack_roll, total_damage, details)

        manual_button.bind(on_press=manual_action)
        auto_button.bind(on_press=auto_action)
        popup.open()

    def end_session_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Möchten Sie die Sitzung wirklich beenden?\nAlle Spieler werden getrennt.'))
        btn_layout = BoxLayout(spacing=10)
        yes_btn = Button(text="Ja, beenden", on_press=self.do_end_session)
        no_btn = Button(text="Nein", on_press=lambda x: self.confirmation_popup.dismiss())
        btn_layout.add_widget(yes_btn)
        btn_layout.add_widget(no_btn)
        content.add_widget(btn_layout)
        apply_styles_to_widget(content)
        self.confirmation_popup = create_styled_popup(title="Sitzung beenden bestätigen", content=content, size_hint=(0.6, 0.5))
        self.confirmation_popup.open()

    def do_end_session(self, instance):
        self.confirmation_popup.dismiss()
        self.log_message("Sitzung wird beendet...")
        self.network_manager.shutdown()
        self.app.change_screen('main')
