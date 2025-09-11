import json
import random
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from queue import Empty

from core.enemy import Enemy
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup
from functools import partial
from data_manager import ENEMY_DATA
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

class DMMainScreen(Screen):
    """The main screen for the Dungeon Master to manage the game."""
    def __init__(self, **kwargs):
        super(DMMainScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.network_manager = self.app.network_manager
        self.update_event = None

        # Game state - this could be moved to a separate state manager later
        self.offline_players = []
        self.enemies = []
        self.initiative_order = []

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def on_enter(self, *args):
        # Announce game start to all clients
        self.network_manager.broadcast_message("GAME_START", "Das Spiel beginnt!")

        # Initialize UI from the current state
        self.load_state_from_manager()
        self.update_ui()

        # Start polling for in-game messages
        self.update_event = Clock.schedule_interval(self.check_for_updates, 0.2)

    def on_leave(self, *args):
        # Stop polling for updates when leaving the screen
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None

    def load_state_from_manager(self):
        """Loads the game state, either from a loaded session or a new one."""
        if self.app.loaded_session_data:
            # If we loaded a session, this data is the source of truth
            session = self.app.loaded_session_data
            self.offline_players = session.get('offline_players', [])
            self.enemies = [Enemy.from_dict(e) for e in session.get('enemies', [])]
            self.ids.log_output.text = session.get('log', '')
            # loaded_session_data is consumed after being loaded
            self.app.loaded_session_data = None
        else:
            # For a new game, the state is fresh
            self.ids.log_output.text = "Neue Sitzung gestartet.\n"

    def check_for_updates(self, dt):
        """Polls the network queue for messages and updates the game state."""
        try:
            while True:
                item = self.network_manager.incoming_messages.get_nowait()
                if isinstance(item, tuple) and len(item) == 2:
                    source, message = item
                    # Check for system messages (join/leave)
                    if source in ['PLAYER_JOINED', 'PLAYER_LEFT']:
                        self.log_message(f"System: {source} - {message.get('name', message.get('char', 'Unknown'))}")
                        self.update_online_players_list()
                        self.broadcast_game_state()
                        continue

                    # Handle in-game messages from clients
                    msg_type = message.get('type')
                    payload = message.get('payload')

                    if msg_type == 'LOG':
                        player_name = self.network_manager.clients[source]['character'].name
                        self.log_message(f"{player_name}: {payload}")
                    elif msg_type == 'UPDATE_STAT':
                        with self.network_manager.lock:
                            if source in self.network_manager.clients:
                                character_to_update = self.network_manager.clients[source]['character']
                                stat = payload.get('stat')
                                value = payload.get('value')
                                if hasattr(character_to_update, stat):
                                    setattr(character_to_update, stat, value)
                                    self.log_message(f"System: {character_to_update.name}'s {stat} wurde auf {value} aktualisiert.")
                                    self.update_online_players_list() # Refresh the UI

        except Empty:
            pass

    def update_ui(self):
        self.update_online_players_list()
        self.update_offline_players_list()
        self.update_enemies_list_ui()

    def update_online_players_list(self):
        player_list_widget = self.ids.online_players_list
        player_list_widget.clear_widgets()
        with self.network_manager.lock:
            # Create a copy to avoid issues if the dict changes during iteration
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
        """Rolls initiative for all players and enemies."""
        self.initiative_order = []

        # Roll for online players
        with self.network_manager.lock:
            for client_info in self.network_manager.clients.values():
                char = client_info['character']
                roll = random.randint(1, 20) + char.initiative
                self.initiative_order.append((roll, char.name))

        # Roll for enemies
        for enemy in self.enemies:
            # Assuming enemies have no initiative modifier for simplicity
            roll = random.randint(1, 20)
            self.initiative_order.append((roll, enemy.name))

        # Sort by initiative roll, descending
        self.initiative_order.sort(key=lambda x: x[0], reverse=True)

        self.update_initiative_ui()

        # Log and broadcast the result
        log_msg = "Initiativereihenfolge:\n" + "\n".join([f"{roll}: {name}" for roll, name in self.initiative_order])
        self.log_message(log_msg)
        self.broadcast_game_state() # This will contain the initiative order

    def broadcast_game_state(self):
        """Broadcasts the current player list and initiative order to all clients."""
        with self.network_manager.lock:
            player_names = [c['character'].name for c in self.network_manager.clients.values()]

        state = {
            'players': player_names,
            'initiative': self.initiative_order
        }
        self.network_manager.broadcast_message("GAME_STATE_UPDATE", state)

    def update_initiative_ui(self):
        """Updates the UI with the current initiative order."""
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
        """Opens a popup to select and add an enemy."""
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
        """Creates an enemy object and adds it to the list."""
        # Find highest existing number for this enemy type
        count = 1
        for enemy in self.enemies:
            if enemy.name.startswith(name):
                try:
                    num = int(enemy.name.split('#')[-1])
                    if num >= count:
                        count = num + 1
                except (ValueError, IndexError):
                    continue

        unique_name = f"{name} #{count}"
        new_enemy = Enemy(name=unique_name, hp=data['hp'], ac=data['ac'], attacks=data['attacks'])
        self.enemies.append(new_enemy)
        self.update_enemies_list_ui()
        self.log_message(f"Gegner '{unique_name}' hinzugefügt.")
        if hasattr(self, 'enemy_popup'):
            self.enemy_popup.dismiss()

    def update_enemies_list_ui(self):
        """Updates the UI list of enemies."""
        enemy_list_widget = self.ids.enemies_list
        enemy_list_widget.clear_widgets()
        for enemy in self.enemies:
            enemy_entry = BoxLayout(size_hint_y=None, height=40)
            name_button = Button(text=enemy.name)
            name_button.bind(on_press=partial(self.show_enemy_stats, enemy))
            remove_button = Button(text="Entfernen", size_hint_x=0.3)
            remove_button.bind(on_press=partial(self.remove_enemy, enemy))
            enemy_entry.add_widget(name_button)
            enemy_entry.add_widget(remove_button)
            enemy_list_widget.add_widget(enemy_entry)

    def remove_enemy(self, enemy, instance):
        """Removes an enemy from the list."""
        if enemy in self.enemies:
            self.enemies.remove(enemy)
            self.update_enemies_list_ui()
            self.log_message(f"Gegner '{enemy.name}' entfernt.")

    def show_enemy_stats(self, enemy, instance):
        """Shows a popup with the enemy's stats."""
        content = BoxLayout(orientation='vertical', spacing=5, padding=10)
        content.add_widget(Label(text=f"Name: {enemy.name}"))
        content.add_widget(Label(text=f"HP: {enemy.hp}"))
        content.add_widget(Label(text=f"AC: {enemy.ac}"))
        attacks_str = ", ".join([f"{a['name']} ({a['damage']})" for a in enemy.attacks])
        content.add_widget(Label(text=f"Angriffe: {attacks_str}"))
        create_styled_popup(title="Gegner-Statistiken", content=content, size_hint=(0.6, 0.5)).open()

    def save_session(self):
        """Opens a popup to save the current session state to a file."""
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)

        # Add a text input for the session summary
        summary_input = TextInput(hint_text="Kurze Zusammenfassung für Spieler", multiline=True, size_hint_y=None, height=100)

        # Add a text input for the filename
        filename_input = TextInput(hint_text="Dateiname (ohne .session)", multiline=False)

        save_button = Button(text="Speichern")

        content.add_widget(Label(text="Sitzung speichern"))
        content.add_widget(summary_input)
        content.add_widget(filename_input)
        content.add_widget(save_button)

        popup = create_styled_popup(title="Sitzung speichern", content=content, size_hint=(0.8, 0.6))

        def do_save(instance):
            filename = filename_input.text.strip()
            if not filename:
                return # Or show an error

            online_players_data = {}
            with self.network_manager.lock:
                for addr, client_info in self.network_manager.clients.items():
                    # We use the character name as a key, as the address is not persistent
                    char_name = client_info['character'].name
                    online_players_data[char_name] = {
                        'character': client_info['character'].to_dict()
                        # Sockets are not saved
                    }

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
