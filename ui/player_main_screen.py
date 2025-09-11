import socket
import threading
import json
import random
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup
from data_manager import WEAPON_DATA

class PlayerMainScreen(Screen):
    """The main screen for the player during a game session."""
    def __init__(self, **kwargs):
        super(PlayerMainScreen, self).__init__(**kwargs)
        self.character = None
        self.client_socket = None
        self.listener_thread = None
        self.summary = ""

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def set_player_data(self, character, client_socket, summary=""):
        """Receives the character, socket, and summary from the lobby screen."""
        self.character = character
        self.client_socket = client_socket
        self.summary = summary
        print(f"[*] Player screen initialized for {self.character.name}.")
        self.update_ui()
        self.start_listening()

    def update_ui(self):
        """Updates the UI with character info and log."""
        self.update_character_sheet()
        self.update_log("Verbunden mit DM.")
        if self.summary:
            self.ids.summary_label.text = f"[b]Letzte Zusammenfassung:[/b]\n{self.summary}"
        else:
            self.ids.summary_label.text = ""

    def update_character_sheet(self):
        """Loads the character into the embedded character display widget."""
        if self.character:
            self.ids.character_display.character = self.character

    def start_listening(self):
        """Starts a thread to listen for messages from the DM."""
        if self.client_socket:
            self.listener_thread = threading.Thread(target=self.listen_for_dm_messages)
            self.listener_thread.daemon = True
            self.listener_thread.start()
            print("[*] Player listener thread started.")

    def listen_for_dm_messages(self):
        """The actual listener loop."""
        while self.client_socket:
            try:
                header = self.client_socket.recv(10)
                if not header:
                    print("[*] DM disconnected (header empty).")
                    Clock.schedule_once(lambda dt: self.handle_disconnect())
                    break

                msg_len = int(header.strip())
                data = b''
                while len(data) < msg_len:
                    chunk = self.client_socket.recv(msg_len - len(data))
                    if not chunk: break
                    data += chunk

                response = json.loads(data.decode('utf-8'))
                msg_type = response.get('type')
                payload = response.get('payload')

                if msg_type == 'LOG':
                    Clock.schedule_once(lambda dt, m=payload: self.update_log(m))
                elif msg_type == 'KICK':
                    print("[*] Kicked by DM.")
                    Clock.schedule_once(lambda dt: self.handle_disconnect())
                    break
                else:
                    print(f"[*] Received unhandled message type: {msg_type}")

            except (socket.error, OSError) as e:
                print(f"[!] Player listener thread error: {e}")
                Clock.schedule_once(lambda dt: self.handle_disconnect())
                break
        print("[*] Player listener thread finished.")

    def update_log(self, message):
        self.ids.log_output.text += f"\n{message}"

    def handle_disconnect(self):
        self.update_log("DM hat die Verbindung getrennt. Kehre zum Hauptmenü zurück.")
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
        Clock.schedule_once(lambda dt: self.go_to_main_menu(), 3)

    def go_to_main_menu(self):
        self.manager.current = 'main'

    def on_leave(self, *args):
        """Clean up when leaving the screen."""
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None

    def roll_d20(self):
        roll = random.randint(1, 20)
        popup = create_styled_popup(title='d20 Wurf',
                                    content=Label(text=f'Du hast eine {roll} gewürfelt.'),
                                    size_hint=(0.6, 0.4))
        popup.open()
        # Also send to DM
        if self.client_socket:
            # This needs a proper message protocol, but for now, just send a string
            pass

    def roll_damage(self):
        if not self.character: return
        weapon_name = self.character.equipped_weapon
        weapon_info = WEAPON_DATA.get(weapon_name, WEAPON_DATA["Unbewaffneter Schlag"])
        ability_name = weapon_info["ability"]
        modifier = (self.character.abilities[ability_name] - 10) // 2
        parts = weapon_info["damage"].split('d')
        num_dice = int(parts[0])
        dice_type = int(parts[1])
        roll_total = sum(random.randint(1, dice_type) for _ in range(num_dice))
        total_damage = roll_total + modifier

        popup = create_styled_popup(
            title="Schadenswurf",
            content=Label(text=f"{weapon_info['damage']} ({roll_total}) + {ability_name[:3]}-Mod ({modifier}) = {max(1, total_damage)} Schaden"),
            size_hint=(0.8, 0.4)
        )
        popup.open()
