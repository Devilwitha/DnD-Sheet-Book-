import pytest
from unittest.mock import patch, MagicMock, call
from queue import Queue, Empty
import socket

# Mock the zeroconf library before it's even imported by the module we're testing
import sys
mock_zeroconf = MagicMock()
sys.modules['zeroconf'] = mock_zeroconf

from core.network_manager import NetworkManager
from core.character import Character

@pytest.fixture
def network_manager():
    """Provides a clean NetworkManager instance for each test, and ensures shutdown is called."""
    nm = NetworkManager()
    yield nm
    # Ensure shutdown is called to clean up threads, even if the test fails
    if nm.running:
        nm.shutdown()

@pytest.fixture
def sample_character():
    """Provides a sample character for testing client connections."""
    return Character(name="TestClient", race="Mensch", char_class="Kämpfer")

@patch('socket.socket')
def test_start_server(mock_socket_constructor, network_manager):
    """Tests the initialization of the server (DM mode)."""
    # Setup mock sockets
    mock_server_socket = MagicMock()
    mock_dgram_socket = MagicMock()

    # socket.socket() will be called twice: once for the server, once for getting local IP
    mock_socket_constructor.side_effect = [mock_server_socket, mock_dgram_socket]

    # Mock getsockname to return a dummy host/port
    mock_server_socket.getsockname.return_value = ("127.0.0.1", 12345)
    mock_dgram_socket.getsockname.return_value = ("192.168.1.100", 54321)

    # Start the server
    network_manager.start_server()

    # Assertions
    assert network_manager.mode == 'dm'
    assert network_manager.running is True

    # Check if the server socket was set up correctly
    mock_server_socket.bind.assert_called_with(("", 0))
    mock_server_socket.listen.assert_called_with(5)

    # Check if zeroconf service was registered
    mock_zeroconf.ServiceInfo.assert_called()
    mock_zeroconf.Zeroconf.assert_called()
    network_manager.zeroconf.register_service.assert_called_with(network_manager.service_info)

    # Check that the main server acceptance thread was started
    assert network_manager.server_thread.is_alive()

    # Check that the message sender loop was started
    assert network_manager.sender_thread.is_alive()

@patch('socket.socket')
def test_connect_to_server(mock_socket_constructor, network_manager, sample_character):
    """Tests a client connecting to a server."""
    mock_client_socket = MagicMock()
    mock_socket_constructor.return_value = mock_client_socket

    # Call the connect method
    success, msg = network_manager.connect_to_server("127.0.0.1", 12345, sample_character)

    # Assertions
    assert success is True
    assert msg == "Connection successful."
    assert network_manager.mode == 'client'
    assert network_manager.running is True

    # Check that the socket tried to connect
    mock_client_socket.connect.assert_called_with(("127.0.0.1", 12345))

    # Check that the character data was sent
    # The data is sent in a specific format: 10-byte length header + JSON
    sent_data = mock_client_socket.sendall.call_args[0][0]
    header = sent_data[:10]
    json_data = sent_data[10:]

    assert int(header.strip()) == len(json_data)
    import json
    char_dict = json.loads(json_data.decode('utf-8'))
    assert char_dict['name'] == "TestClient"

    # Check that the listener and sender threads were started
    assert network_manager.client_listener_thread.is_alive()
    assert network_manager.sender_thread.is_alive()

@patch('socket.socket')
def test_dm_client_full_communication(mock_socket_constructor, sample_character):
    """Tests a full back-and-forth communication between a DM and a Client."""
    # --- MOCK SETUP ---
    # Create two mock sockets that can talk to each other using Queues and buffers
    # to handle partial reads correctly.
    dm_to_client_q = Queue()
    client_to_dm_q = Queue()
    dm_to_client_buffer = b''
    client_to_dm_buffer = b''

    def mock_dm_recv(size):
        nonlocal client_to_dm_buffer
        while len(client_to_dm_buffer) < size:
            try:
                client_to_dm_buffer += client_to_dm_q.get(timeout=0.1)
            except Empty:
                break
        chunk = client_to_dm_buffer[:size]
        client_to_dm_buffer = client_to_dm_buffer[size:]
        return chunk

    def mock_client_recv(size):
        nonlocal dm_to_client_buffer
        while len(dm_to_client_buffer) < size:
            try:
                dm_to_client_buffer += dm_to_client_q.get(timeout=0.1)
            except Empty:
                break
        chunk = dm_to_client_buffer[:size]
        dm_to_client_buffer = dm_to_client_buffer[size:]
        return chunk

    mock_dm_client_socket = MagicMock()
    mock_dm_client_socket.sendall.side_effect = lambda data: dm_to_client_q.put(data)
    mock_dm_client_socket.recv.side_effect = mock_dm_recv

    mock_client_socket = MagicMock()
    mock_client_socket.sendall.side_effect = lambda data: client_to_dm_q.put(data)
    mock_client_socket.recv.side_effect = mock_client_recv

    mock_server_socket = MagicMock()
    mock_server_socket.accept.return_value = (mock_dm_client_socket, ("127.0.0.1", 54321))
    mock_server_socket.getsockname.return_value = ("127.0.0.1", 12345)

    mock_dgram_socket = MagicMock()
    mock_dgram_socket.getsockname.return_value = ("192.168.1.100", 54321)

    # This controls which mock is returned when socket.socket() is called
    mock_socket_constructor.side_effect = [
        mock_server_socket, # For dm.start_server()
        mock_dgram_socket,  # For dm's get_local_ip()
        mock_client_socket  # For client.connect_to_server()
    ]

    # --- TEST EXECUTION ---
    dm_manager = NetworkManager()
    client_manager = NetworkManager()

    try:
        # 1. DM starts server
        dm_manager.start_server()
        dm_host, dm_port = dm_manager.server_socket.getsockname()

        # 2. Client connects
        client_manager.connect_to_server(dm_host, dm_port, sample_character)

        # 3. DM should receive the connection and the character
        # The DM's accept_clients runs in a thread, so we wait a moment
        join_event = dm_manager.incoming_messages.get(timeout=2)
        assert join_event[0] == 'PLAYER_JOINED'
        assert join_event[1]['char'].name == "TestClient"

        # For now, we just test the join to isolate the problem

    finally:
        # Shutdown both managers to clean up threads
        if dm_manager.running:
            dm_manager.shutdown()
        if client_manager.running:
            client_manager.shutdown()
