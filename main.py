import sys
from kivy.config import Config

if sys.platform.startswith('win'):
    Config.set('input', 'mouse', 'mouse,disable_multitouch')
from utils.helpers import load_settings

# Laden der Einstellungen, um die Tastaturkonfiguration zu bestimmen
settings = load_settings()
if settings.get('keyboard_enabled', False):
    Config.set('kivy', 'keyboard_mode', 'dock')
    Config.set('kivy', 'keyboard_height', '600')
else:
    Config.set('kivy', 'keyboard_mode', '')

Config.set('graphics', 'rotation', 0)

from kivy.core.window import Window
Window.size = (settings.get('window_width', 1280), settings.get('window_height', 720))

import socket
import threading
import json
import random
from queue import Queue
from zeroconf import ServiceInfo, Zeroconf
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock
from utils.helpers import save_settings
from core.character import Character

from ui.main_menu import MainMenu
from ui.character_creator import CharacterCreator
from ui.character_sheet import CharacterSheet
from ui.options_screen import OptionsScreen
from ui.character_menu_screen import CharacterMenuScreen
from ui.level_up_screen import LevelUpScreen
from ui.character_editor import CharacterEditor
from ui.info_screen import InfoScreen
from ui.settings_screen import SettingsScreen
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

class NetworkManager:
    def __init__(self):
        # General
        self.mode = 'idle' # idle, dm, client
        self.lock = threading.Lock()
        self.incoming_messages = Queue()
        self.running = False

        # DM mode attributes
        self.server_socket = None
        self.zeroconf = None
        self.service_info = None
        self.clients = {}  # addr -> {socket, character, thread}
        self.server_thread = None

        # Client mode attributes
        self.client_socket = None
        self.client_listener_thread = None

    def start_server(self):
        if self.running or self.mode != 'idle':
            print(f"[!] Cannot start server. Running: {self.running}, Mode: {self.mode}")
            return
        self.mode = 'dm'
        self.running = True

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("", 0))
        self.server_socket.listen(5)
        host, port = self.server_socket.getsockname()

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except Exception:
            ip_address = "127.0.0.1"

        print(f"[*] DM Server starting on {ip_address}:{port}")

        service_name = f"DnD_DM_Server_{random.randint(1000, 9999)}._http._tcp.local."
        self.service_info = ServiceInfo(
            "_http._tcp.local.",
            service_name,
            addresses=[socket.inet_aton(ip_address)],
            port=port,
            properties={'name': 'DM_Lobby'},
        )
        self.zeroconf = Zeroconf()
        self.zeroconf.register_service(self.service_info)

        self.server_thread = threading.Thread(target=self.accept_clients)
        self.server_thread.daemon = True
        self.server_thread.start()

    def accept_clients(self):
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                if not self.running: break
                print(f"[*] Accepted connection from {client_address}")
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, client_address))
                client_thread.daemon = True
                client_thread.start()
            except OSError:
                break # Server socket was closed

    def handle_client(self, client_socket, client_address):
        print(f"[*] Handling client {client_address}")
        try:
            # Initial data exchange
            header = client_socket.recv(10)
            if not header: return
            msg_len = int(header.strip())
            data = b''
            while len(data) < msg_len:
                chunk = client_socket.recv(msg_len - len(data))
                if not chunk: break
                data += chunk

            char_data = json.loads(data.decode('utf-8'))
            character = Character.from_dict(char_data)

            with self.lock:
                self.clients[client_address] = {
                    'socket': client_socket,
                    'character': character,
                    'thread': threading.current_thread()
                }

            # Put a special message on the queue to notify the UI of a new player
            self.incoming_messages.put(('PLAYER_JOINED', {'addr': client_address, 'char': character}))

            # Main listening loop
            while self.running:
                header = client_socket.recv(10)
                if not header:
                    break # Client disconnected

                msg_len = int(header.strip())
                data = b''
                while len(data) < msg_len:
                    chunk = client_socket.recv(msg_len - len(data))
                    if not chunk: break
                    data += chunk

                if data:
                    message = json.loads(data.decode('utf-8'))
                    self.incoming_messages.put((client_address, message))

        except (OSError, ConnectionResetError) as e:
            print(f"[!] Connection error with {client_address}: {e}")
        finally:
            self.handle_disconnect(client_address, client_socket)

    def handle_disconnect(self, client_address, client_socket):
        client_socket.close()
        with self.lock:
            if client_address in self.clients:
                char_name = self.clients[client_address]['character'].name
                del self.clients[client_address]
                self.incoming_messages.put(('PLAYER_LEFT', {'addr': client_address, 'name': char_name}))
                print(f"[*] Client {char_name} ({client_address}) disconnected.")

    def stop_server(self):
        if not self.running:
            return
        self.running = False

        with self.lock:
            for addr, client_info in list(self.clients.items()):
                try:
                    client_info['socket'].shutdown(socket.SHUT_RDWR)
                    client_info['socket'].close()
                except OSError:
                    pass
            self.clients.clear()

        if self.zeroconf and self.service_info:
            self.zeroconf.unregister_service(self.service_info)
            self.zeroconf.close()

        if self.server_socket:
            self.server_socket.close()

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1)

        print("[*] DM Server stopped.")

    def send_message(self, client_address, msg_type, payload):
        with self.lock:
            client_info = self.clients.get(client_address)
            if client_info:
                try:
                    data = json.dumps({'type': msg_type, 'payload': payload})
                    message = f"{len(data):<10}{data}".encode('utf-8')
                    client_info['socket'].sendall(message)
                except (OSError, BrokenPipeError) as e:
                    print(f"[!] Failed to send message to {client_address}: {e}")
                    # The disconnect will be handled by the listener thread

    def broadcast_message(self, msg_type, payload):
        with self.lock:
            for addr in self.clients:
                self.send_message(addr, msg_type, payload)

    def kick_player(self, client_address):
        with self.lock:
            client_info = self.clients.get(client_address)
            if client_info:
                try:
                    self.send_message(client_address, 'KICK', 'You have been kicked.')
                    client_info['socket'].shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def connect_to_server(self, ip, port, character):
        if self.running or self.mode != 'idle':
            return False, "Network manager is busy."

        self.mode = 'client'
        self.running = True
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.client_socket.connect((ip, port))
            char_json = json.dumps(character.to_dict())
            message = f"{len(char_json):<10}{char_json}".encode('utf-8')
            self.client_socket.sendall(message)

            self.client_listener_thread = threading.Thread(target=self.listen_as_client)
            self.client_listener_thread.daemon = True
            self.client_listener_thread.start()
            return True, "Connection successful."

        except (socket.error, OSError) as e:
            print(f"[!] Failed to connect to {ip}:{port}: {e}")
            self.shutdown()
            return False, str(e)

    def listen_as_client(self):
        while self.running:
            try:
                header = self.client_socket.recv(10)
                if not header:
                    break # Disconnected

                msg_len = int(header.strip())
                data = b''
                while len(data) < msg_len:
                    chunk = self.client_socket.recv(msg_len - len(data))
                    if not chunk: break
                    data += chunk

                if data:
                    message = json.loads(data.decode('utf-8'))
                    self.incoming_messages.put(('DM', message))

            except (socket.error, OSError, ConnectionResetError):
                break

        self.shutdown() # Clean up on disconnect

    def send_to_dm(self, msg_type, payload):
        if self.mode != 'client' or not self.client_socket:
            return
        try:
            data = json.dumps({'type': msg_type, 'payload': payload})
            message = f"{len(data):<10}{data}".encode('utf-8')
            self.client_socket.sendall(message)
        except (socket.error, OSError) as e:
            print(f"[!] Failed to send message to DM: {e}")
            self.shutdown()

    def shutdown(self):
        if not self.running:
            return

        self.running = False
        mode = self.mode
        self.mode = 'idle'

        if mode == 'dm':
            self.stop_server()
        elif mode == 'client':
            if self.client_socket:
                try:
                    self.client_socket.shutdown(socket.SHUT_RDWR)
                    self.client_socket.close()
                except OSError: pass
            if self.client_listener_thread and self.client_listener_thread.is_alive():
                self.client_listener_thread.join(timeout=1)
            print("[*] Client connection shut down.")

        # Clear the queue
        while not self.incoming_messages.empty():
            try: self.incoming_messages.get_nowait()
            except Empty: break

