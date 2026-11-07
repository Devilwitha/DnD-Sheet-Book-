from kivy.metrics import dp
import json
import os
import sys
from functools import partial
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from utils.formats import decode_session
from utils.storage import read_json, safe_save_path
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup, get_user_saves_dir

class DMSpielScreen(Screen):
    """Screen for DM Spiel options."""
    def __init__(self, **kwargs):
        super(DMSpielScreen, self).__init__(**kwargs)

    def on_pre_enter(self, *args):
        # Clear any previously loaded session data when re-entering this screen
        app = App.get_running_app()
        app.loaded_session_data = None
        app.prepared_session_data = None
        apply_background(self)
        apply_styles_to_widget(self)

        is_windows = sys.platform.startswith('win')

        dm_buttons = ['host_dm_btn', 'prepare_dm_btn', 'load_session_btn', 'archive_btn']
        for btn_id in dm_buttons:
            button = self.ids.get(btn_id)
            if button:
                if not is_windows:
                    button.size_hint_y = None
                    button.height = 0
                    button.opacity = 0
                    button.disabled = True
                else:
                    button.size_hint_y = None
                    button.height = 80
                    button.opacity = 1
                    button.disabled = False

    def host_dm(self):
        try:
            App.get_running_app().sm.get_screen('dm_main').start_new_dm_session()
        except Exception as exc:
            create_styled_popup(title='Archivfehler', content=Label(text=str(exc)), size_hint=(.8,.5)).open()
            return
        self.manager.current = 'dm_lobby'

    def show_archive(self):
        from ui.session_archive_dialog import ArchiveBrowser
        try:
            self.archive_browser = ArchiveBrowser(App.get_running_app())
            self.archive_browser.open()
        except Exception as exc:
            create_styled_popup(title='Archivfehler', content=Label(text=str(exc)), size_hint=(.8,.5)).open()

    def join_player(self):
        self.manager.current = 'player_lobby'

    def prepare_dm(self):
        from ui.campaign_browser import CampaignBrowser
        try:
            self.campaign_browser = CampaignBrowser(App.get_running_app())
            self.campaign_browser.open()
        except Exception as exc:
            App.get_running_app()._popup('Kampagnen', str(exc))

    def open_map_workshop(self):
        app = App.get_running_app()
        editor = app.sm.get_screen('map_editor')
        if editor.begin_edit('library'):
            app.change_screen('map_editor')

    def load_session(self):
        """Opens a popup to select and load a session file."""
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        saves_dir = get_user_saves_dir("sessions")
        session_files = [f for f in os.listdir(saves_dir) if f.endswith('.json')]
        if not session_files:
            create_styled_popup(title="Keine Sitzungen", content=Label(text="Keine gespeicherten Sitzungen gefunden."), size_hint=(0.6, 0.4)).open()
            return

        for filename in session_files:
            btn = Button(text=filename, size_hint_y=None, height=dp(48))
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
            path = safe_save_path(get_user_saves_dir('sessions'), filename)
            session_data = decode_session(read_json(path))
        except FileNotFoundError:
            msg = 'Die Datei wurde nicht gefunden.'
        except json.JSONDecodeError:
            msg = 'Die Datei ist beschaedigt (kein gueltiges JSON).'
        except (ValueError, KeyError, TypeError) as e:
            msg = f'Ungueltige Sitzungsdatei: {e}'
        except OSError as e:
            msg = f'Datei konnte nicht gelesen werden: {e}'
        except Exception as e:
            msg = f'Unerwarteter Fehler: {e}'
        else:
            app = App.get_running_app()
            app.loaded_session_data = session_data
            if hasattr(self, 'load_popup'):
                self.load_popup.dismiss()
            self.manager.current = 'dm_lobby'
            return
        create_styled_popup(title='Ladefehler', content=Label(text=f'Fehler beim Laden:\n{msg}'), size_hint=(0.7, 0.5)).open()
