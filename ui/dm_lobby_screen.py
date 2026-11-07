import hashlib
import os
import socket
import threading
from functools import partial
from queue import Empty

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.properties import BooleanProperty
from kivy.uix.filechooser import FileChooserListView

from core.character import Character
from ui.character_approval import ask_dm, character_summary
from utils.helpers import apply_background, apply_styles_to_widget, load_settings, save_settings, create_styled_popup

try:
    from utils import diagnostics
except Exception:
    diagnostics = None

DEFAULT_NAME = 'DM Spiel'
MAX_BACKGROUND_BYTES = 8 * 1024 * 1024
BACKGROUND_CHUNK = 64 * 1024
MAX_EVENTS_PER_FRAME = 64


def _record(event, error):
    try:
        if diagnostics:
            diagnostics.record_error(event, error)
    except Exception:
        pass


def _local_ipv4s():
    from utils.wire import get_local_ipv4s
    return get_local_ipv4s()


class DMLobbyScreen(Screen):
    """Screen for the DM lobby."""
    host_ready = BooleanProperty(False)
    def __init__(self, **kwargs):
        super(DMLobbyScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.network_manager = self.app.network_manager
        self.update_event = None
        self.player_widgets = {}
        self.is_starting_game = False
        self.popup = None
        self._enter_gen = 0

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def on_enter(self, *args):
        self.is_starting_game = False
        self._enter_gen += 1
        self._session_running = bool(getattr(self.app, 'dm_session_active', False))
        if self._session_running:
            self._start_lobby(self._enter_gen)
            return
        self.host_ready = False
        self.ids.endpoint_label.text = 'Verbindung wird vorbereitet …'
        from ui.network_help import prepare_host
        generation = self._enter_gen
        prepare_host(self, lambda: self._start_lobby(generation))

    def _start_lobby(self, generation):
        if generation != self._enter_gen or not self.manager or self.manager.current != self.name:
            return
        session_name = self.ids.session_name_input.text.strip() or DEFAULT_NAME
        ok, reason = self.network_manager.start_server(display_name=session_name)
        if not ok:
            self.app._popup('DM-Host konnte nicht starten', reason)
            self.ids.endpoint_label.text = 'Host nicht gestartet.'
            return
        self.host_ready = True

        self.ids.player_list.clear_widgets()
        self.player_widgets.clear()

        with self.network_manager.lock:
            existing = [(a, c['character']) for a, c in self.network_manager.clients.items()]
        for addr, character in existing:
            self.add_player_to_list(addr, character)

        self._show_join_info()

        if self.app.loaded_session_data:
            self.ids.lobby_title.text = 'DM Lobby (Geladene Sitzung)'
            self.ids.summary_label.text = self.app.loaded_session_data.get(
                'summary', 'Keine Zusammenfassung für diese Sitzung gefunden.')
        elif getattr(self.app, 'prepared_session_data', None):
            self.ids.lobby_title.text = 'DM Lobby (Vorbereitete Sitzung)'
            self.ids.summary_label.text = ''
        else:
            self.ids.lobby_title.text = 'DM Lobby'
            self.ids.summary_label.text = ''

        self.update_event = Clock.schedule_interval(self.check_for_updates, 0.5)

    # ---------- endpoint / join code ----------
    def _show_join_info(self):
        self.ids.join_code_label.text = str(getattr(self.network_manager, 'join_code', '') or '-')
        self.ids.endpoint_label.text = 'Ermittle Adresse...'
        threading.Thread(target=self._endpoint_worker, args=(self._enter_gen,), daemon=True).start()

    def _endpoint_worker(self, gen):
        ips = _local_ipv4s()
        Clock.schedule_once(partial(self._set_endpoints, gen, ips))

    def _set_endpoints(self, gen, ips, dt):
        if gen != self._enter_gen:
            return
        port = getattr(self.network_manager, 'port', None) or getattr(self.network_manager, 'server_port', None)
        if not ips:
            self.ids.endpoint_label.text = 'Keine Netzwerkadresse gefunden'
        elif port:
            self.ids.endpoint_label.text = ', '.join('%s:%s' % (ip, port) for ip in ips)
        else:
            self.ids.endpoint_label.text = ', '.join(ips)

    # ---------- player events ----------
    def check_for_updates(self, dt):
        if getattr(self, '_session_running', False):
            # The running DM screen owns the queue, including actions and approvals.
            with self.network_manager.lock:
                existing = [(addr, c['character']) for addr, c in self.network_manager.clients.items()]
            addresses = {addr for addr, _ in existing}
            for addr in list(self.player_widgets):
                if addr not in addresses:
                    self.remove_player_from_list(addr)
            for addr, character in existing:
                self.add_player_to_list(addr, character)
            return
        for _ in range(MAX_EVENTS_PER_FRAME):
            try:
                item = self.network_manager.incoming_messages.get_nowait()
            except Empty:
                break
            try:
                if isinstance(item, tuple) and len(item) == 2:
                    message_type, payload = item
                    if message_type == 'PLAYER_JOINED':
                        with self.network_manager.lock:
                            live = self.network_manager.clients.get(payload['addr'])
                        if not live:
                            continue
                        self.add_player_to_list(payload['addr'], live['character'])
                        self.handle_new_player_connection(payload['addr'])
                        self._broadcast_lobby_players()
                    elif message_type == 'PLAYER_LEFT':
                        with self.network_manager.lock:
                            live_addresses = set(self.network_manager.clients)
                        for address in list(self.player_widgets):
                            if address not in live_addresses:
                                self.remove_player_from_list(address)
                        self._broadcast_lobby_players()
            except Exception as e:
                _record('lobby_event', e)

    def add_player_to_list(self, addr, character):
        with self.network_manager.lock:
            approved = self.network_manager.clients.get(addr, {}).get('approved', True)
        text = f'{character.name} · {character.char_class} · Stufe {character.level} (' + ('bereit' if approved else 'Freigabe offen') + ')'
        if addr in self.player_widgets:
            self.player_widgets[addr].text = text
            return
        label = Label(text=text, size_hint_y=None, height=dp(48))
        self.ids.player_list.add_widget(label)
        self.player_widgets[addr] = label

    def remove_player_from_list(self, addr):
        widget = self.player_widgets.pop(addr, None)
        if widget is not None:
            self.ids.player_list.remove_widget(widget)

    @staticmethod
    def _find_saved(players, character):
        cid = getattr(character, 'character_id', None)
        if cid:
            for d in players:
                if isinstance(d, dict) and d.get('character_id') == cid:
                    return d
        # legacy fallback: saved entries without a stable id, matched by name
        for d in players:
            if isinstance(d, dict) and not d.get('character_id') and d.get('name') == character.name:
                return d
        return None

    def handle_new_player_connection(self, addr):
        """Handles logic when a new player connects (duplicate active players are denied by NetworkManager)."""
        nm = self.network_manager
        with nm.lock:
            client = nm.clients.get(addr)
            character = client['character'] if client else None
        if character is None:
            return
        session = self.app.loaded_session_data or getattr(self.app, 'prepared_session_data', None) or {}
        players = (session.get('online_players') or []) + (session.get('offline_players') or [])
        saved = self._find_saved(players, character)
        if not session or (not saved and not self.app.loaded_session_data):
            def accept():
                with nm.lock:
                    if nm.clients.get(addr) is not client:
                        return
                    client['approved'] = True
                self.add_player_to_list(addr, character)
                nm.send_message(addr, 'CHAR_DATA', character.to_dict())
                nm.send_message(addr, 'OK', 'Willkommen in der neuen Sitzung!')
            ask_dm('Neuen Charakter aufnehmen', character_summary(character), accept,
                   lambda: nm.kick_player(addr), 'Charakter übernehmen')
            return
        if saved is None:
            nm.send_message(addr, 'ERROR', 'Charakter nicht in dieser Sitzung gefunden.')
            nm.kick_player(addr)
            return
        try:
            saved_char = Character.from_dict(saved)
        except Exception as e:
            _record('lobby_restore_character', e)
            nm.send_message(addr, 'ERROR', 'Gespeicherter Charakter ist ungültig.')
            return
        with nm.lock:
            if addr in nm.clients:
                nm.clients[addr]['character'] = saved_char
                nm.clients[addr]['approved'] = True
        self.add_player_to_list(addr, saved_char)
        summary = 'Dein bestätigter Charakterstand wurde vom DM übernommen.'
        nm.send_message(addr, 'CHAR_DATA', saved)
        nm.send_message(addr, 'SUMMARY', summary)

    # ---------- navigation ----------
    def start_game(self):
        if getattr(self.network_manager, 'mode', 'dm') != 'dm' or not getattr(self.network_manager, 'running', True):
            self.app._popup('Verbindung vorbereiten', 'Bitte zuerst die DM-Verbindungseinrichtung abschließen.')
            return
        with self.network_manager.lock:
            pending = any(not c.get('approved', True) for c in self.network_manager.clients.values())
        if pending:
            self.app._popup('Freigabe offen', 'Bitte zuerst die neuen Charaktere zulassen oder ablehnen.')
            return
        self.is_starting_game = True
        self.manager.current = 'dm_main'

    def go_back(self):
        self.app.go_back_screen()

    # ---------- background ----------
    def change_background(self):
        content = FileChooserListView(path=os.path.expanduser('~'), filters=['*.png', '*.jpg', '*.jpeg'])
        content.bind(on_submit=self._set_background)
        self.popup = Popup(title='Hintergrundbild wählen', content=content, size_hint=(0.95, 0.9))
        self.popup.open()

    def _set_background(self, instance, value, *args):
        if value:
            selected_file = value[0]
            try:
                settings = load_settings()
                settings['lobby_background_path'] = selected_file
                save_settings(settings)
                apply_background(self)
            except Exception as e:
                _record('lobby_background_apply', e)
            threading.Thread(target=self._send_background, args=(selected_file,), daemon=True).start()
        if self.popup:
            self.popup.dismiss()
            self.popup = None

    def _send_background(self, path):
        nm = self.network_manager
        try:
            if os.path.getsize(path) > MAX_BACKGROUND_BYTES:
                raise ValueError('Bild ist größer als 8 MiB und wird nicht an Spieler gesendet.')
            with open(path, 'rb') as f:
                data = f.read(MAX_BACKGROUND_BYTES + 1)
            if len(data) > MAX_BACKGROUND_BYTES:
                raise ValueError('Bild ist größer als 8 MiB und wird nicht an Spieler gesendet.')
            nm.broadcast_message('BACKGROUND_START', {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            for i in range(0, len(data), BACKGROUND_CHUNK):
                nm.broadcast_message('BACKGROUND_CHUNK', data[i:i + BACKGROUND_CHUNK].hex())
            nm.broadcast_message('BACKGROUND_END', {})
        except Exception as e:
            _record('background_broadcast', e)
            Clock.schedule_once(partial(self._background_error, str(e)))

    def _background_error(self, message, dt):
        lbl = Label(text=message, halign='center')
        lbl.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)))
        create_styled_popup(title='Hinweis', content=lbl, size_hint=(0.8, 0.4)).open()

    def on_leave(self, *args):
        self._enter_gen += 1
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None

        if not self.is_starting_game and not getattr(self, '_session_running', False):
            self.network_manager.shutdown()
            self.app.loaded_session_data = None
            if hasattr(self.app, 'prepared_session_data'):
                self.app.prepared_session_data = None

    def confirm_session_name(self):
        session_name = self.ids.session_name_input.text.strip() or DEFAULT_NAME
        if self.network_manager.mode == 'dm':
            self.network_manager.update_service_name(session_name)
    def _broadcast_lobby_players(self):
        nm = self.network_manager
        with nm.lock:
            names = [c['character'].name for c in nm.clients.values() if c.get('character') is not None]
        nm.broadcast_message('GAME_STATE_UPDATE', {'players': sorted(names)})

    def show_join_qr(self):
        from ui.join_dialog import show_join_dialog
        show_join_dialog(self.network_manager)

    def show_network_help(self):
        from ui.network_help import show_network_help
        show_network_help(self.network_manager)
