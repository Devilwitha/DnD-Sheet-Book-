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
        self.network_manager.broadcast_message("GAME_START", "Das Spiel beginnt!")
        self.load_state_from_manager()
        self.update_ui()
        self.update_event = Clock.schedule_interval(self.check_for_updates, 0.2)

    def on_leave(self, *args):
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None

    def load_state_from_manager(self):
        if self.app.loaded_session_data:
            session = self.app.loaded_session_data
            self.offline_players = session.get('offline_players', [])
            self.enemies = [Enemy.from_dict(e) for e in session.get('enemies', [])]
            self.ids.log_output.text = session.get('log', '')
            self.app.loaded_session_data = None
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
                self.move_object(payload['name'], payload['to_pos'])
                # The move_object function already logs the move.
                # Now, broadcast the entire updated map state.
                self.broadcast_map_data()

        except Empty:
            pass

    def update_ui(self):
        self.update_online_players_list()
        self.update_offline_players_list()
        self.update_enemies_list_ui()
        if self.map_data:
            self.update_map_view()

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
            self.broadcast_map_data()
            if hasattr(self, 'load_map_popup_widget'): self.load_map_popup_widget.dismiss()
        except Exception as e:
            create_styled_popup(title="Load Error", content=Label(text=f"Error loading map:\n{e}"), size_hint=(0.7, 0.5)).open()

    def broadcast_map_data(self):
        if self.map_data:
            map_data_str_keys = self.map_data.copy()
            map_data_str_keys['tiles'] = {str(k): v for k, v in self.map_data['tiles'].items()}
            self.network_manager.broadcast_message("MAP_DATA", map_data_str_keys)
            self.update_map_view()

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
                tile_button.background_color = bg_color
                obj = tile_data.get('object')
                if obj:
                    tile_button.text = obj[:3]
                    if obj in [e.name for e in self.enemies]: tile_button.color = (1, 0.5, 0.5, 1)
                    else: tile_button.color = (0.5, 1, 0.5, 1)
                grid.add_widget(tile_button)

    def on_tile_click(self, row, col, instance):
        if self.selected_object and (row, col) in self.highlighted_tiles:
            self.move_object(self.selected_object['name'], (row, col))
            self.broadcast_map_data()
            self.selected_object = None
            self.highlighted_tiles = []
            # broadcast_map_data calls update_map_view, so this is redundant
            # self.update_map_view()
        else:
            self.highlighted_tiles = []
            tile_data = self.map_data['tiles'].get((row, col))
            if tile_data and tile_data.get('object'):
                obj_name = tile_data['object']
                self.selected_object = {'name': obj_name, 'pos': (row, col)}
                self.highlight_movement_range(obj_name, row, col)
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
                    if tile_data and tile_data['type'] != 'Wall' and not tile_data.get('object'):
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

    def show_map_options_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)

        load_button = Button(text="Load Map")
        create_button = Button(text="Create New Map")
        edit_button = Button(text="Edit Existing Map")

        content.add_widget(load_button)
        content.add_widget(create_button)
        content.add_widget(edit_button)

        popup = create_styled_popup(title="Map Options", content=content, size_hint=(0.6, 0.5))

        def go_to_editor(instance):
            self.manager.current = 'map_editor'
            popup.dismiss()

        load_button.bind(on_press=lambda x: (self.load_map_popup(), popup.dismiss()))
        create_button.bind(on_press=go_to_editor)
        edit_button.bind(on_press=go_to_editor)

        popup.open()
