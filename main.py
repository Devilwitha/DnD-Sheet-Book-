import os
import sys
import json

# Separate elevated helper: no GUI, no session data, no arbitrary program argument.
if __name__ == '__main__' and sys.argv[1:] == ['--configure-lan']:
    from utils.windows_network import apply_firewall_rules
    sys.exit(apply_firewall_rules())

# A windowed Windows executable can inherit invalid console handles from launchers.
# Kivy's stderr redirection otherwise recursively logs the console write failure.
# Keep the file-based diagnostic and Kivy logs; this app has no console window.
if sys.platform == 'win32' and getattr(sys, 'frozen', False):
    os.environ['KIVY_NO_CONSOLELOG'] = '1'

from utils.paths import resource_path, user_data_dir

# Kivy home must be set before ANY kivy import.
def _prepare_kivy_home():
    home = os.path.join(user_data_dir(), 'kivy')
    os.makedirs(os.path.join(home, 'icon'), exist_ok=True)
    os.environ['KIVY_HOME'] = home


def _read_minimal_settings():
    try:
        with open(os.path.join(user_data_dir(), 'settings.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


_prepare_kivy_home()
try:
    from utils import diagnostics
    diagnostics.configure()
except Exception:
    diagnostics = None

_boot_settings = _read_minimal_settings()

from kivy.config import Config
from kivy.utils import platform

if platform == 'win':
    Config.set('input', 'mouse', 'mouse,disable_multitouch')

if _boot_settings.get('keyboard_enabled', False):
    Config.set('kivy', 'keyboard_mode', 'dock')
    Config.set('kivy', 'keyboard_height', '600')
else:
    Config.set('kivy', 'keyboard_mode', '')

Config.set('graphics', 'rotation', 0)

# Helpers may import kivy; only import after Config is set.
from utils.helpers import load_settings, save_settings
settings = load_settings()

from kivy.core.window import Window
if platform not in ('android', 'ios'):
    Window.size = (settings.get('window_width', 1280), settings.get('window_height', 720))
    # A hidden or just-created Windows handle can briefly report zero DPI.
    # Do not let that collapse touch targets or divide by zero in Kivy Switch.
    from kivy.metrics import Metrics
    if Window.dpi <= 0:
        Window.dpi = 96
    if Metrics.density <= 0:
        Metrics.density = 1
    if Metrics.fontscale <= 0:
        Metrics.fontscale = 1

from queue import Empty
from utils.data_manager import initialize_data
from utils.formats import decode_map
from kivy.app import App
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.modalview import ModalView
from kivy.uix.label import Label
from kivy.clock import Clock
from core.character import Character
from core.network_manager import NetworkManager

from ui.main_menu import MainMenu
from ui.character_creator import CharacterCreator
from ui.character_sheet import CharacterSheet
from ui.options_screen import OptionsScreen
from ui.character_menu_screen import CharacterMenuScreen
from ui.level_up_screen import LevelUpScreen
from ui.character_editor import CharacterEditor
from ui.info_menu_screen import InfoMenuScreen
from ui.model_screen import ModelScreen
from ui.version_screen import VersionScreen
from ui.settings_screen import SettingsScreen
from ui.background_settings_screen import BackgroundSettingsScreen
from ui.customization_settings_screen import CustomizationSettingsScreen
from ui.splash_screen import SplashScreen
from ui.system_screen import SystemScreen
from ui.changelog_screen import ChangelogScreen
from ui.transfer_screen import TransferScreen
from ui.dm_spiel_screen import DMSpielScreen
from ui.dm_lobby_screen import DMLobbyScreen
from ui.player_lobby_screen import PlayerLobbyScreen
from ui.dm_prep_screen import DMPrepScreen
from ui.dm_main_screen import DMMainScreen
from ui.player_character_sheet import PlayerCharacterSheet
from ui.player_waiting_screen import PlayerWaitingScreen
from ui.map_editor_screen import MapEditorScreen
from ui.player_map_screen import PlayerMapScreen

ROOT_SCREENS = ('main', 'dm_spiel', 'player_sheet')
MAX_EVENTS_PER_FRAME = 64
PARENT_MAP = {
    'dm_spiel': 'main',
    'character_menu': 'main', 'creator': 'character_menu', 'editor': 'character_menu',
    'sheet': 'character_menu', 'options': 'main', 'settings': 'options',
    'background_settings': 'settings', 'customization_settings': 'settings',
    'system': 'options', 'changelog': 'system', 'system_info': 'system',
    'info_menu': 'main', 'model': 'info_menu', 'version': 'info_menu',
    'level_up': 'sheet', 'transfer': 'main', 'player_lobby': 'dm_spiel',
    'dm_lobby': 'dm_spiel', 'dm_prep': 'dm_spiel', 'dm_main': 'dm_spiel',
    'player_waiting': 'dm_spiel', 'map_editor': 'dm_spiel', 'player_map': 'player_sheet',
}
KV_FILES = [
    'commoncontrols',
    'splashscreen', 'mainmenu', 'charactercreator', 'charactereditor', 'charactersheet',
    'charactermenuscreen', 'levelupscreen', 'optionsscreen', 'settingsscreen',
    'backgroundsettingsscreen', 'customizationsettingsscreen', 'systemscreen',
    'changelogscreen', 'infomenuscreen', 'modelscreen', 'versionscreen',
    'systeminfoscreen', 'transferscreen', 'dmspielscreen', 'dmlobbyscreen',
    'playerlobbyscreen', 'dmprepscreen', 'dmmainscreen', 'playerwaitingscreen',
    'playercharactersheet', 'mapeditorscreen', 'playermapscreen',
]


def _record(event, error):
    try:
        if diagnostics:
            diagnostics.record_error(event, error)
    except Exception:
        pass


class DnDApp(App):
    """Haupt-App-Klasse."""
    def __init__(self, **kwargs):
        super(DnDApp, self).__init__(**kwargs)
        self.network_manager = NetworkManager()
        self.loaded_session_data = None
        self.character = None
        self.screen_history = []  # actual visited screens
        self.edited_map_data = None
        self.player_game_loop = None
        self.sm = None
        self._last_screen = None
        self._going_back = False
        self._update_error_shown = False
        self._character_request = None
        from core.game_manager import GameManager
        self.game_manager = GameManager()

    # ---------- player game loop ----------
    def start_player_gameloop(self):
        if self.player_game_loop:
            self.player_game_loop.cancel()
        self._update_error_shown = False
        self.player_game_loop = Clock.schedule_interval(self.check_for_player_updates, 0.5)

    def stop_player_gameloop(self):
        if self.player_game_loop:
            self.player_game_loop.cancel()
            self.player_game_loop = None

    def _popup(self, title, text, size_hint=(0.7, 0.4)):
        from utils.helpers import create_styled_popup
        lbl = Label(text=str(text), halign='center')
        lbl.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)))
        p = create_styled_popup(title=title, content=lbl, size_hint=size_hint)
        p.open()
        return p

    def _report_update_error(self, error):
        _record('player_update', error)
        if not self._update_error_shown:
            self._update_error_shown = True
            self._popup('Hinweis', 'Ein Update vom DM konnte nicht verarbeitet werden.')

    def check_for_player_updates(self, dt):
        nm = self.network_manager
        if not nm.running and nm.mode == 'idle':
            self.disconnect_player('Verbindung zum DM verloren.', intentional=False)
            return
        for _ in range(MAX_EVENTS_PER_FRAME):
            try:
                source, message = nm.incoming_messages.get_nowait()
            except Empty:
                break
            except Exception as e:
                self._report_update_error(e)
                break
            try:
                if self._handle_player_message(message):
                    return
            except Exception as e:
                self._report_update_error(e)

    def _handle_player_message(self, message):
        """Returns True if the loop must stop (disconnected)."""
        sm = self.sm
        msg_type = message.get('type')
        payload = message.get('payload')

        if msg_type == 'KICK':
            self.disconnect_player('Du wurdest vom DM gekickt.', intentional=False)
            return True
        elif msg_type == 'MAP_DATA':
            map_data = decode_map(payload)  # decode exactly once
            if sm.has_screen('player_map'):
                sm.get_screen('player_map').set_map_data(map_data)
            if sm.has_screen('player_sheet'):
                ps = sm.get_screen('player_sheet')
                ps.map_data = map_data
                ps.ids.view_map_button.disabled = False
        elif msg_type == 'TRIGGER_MESSAGE':
            self._popup('!', (payload or {}).get('message', '...'), (0.7, 0.5))
        elif msg_type == 'GAME_STATE_UPDATE':
            payload = payload or {}
            if sm.has_screen('player_sheet'):
                ps = sm.get_screen('player_sheet')
                ps.update_player_list(payload.get('players', []))
                ps.update_initiative_order(payload.get('initiative', []))
            if sm.has_screen('player_map'):
                sm.get_screen('player_map').update_game_state(payload)
        elif msg_type == 'VICTORY':
            self._popup('Sieg!', payload, (0.7, 0.5))
        elif msg_type in ('ERROR', 'ACTION_RESULT'):
            message = payload.get('message', '') if isinstance(payload, dict) else str(payload)
            if sm.has_screen('player_map'):
                request_id = payload.get('request_id') if isinstance(payload, dict) else None
                sm.get_screen('player_map').show_action_result(message, request_id)
            if sm.current != 'player_map':
                self._popup('Aktion' if msg_type == 'ACTION_RESULT' else 'Aktion nicht möglich', message)
            if msg_type == 'ERROR':
                _record('server_error', RuntimeError(message))
        elif msg_type == 'CHARACTER_ACTION_RESULT':
            if isinstance(payload, dict):
                if payload.get('request_id') == getattr(self, '_character_request', None):
                    self._character_request = None
                self._popup('Charakteraktion' if payload.get('success') else 'Aktion nicht möglich', payload.get('message', ''))
        elif msg_type in ('SET_CHARACTER_DATA', 'SYNC_CHARACTER', 'CHAR_DATA'):
            data = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
            local_save_name = getattr(self.character, '_local_save_name', None)
            self.character = Character.from_dict(data)
            if local_save_name:
                self.character._local_save_name = local_save_name
            if sm.has_screen('player_sheet'):
                ps = sm.get_screen('player_sheet')
                ps.character = self.character
                ps.update_sheet()
            if sm.has_screen('sheet') and self.network_manager.mode == 'client':
                sheet = sm.get_screen('sheet')
                sheet.character = self.character
                if sm.current == 'sheet':
                    sheet.load_character(self.character)
            if sm.has_screen('level_up') and self.network_manager.mode == 'client':
                level = sm.get_screen('level_up')
                level.character = self.character
                level.reset_choices()
                if sm.current == 'level_up':
                    sm.current = 'sheet'
            if msg_type == 'SET_CHARACTER_DATA':
                self._popup('Update', 'Dein Charakter wurde vom DM aktualisiert.', (0.6, 0.4))
        elif msg_type == 'SAVE_YOUR_CHARACTER':
            if sm.has_screen('player_sheet'):
                sm.get_screen('player_sheet').save_character()
        return False

    def request_character_action(self, action, **args):
        """Send an intent once, without optimistic edits to the character sheet."""
        from uuid import uuid4
        from core.character_actions import state_token
        if self.network_manager.mode != 'client' or self.character is None:
            self._popup('Nicht verbunden', 'Bitte zuerst der DM-Sitzung beitreten.')
            return False
        if getattr(self, '_character_request', None):
            self._popup('Bitte warten', 'Eine Charakteraktion wartet noch auf die Antwort des DM. Rasten muss der DM bestätigen.')
            return False
        request_id = uuid4().hex
        self._character_request = request_id
        if not self.network_manager.send_to_dm('CHARACTER_ACTION', {
                'request_id': request_id, 'state': state_token(self.character), 'action': action, 'args': args}):
            self._character_request = None
            self._popup('Nicht gesendet', 'Die Verbindung zum DM ist unterbrochen.')
            return False
        return True

    # ---------- disconnect ----------
    def disconnect_player(self, message=None, intentional=False):
        """Stops the client session and returns to main. Popup opens after navigation."""
        self.stop_player_gameloop()
        self._character_request = None
        nm = self.network_manager
        try:
            if nm.running or nm.mode != 'idle':
                nm.shutdown()
        except Exception as e:
            _record('disconnect', e)
        self.change_screen('main', 'right')
        if message and not intentional:
            self._popup('Verbindung getrennt', message)

    def handle_disconnect(self, message):
        self.disconnect_player(message, intentional=False)

    def intentional_disconnect(self):
        """For the player_sheet disconnect button / back key."""
        from ui.character_approval import ask_dm
        ask_dm('Sitzung verlassen?', 'Die Verbindung zum DM wird getrennt. Der bestätigte Stand bleibt beim DM erhalten.',
               lambda: self.disconnect_player(None, intentional=True), lambda: None, 'Sitzung verlassen')

    # ---------- navigation ----------
    def _on_screen_current(self, sm, value):
        prev, self._last_screen = self._last_screen, value
        if prev is None or prev == value or self._going_back:
            return
        if value in ROOT_SCREENS:
            self.screen_history = []
            return
        if value in self.screen_history:
            # returning to an earlier screen: cut the loop
            self.screen_history = self.screen_history[:self.screen_history.index(value)]
            return
        if prev != 'splash' and (not self.screen_history or self.screen_history[-1] != prev):
            self.screen_history.append(prev)

    def change_screen(self, screen_name, transition_direction='left', is_go_back=False):
        sm = self.sm
        if sm is None or screen_name == sm.current or not sm.has_screen(screen_name):
            return
        sm.transition.direction = transition_direction
        if is_go_back:
            self._going_back = True
            try:
                sm.current = screen_name
            finally:
                self._going_back = False
        else:
            sm.current = screen_name

    def go_back_screen(self):
        """Returns True if navigation happened."""
        sm = self.sm
        current = sm.current
        while self.screen_history:
            target = self.screen_history.pop()
            if target != current and sm.has_screen(target):
                self.change_screen(target, 'right', is_go_back=True)
                return True
        parent = PARENT_MAP.get(current)
        if parent and sm.has_screen(parent):
            self.change_screen(parent, 'right', is_go_back=True)
            return True
        if current not in ROOT_SCREENS and sm.has_screen('main'):
            self.change_screen('main', 'right', is_go_back=True)
            return True
        return False

    def _on_keyboard(self, window, key, *args):
        if key != 27:
            return False
        for w in list(Window.children):
            if isinstance(w, ModalView):
                try:
                    cancel = getattr(w, 'cancel_decision', None)
                    if callable(cancel):
                        cancel()
                    elif w.auto_dismiss:
                        w.dismiss()
                except Exception as e:
                    _record('popup_dismiss', e)
                return True
        if self.sm.current == 'player_sheet':
            self.intentional_disconnect()
            return True
        if self.sm.current == 'map_editor':
            self.sm.get_screen('map_editor').go_back()
            return True
        self.go_back_screen()  # at main: consumed, app has explicit exit button
        return True

    # ---------- lifecycle ----------
    def build(self):
        from utils.paths import migrate_legacy_saves
        migrate_legacy_saves()
        initialize_data()

        for name in KV_FILES:
            Builder.load_file(resource_path('ui/%s.kv' % name))

        if platform == 'win':
            Window.fullscreen = False
            Window.set_icon(resource_path('logo/logo.png'))
        else:
            Window.fullscreen = 'auto'

        Window.clearcolor = (0.1, 0.1, 0.1, 1)

        root = FloatLayout()
        sm = ScreenManager()
        self.sm = sm
        sm.add_widget(SplashScreen(name='splash'))
        sm.add_widget(MainMenu(name='main'))
        sm.add_widget(CharacterMenuScreen(name='character_menu'))
        sm.add_widget(CharacterCreator(name='creator'))
        sm.add_widget(CharacterEditor(name='editor'))
        sm.add_widget(CharacterSheet(name='sheet'))
        sm.add_widget(OptionsScreen(name='options'))
        sm.add_widget(SettingsScreen(name='settings'))
        sm.add_widget(BackgroundSettingsScreen(name='background_settings'))
        sm.add_widget(CustomizationSettingsScreen(name='customization_settings'))
        sm.add_widget(SystemScreen(name='system'))
        sm.add_widget(ChangelogScreen(name='changelog'))
        sm.add_widget(InfoMenuScreen(name='info_menu'))
        sm.add_widget(ModelScreen(name='model'))
        sm.add_widget(VersionScreen(name='version'))
        if platform not in ('android', 'ios'):
            from ui.system_info_screen import SystemInfoScreen
            sm.add_widget(SystemInfoScreen(name='system_info'))
        sm.add_widget(LevelUpScreen(name='level_up'))
        sm.add_widget(TransferScreen(name='transfer'))
        sm.add_widget(DMSpielScreen(name='dm_spiel'))
        sm.add_widget(DMLobbyScreen(name='dm_lobby'))
        sm.add_widget(PlayerLobbyScreen(name='player_lobby'))
        sm.add_widget(DMPrepScreen(name='dm_prep'))
        sm.add_widget(DMMainScreen(name='dm_main'))
        sm.add_widget(PlayerWaitingScreen(name='player_waiting'))
        sm.add_widget(PlayerCharacterSheet(name='player_sheet'))
        sm.add_widget(MapEditorScreen(name='map_editor'))
        sm.add_widget(PlayerMapScreen(name='player_map'))

        self._last_screen = sm.current
        sm.bind(current=self._on_screen_current)
        Window.bind(on_keyboard=self._on_keyboard)

        root.add_widget(sm)
        return root

    def on_pause(self):
        try:
            if self.sm is not None and self.sm.has_screen('map_editor'):
                self.sm.get_screen('map_editor').checkpoint_atlas()
        except Exception as e:
            _record('pause_atlas', e)
        try:
            if self.sm is not None and self.sm.has_screen('dm_prep'):
                self.sm.get_screen('dm_prep').save_preparation()
        except Exception as e:
            _record('pause_preparation', e)
        try:
            if self.sm is not None and self.sm.has_screen('dm_main'):
                self.sm.get_screen('dm_main').checkpoint_archive()
        except Exception as e:
            _record('pause_archive', e)
        return True

    def on_stop(self):
        try:
            if self.sm is not None and self.sm.has_screen('map_editor'):
                self.sm.get_screen('map_editor').checkpoint_atlas()
        except Exception as e:
            _record('stop_atlas', e)
        try:
            if self.sm is not None and self.sm.has_screen('dm_prep'):
                self.sm.get_screen('dm_prep').save_preparation()
        except Exception as e:
            _record('stop_preparation', e)
        try:
            if self.sm is not None and self.sm.has_screen('dm_main'):
                self.sm.get_screen('dm_main').checkpoint_archive()
        except Exception as e:
            _record('stop_archive', e)
        try:
            self.stop_player_gameloop()
            self.network_manager.shutdown()
        except Exception as e:
            _record('stop_network', e)
        try:
            if self.sm is not None and self.sm.has_screen('transfer'):
                screen = self.sm.get_screen('transfer')
                for name in ('cleanup_transfer', 'cleanup', 'stop_transfer'):
                    fn = getattr(screen, name, None)
                    if callable(fn):
                        fn()
                        break
        except Exception as e:
            _record('stop_transfer', e)
        if platform not in ('android', 'ios'):
            try:
                s = load_settings()
                s['window_width'] = Window.width
                s['window_height'] = Window.height
                save_settings(s)
            except Exception as e:
                _record('save_window', e)


if __name__ == '__main__':
    DnDApp().run()
