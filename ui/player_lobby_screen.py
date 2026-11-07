import threading
from functools import partial

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from zeroconf import ServiceBrowser, Zeroconf

from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup
from utils.storage import CharacterRepository
from utils.pairing import normalize_code, valid_code16hex
from utils.network_setup import lan_address, MAX_ADDRESSES, connection_help
from core.network_manager import PROTOCOL

try:
    from utils import diagnostics
except Exception:
    diagnostics = None

SERVICE_TYPE = '_dndgame._tcp.local.'


def _record(event, error):
    try:
        if diagnostics:
            diagnostics.record_error(event, error)
    except Exception:
        pass


def parse_endpoint(text):
    """Parses 'host:port' or '[v6]:port'. Returns (host, port) or None if empty."""
    text = (text or '').strip()
    if not text:
        return None
    if text.startswith('['):
        host, _, rest = text[1:].partition(']')
        port = rest[1:] if rest.startswith(':') else ''
    elif text.count(':') == 1:
        host, _, port = text.partition(':')
    else:
        raise ValueError('Format: IP:Port')
    host = host.strip()
    port = port.strip()
    if not host or not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError('Format: IP:Port')
    return host, int(port)


def build_entry(info):
    """Keep all advertised LAN addresses, including legacy 0.5.7 advertisements."""
    props = info.properties or {}
    if props.get(b'proto') not in (b'3', str(PROTOCOL).encode('ascii')):
        return None
    ips = []
    for a in info.parsed_addresses():
        try:
            a = lan_address(a)
        except ValueError:
            continue
        if a not in ips:
            ips.append(a)
    ips = ips[:MAX_ADDRESSES]
    if not ips or not info.port:
        return None
    display = props.get(b'name', b'DM').decode('utf-8', 'replace')
    return {'display': display, 'addresses': ips, 'port': int(info.port)}


class DMListener:
    def __init__(self, screen, gen):
        self.screen = screen
        self.gen = gen

    def add_service(self, zc, type_, name):
        self._resolve(zc, type_, name)

    def update_service(self, zc, type_, name):
        self._resolve(zc, type_, name)

    def remove_service(self, zc, type_, name):
        Clock.schedule_once(partial(self._remove, name))

    def _remove(self, name, dt):
        self.screen.remove_dm_service(self.gen, name)

    def _resolve(self, zc, type_, name):
        threading.Thread(target=self._work, args=(zc, type_, name), daemon=True).start()

    def _work(self, zc, type_, name):
        if self.gen != self.screen._gen:
            return
        try:
            info = zc.get_service_info(type_, name, 3000)
            entry = build_entry(info) if info else None
        except Exception as e:
            _record('discovery_resolve', e)
            return
        Clock.schedule_once(partial(self._upsert, name, entry))

    def _upsert(self, name, entry, dt):
        self.screen.upsert_dm_service(self.gen, name, entry)


