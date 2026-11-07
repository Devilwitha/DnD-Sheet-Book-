"""Real loopback integration, with only LAN advertisements mocked."""
from unittest.mock import patch
from core.network_manager import NetworkManager
from core.character import Character
import pytest


@pytest.fixture
def peers():
    with patch('core.network_manager.NetworkManager._advertise'):
        server, client = NetworkManager(), NetworkManager()
        yield server, client
        client.shutdown()
        server.shutdown()


def test_actual_character_roundtrip_and_messages(peers):
    server, client = peers
    assert server.start_server('Test', host='127.0.0.1')[0]
    character = Character('Nara', 'Mensch', 'Barbar')
    character.initialize_character()
    assert client.connect_to_server('127.0.0.1', server.port, character, server.join_code)[0]
    event, data = server.incoming_messages.get(timeout=3)
    assert event == 'PLAYER_JOINED'
    assert data['char'].character_id == character.character_id
    assert data['char'].hit_points == character.hit_points
    assert client.send_to_dm('LOG', 'Probewurf')
    source, message = server.incoming_messages.get(timeout=3)
    assert source == data['addr'] and message['payload'] == 'Probewurf'
    assert server.send_message(source, 'SYNC_CHARACTER', character.to_dict())
    source, message = client.incoming_messages.get(timeout=3)
    assert source == 'DM' and message['type'] == 'SYNC_CHARACTER'
    assert Character.from_dict(message['payload']).name == character.name


def test_missing_code_is_rejected_without_poisoning_client(peers):
    server, client = peers
    assert server.start_server(host='127.0.0.1')[0]
    character = Character('Nara', 'Mensch', 'Barbar')
    assert not client.connect_to_server('127.0.0.1', server.port, character)[0]
    assert client.mode == 'idle' and not client.running
    assert client.connect_to_server('127.0.0.1', server.port, character, server.join_code)[0]


def test_shutdown_and_rehosting_uses_fresh_queue(peers):
    server, _ = peers
    assert server.start_server(host='127.0.0.1')[0]
    old = server.incoming_messages
    server.shutdown()
    old.put(('OLD', {}))
    assert server.start_server(host='127.0.0.1')[0]
    assert server.incoming_messages.empty()
    assert server.running and server.mode == 'dm'
