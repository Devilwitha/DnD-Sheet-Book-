from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.app import App
from utils.helpers import apply_background, apply_styles_to_widget
from core.character import Character
from queue import Empty

class PlayerWaitingScreen(Screen):
    """A screen for the player to wait in while the DM prepares the game."""
    def __init__(self, **kwargs):
        super(PlayerWaitingScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.network_manager = self.app.network_manager
        self.update_event = None

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def on_enter(self, *args):
        self.ids.waiting_label.text = "Verbunden mit DM. Warten auf Antwort..."
        self.ids.summary_label.text = ""
        self.update_event = Clock.schedule_interval(self.check_for_updates, 0.5)

    def check_for_updates(self, dt):
        # Check if the connection was dropped
        if not self.network_manager.running and self.network_manager.mode == 'idle':
            print("[WAITING_SCREEN] Disconnected, handling.")
            self.handle_disconnect("Verbindung zum DM verloren.")
            return

        try:
            while True:
                # print("[WAITING_SCREEN] Polling for messages...")
                source, message = self.network_manager.incoming_messages.get_nowait()
                print(f"[WAITING_SCREEN] Dequeued message: {message}")
                if source != 'DM': continue # Should not happen in client mode

                msg_type = message.get('type')
                payload = message.get('payload')

                if msg_type == 'CHAR_DATA':
                    self.app.character = Character.from_dict(payload)
                elif msg_type == 'SUMMARY':
                    self.ids.summary_label.text = f"Sitzungs-Zusammenfassung:\n{payload}"
                elif msg_type == 'OK':
                    self.ids.waiting_label.text = "Willkommen! Warten bis das Spiel startet..."
                elif msg_type == 'ERROR':
                    self.handle_disconnect(f"Fehler vom DM: {payload}")
                elif msg_type == 'KICK':
                    self.handle_disconnect("Du wurdest vom DM gekickt.")
                elif msg_type == 'GAME_START':
                    self.proceed_to_game()
                    return # Stop checking for messages here
                elif msg_type == 'GAME_STATE_UPDATE':
                    self.update_player_list(payload.get('players', []))

        except Empty:
            pass

    def proceed_to_game(self):
        # The character and connection are already managed by the app/network_manager
        self.app.start_player_gameloop()
        self.manager.current = 'player_sheet'

    def handle_disconnect(self, message):
        # This function might be called multiple times from the update loop
        # so we check if the event is still active before proceeding.
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None
            # Call the app's central disconnect handler
            self.app.handle_disconnect(message)

    def on_leave(self, *args):
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None

        # If we are not going to the game, manually shut down the connection
        if self.manager.current != 'player_sheet':
            self.network_manager.shutdown()

    def update_player_list(self, players):
        """Updates the player list UI."""
        player_list_widget = self.ids.player_list
        player_list_widget.clear_widgets()
        for player_name in players:
            player_list_widget.add_widget(Label(text=player_name, size_hint_y=None, height=30))
