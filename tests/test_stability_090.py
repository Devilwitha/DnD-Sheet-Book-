import copy
import json
from queue import Empty
from unittest.mock import patch

import pytest

from core.character import Character
from core.enemy import Enemy
from core.game_manager import GameManager
from core.network_manager import EventQueue, NetworkManager
from utils.formats import encode_map, encode_session
from utils.map_document import new_map
from utils.storage import atomic_write_json, read_json


def combat():
    gm = GameManager(lambda *_: None)
    hero = Character('Hero', 'Mensch', 'Kämpfer')
    hero.hit_points, hero.max_hit_points = 3, 12
    enemy = Enemy('Goblin', 100, 10, [{'name': 'Biss', 'damage': '1d1+2'}])
    gm.offline_players = [hero]
    gm.enemies = [enemy]
    gm.map_data = new_map(2, 2)
    gm.map_data['tiles'][(0, 0)]['object'] = hero.name
    gm.map_data['tiles'][(0, 1)]['object'] = enemy.name
    gm.initiative_order = [(15, enemy.name), (10, hero.name)]
    gm.current_turn_index = 0
    gm.start_next_turn()
    return gm, hero, enemy


def test_zero_hp_preserves_position_and_turn_but_blocks_player_actions():
    gm, hero, enemy = combat()
    result = gm.handle_attack(enemy.name, hero.name, attack_roll=100, damage_roll=8)
    assert result['incapacitated'] and not result.get('defeated')
    assert hero.hit_points == 0 and gm.find_object_pos(hero.name) == (0, 0)
    gm.end_turn()
    assert gm.get_current_turn_info()['name'] == hero.name
    assert gm.turn_action_state == {'movement_left': 0, 'attacks_left': 0}
    assert not gm.move_object(hero.name, (1, 0))[0]
    assert gm.move_object(hero.name, (1, 0), dm_override=True)[0]
    assert not gm.handle_attack(hero.name, enemy.name)['success']
    hero.hit_points = 5
    gm.start_next_turn()
    assert gm.turn_action_state['attacks_left'] > 0


def test_natural_rolls_and_critical_dice_do_not_double_fixed_or_manual_damage():
    gm, hero, enemy = combat()
    hero.hit_points = hero.max_hit_points = 100
    hero.armor_class = 30
    result = gm.handle_attack(enemy.name, hero.name, natural_roll=20, dm_override=True)
    assert result['hit'] and result['critical'] and result['damage'] == 4  # 2d1+2
    result = gm.handle_attack(enemy.name, hero.name, natural_roll=20, damage_roll=7, dm_override=True)
    assert result['damage'] == 7
    hero.armor_class = 1
    before = hero.hit_points
    assert not gm.handle_attack(enemy.name, hero.name, natural_roll=1, dm_override=True)['hit']
    assert hero.hit_points == before


def test_large_map_roundtrip_through_file_and_wire(tmp_path):
    from utils.wire import encode_message, decode_message
    data = encode_map(new_map(100, 100))
    path = tmp_path / 'map.json'
    atomic_write_json(path, data)
    assert len(read_json(path)['tiles']) == 10000
    frame = encode_message({'type': 'MAP_DATA', 'payload': data})
    assert len(decode_message(frame[4:])['payload']['tiles']) == 10000


def test_enemy_hp_and_attack_copy_are_saveable():
    attacks = [{'name': 'Biss', 'damage': '1d4'}]
    enemy = Enemy.from_dict({'name': 'Riese', 'hp': 20000, 'attacks': attacks})
    enemy.attacks[0]['damage'] = '1d6'
    assert attacks[0]['damage'] == '1d4'
    assert enemy.hp == 10000
    encode_session({'enemies': [enemy.to_dict()]})


def test_departure_survives_full_queue_and_stays_bounded():
    queue = EventQueue(2)
    queue.put_nowait(('one', {}))
    queue.put_nowait(('two', {}))
    queue.put_departure(('a', 1))
    assert queue.get_nowait() == ('PLAYER_LEFT', {'addr': ('a', 1)})
    assert queue.get_nowait()[0] == 'one'
    for i in range(1000):
        queue.put_departure(('a', i))
    assert len(queue.departures) <= 16


