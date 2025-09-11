from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.clock import Clock
import socket
import threading
from utils.helpers import apply_background, apply_styles_to_widget

class PlayerMainScreen(Screen):
    """The main screen for the player during a game session."""
    def __init__(self, **kwargs):
        super(PlayerMainScreen, self).__init__(**kwargs)
        self.character = None
        self.client_socket = None
        self.listener_thread = None

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
        """Loads the character into the embedded character sheet widget."""
        if self.character:
            self.ids.character_sheet_widget.load_character(self.character)

    def start_listening(self):
        """Starts a thread to listen for messages from the DM."""
        self.listener_thread = threading.Thread(target=self.listen_for_dm_messages)
        self.listener_thread.daemon = True
        self.listener_thread.start()

    def listen_for_dm_messages(self):
        """The actual listener loop."""
        while self.client_socket:
            try:
                message = self.client_socket.recv(1024).decode('utf-8')
                if message:
                    Clock.schedule_once(lambda dt: self.update_log(message))
                else:
                    # DM disconnected
                    Clock.schedule_once(lambda dt: self.handle_disconnect())
                    break
            except (socket.error, OSError):
                Clock.schedule_once(lambda dt: self.handle_disconnect())
                break

    def update_log(self, message):
        self.ids.log_output.text += f"\n{message}"

    def handle_disconnect(self):
        self.update_log("DM has disconnected. Returning to main menu.")
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
        # After a delay, go back to the main menu
        Clock.schedule_once(lambda dt: self.go_to_main_menu(), 3)

    def go_to_main_menu(self):
        self.manager.current = 'main'

    def on_leave(self, *args):
        """Clean up when leaving the screen."""
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
