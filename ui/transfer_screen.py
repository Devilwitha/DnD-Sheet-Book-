from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, ListProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.clock import Clock
from utils.helpers import apply_background, apply_styles_to_widget, get_local_ip
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
    char_files = ListProperty([])
    discovered_services = ListProperty([])

    def __init__(self, **kwargs):
        super(TransferScreen, self).__init__(**kwargs)
        self.selected_files = []
        self.zeroconf = Zeroconf()
        self.browser = None
        self.service_info = None

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

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
        # Find service by name and remove
        service_to_remove = next((s for s in self.discovered_services if s.name == name), None)
        if service_to_remove:
            self.discovered_services.remove(service_to_remove)
        self._update_service_list_ui()

    def list_char_files(self):
        self.char_files = [f for f in os.listdir('.') if f.endswith('.char')]
        if not self.char_files:
            self.status_message = "Keine .char-Dateien gefunden."

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

        # Register Zeroconf service
        service_name = f"{platform.node()}._dndchar._tcp.local."
        local_ip = get_local_ip()
        self.service_info = ServiceInfo(
            "_dndchar._tcp.local.",
            service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties={'user': platform.node()}
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
                    # Send number of files
                    num_files = len(self.selected_files)
                    conn.sendall(str(num_files).encode('utf-8'))
                    time.sleep(0.1)

                    for file_path in self.selected_files:
                        conn.sendall(file_path.encode('utf-8'))
                        time.sleep(0.1)
                        with open(file_path, 'rb') as f:
                            data = f.read()
                            conn.sendall(str(len(data)).encode('utf-8'))
                            time.sleep(0.1)
                            conn.sendall(data)
                    self.status_message = f"{num_files} Dateien erfolgreich gesendet."
        finally:
            self.zeroconf.unregister_service(self.service_info)
            self.service_info = None
            self.status_message = "Übertragung beendet."


    def connect_to_sender(self, service_info):
        host = socket.inet_ntoa(service_info.addresses[0])
        port = service_info.port
        self.status_message = f"Verbinde mit {service_info.name}..."
        threading.Thread(target=self._start_client, args=(host, port)).start()
        self.stop_service_browser()

    def _start_client(self, host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((host, port))
                self.status_message = f"Verbunden mit Server {host}"

                # Receive number of files
                num_files_str = s.recv(1024).decode('utf-8')
                num_files = int(num_files_str)

                for _ in range(num_files):
                    # Receive filename
                    filename = s.recv(1024).decode('utf-8')

                    # Receive file size
                    filesize_str = s.recv(1024).decode('utf-8')
                    filesize = int(filesize_str)

                    # Receive file content
                    data = b''
                    while len(data) < filesize:
                        packet = s.recv(4096)
                        if not packet:
                            break
                        data += packet

                    with open(filename, 'wb') as f:
                        f.write(data)
                    self.status_message = f"Datei {filename} empfangen."

            except Exception as e:
                self.status_message = f"Fehler beim Empfangen: {e}"

    def go_to_send_view(self):
        self.list_char_files()
        # Populate the file list
        file_list_widget = self.ids.file_list
        file_list_widget.clear_widgets()
        for f in self.char_files:
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