def test_reconnect_keeps_host_values_and_rejects_impostor_and_kicked_client():
    with patch.object(NetworkManager, '_advertise'):
        host, client, impostor = NetworkManager(), NetworkManager(), NetworkManager()
        try:
            assert host.start_server(host='127.0.0.1')[0]
            hero = Character('Hero', 'Mensch', 'Kämpfer')
            hero.hit_points = hero.max_hit_points = 10
            def join(peer):
                return peer.connect_to_server('127.0.0.1', host.port, hero, host.join_code)
            assert join(client)[0]
            _, event = host.incoming_messages.get(timeout=3)
            addr = event['addr']
            host.clients[addr]['approved'] = True
            host.clients[addr]['character'].hit_points = 2
            host.broadcast_message('PING', {})
            assert client.incoming_messages.get(timeout=3)[1]['type'] == 'PING'
            assert not join(impostor)[0]
            assert len(host.clients) == 1
            client.shutdown()
            assert host.incoming_messages.get(timeout=3)[0] == 'PLAYER_LEFT'
            hero.hit_points = 99  # local edits must not become authoritative
            assert join(client)[0]
            _, event = host.incoming_messages.get(timeout=3)
            addr = event['addr']
            assert event['char'].hit_points == 2
            assert host.clients[addr]['approved']
            host.kick_player(addr)
            client.shutdown()
            assert not join(client)[0]
        finally:
            client.shutdown()
            impostor.shutdown()
            host.shutdown()


def test_unapproved_client_receives_no_broadcast():
    with patch.object(NetworkManager, '_advertise'):
        host, client = NetworkManager(), NetworkManager()
        try:
            assert host.start_server(host='127.0.0.1')[0]
            char = Character('Pending', 'Mensch', 'Kämpfer')
            assert client.connect_to_server('127.0.0.1', host.port, char, host.join_code)[0]
            host.incoming_messages.get(timeout=3)
            host.broadcast_message('MAP_DATA', {'secret': 'hidden'})
            with pytest.raises(Empty):
                client.incoming_messages.get(timeout=.1)
        finally:
            client.shutdown()
            host.shutdown()


def test_journal_keeps_rejected_content_and_continues(tmp_path, monkeypatch):
    from utils.session_archive import SessionArchive
    import utils.session_archive as archive_module
    from ui.archive_controller import ArchiveController
    def folder(name):
        path = tmp_path / name
        path.mkdir(exist_ok=True)
        return str(path)
    monkeypatch.setattr(archive_module, 'get_user_saves_dir', folder)
    archive = SessionArchive()
    class Host(ArchiveController):
        @property
        def archive(self):
            return archive
    host = Host()
    host.init_archive()
    host.ids = {}
    host.archive_id = archive.create()
    invalid = 'x' * 70000 + '\x00'
    host._journal_pending = [(invalid, 'DM', 't1'), ('Valid', 'DM', 't2')]
    host.flush_journal()
    assert not host._journal_pending
    assert archive.events(host.archive_id)[1][0]['message'] == 'Valid'
    with archive.connect() as db:
        payload = db.execute('SELECT payload FROM rejected_events').fetchone()[0]
    assert json.loads(payload)[0] == invalid


def test_settings_validate_types_and_preserve_unicode():
    from utils.helpers import validated_settings
    defaults = {'window_width': 1280, 'transparency_enabled': False,
                'custom_font_color': [1, 1, 1, 1], 'background_path': ''}
    actual = validated_settings(defaults, {'window_width': 'bad', 'transparency_enabled': 'false',
                                         'custom_font_color': [1, 0, 0, -1], 'background_path': 'Wälder/Öl.png'})
    assert actual['window_width'] == 1280 and actual['transparency_enabled'] is False
    assert actual['custom_font_color'] == [1, 1, 1, 1]
    assert actual['background_path'] == 'Wälder/Öl.png'
    actual['custom_font_color'][0] = 0
    assert defaults['custom_font_color'][0] == 1
