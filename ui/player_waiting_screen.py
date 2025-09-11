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
            self.handle_disconnect("Verbindung zum DM verloren.")
            return

        try:
            while True:
                source, message = self.network_manager.incoming_messages.get_nowait()
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

        except Empty:
            pass

    def proceed_to_game(self):
        # The character and connection are already managed by the app/network_manager
        self.manager.current = 'player_sheet'

    def handle_disconnect(self, message):
        from utils.helpers import create_styled_popup
        from kivy.uix.label import Label

        # This function might be called multiple times, ensure it only runs once
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None

            # The network manager's shutdown will handle socket closure
            self.network_manager.shutdown()

            create_styled_popup(title="Verbindung getrennt",
                                content=Label(text=message),
                                size_hint=(0.7, 0.4)).open()
            self.manager.current = 'main'

    def on_leave(self, *args):
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None

        # If we are not going to the game, manually shut down the connection
        if self.manager.current != 'player_sheet':
            self.network_manager.shutdown()
