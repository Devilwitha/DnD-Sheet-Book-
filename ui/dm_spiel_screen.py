import json
import os
from functools import partial
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup

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
        """Opens a popup to select and load a session file."""
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        session_files = [f for f in os.listdir('.') if f.endswith('.session')]
        if not session_files:
            create_styled_popup(title="Keine Sitzungen", content=Label(text="Keine gespeicherten Sitzungen gefunden."), size_hint=(0.6, 0.4)).open()
            return

        for filename in session_files:
            btn = Button(text=filename, size_hint_y=None, height=44)
            btn.bind(on_press=partial(self.do_load_file, filename))
            scroll_content.add_widget(btn)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        content.add_widget(scroll_view)

        self.load_popup = create_styled_popup(title="Sitzung laden", content=content, size_hint=(0.8, 0.8))
        self.load_popup.open()

    def do_load_file(self, filename, instance):
        """Loads the selected file and transitions to the lobby."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            app = App.get_running_app()
            app.loaded_session_data = session_data

            if hasattr(self, 'load_popup'):
                self.load_popup.dismiss()

            self.manager.current = 'dm_lobby'

        except Exception as e:
            create_styled_popup(title="Ladefehler", content=Label(text=f"Fehler beim Laden:\n{e}"), size_hint=(0.7, 0.5)).open()
