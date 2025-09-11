import json
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from utils.helpers import apply_background, apply_styles_to_widget

class DMSpielScreen(Screen):
    """Screen for DM Spiel options."""
    def __init__(self, **kwargs):
        super(DMSpielScreen, self).__init__(**kwargs)

    def on_pre_enter(self, *args):
        # Clear any previously loaded session data when re-entering this screen
        app = App.get_running_app()
        if hasattr(app, 'loaded_session_data'):
            del app.loaded_session_data
        apply_background(self)
        apply_styles_to_widget(self)

    def host_dm(self):
        self.manager.current = 'dm_lobby'

    def join_player(self):
        self.manager.current = 'player_lobby'

    def prepare_dm(self):
        self.manager.current = 'dm_prep'

    def load_session(self):
        """Loads a session file and stores it in the app for the lobby to use."""
        # For now, load from a hardcoded file. Later, use a file chooser.
        filename = "last_session.session"
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            # Store the loaded data in the main app instance
            app = App.get_running_app()
            app.loaded_session_data = session_data

            popup = Popup(title='Geladen',
                          content=Label(text=f"Sitzung '{filename}' geladen.\nStarte eine DM Lobby, um fortzufahren."),
                          size_hint=(None, None), size=(400, 200))
            popup.open()
            print(f"[*] Session loaded from {filename}")

        except FileNotFoundError:
            popup = Popup(title='Fehler',
                          content=Label(text=f"Sitzungsdatei nicht gefunden:\n{filename}"),
                          size_hint=(None, None), size=(400, 200))
            popup.open()
        except Exception as e:
            popup = Popup(title='Fehler',
                          content=Label(text=f"Fehler beim Laden der Sitzung:\n{e}"),
                          size_hint=(None, None), size=(400, 200))
            popup.open()
            print(f"[!] Error loading session: {e}")
