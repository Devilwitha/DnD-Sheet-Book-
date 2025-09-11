import os
import pickle
import json
import socket
import threading
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.clock import Clock
from zeroconf import ServiceBrowser, Zeroconf
from kivy.uix.screenmanager import Screen
from utils.helpers import apply_background, apply_styles_to_widget, ensure_character_attributes, create_styled_popup
from core.character import Character

class DMListener:
    def __init__(self, screen):
        self.screen = screen

    def remove_service(self, zeroconf, type, name):
        Clock.schedule_once(lambda dt: self.screen.remove_dm_service(name))

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            Clock.schedule_once(lambda dt: self.screen.add_dm_service(info))

    def update_service(self, zeroconf, type, name):
        self.add_service(zeroconf, type, name)


class PlayerLobbyScreen(Screen):
    """Screen for the player lobby."""
    def __init__(self, **kwargs):
        super(PlayerLobbyScreen, self).__init__(**kwargs)
        self.zeroconf = None
        self.browser = None
        self.available_dms = {}
        self.selected_dm = None
        self.client_socket = None
        self.selected_char_file = None
        self.char_popup = None

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        self.ids.selected_char_label.text = "Kein Charakter ausgewählt"
        self.selected_char_file = None
        self.client_socket = None
        self.selected_dm = None


    def on_enter(self, *args):
        self.start_discovery()

    def start_discovery(self):
        self.ids.dm_list.clear_widgets()
        self.available_dms.clear()
        self.zeroconf = Zeroconf()
        listener = DMListener(self)
        self.browser = ServiceBrowser(self.zeroconf, "_http._tcp.local.", listener)
        print("[*] Started Zeroconf discovery.")

    def add_dm_service(self, info):
        if info.name in self.available_dms:
            return
        self.available_dms[info.name] = info
        dm_button = Button(
            text=f"{info.properties.get(b'name', b'Unknown DM').decode()} at {socket.inet_ntoa(info.addresses[0])}",
            size_hint_y=None,
            height=60
        )
        dm_button.bind(on_press=lambda x, name=info.name: self.select_dm(name))
        self.ids.dm_list.add_widget(dm_button)
        print(f"[*] Found DM: {info.name}")

    def remove_dm_service(self, name):
        if name in self.available_dms:
            del self.available_dms[name]
            self.ids.dm_list.clear_widgets()
            for info in self.available_dms.values():
                self.add_dm_service(info)
            print(f"[*] Lost DM: {name}")

    def select_dm(self, name):
        self.selected_dm = self.available_dms.get(name)
        print(f"[*] Selected DM: {self.selected_dm.name if self.selected_dm else 'None'}")

    def show_char_selection_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        popup_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        popup_layout.bind(minimum_height=popup_layout.setter('height'))

        files = [f for f in os.listdir('.') if f.endswith('.char')]
        for filename in files:
            load_btn = Button(text=filename)
            load_btn.bind(on_release=lambda btn, fn=filename: self.select_character(fn))
            popup_layout.add_widget(load_btn)

        scroll_view = ScrollView(size_hint=(1, 1))
        scroll_view.add_widget(popup_layout)
        content.add_widget(scroll_view)

        apply_styles_to_widget(content)
        self.char_popup = create_styled_popup(title="Charakter auswählen", content=content, size_hint=(0.8, 0.8))
        self.char_popup.open()

    def select_character(self, filename):
        self.selected_char_file = filename
        self.ids.selected_char_label.text = f"Ausgewählt: {filename}"
        if self.char_popup:
            self.char_popup.dismiss()
            self.char_popup = None

    def connect_to_dm(self):
        if not self.selected_char_file:
            create_styled_popup(title="Fehler", content=Label(text="Bitte wähle zuerst einen Charakter aus."), size_hint=(0.6, 0.4)).open()
            return
        if not self.selected_dm:
            create_styled_popup(title="Fehler", content=Label(text="Bitte wähle zuerst einen DM aus der Liste aus."), size_hint=(0.6, 0.4)).open()
            return

        try:
            ip_address = socket.inet_ntoa(self.selected_dm.addresses[0])
            port = self.selected_dm.port

            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((ip_address, port))
            print(f"[*] Connected to DM at {ip_address}:{port}")

            self.send_character_data(self.selected_char_file)

        except Exception as e:
            print(f"[!] Failed to connect to DM: {e}")

    def send_character_data(self, char_file):
        try:
            with open(char_file, 'rb') as f:
                character = pickle.load(f)

            character = ensure_character_attributes(character)
            char_dict = character.to_dict()
            char_json = json.dumps(char_dict)

            message = f"{len(char_json):<10}{char_json}"
            self.client_socket.sendall(message.encode('utf-8'))
            print(f"[*] Sent initial character data for {character.name}. Waiting for DM response...")

            response_thread = threading.Thread(target=self.listen_for_dm_response, args=(character,))
            response_thread.daemon = True
            response_thread.start()

        except FileNotFoundError:
            print(f"[!] Character file not found: {char_file}")
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None
        except Exception as e:
            print(f"[!] Failed to send character data: {e}")
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None

    def listen_for_dm_response(self, initial_character):
        final_character = initial_character
        summary = ""
        try:
            while True:
                header = self.client_socket.recv(10)
                if not header: break
                msg_len = int(header.strip())
                data = b''
                while len(data) < msg_len:
                    chunk = self.client_socket.recv(msg_len - len(data))
                    if not chunk: break
                    data += chunk

                response = json.loads(data.decode('utf-8'))
                msg_type = response.get('type')
                payload = response.get('payload')

                if msg_type == 'CHAR_DATA':
                    print("[*] Received updated character data from DM.")
                    final_character = Character.from_dict(payload)
                elif msg_type == 'SUMMARY':
                    print("[*] Received session summary from DM.")
                    summary = payload
                elif msg_type == 'OK':
                    print("[*] New session confirmed by DM.")
                    Clock.schedule_once(lambda dt: self.proceed_to_game(final_character, summary))
                    return
                elif msg_type == 'ERROR':
                    print(f"[!] Error from DM: {payload}")
                    self.client_socket.close()
                    return

                if final_character != initial_character and summary:
                     Clock.schedule_once(lambda dt: self.proceed_to_game(final_character, summary))
                     return
        except Exception as e:
            print(f"[!] Error while waiting for DM response: {e}")
            if self.client_socket:
                self.client_socket.close()

    def proceed_to_game(self, character, summary):
        player_waiting_screen = self.manager.get_screen('player_waiting')
        player_waiting_screen.set_data(character, self.client_socket, summary)
        self.manager.current = 'player_waiting'

    def on_leave(self, *args):
        self.stop_discovery()
        if self.manager.current not in ['player_waiting', 'player_main'] and self.client_socket:
            self.client_socket.close()
            self.client_socket = None

    def stop_discovery(self):
        if self.zeroconf:
            self.zeroconf.close()
            self.zeroconf = None
            self.browser = None
            print("[*] Stopped Zeroconf discovery.")
