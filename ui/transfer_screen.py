from kivy.metrics import dp
import os
import platform
import socket
import threading

from kivy.clock import Clock
from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen

from core import file_transfer as ft
from utils import storage
from utils.helpers import apply_background, apply_styles_to_widget, get_local_ip
from utils.paths import get_user_saves_dir

SERVICE_TYPE = '_dndchar._tcp.local.'


class FileCheckBox(BoxLayout):
    text = StringProperty('')
    active = BooleanProperty(False)

    def __init__(self, **kwargs):
        self.callback = kwargs.pop('on_active', None)
        super(FileCheckBox, self).__init__(**kwargs)

    def on_checkbox_active(self, checkbox, value):
        if self.callback:
            self.callback(self.text, value)


class TransferScreen(Screen):
    """Screen for sending and receiving validated game files over the LAN."""
    status_message = StringProperty('Wähle eine Aktion')
    files_for_transfer = ListProperty([])
    discovered_services = ListProperty([])

    DATA_TYPE_INFO = {
        'characters': {'folder': 'characters', 'ext': '.char', 'name': 'Charaktere'},
        'maps': {'folder': 'maps', 'ext': '.json', 'name': 'Karten'},
        'enemies': {'folder': 'enemies', 'ext': '.enemies', 'name': 'Gegnerlisten'},
        'sessions': {'folder': 'sessions', 'ext': '.json', 'name': 'Sitzungen'},
    }

    def __init__(self, **kwargs):
        super(TransferScreen, self).__init__(**kwargs)
        self.selected_files = []
        self.current_transfer_type = None
        self.browser = None
        self._listener = None
        self._zc = None
        self._zc_lock = threading.Lock()
        self.service_info = None
        self._stop = None
        self._worker = None

    # ---- helpers -------------------------------------------------
    def _post(self, fn, *args):
        Clock.schedule_once(lambda dt: fn(*args), 0)

    def _set_status(self, msg):
        self.status_message = msg

    def _dir(self, kind):
        path = str(get_user_saves_dir(self.DATA_TYPE_INFO[kind]['folder']))
        os.makedirs(path, exist_ok=True)
        return path

    def _get_zeroconf(self):
        with self._zc_lock:
            if self._zc is None:
                from zeroconf import Zeroconf
                self._zc = Zeroconf()
            return self._zc

    def _close_zeroconf(self):
        with self._zc_lock:
            zc, self._zc = self._zc, None
        if zc is not None:
            try:
                zc.close()
            except Exception:
                pass

    def _stop_transfer(self):
        stop, worker = self._stop, self._worker
        self._stop = None
        self._worker = None
        if stop is not None:
            stop.set()
        if worker is not None and worker is not threading.current_thread():
            worker.join(1.5)
        self._clear_code()

    def _clear_code(self):
        label = self.ids.get('code_label')
        if label is not None:
            label.text = ''

    # ---- lifecycle -----------------------------------------------
    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def on_leave(self, *args):
        self._stop_transfer()
        self.stop_service_browser()
        self._close_zeroconf()

    def cleanup_transfer(self):
        self.on_leave()

    # ---- discovery list ------------------------------------------
    def _update_service_list_ui(self):
        widget = self.ids.service_list
        widget.clear_widgets()
        for info in self.discovered_services:
            btn = Button(text=info['name'], size_hint_y=None, height=dp(80), font_size='20sp')
            btn.bind(on_press=lambda x, info=info: self.connect_to_sender(info))
            widget.add_widget(btn)
        self.status_message = f'{len(self.discovered_services)} Sender gefunden.'

    def _add_service(self, info):
        others = [s for s in self.discovered_services if s['name'] != info['name']]
        self.discovered_services = others + [info]
        self._update_service_list_ui()

    def _remove_service(self, name):
        self.discovered_services = [s for s in self.discovered_services if s['name'] != name]
        self._update_service_list_ui()

    def start_service_browser(self):
        if self.browser is not None:
            return
        self.discovered_services = []
        try:
            from zeroconf import ServiceBrowser
            zc = self._get_zeroconf()
            self._listener = ServiceListener(self)
            self.browser = ServiceBrowser(zc, SERVICE_TYPE, self._listener)
        except Exception:
            self.browser = None
            self._listener = None
            self.status_message = 'Automatische Suche nicht verfügbar. Bitte Host:Port und Code manuell eingeben.'

    def stop_service_browser(self):
        if self._listener is not None:
            self._listener.active = False
            self._listener = None
        if self.browser is not None:
            try:
                self.browser.cancel()
            except Exception:
                pass
            self.browser = None

    # ---- sending -------------------------------------------------
    def list_files_for_transfer(self, data_type):
        self.current_transfer_type = data_type
        self.selected_files = []
        info = self.DATA_TYPE_INFO.get(data_type)
        if not info:
            self.status_message = f'Unbekannter Datentyp: {data_type}'
            self.files_for_transfer = []
            return
        try:
            folder = self._dir(data_type)
            names = sorted(f for f in os.listdir(folder)
                           if f.endswith(info['ext']) and os.path.isfile(os.path.join(folder, f)))
        except OSError:
            self.files_for_transfer = []
            self.status_message = 'Ordner konnte nicht gelesen werden.'
            return
        self.files_for_transfer = names
        if names:
            self.status_message = f"Wähle {info['name']} zum Senden."
        else:
            self.status_message = f"Keine {info['name']} gefunden."

    def toggle_file_selection(self, file_path, is_active):
        if is_active:
            if file_path not in self.selected_files:
                self.selected_files.append(file_path)
        elif file_path in self.selected_files:
            self.selected_files.remove(file_path)

    def _snapshot(self, kind, names):
        """Read and validate selected originals on the UI thread before any worker starts."""
        folder = self._dir(kind)
        items = []
        if not 1 <= len(names) <= ft.MAX_FILES:
            raise ft.PayloadError('count')
        total = 0
        for name in names:
            path = storage.safe_save_path(folder, name)
            if os.path.getsize(path) > ft.MAX_FILE:
                raise ft.PayloadError('too large')
            with open(path, 'rb') as f:
                data = f.read(ft.MAX_FILE + 1)
            total += len(data)
            if len(data) > ft.MAX_FILE or total > ft.MAX_TOTAL:
                raise ft.PayloadError('total')
            items.append((kind, data))
        return ft.prepare_payloads(items, storage)

    def send_files(self):
        kind = self.current_transfer_type
        if not self.selected_files or kind not in self.DATA_TYPE_INFO:
            self.status_message = 'Keine Dateien zum Senden ausgewählt.'
            return
        try:
            payloads = self._snapshot(kind, list(self.selected_files))
        except ft.TransferError as e:
            self.status_message = ft.friendly_message(e)
            return
        except Exception:
            self.status_message = 'Dateien konnten nicht gelesen oder geprüft werden.'
            return
        self._stop_transfer()
        code = ft.generate_code()
        stop = threading.Event()
        self._stop = stop
        self.status_message = 'Starte Server... Warte auf Verbindung.'
        t = threading.Thread(target=self._start_server, args=(payloads, code, stop, kind), daemon=True)
        self._worker = t
        t.start()

    def _on_listening(self, stop, code, port):
        if self._stop is not stop:
            return
        try:
            ip = get_local_ip()
        except Exception:
            ip = '?'
        label = self.ids.get('code_label')
        if label is not None:
            label.text = f'Code: {code}'
        self.status_message = f'Bereit auf {ip}:{port}. Code {code} dem Empfänger mitteilen.'

    def _advertise(self, port, kind, stop):
        """Worker thread: best-effort mDNS announcement. The code is never advertised."""
        try:
            from zeroconf import ServiceInfo
            if stop.is_set():
                return None
            zc = self._get_zeroconf()
            host = (platform.node() or 'dnd').replace('.', '-')[:40]
            info = ServiceInfo(SERVICE_TYPE, f'{host}.{SERVICE_TYPE}',
                               addresses=[socket.inet_aton(get_local_ip())], port=port,
                               properties={b'proto': b'3', b'type': kind.encode('ascii')})
            zc.register_service(info, allow_name_change=True)
            return zc, info
        except Exception:
            return None

    def _unadvertise(self, advertised):
        if advertised is not None:
            zc, info = advertised
            try:
                zc.unregister_service(info)
            except Exception:
                pass

    def _start_server(self, payloads, code, stop, kind):
        """Worker: no Kivy access except Clock.schedule_once."""
        advertised = None
        def ready(port):
            nonlocal advertised
            advertised = self._advertise(port, kind, stop)
            self._post(self._on_listening, stop, code, port)
        try:
            ft.serve_once(payloads, code, stop, on_ready=ready)
            msg = f'{len(payloads)} Datei(en) erfolgreich gesendet.'
        except Exception as e:
            msg = ft.friendly_message(e)
        self._unadvertise(advertised)
        self._post(self._on_worker_done, stop, msg)

    def _on_worker_done(self, stop, msg):
        if self._stop is stop:
            self._stop = None
            self._worker = None
            self._clear_code()
            self.status_message = msg

    # ---- receiving -----------------------------------------------
    def _begin_receive(self, host, port):
        code = ft.pairing.normalize_code(self.ids.code_input.text)
        if not ft.valid_code(code):
            self.status_message = 'Bitte den 16-stelligen Code des Senders eingeben.'
            return
        self._stop_transfer()
        stop = threading.Event()
        self._stop = stop
        self.stop_service_browser()
        self.status_message = f'Verbinde mit {host}...'
        t = threading.Thread(target=self._start_client, args=(host, port, code, stop), daemon=True)
        self._worker = t
        t.start()

    def connect_to_sender(self, service_info):
        try:
            host, port = service_info['host'], int(service_info['port'])
        except (KeyError, TypeError, ValueError):
            self.status_message = 'Ungültiger Sender.'
            return
        self._begin_receive(host, port)

    def connect_manual(self):
        try:
            host, port = ft.parse_endpoint(self.ids.host_input.text)
        except ValueError:
            self.status_message = 'Ungültige Adresse. Format: host:port'
            return
        self._begin_receive(host, port)

    def _folder_for(self, kind):
        return self._dir(kind)

    def _start_client(self, host, port, code, stop):
        """Worker: receiver-supplied names are never used; files get local UUID names."""
        try:
            paths = ft.connect_and_receive(host, port, code, self._folder_for, stop, storage)
            msg = f'{len(paths)} Datei(en) empfangen und gespeichert.'
        except Exception as e:
            msg = ft.friendly_message(e)
        self._post(self._on_worker_done, stop, msg)

    # ---- navigation ----------------------------------------------
    def go_to_send_view_with_type(self, data_type):
        self.list_files_for_transfer(data_type)
        widget = self.ids.file_list
        widget.clear_widgets()
        for f in self.files_for_transfer:
            widget.add_widget(FileCheckBox(text=f, on_active=self.toggle_file_selection))
        self.ids.transfer_sm.current = 'send'

    def go_to_receive_view(self):
        self.status_message = 'Suche nach Sendern...'
        self.ids.transfer_sm.current = 'receive'
        self.start_service_browser()

    def back_to_main_transfer(self):
        self._stop_transfer()
        self.stop_service_browser()
        self.ids.transfer_sm.current = 'main'
        self.status_message = 'Wähle eine Aktion'


class ServiceListener:
    def __init__(self, screen):
        self.screen = screen
        self.active = True

    def _resolve(self, zeroconf, type_, name):
        try:
            info = zeroconf.get_service_info(type_, name, timeout=3000)
            if not info or not self.active or info.properties.get(b'proto') != b'3':
                return
            hosts = info.parsed_addresses() if hasattr(info, 'parsed_addresses') else [socket.inet_ntoa(info.addresses[0])]
            if not hosts:
                return
            entry = {'name': name.split('.')[0], 'key': name, 'host': hosts[0], 'port': int(info.port)}
        except Exception:
            return
        Clock.schedule_once(lambda dt: self.screen._add_service(entry) if self.active else None, 0)

    def _spawn(self, zeroconf, type_, name):
        if self.active:
            threading.Thread(target=self._resolve, args=(zeroconf, type_, name), daemon=True).start()

    def add_service(self, zeroconf, type, name):
        self._spawn(zeroconf, type, name)

    def update_service(self, zeroconf, type, name):
        self._spawn(zeroconf, type, name)

    def remove_service(self, zeroconf, type, name):
        short = name.split('.')[0]
        Clock.schedule_once(lambda dt: self.screen._remove_service(short) if self.active else None, 0)
