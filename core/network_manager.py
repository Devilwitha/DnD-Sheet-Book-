import socket
import threading
import json
import random
from queue import Queue, Empty
from zeroconf import ServiceInfo, Zeroconf
from core.character import Character

class NetworkManager:
    def __init__(self):
        # General
        self.mode = 'idle' # idle, dm, client
        self.lock = threading.Lock()
        self.incoming_messages = Queue()
        self.outgoing_messages = Queue()
        self.running = False
        self.sender_thread = None

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

        self.sender_thread = threading.Thread(target=self.sender_loop)
        self.sender_thread.daemon = True
        self.sender_thread.start()

    def sender_loop(self):
        """Monitors the outgoing queue and sends messages."""
        print("[SENDER_THREAD] Sender loop started.")
        while self.running:
            try:
                recipient_socket, message = self.outgoing_messages.get(timeout=1)
                if recipient_socket is None: # Shutdown signal
                    break
                print(f"[SENDER_THREAD] Dequeued message to send: {message[:50]}...")
                recipient_socket.sendall(message)
                print(f"[SENDER_THREAD] Message sent successfully.")
            except Empty:
                continue
            except (OSError, BrokenPipeError) as e:
                print(f"[!] Sender loop error: {e}")
                # The listener thread for this socket will handle the disconnect
        print("[*] Sender loop terminating.")

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

            self.incoming_messages.put(('PLAYER_JOINED', {'addr': client_address, 'char': character}))

            while self.running:
                header = client_socket.recv(10)
                if not header:
                    break

                msg_len = int(header.strip())
                data = b''
                while len(data) < msg_len:
                    chunk = self.client_socket.recv(msg_len - len(data))
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
                data = json.dumps({'type': msg_type, 'payload': payload})
                message = f"{len(data):<10}{data}".encode('utf-8')
                self.outgoing_messages.put((client_info['socket'], message))

    def broadcast_message(self, msg_type, payload):
        print(f"[DM] Broadcasting message: Type={msg_type}, Payload={payload}")
        with self.lock:
            data = json.dumps({'type': msg_type, 'payload': payload})
            message = f"{len(data):<10}{data}".encode('utf-8')
            for client_info in self.clients.values():
                print(f"[DM] Queuing broadcast for client {client_info['character'].name}")
                self.outgoing_messages.put((client_info['socket'], message))

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

            self.sender_thread = threading.Thread(target=self.sender_loop)
            self.sender_thread.daemon = True
            self.sender_thread.start()
            return True, "Connection successful."

        except (socket.error, OSError) as e:
            print(f"[!] Failed to connect to {ip}:{port}: {e}")
            self.shutdown()
            return False, str(e)

    def listen_as_client(self):
        print("[CLIENT_THREAD] Listener loop started.")
        while self.running:
            try:
                header = self.client_socket.recv(10)
                if not header:
                    print("[CLIENT_THREAD] Disconnected (no header).")
                    break

                print(f"[CLIENT_THREAD] Received header: {header.strip()}")
                msg_len = int(header.strip())
                data = b''
                while len(data) < msg_len:
                    chunk = self.client_socket.recv(msg_len - len(data))
                    if not chunk: break
                    data += chunk

                print(f"[CLIENT_THREAD] Received data: {data.decode('utf-8')}")
                if data:
                    message = json.loads(data.decode('utf-8'))
                    print(f"[CLIENT_THREAD] Queuing incoming message: {message}")
                    self.incoming_messages.put(('DM', message))

            except (socket.error, OSError, ConnectionResetError) as e:
                print(f"[CLIENT_THREAD] Connection error: {e}")
                break

        self.shutdown()

    def send_to_dm(self, msg_type, payload):
        if self.mode != 'client' or not self.client_socket:
            return
        data = json.dumps({'type': msg_type, 'payload': payload})
        message = f"{len(data):<10}{data}".encode('utf-8')
        self.outgoing_messages.put((self.client_socket, message))

    def shutdown(self):
        if not self.running:
            return

        print("[*] Network manager shutting down...")
        self.running = False
        self.outgoing_messages.put((None, None))

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

        if self.sender_thread and self.sender_thread.is_alive():
            self.sender_thread.join(timeout=1)

        print("[*] Network manager shut down successfully.")

        while not self.incoming_messages.empty():
            try: self.incoming_messages.get_nowait()
            except Empty: break
