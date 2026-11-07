from kivy.metrics import dp
import hashlib
import json
import os
from queue import Empty

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from core import file_transfer as ft
from core.character import Character
from utils import storage
from utils.helpers import apply_background, apply_styles_to_widget, load_settings, save_settings
from utils.paths import get_user_saves_dir

MAX_BG_BYTES = 8 * 1024 * 1024
MAX_CHUNK_HEX = 128 * 1024


class PlayerWaitingScreen(Screen):
    """A screen for the player to wait in while the DM prepares the game."""

    def __init__(self, **kwargs):
        super(PlayerWaitingScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.network_manager = self.app.network_manager
        self.update_event = None
        self._bg = None

    def _reset_background(self):
        self._bg = None

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def on_enter(self, *args):
        self._reset_background()
        self.ids.waiting_label.text = 'Verbunden mit DM. Warten auf Antwort...'
        self.ids.summary_label.text = ''
        self.update_event = Clock.schedule_interval(self.check_for_updates, 0.5)

    def check_for_updates(self, dt):
        if not self.network_manager.running and self.network_manager.mode == 'idle':
            self.handle_disconnect('Verbindung zum DM verloren.')
            return
        for _ in range(64):
            try:
                item = self.network_manager.incoming_messages.get_nowait()
            except Empty:
                return
            try:
                source, message = item
                if source != 'DM':
                    continue
                if not isinstance(message, dict):
                    raise ValueError('message')
                if self._handle_message(message.get('type'), message.get('payload')):
                    return
            except Exception:
                self.handle_disconnect('Ungültige Nachricht vom DM. Verbindung getrennt.')
                return

    def _handle_message(self, msg_type, payload):
        """Returns True when message polling should stop. Raises on malformed input."""
        if msg_type == 'CHAR_DATA':
            data = json.loads(payload) if isinstance(payload, (str, bytes, bytearray)) else payload
            if not isinstance(data, dict):
                raise ValueError('char data')
            local_save_name = getattr(self.app.character, '_local_save_name', None)
            new_char = Character.from_dict(data)
            if local_save_name:
                new_char._local_save_name = local_save_name
            self.app.character = new_char
        elif msg_type == 'SUMMARY':
            self.ids.summary_label.text = 'Sitzungs-Zusammenfassung:\n' + str(payload)
        elif msg_type == 'OK':
            self.ids.waiting_label.text = 'Willkommen! Warten bis das Spiel startet...'
        elif msg_type == 'ERROR':
            self.handle_disconnect('Fehler vom DM: ' + str(payload)[:200])
            return True
        elif msg_type == 'KICK':
            self.handle_disconnect('Du wurdest vom DM gekickt.')
            return True
        elif msg_type == 'GAME_START':
            self.proceed_to_game()
            return True
        elif msg_type == 'GAME_STATE_UPDATE':
            players = payload.get('players', []) if isinstance(payload, dict) else None
            if not isinstance(players, list) or not all(isinstance(p, str) for p in players):
                raise ValueError('players')
            self.update_player_list(players)
        elif msg_type == 'BACKGROUND_START':
            self._background_start(payload)
        elif msg_type == 'BACKGROUND_CHUNK':
            self._background_chunk(payload)
        elif msg_type == 'BACKGROUND_END':
            self.handle_background_data()
        return False

    def _background_start(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('start')
        size, sha = payload.get('size'), payload.get('sha256')
        if type(size) is not int or not 0 < size <= MAX_BG_BYTES or not ft._is_hex(sha, 64):
            raise ValueError('start fields')
        self._bg = {'size': size, 'sha256': sha, 'buf': bytearray()}

    def _background_chunk(self, payload):
        if self._bg is None:
            return
        if not isinstance(payload, str) or not 0 < len(payload) <= MAX_CHUNK_HEX:
            self._reset_background()
            raise ValueError('chunk')
        part = bytes.fromhex(payload)
        if len(self._bg['buf']) + len(part) > self._bg['size']:
            self._reset_background()
            raise ValueError('too much data')
        self._bg['buf'] += part

    def handle_background_data(self):
        """Validates, saves (local UUID name, atomic) and applies the received background."""
        bg, self._bg = self._bg, None
        if bg is None:
            return
        data = bytes(bg['buf'])
        try:
            if len(data) != bg['size'] or hashlib.sha256(data).hexdigest() != bg['sha256']:
                raise ft.PayloadError('checksum')
            ext = ft.image_extension(data)
            folder = str(get_user_saves_dir('backgrounds'))
            os.makedirs(folder, exist_ok=True)
            path = storage.unique_import_path(folder, ext)
            storage.atomic_write_bytes(path, data)
            settings = load_settings()
            settings['lobby_background_path'] = str(path)
            save_settings(settings)
            apply_background(self)
        except ft.TransferError:
            self.ids.waiting_label.text = 'Hintergrund ungültig und verworfen.'
        except Exception:
            self.ids.waiting_label.text = 'Hintergrund konnte nicht gespeichert werden.'

    def proceed_to_game(self):
        self._reset_background()
        # on_leave fires only after the screen transition. Stop this consumer now,
        # otherwise it can swallow MAP_DATA/SYNC_CHARACTER before the game loop runs.
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None
        self.app.start_player_gameloop()
        self.manager.current = 'player_sheet'

    def handle_disconnect(self, message):
        self._reset_background()
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None
            self.app.handle_disconnect(message)

    def on_leave(self, *args):
        self._reset_background()
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None
        if self.manager.current != 'player_sheet':
            self.network_manager.shutdown()

    def update_player_list(self, players):
        """Updates the player list UI."""
        widget = self.ids.player_list
        widget.clear_widgets()
        for name in players:
            widget.add_widget(Label(text=name, size_hint_y=None, height=dp(48)))
