from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, ListProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from utils.helpers import apply_background, apply_styles_to_widget
import os
import socket
import threading
import time

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

    def __init__(self, **kwargs):
        super(TransferScreen, self).__init__(**kwargs)
        self.selected_files = []

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

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
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            s.listen()
            self.status_message = f"Server lauscht auf {socket.gethostbyname(socket.gethostname())}:{port}"
            conn, addr = s.accept()
            with conn:
                self.status_message = f"Verbunden mit {addr}"
                # Send number of files
                num_files = len(self.selected_files)
                conn.sendall(str(num_files).encode('utf-8'))
                time.sleep(0.1) # Give client time to process

                for file_path in self.selected_files:
                    # Send filename
                    conn.sendall(file_path.encode('utf-8'))
                    time.sleep(0.1)

                    # Send file content
                    with open(file_path, 'rb') as f:
                        data = f.read()
                        conn.sendall(str(len(data)).encode('utf-8')) # Send file size
                        time.sleep(0.1)
                        conn.sendall(data)
                self.status_message = f"{num_files} Dateien erfolgreich gesendet."

    def receive_files(self, server_ip):
        if not server_ip:
            self.status_message = "Bitte gib eine IP-Adresse ein."
            return

        self.status_message = f"Verbinde mit {server_ip}..."
        threading.Thread(target=self._start_client, args=(server_ip,)).start()

    def _start_client(self, host):
        port = 65432
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
        self.ids.send_receive_buttons.opacity = 0
        self.ids.send_receive_buttons.size_hint_y = 0
        self.ids.file_list_view.opacity = 1
        self.ids.file_list_view.size_hint_y = 1
        self.list_char_files()

    def go_to_receive_view(self):
        self.ids.send_receive_buttons.opacity = 0
        self.ids.send_receive_buttons.size_hint_y = 0
        self.ids.file_list_view.opacity = 0
        self.ids.file_list_view.size_hint_y = 0
        self.ids.receive_view.opacity = 1
        self.ids.receive_view.size_hint_y = 1
        self.status_message = "Bereit zum Empfangen. Gib die IP des Senders ein."


    def back_to_main_transfer(self):
        self.ids.send_receive_buttons.opacity = 1
        self.ids.send_receive_buttons.size_hint_y = 1
        self.ids.file_list_view.opacity = 0
        self.ids.file_list_view.size_hint_y = 0
        self.ids.receive_view.opacity = 0
        self.ids.receive_view.size_hint_y = 0
        self.status_message = "Wähle eine Aktion"