class PlayerLobbyScreen(Screen):
    """Screen for the player lobby."""
    def __init__(self, **kwargs):
        super(PlayerLobbyScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.network_manager = self.app.network_manager
        self.zeroconf = None
        self.browser = None
        self.entries = {}
        self.selected_key = None
        self.selected_char_file = None
        self.char_popup = None
        self._gen = 0
        self._lock = threading.Lock()
        self._connect_token = 0
        self._connecting = False
        self._qr_candidates = None

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        self.ids.selected_char_label.text = 'Kein Charakter ausgewählt'
        self.ids.status_label.text = ''
        self.ids.connect_button.disabled = False
        self.selected_char_file = None
        self.selected_key = None
        self._connecting = False

    def on_enter(self, *args):
        self.start_discovery()

    # ---------- discovery ----------
    def start_discovery(self):
        self.stop_discovery()
        self.entries = {}
        self._rebuild_list()
        threading.Thread(target=self._start_zeroconf, args=(self._gen,), daemon=True).start()

    def _start_zeroconf(self, gen):
        zc = None
        try:
            zc = Zeroconf()
            with self._lock:
                if gen != self._gen:
                    stale = True
                else:
                    stale = False
                    self.zeroconf = zc
                    self.browser = ServiceBrowser(zc, SERVICE_TYPE, DMListener(self, gen))
            if stale:
                zc.close()
        except Exception as e:
            _record('discovery_start', e)
            try:
                if zc:
                    zc.close()
            except Exception:
                pass
            Clock.schedule_once(partial(self._discovery_failed, gen))

    def _discovery_failed(self, gen, dt):
        if gen == self._gen:
            self.show_error_popup('Netzwerkfehler', 'Konnte keine Spiele im lokalen Netzwerk suchen. Manuelle Eingabe ist möglich.')

    def stop_discovery(self):
        with self._lock:
            self._gen += 1
            zc, browser = self.zeroconf, self.browser
            self.zeroconf = None
            self.browser = None
        if zc or browser:
            threading.Thread(target=self._close_zeroconf, args=(zc, browser), daemon=True).start()

    @staticmethod
    def _close_zeroconf(zc, browser):
        try:
            if browser:
                browser.cancel()
        except Exception as e:
            _record('discovery_cancel', e)
        try:
            if zc:
                zc.close()
        except Exception as e:
            _record('discovery_close', e)

    def upsert_dm_service(self, gen, name, entry):
        if gen != self._gen:
            return
        if entry is None:
            self.entries.pop(name, None)
        else:
            self.entries[name] = entry
        self._rebuild_list()

    def remove_dm_service(self, gen, name):
        if gen != self._gen:
            return
        if self.entries.pop(name, None) is not None:
            if self.selected_key == name:
                self.selected_key = None
            self._rebuild_list()

    def _rebuild_list(self):
        box = self.ids.dm_list
        box.clear_widgets()
        for key in sorted(self.entries):
            e = self.entries[key]
            extra = ' (+%d)' % (len(e['addresses']) - 1) if len(e['addresses']) > 1 else ''
            btn = Button(text='%s - %s:%d%s' % (e['display'], e['addresses'][0], e['port'], extra),
                         size_hint_y=None, height=dp(48))
            if key == self.selected_key:
                btn.background_color = (0.2, 0.7, 0.3, 1)
            btn.bind(on_release=partial(self._on_dm_pressed, key))
            box.add_widget(btn)

    def _on_dm_pressed(self, key, *args):
        self.select_dm(key)

    def select_dm(self, key):
        self.selected_key = key
        self._qr_candidates = None
        self.ids.manual_input.text = ''
        self._rebuild_list()

    # ---------- character selection ----------
    def show_char_selection_popup(self):
        content = BoxLayout(orientation='vertical', spacing=dp(10))
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        try:
            files = list(CharacterRepository().list_files())
        except Exception as e:
            _record('list_characters', e)
            files = []
        for filename in files:
            try:
                label = CharacterRepository().load(filename).name
            except ValueError:
                label = filename + ' (zuerst im Charaktermenü übernehmen)'
            btn = Button(text=label, size_hint_y=None, height=dp(48))
            btn.bind(on_release=partial(self._on_char_pressed, filename))
            grid.add_widget(btn)
        if not files:
            grid.add_widget(Label(text='Keine Charaktere gefunden', size_hint_y=None, height=dp(48)))
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        scroll.add_widget(grid)
        content.add_widget(scroll)
        self.char_popup = create_styled_popup(title='Charakter auswählen', content=content, size_hint=(0.9, 0.8))
        self.char_popup.open()

    def _on_char_pressed(self, filename, *args):
        self.select_character(filename)

    def select_character(self, filename):
        self.selected_char_file = filename
        try:
            label = CharacterRepository().load(filename).name
        except ValueError:
            label = filename
        self.ids.selected_char_label.text = 'Ausgewählt: %s' % label
        if self.char_popup:
            self.char_popup.dismiss()
            self.char_popup = None

    # ---------- connect ----------
    def connect_to_dm(self):
        if self._connecting:
            return
        if not self.selected_char_file:
            self.show_error_popup('Fehler', 'Bitte wähle zuerst einen Charakter aus.')
            return
        try:
            manual = parse_endpoint(self.ids.manual_input.text)
        except ValueError as e:
            self.show_error_popup('Fehler', str(e))
            return
        if manual:
            ip, port = manual
            addresses = [ip]
            qr = getattr(self, '_qr_candidates', None)
            if qr and (ip, port) == (qr[0][0], qr[1]):
                addresses = qr[0]
        elif self.selected_key in self.entries:
            e = self.entries[self.selected_key]
            addresses, port = e['addresses'], e['port']
        else:
            self.show_error_popup('Fehler', 'Bitte wähle einen DM aus oder gib IP:Port ein.')
            return
        code = normalize_code(self.ids.join_code_input.text)
        if not valid_code16hex(code):
            self.show_error_popup('Fehler', 'Gib den 16-stelligen Beitrittscode vom DM ein (0–9 und A–F).')
            return

        self._connecting = True
        self._connect_token += 1
        token = self._connect_token
        self.ids.connect_button.disabled = True
        self.ids.status_label.text = 'Verbinde...'
        threading.Thread(target=self._connect_worker,
                         args=(token, self.selected_char_file, addresses, port, code),
                         daemon=True).start()

    def _connect_worker(self, token, filename, addresses, port, code):
        character = None
        ok = False
        msg = ''
        try:
            character = CharacterRepository().load(filename)
            if character is None:
                raise ValueError('Charakter konnte nicht geladen werden.')
            def progress(index, total):
                Clock.schedule_once(partial(self._connect_progress, token, index, total))
            ok, msg = self.network_manager.connect_to_candidates(addresses, port, character, join_code=code,
                         cancelled=lambda: token != self._connect_token, progress=progress)
        except Exception as e:
            ok, msg = False, str(e)
            _record('connect', e)
        Clock.schedule_once(partial(self._finish_connect, token, ok, msg, character))

    def _connect_progress(self, token, index, total, dt):
        if token == self._connect_token and self._connecting:
            self.ids.status_label.text = f'Verbindung wird geprüft · Adresse {index} von {total} …'

    def _finish_connect(self, token, ok, msg, character, dt):
        current = token == self._connect_token
        if current:
            self._connecting = False
            self.ids.connect_button.disabled = False
            self.ids.status_label.text = ''
        on_screen = self.manager is not None and self.manager.current == self.name
        if not current or not on_screen:
            return
        if ok:
            self.app.character = character
            self.manager.get_screen('player_map').reset_session()
            self.manager.current = 'player_waiting'
        else:
            self.show_error_popup('Verbindung zum DM', connection_help(msg))

    def on_leave(self, *args):
        self._connect_token += 1  # invalidate retries before shutting down the current socket
        if self._connecting:
            self.network_manager.shutdown()
        self._connecting = False
        self.stop_discovery()

    def scan_join_qr(self):
        if self._connecting:
            return
        from utils.android_qr import start_scan
        token = self._connect_token
        def scanned(text, error=None):
            if token != self._connect_token or self.manager.current != self.name:
                return
            if error:
                self.show_error_popup('QR-Code', error)
            elif text:
                self.accept_join_qr(text)
        start_scan(scanned)

    def accept_join_qr(self, text):
        from utils.join_qr import parse_join_candidates
        try:
            hosts, port, code = parse_join_candidates(text)
        except ValueError as error:
            self.show_error_popup('QR-Code ungültig', str(error))
            return False
        self._qr_candidates = (hosts, port)
        self.ids.manual_input.text = f'{hosts[0]}:{port}'
        self.ids.join_code_input.text = code
        self.selected_key = None
        self.ids.status_label.text = f'QR-Code übernommen ({len(hosts)} Adressen). Charakter wählen und Verbinden drücken.'
        return True

    def show_error_popup(self, title, message):
        box = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(8))
        scroll = ScrollView(do_scroll_x=False)
        lbl = Label(text=str(message), halign='left', size_hint_y=None)
        lbl.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)),
                 texture_size=lambda w, v: setattr(w, 'height', v[1] + dp(12)))
        scroll.add_widget(lbl)
        box.add_widget(scroll)
        close = Button(text='Zurück', size_hint_y=None, height=dp(48))
        box.add_widget(close)
        popup = create_styled_popup(title=title, content=box, size_hint=(0.92, 0.8))
        close.bind(on_release=popup.dismiss)
        popup.open()
