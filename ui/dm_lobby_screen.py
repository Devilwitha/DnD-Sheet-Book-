import socket
import threading
import random
import json
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.clock import Clock
from zeroconf import ServiceInfo, Zeroconf
from utils.helpers import apply_background, apply_styles_to_widget
from core.character import Character

class DMLobbyScreen(Screen):
    """Screen for the DM lobby."""
    def __init__(self, **kwargs):
        super(DMLobbyScreen, self).__init__(**kwargs)
        self.server_socket = None
        self.zeroconf = None
        self.service_info = None
        self.clients = {}  # To store client sockets and addresses
        self.server_thread = None
        self.loaded_session = None

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def on_enter(self, *args):
        app = App.get_running_app()
        if hasattr(app, 'loaded_session_data'):
            self.loaded_session = app.loaded_session_data
            self.ids.lobby_title.text = "DM Lobby (Geladene Sitzung)"
            # Populate the list with expected players from the session
            for player_str, player_data in self.loaded_session['online_players'].items():
                char_name = player_data['character']['name']
                self.update_player_list(f"{char_name} (Erwartet)", player_str)
            delattr(app, 'loaded_session_data') # Consume the data
        else:
            self.loaded_session = None
            self.ids.lobby_title.text = "DM Lobby"

        self.start_server()

    def start_server(self):
        # Setup server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("", 0))  # Bind to any address, OS chooses port
        self.server_socket.listen(5)
        host, port = self.server_socket.getsockname()

        # Get local IP address
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except Exception:
            ip_address = "127.0.0.1"

        print(f"[*] Listening on {ip_address}:{port}")

        # Setup Zeroconf service
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
        print(f"[*] Zeroconf service '{service_name}' registered.")

        # Start listening for clients in a new thread
        self.server_thread = threading.Thread(target=self.accept_clients)
        self.server_thread.daemon = True
        self.server_thread.start()

    def accept_clients(self):
        while self.server_socket:
            try:
                client_socket, client_address = self.server_socket.accept()
                print(f"[*] Accepted connection from {client_address[0]}:{client_address[1]}")

                # Start a new thread to handle this client
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, client_address))
                client_thread.daemon = True
                client_thread.start()

            except (OSError, AttributeError):
                break

    def handle_client(self, client_socket, client_address):
        try:
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

            self.clients[client_address] = {'socket': client_socket, 'character': character}

            # If in a loaded session, find the saved data and send it back
            if self.loaded_session:
                found_player = False
                for player_str, player_data in self.loaded_session['online_players'].items():
                    if player_data['character']['name'] == character.name:
                        # Send the saved character data back to the player
                        saved_char_json = json.dumps(player_data['character'])
                        self.send_message(client_socket, 'CHAR_DATA', saved_char_json)

                        # Send the session summary
                        summary = self.loaded_session.get('summary', 'Keine Zusammenfassung verfügbar.')
                        self.send_message(client_socket, 'SUMMARY', summary)

                        found_player = True
                        break
                if not found_player:
                    self.send_message(client_socket, 'ERROR', 'Charakter nicht in dieser Sitzung gefunden.')
            else:
                # In a new session, just confirm the connection
                self.send_message(client_socket, 'OK', 'Willkommen in der neuen Sitzung!')

            Clock.schedule_once(lambda dt: self.update_player_list(f"{character.name} (Verbunden)", client_address))

        except Exception as e:
            print(f"[!] Error handling client {client_address}: {e}")
            client_socket.close()

    def send_message(self, client_socket, msg_type, payload):
        """Sends a message with a type and payload."""
        try:
            data = json.dumps({'type': msg_type, 'payload': payload})
            message = f"{len(data):<10}{data}"
            client_socket.sendall(message.encode('utf-8'))
        except Exception as e:
            print(f"[!] Failed to send message of type {msg_type}: {e}")

    def update_player_list(self, player_name, client_address):
        # We can use the address to uniquely identify the label if we need to remove it later
        player_label = Label(text=player_name, size_hint_y=None, height=40)
        self.ids.player_list.add_widget(player_label)

    def start_game(self):
        """Passes the client data to the main DM screen and switches to it."""
        dm_main_screen = self.manager.get_screen('dm_main')
        session_data_to_pass = {}

        if self.loaded_session:
            # Use the loaded session as the base
            session_data_to_pass = self.loaded_session
            # Merge live sockets into the loaded data
            for addr, client_info in self.clients.items():
                for player_str, player_data in session_data_to_pass['online_players'].items():
                    if client_info['character'].name == player_data['character']['name']:
                        player_data['socket'] = client_info['socket']
                        break
        else:
            # Create a new session structure for a new game
            if not self.clients:
                print("[!] No players have joined yet!")
                return
            session_data_to_pass = {
                'online_players': self.clients,
                'offline_players': [],
                'enemies': [],
                'log': "Sitzung gestartet.\n",
                'summary': ""
            }

        dm_main_screen.set_game_data(session_data_to_pass)

        # Stop the server so no new players can join
        self.stop_server()
        self.manager.current = 'dm_main'

    def on_leave(self, *args):
        self.stop_server()

    def stop_server(self):
        if self.zeroconf and self.service_info:
            self.zeroconf.unregister_service(self.service_info)
            self.zeroconf.close()
            self.zeroconf = None
            self.service_info = None
            print("[*] Zeroconf service unregistered.")

        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
            print("[*] Server socket closed.")

        for client_socket in self.clients.values():
            client_socket.close()
        self.clients.clear()

        # Clear the player list on the UI
        if self.ids.player_list:
            self.ids.player_list.clear_widgets()
