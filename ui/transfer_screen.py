from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, ListProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.clock import Clock
from utils.helpers import apply_background, apply_styles_to_widget, get_local_ip, get_user_saves_dir
import os
import socket
import threading
import time
from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo
import platform

class FileCheckBox(BoxLayout):
    text = StringProperty('')
    active = BooleanProperty(False)

    def __init__(self, **kwargs):
        super(FileCheckBox, self).__init__(**kwargs)
        self.on_active = kwargs.get('on_active')

    def on_checkbox_active(self, checkbox, value):
        if self.on_active:
            self.on_active(self.text, value)

class TransferScreen(Screen):
    """Screen for sending and receiving character files."""
    status_message = StringProperty("Wähle eine Aktion")
    files_for_transfer = ListProperty([])
    discovered_services = ListProperty([])

    DATA_TYPE_INFO = {
        'characters': {'dir': get_user_saves_dir('characters'), 'ext': '.char', 'name': 'Charaktere'},
        'maps': {'dir': get_user_saves_dir('maps'), 'ext': '.json', 'name': 'Karten'},
        'enemies': {'dir': get_user_saves_dir('enemies'), 'ext': '.enemies', 'name': 'Gegnerlisten'},
        'sessions': {'dir': get_user_saves_dir('sessions'), 'ext': '.session', 'name': 'Sitzungen'},
        'logs': {'dir': get_user_saves_dir('logs'), 'ext': '.log', 'name': 'Logs'},
    }

    def __init__(self, **kwargs):
        super(TransferScreen, self).__init__(**kwargs)
        self.selected_files = []
        self.zeroconf = Zeroconf()
        self.browser = None
        self.service_info = None
        self.current_transfer_type = None
        for info in self.DATA_TYPE_INFO.values():
            os.makedirs(info['dir'], exist_ok=True)

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        # Set the sender name to the device's hostname by default
        self.ids.sender_name_input.text = platform.node() or "Unbekanntes Gerät"

    def _update_service_list_ui(self):
        service_list_widget = self.ids.service_list
        service_list_widget.clear_widgets()
        for info in self.discovered_services:
            btn = Button(text=info.name, size_hint_y=None, height=80, font_size='20sp')
            btn.bind(on_press=lambda x, info=info: self.connect_to_sender(info))
            service_list_widget.add_widget(btn)
        self.status_message = f"{len(self.discovered_services)} Sender gefunden."

    def _add_service(self, info):
        if info not in self.discovered_services:
            self.discovered_services.append(info)
        self._update_service_list_ui()

    def _remove_service(self, name):
        service_to_remove = next((s for s in self.discovered_services if s.name == name), None)
        if service_to_remove:
            self.discovered_services.remove(service_to_remove)
        self._update_service_list_ui()

    def list_files_for_transfer(self, data_type):
        self.current_transfer_type = data_type
        info = self.DATA_TYPE_INFO.get(data_type)
        if not info:
            self.status_message = f"Unbekannter Datentyp: {data_type}"
            self.files_for_transfer = []
            return

        try:
            file_list = [f for f in os.listdir(info['dir']) if f.endswith(info['ext'])]
            self.files_for_transfer = file_list
            if not self.files_for_transfer:
                self.status_message = f"Keine {info['name']} gefunden."
            else:
                self.status_message = f"Wähle {info['name']} zum Senden."
        except FileNotFoundError:
            self.files_for_transfer = []
            self.status_message = f"Ordner nicht gefunden: {info['dir']}"

    def toggle_file_selection(self, file_path, is_active):
        if is_active:
            if file_path not in self.selected_files:
                self.selected_files.append(file_path)
        else:
            if file_path in self.selected_files:
                self.selected_files.remove(file_path)

    def send_files(self):
        if not self.selected_files:
            self.status_message = "Keine Dateien zum Senden ausgewählt."
            return
        self.status_message = "Starte Server... Warte auf Verbindung."
        threading.Thread(target=self._start_server).start()

    def _start_server(self):
        host = '0.0.0.0'
        port = 65432
        info = self.DATA_TYPE_INFO.get(self.current_transfer_type)
        if not info:
            self.status_message = "Fehler: Transfertyp nicht gesetzt."
            return

        custom_name = self.ids.sender_name_input.text.strip()
        if not custom_name:
            custom_name = platform.node() or "Unbenannter Sender"

        service_name = f"{custom_name}._dndchar._tcp.local."
        local_ip = get_local_ip()
        properties = {
            b'user': custom_name.encode('utf-8'),
            b'type': self.current_transfer_type.encode('utf-8')
        }
        self.service_info = ServiceInfo(
            "_dndchar._tcp.local.",
            service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties=properties,
        )
        self.zeroconf.register_service(self.service_info, allow_name_change=True)
        self.status_message = f"Server gestartet, sichtbar als '{platform.node()}'"

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                s.listen()
                conn, addr = s.accept()
                with conn:
                    self.status_message = f"Verbunden mit {addr}"
                    num_files = len(self.selected_files)
                    conn.sendall(str(num_files).encode('utf-8'))
                    time.sleep(0.1)

                    for file_name in self.selected_files:
                        conn.sendall(file_name.encode('utf-8'))
                        time.sleep(0.1)
                        file_path = os.path.join(info['dir'], file_name)
                        with open(file_path, 'rb') as f:
                            data = f.read()
                            conn.sendall(str(len(data)).encode('utf-8'))
                            time.sleep(0.1)
                            conn.sendall(data)
                    self.status_message = f"{num_files} Dateien erfolgreich gesendet."
        finally:
            if self.service_info:
                self.zeroconf.unregister_service(self.service_info)
                self.service_info = None
            self.status_message = "Übertragung beendet."

    def connect_to_sender(self, service_info):
        host = socket.inet_ntoa(service_info.addresses[0])
        port = service_info.port
        data_type = service_info.properties.get(b'type', b'characters').decode('utf-8')
        self.status_message = f"Verbinde mit {service_info.name}..."
        threading.Thread(target=self._start_client, args=(host, port, data_type)).start()
        self.stop_service_browser()

    def _start_client(self, host, port, data_type):
        info = self.DATA_TYPE_INFO.get(data_type)
        if not info:
            self.status_message = f"Fehler: Unbekannter Datentyp '{data_type}' vom Sender."
            return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((host, port))
                self.status_message = f"Verbunden mit Server {host}"
                num_files_str = s.recv(1024).decode('utf-8')
                num_files = int(num_files_str)

                for _ in range(num_files):
                    filename = s.recv(1024).decode('utf-8')
                    filesize_str = s.recv(1024).decode('utf-8')
                    filesize = int(filesize_str)
                    data = b''
                    while len(data) < filesize:
                        packet = s.recv(4096)
                        if not packet: break
                        data += packet

                    save_dir = info['dir']
                    os.makedirs(save_dir, exist_ok=True)
                    file_path = os.path.join(save_dir, filename)
                    with open(file_path, 'wb') as f:
                        f.write(data)
                    self.status_message = f"Datei {filename} in {save_dir} empfangen."

            except Exception as e:
                self.status_message = f"Fehler beim Empfangen: {e}"

    def go_to_send_view_with_type(self, data_type):
        self.list_files_for_transfer(data_type)
        file_list_widget = self.ids.file_list
        file_list_widget.clear_widgets()
        for f in self.files_for_transfer:
            cb = FileCheckBox(text=f, on_active=self.toggle_file_selection)
            file_list_widget.add_widget(cb)
        self.ids.transfer_sm.current = 'send'

    def go_to_receive_view(self):
        self.status_message = "Suche nach Sendern..."
        self.ids.transfer_sm.current = 'receive'
        self.start_service_browser()

    def back_to_main_transfer(self):
        self.stop_service_browser()
        self.ids.transfer_sm.current = 'main'
        self.status_message = "Wähle eine Aktion"

    def start_service_browser(self):
        if self.browser is None:
            self.discovered_services.clear()
            listener = ServiceListener(self)
            self.browser = ServiceBrowser(self.zeroconf, "_dndchar._tcp.local.", listener)

    def stop_service_browser(self):
        if self.browser:
            self.browser.cancel()
            self.browser = None

class ServiceListener:
    def __init__(self, screen):
        self.screen = screen

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            Clock.schedule_once(lambda dt: self.screen._add_service(info))

    def remove_service(self, zeroconf, type, name):
        # Service has been removed, so info may not be available. Act on name.
        Clock.schedule_once(lambda dt: self.screen._remove_service(name))

    def update_service(self, zeroconf, type, name):
        # For now, we don't need to handle updates
        pass
