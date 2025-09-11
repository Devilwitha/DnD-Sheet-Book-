import socket
import threading
import json
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from utils.helpers import apply_background, apply_styles_to_widget

class PlayerWaitingScreen(Screen):
    """A screen for the player to wait in while the DM prepares the game."""
    def __init__(self, **kwargs):
        super(PlayerWaitingScreen, self).__init__(**kwargs)
        self.character = None
        self.client_socket = None
        self.summary = ""
        self.listener_thread = None

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def set_data(self, character, client_socket, summary):
        self.character = character
        self.client_socket = client_socket
        self.summary = summary
        self.ids.waiting_label.text = f"Verbunden mit DM. Warten bis das Spiel startet..."
        self.start_listening()

    def start_listening(self):
        if self.client_socket:
            self.listener_thread = threading.Thread(target=self.listen_for_game_start)
            self.listener_thread.daemon = True
            self.listener_thread.start()

    def listen_for_game_start(self):
        while self.client_socket:
            try:
                header = self.client_socket.recv(10)
                if not header:
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

                if msg_type == 'GAME_START':
                    print("[*] Received GAME_START signal from DM.")
                    Clock.schedule_once(lambda dt: self.proceed_to_game())
                    break
                elif msg_type == 'KICK':
                    print("[*] Kicked by DM from waiting room.")
                    Clock.schedule_once(lambda dt: self.handle_disconnect())
                    break
            except (socket.error, OSError):
                Clock.schedule_once(lambda dt: self.handle_disconnect())
                break

    def proceed_to_game(self):
        main_screen = self.manager.get_screen('player_main')
        main_screen.set_player_data(self.character, self.client_socket, self.summary)
        self.manager.current = 'player_main'

    def handle_disconnect(self):
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
        self.manager.current = 'main'

    def on_leave(self, *args):
        # The socket is passed to the next screen, so we only close it
        # if we are NOT proceeding to the main game screen.
        if self.manager.current != 'player_main' and self.client_socket:
            self.client_socket.close()
            self.client_socket = None
