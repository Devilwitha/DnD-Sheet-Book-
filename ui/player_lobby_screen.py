import socket
import pickle
import json
from kivy.uix.button import Button
from kivy.clock import Clock
from zeroconf import ServiceBrowser, Zeroconf
from kivy.uix.screenmanager import Screen
from utils.helpers import apply_background, apply_styles_to_widget
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
        # For now, we'll just treat update as add
        self.add_service(zeroconf, type, name)


class PlayerLobbyScreen(Screen):
    """Screen for the player lobby."""
    def __init__(self, **kwargs):
        super(PlayerLobbyScreen, self).__init__(**kwargs)
        self.zeroconf = None
        self.browser = None
        self.available_dms = {} # Store service info by name
        self.selected_dm = None
        self.client_socket = None

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

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
        # Avoid adding duplicates
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
            # Rebuild the list of buttons
            self.ids.dm_list.clear_widgets()
            for info in self.available_dms.values():
                self.add_dm_service(info)
            print(f"[*] Lost DM: {name}")

    def select_dm(self, name):
        # Simple visual feedback for selection could be added here
        self.selected_dm = self.available_dms.get(name)
        print(f"[*] Selected DM: {self.selected_dm.name if self.selected_dm else 'None'}")


    def connect_to_dm(self):
        if not self.selected_dm:
            print("[!] No DM selected.")
            return

        try:
            ip_address = socket.inet_ntoa(self.selected_dm.addresses[0])
            port = self.selected_dm.port

            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((ip_address, port))
            print(f"[*] Connected to DM at {ip_address}:{port}")

            # For now, we hardcode the character file. Later, we'll use a file chooser.
            self.send_character_data("thul'zaran.char")

        except Exception as e:
            print(f"[!] Failed to connect to DM: {e}")

    def send_character_data(self, char_file):
        try:
            with open(char_file, 'rb') as f:
                character = pickle.load(f)

            char_dict = character.to_dict()
            char_json = json.dumps(char_dict)

            message = f"{len(char_json):<10}{char_json}"
            self.client_socket.sendall(message.encode('utf-8'))
            print(f"[*] Sent initial character data for {character.name}. Waiting for DM response...")

            # Start a thread to listen for the DM's response
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
        """Waits for the DM to send back session info (or an OK)."""
        final_character = initial_character
        summary = ""
        try:
            while True: # Loop to process multiple messages like CHAR_DATA and SUMMARY
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
                    # We've received the confirmation, we can stop listening for setup messages
                    Clock.schedule_once(lambda dt: self.proceed_to_game(final_character, summary))
                    return
                elif msg_type == 'ERROR':
                    print(f"[!] Error from DM: {payload}")
                    # Handle error, maybe show a popup
                    self.client_socket.close()
                    return

                # In a loaded session, we expect CHAR_DATA and SUMMARY, then we proceed.
                # We can assume for now the server sends them back-to-back.
                if final_character != initial_character and summary:
                     Clock.schedule_once(lambda dt: self.proceed_to_game(final_character, summary))
                     return


        except Exception as e:
            print(f"[!] Error while waiting for DM response: {e}")
            if self.client_socket:
                self.client_socket.close()

    def proceed_to_game(self, character, summary):
        """Transitions to the main game screen."""
        player_main_screen = self.manager.get_screen('player_main')
        player_main_screen.set_player_data(character, self.client_socket, summary)
        self.manager.current = 'player_main'

    def on_leave(self, *args):
        self.stop_discovery()
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None

    def stop_discovery(self):
        if self.zeroconf:
            self.zeroconf.close()
            self.zeroconf = None
            self.browser = None
            print("[*] Stopped Zeroconf discovery.")
