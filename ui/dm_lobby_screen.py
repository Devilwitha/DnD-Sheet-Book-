import json
import os
import base64
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.clock import Clock
from utils.helpers import apply_background, apply_styles_to_widget
from queue import Empty

class DMLobbyScreen(Screen):
    """Screen for the DM lobby."""
    def __init__(self, **kwargs):
        super(DMLobbyScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.network_manager = self.app.network_manager
        self.update_event = None
        self.player_widgets = {} # addr -> Label widget
        self.is_starting_game = False

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def on_enter(self, *args):
        # Reset the flag when entering the screen
        self.is_starting_game = False

        # Start the server if it's not already running
        self.network_manager.start_server()

        self.ids.player_list.clear_widgets()
        self.player_widgets.clear()

        # Populate with already connected players
        with self.network_manager.lock:
            for addr, client_info in self.network_manager.clients.items():
                self.add_player_to_list(addr, client_info['character'])

        # Check for loaded or prepared session data from the app instance
        if self.app.loaded_session_data:
            self.ids.lobby_title.text = "DM Lobby (Geladene Sitzung)"
            # You could show expected players here if desired
        elif hasattr(self.app, 'prepared_session_data') and self.app.prepared_session_data:
            self.ids.lobby_title.text = "DM Lobby (Vorbereitete Sitzung)"
        else:
            self.ids.lobby_title.text = "DM Lobby"

        # Start polling for network updates
        self.update_event = Clock.schedule_interval(self.check_for_updates, 0.5)

    def check_for_updates(self, dt):
        """Checks the incoming message queue for player join/leave events."""
        try:
            while True:
                # The queue holds tuples: (type, payload) or (addr, message)
                item = self.network_manager.incoming_messages.get_nowait()
                if isinstance(item, tuple) and len(item) == 2:
                    message_type, payload = item
                    if message_type == 'PLAYER_JOINED':
                        self.add_player_to_list(payload['addr'], payload['char'])
                        self.handle_new_player_connection(payload['addr'])
                    elif message_type == 'PLAYER_LEFT':
                        self.remove_player_from_list(payload['addr'])
        except Empty:
            pass # No new messages

    def add_player_to_list(self, addr, character):
        if addr not in self.player_widgets:
            player_name = f"{character.name} (Verbunden)"
            player_label = Label(text=player_name, size_hint_y=None, height=40)
            self.ids.player_list.add_widget(player_label)
            self.player_widgets[addr] = player_label

    def remove_player_from_list(self, addr):
        if addr in self.player_widgets:
            widget = self.player_widgets.pop(addr)
            self.ids.player_list.remove_widget(widget)

    def handle_new_player_connection(self, addr):
        """Handles logic when a new player connects, e.g., for loaded sessions."""
        if self.app.loaded_session_data:
            char_name = ""
            with self.network_manager.lock:
                if addr in self.network_manager.clients:
                    char_name = self.network_manager.clients[addr]['character'].name

            if not char_name: return

            found_player = False
            for p_str, p_data in self.app.loaded_session_data['online_players'].items():
                if p_data['character']['name'] == char_name:
                    saved_char_json = json.dumps(p_data['character'])
                    summary = self.app.loaded_session_data.get('summary', 'Keine Zusammenfassung.')
                    self.network_manager.send_message(addr, 'CHAR_DATA', saved_char_json)
                    self.network_manager.send_message(addr, 'SUMMARY', summary)
                    found_player = True
                    break
            if not found_player:
                self.network_manager.send_message(addr, 'ERROR', 'Charakter nicht in dieser Sitzung gefunden.')
                # Consider kicking the player
        else:
            self.network_manager.send_message(addr, 'OK', 'Willkommen in der neuen Sitzung!')

    def start_game(self):
        """Switches to the main DM screen."""
        with self.network_manager.lock:
            if not self.network_manager.clients:
                print("[!] No players have joined yet!")
                # Optionally show a popup
                return

        self.is_starting_game = True
        self.manager.current = 'dm_main'

    def prepare_map(self):
        """Switches to the map editor screen."""
        self.manager.current = 'map_editor'

    def set_custom_background(self):
        """Opens a file chooser to select a custom background image."""
        content = FileChooserListView(path=os.path.expanduser("~"), filters=['*.png', '*.jpg', '*.jpeg'])
        content.bind(selection=self._on_background_selected)
        self.popup = Popup(title="Select Background Image", content=content, size_hint=(0.9, 0.9))
        self.popup.open()

    def _on_background_selected(self, instance, selection):
        if selection:
            filepath = selection[0]
            with open(filepath, 'rb') as f:
                image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            self.network_manager.broadcast_message('SET_BACKGROUND', {'image': image_base64})
            self.popup.dismiss()

    def send_welcome_message(self, message_text):
        """Sends the welcome message to all clients."""
        if message_text:
            self.network_manager.broadcast_message('SET_WELCOME_MESSAGE', {'message': message_text})

    def trigger_send_welcome_message(self):
        """Gets text from input and calls send_welcome_message."""
        welcome_text = self.ids.welcome_message_input.text
        self.send_welcome_message(welcome_text)

    def go_back(self):
        self.manager.current = 'dm_spiel'

    def on_leave(self, *args):
        # Stop polling for updates when leaving the screen
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None

        # If we are not starting the game, it means we are going back,
        # so shut down the server.
        if not self.is_starting_game:
            self.network_manager.shutdown() # Use the generic shutdown
            if self.app.loaded_session_data:
                self.app.loaded_session_data = None # Clear session data
            if hasattr(self.app, 'prepared_session_data'):
                self.app.prepared_session_data = None # Clear prepared data