class DnDApp(App):
    """Haupt-App-Klasse."""
    def __init__(self, **kwargs):
        super(DnDApp, self).__init__(**kwargs)
        self.network_manager = NetworkManager()
        self.loaded_session_data = None
        self.source_screen = None # For back navigation

    def build(self):
        Builder.load_file('ui/splashscreen.kv')
        Builder.load_file('ui/mainmenu.kv')
        Builder.load_file('ui/charactercreator.kv')
        Builder.load_file('ui/charactereditor.kv')
        Builder.load_file('ui/charactersheet.kv')
        Builder.load_file('ui/charactermenuscreen.kv')
        Builder.load_file('ui/levelupscreen.kv')
        Builder.load_file('ui/optionsscreen.kv')
        Builder.load_file('ui/settingsscreen.kv')
        Builder.load_file('ui/systemscreen.kv')
        Builder.load_file('ui/changelogscreen.kv')
        Builder.load_file('ui/infoscreen.kv')
        Builder.load_file('ui/transferscreen.kv')
        Builder.load_file('ui/dmspielscreen.kv')
        Builder.load_file('ui/dmlobbyscreen.kv')
        Builder.load_file('ui/playerlobbyscreen.kv')
        Builder.load_file('ui/dmprepscreen.kv')
        Builder.load_file('ui/dmmainscreen.kv')
        Builder.load_file('ui/playerwaitingscreen.kv')
        Builder.load_file('ui/playercharactersheet.kv')

        if sys.platform.startswith('win'):
            Window.fullscreen = 'auto'
        else:
            Window.fullscreen = False

        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        
        root = FloatLayout()

        sm = ScreenManager()
        sm.add_widget(SplashScreen(name='splash'))
        sm.add_widget(MainMenu(name='main'))
        sm.add_widget(CharacterMenuScreen(name='character_menu'))
        sm.add_widget(CharacterCreator(name='creator'))
        sm.add_widget(CharacterEditor(name='editor'))
        sm.add_widget(CharacterSheet(name='sheet'))
        sm.add_widget(OptionsScreen(name='options'))
        sm.add_widget(SettingsScreen(name='settings'))
        sm.add_widget(SystemScreen(name='system'))
        sm.add_widget(ChangelogScreen(name='changelog'))
        sm.add_widget(InfoScreen(name='info'))
        sm.add_widget(LevelUpScreen(name='level_up'))
        sm.add_widget(TransferScreen(name='transfer'))
        sm.add_widget(DMSpielScreen(name='dm_spiel'))
        sm.add_widget(DMLobbyScreen(name='dm_lobby'))
        sm.add_widget(PlayerLobbyScreen(name='player_lobby'))
        sm.add_widget(DMPrepScreen(name='dm_prep'))
        sm.add_widget(DMMainScreen(name='dm_main'))
        sm.add_widget(PlayerWaitingScreen(name='player_waiting'))
        sm.add_widget(PlayerCharacterSheet(name='player_sheet'))


        root.add_widget(sm)

        return root

    def on_stop(self):
        """Wird aufgerufen, wenn die App geschlossen wird."""
        settings = load_settings()
        settings['window_width'] = Window.width
        settings['window_height'] = Window.height
        save_settings(settings)

if __name__ == '__main__':
    DnDApp().run()