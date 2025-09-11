import json
import random
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from core.enemy import Enemy
from utils.helpers import apply_background, apply_styles_to_widget

class DMMainScreen(Screen):
    """The main screen for the Dungeon Master to manage the game."""
    def __init__(self, **kwargs):
        super(DMMainScreen, self).__init__(**kwargs)
        self.online_players = {}
        self.offline_players = []
        self.enemies = []
        self.initiative_order = []
        self.game_log = []

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def set_game_data(self, session_data):
        """Receives the full session data from the lobby screen."""
        self.online_players = session_data.get('online_players', {})
        self.offline_players = session_data.get('offline_players', [])
        self.enemies = session_data.get('enemies', [])
        self.ids.log_output.text = session_data.get('log', '')

        print(f"[*] Game data set. {len(self.online_players)} online players.")
        self.update_ui()

    def update_ui(self):
        """Updates the entire UI based on the current game state."""
        self.update_online_players_list()
        self.update_offline_players_list()
        self.update_enemies_list_ui()

    def update_online_players_list(self):
        player_list_widget = self.ids.online_players_list
        player_list_widget.clear_widgets()
        for addr, player_info in self.online_players.items():
            # In a loaded session, the character object needs to be recreated
            if isinstance(player_info['character'], dict):
                from core.character import Character
                char = Character.from_dict(player_info['character'])
                player_info['character'] = char
            else:
                char = player_info['character']

            # This is still a placeholder. A more detailed widget is needed.
            player_list_widget.add_widget(Label(text=f"{char.name} ({char.char_class})"))

    def roll_initiative_for_all(self):
        """Rolls initiative for all players and enemies."""
        self.initiative_order = []

        # Roll for online players
        for addr, player_info in self.online_players.items():
            char = player_info['character']
            roll = random.randint(1, 20)
            total = roll + char.initiative
            self.initiative_order.append({'name': char.name, 'roll': total, 'type': 'player'})
            self.log_message(f"Initiative für {char.name}: {roll} + {char.initiative} = {total}")

        # Roll for offline players
        for player_name in self.offline_players:
            roll = random.randint(1, 20)
            self.initiative_order.append({'name': player_name, 'roll': roll, 'type': 'player'})
            self.log_message(f"Initiative für {player_name} (Offline): {roll}")

        # Roll for enemies
        for enemy in self.enemies:
            roll = random.randint(1, 20)
            total = roll + enemy.initiative
            self.initiative_order.append({'name': enemy.name, 'roll': total, 'type': 'enemy'})
            self.log_message(f"Initiative für {enemy.name}: {roll} + {enemy.initiative} = {total}")

        # Sort the list by roll, descending
        self.initiative_order.sort(key=lambda x: x['roll'], reverse=True)

        self.update_initiative_ui()

    def update_initiative_ui(self):
        init_list_widget = self.ids.initiative_list
        init_list_widget.clear_widgets()
        for participant in self.initiative_order:
            label_text = f"{participant['roll']}: {participant['name']}"
            participant_label = Label(text=label_text, size_hint_y=None, height=40)
            init_list_widget.add_widget(participant_label)

    def log_message(self, message):
        self.ids.log_output.text += f"{message}\n"

    def add_offline_player(self):
        """Opens a popup to add an offline player."""
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.textinput import TextInput
        from kivy.uix.button import Button

        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        name_input = TextInput(hint_text="Name des Offline-Spielers")
        content.add_widget(name_input)
        save_button = Button(text="Hinzufügen")
        content.add_widget(save_button)

        popup = Popup(title="Offline-Spieler hinzufügen", content=content, size_hint=(0.8, 0.5))

        def save_action(instance):
            player_name = name_input.text.strip()
            if player_name and player_name not in self.offline_players:
                self.offline_players.append(player_name)
                self.update_offline_players_list()
                self.log_message(f"Offline-Spieler '{player_name}' hinzugefügt.")
            popup.dismiss()

        save_button.bind(on_press=save_action)
        popup.open()

    def update_offline_players_list(self):
        offline_list_widget = self.ids.offline_players_list
        offline_list_widget.clear_widgets()
        for player_name in self.offline_players:
            player_label = Label(text=player_name)
            offline_list_widget.add_widget(player_label)

    def add_enemy(self):
        """Loads an enemy list and opens a popup to add one to the combat."""
        try:
            with open("my_enemies.enemies", 'r', encoding='utf-8') as f:
                enemy_data_list = json.load(f)

            available_enemies = [Enemy.from_dict(data) for data in enemy_data_list]

            content = BoxLayout(orientation='vertical', padding=10, spacing=10)

            for enemy in available_enemies:
                btn = Button(text=enemy.name)
                btn.bind(on_press=lambda x, e=enemy: add_selected_enemy(e, popup))
                content.add_widget(btn)

            popup = Popup(title="Gegner auswählen", content=content, size_hint=(0.8, 0.8))

            def add_selected_enemy(enemy_obj, p):
                self.enemies.append(enemy_obj)
                self.update_enemies_list_ui()
                self.log_message(f"Gegner '{enemy_obj.name}' zum Kampf hinzugefügt.")
                p.dismiss()

            popup.open()

        except FileNotFoundError:
            self.log_message("Fehler: 'my_enemies.enemies' nicht gefunden. Erstelle zuerst eine Liste im Vorbereitungsbildschirm.")
        except Exception as e:
            self.log_message(f"Fehler beim Laden der Gegnerliste: {e}")

    def update_enemies_list_ui(self):
        enemy_list_widget = self.ids.enemies_list
        enemy_list_widget.clear_widgets()
        for enemy in self.enemies:
            enemy_label = Label(text=f"{enemy.name} (HP: {enemy.hp}, AC: {enemy.ac})")
            enemy_list_widget.add_widget(enemy_label)

    def save_session(self):
        """Opens a popup to get a summary and then saves the session."""
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.textinput import TextInput
        from kivy.uix.button import Button

        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        summary_input = TextInput(hint_text="Sitzungszusammenfassung eingeben...")
        content.add_widget(summary_input)
        save_button = Button(text="Speichern")
        content.add_widget(save_button)

        popup = Popup(title="Sitzung speichern", content=content, size_hint=(0.8, 0.5))

        def do_save(instance):
            summary = summary_input.text
            session_data = {
                'online_players': {},
                'offline_players': self.offline_players,
                'enemies': [enemy.to_dict() for enemy in self.enemies],
                'log': self.ids.log_output.text,
                'summary': summary
            }

            for addr, player_info in self.online_players.items():
                player_addr_str = f"{addr[0]}:{addr[1]}"
                session_data['online_players'][player_addr_str] = {
                    'character': player_info['character'].to_dict()
                }

            filename = "last_session.session"
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, indent=4, ensure_ascii=False)
                print(f"[*] Session saved to {filename}")
            except Exception as e:
                print(f"[!] Error saving session: {e}")

            popup.dismiss()

        save_button.bind(on_press=do_save)
        popup.open()
