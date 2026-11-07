"""Regressions for late joins, visible action feedback, map placement and QR invitations."""
import json
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from core.character import Character
from core.enemy import Enemy
from core.game_manager import GameManager
from utils.join_qr import make_join_payload, parse_join_payload
from utils.map_actions import reachable_tiles


def game():
    gm = GameManager(lambda message: None)
    player = Character('Nara', 'Mensch', 'Kämpfer')
    player.initialize_character()
    gm.online_players = {'Nara': player}
    gm.enemies = [Enemy('Goblin #1', 30, 5, [{'name': 'Biss', 'damage': '1d4'}])]
    gm.map_data = {'rows': 3, 'cols': 4, 'tiles': {
        (r, c): {'type': 'Floor', 'object': None} for r in range(3) for c in range(4)}}
    gm.map_data['tiles'][(0, 0)]['object'] = player.name
    gm.map_data['tiles'][(0, 2)]['object'] = 'Goblin #1'
    gm.initiative_order = [(15, player.name), (10, 'Goblin #1')]
    gm.current_turn_index = 0
    gm.start_next_turn()
    return gm, player


def screen(gm, player):
    from ui.dm_main_screen import DMMainScreen
    obj = object.__new__(DMMainScreen)
    addr = ('127.0.0.1', 4567)
    nm = SimpleNamespace(clients={addr: {'character': player}}, lock=threading.Lock(),
                         send_message=MagicMock(), broadcast_message=MagicMock(), kick_player=MagicMock())
    obj.network_manager = nm
    obj.game_manager = gm
    obj.session_roster = {}
    obj.update_ui = MagicMock()
    obj.update_map_view = MagicMock()
    obj.log_message = MagicMock()
    obj.check_for_trigger = MagicMock()
    obj._log_times = {}
    obj._map_feedback = ''
    return obj, addr


def test_end_turn_rotates_actors_without_ending_session():
    gm, player = game()
    assert gm.end_turn()['name'] == 'Goblin #1'
    assert gm.end_turn()['name'] == player.name
    assert gm.online_players['Nara'] is player
    assert gm.map_data is not None


def test_waiting_screen_releases_queue_before_starting_game_loop():
    from ui.player_waiting_screen import PlayerWaitingScreen
    waiting = object.__new__(PlayerWaitingScreen)
    calls = []
    waiting._bg = None
    waiting.update_event = SimpleNamespace(cancel=lambda: calls.append('waiting stopped'))
    waiting.app = SimpleNamespace(start_player_gameloop=lambda: calls.append('game started'))
    waiting.manager = SimpleNamespace(current='player_waiting')
    waiting.proceed_to_game()
    assert calls == ['waiting stopped', 'game started']
    assert waiting.update_event is None and waiting.manager.current == 'player_sheet'


def test_late_join_receives_start_map_state_and_does_not_reset_current_turn():
    gm, _ = game()
    newcomer = Character('Neu', 'Mensch', 'Barbar')
    s, addr = screen(gm, newcomer)
    gm.turn_action_state = {'movement_left': 2, 'attacks_left': 0}
    s._handle_network_item(('PLAYER_JOINED', {'addr': addr, 'char': newcomer}))
    assert [c.args[1] for c in s.network_manager.send_message.call_args_list][:2] == ['CHAR_DATA', 'GAME_START']
    assert [c.args[0] for c in s.network_manager.broadcast_message.call_args_list] == ['MAP_DATA', 'GAME_STATE_UPDATE']
    assert gm.get_current_turn_info()['name'] == 'Nara'
    assert gm.turn_action_state == {'movement_left': 2, 'attacks_left': 0}
    assert gm.initiative_order[-1][1] == newcomer.name


def test_rejoin_restores_saved_hp_without_duplicate_initiative():
    gm, player = game()
    s, addr = screen(gm, player)
    saved = dict(player.to_dict(), hit_points=3)
    s.session_roster[player.character_id] = saved
    s._handle_network_item(('PLAYER_JOINED', {'addr': addr, 'char': player}))
    assert gm.online_players['Nara'].hit_points == 3
    assert s.network_manager.clients[addr]['character'] is gm.online_players['Nara']
    assert len(gm.initiative_order) == 2


def test_move_broadcasts_remaining_budget_and_acknowledges_sender():
    gm, player = game()
    s, addr = screen(gm, player)
    s._handle_network_item((addr, {'type': 'MOVE_OBJECT', 'payload': {'to_pos': [0, 1]}}))
    assert gm.find_object_pos('Nara') == (0, 1)
    states = [c.args[1] for c in s.network_manager.broadcast_message.call_args_list if c.args[0] == 'GAME_STATE_UPDATE']
    assert states[-1]['turn_action_state']['movement_left'] == player.speed - 1
    assert s.network_manager.send_message.call_args_list[-1].args[1] == 'ACTION_RESULT'


def test_attack_from_client_changes_target_and_returns_result():
    gm, player = game()
    assert gm.move_object('Nara', (0, 1))[0]
    s, addr = screen(gm, player)
    s._handle_network_item((addr, {'type': 'PLAYER_ATTACK', 'payload': {
        'type': 'manual', 'enemy_name': 'Goblin #1', 'attack_roll': 20, 'damage': 4}}))
    assert gm.enemies[0].hp == 26
    assert gm.turn_action_state['attacks_left'] == 0
    assert s.network_manager.send_message.call_args_list[-1].args[1] == 'ACTION_RESULT'


def test_failed_move_returns_readable_error_without_mutation():
    gm, player = game()
    s, addr = screen(gm, player)
    gm.map_data['tiles'][(0, 1)]['type'] = 'Wall'
    s._handle_network_item((addr, {'type': 'MOVE_OBJECT', 'payload': {'to_pos': [0, 1]}}))
    assert gm.find_object_pos('Nara') == (0, 0)
    assert s.network_manager.send_message.call_args.args == (addr, 'ERROR', 'Eine Wand blockiert dieses Feld.')


def test_host_can_move_and_attack_for_each_player(monkeypatch):
    gm, first = game()
    second = Character('Zweiter', 'Mensch', 'Kämpfer')
    second.initialize_character()
    gm.offline_players = [second]
    gm.initiative_order.append((1, second.name))
    assert gm.place_object(second.name, (2, 0))[0]
    s, _ = screen(gm, first)
    monkeypatch.setattr('core.game_manager.random.randint', lambda a, b: b)
    s.move_object(first.name, (0, 1))
    s.dm_attack(first.name, 'Goblin #1')
    assert gm.enemies[0].hp < 30
    gm.end_turn()
    gm.end_turn()
    s.move_object(second.name, (1, 1))
    hp = gm.enemies[0].hp
    s.dm_attack(second.name, 'Goblin #1')
    assert gm.enemies[0].hp < hp


def test_movement_highlights_match_legal_paths_and_block_furniture():
    gm, player = game()
    gm.map_data['tiles'][(0, 1)]['type'] = 'Wall'
    gm.map_data['tiles'][(1, 0)]['furniture'] = {'type': 'Tisch'}
    assert reachable_tiles(gm.map_data, (0, 0), 6) == {}
    assert not gm.move_object(player.name, (1, 1))[0]


def test_dm_placement_is_atomic_and_does_not_spend_or_restore_turn_resources():
    gm, player = game()
    gm.turn_action_state['movement_left'] = 2
    assert not gm.place_object(player.name, (0, 2))[0]
    assert gm.find_object_pos(player.name) == (0, 0)
    assert gm.place_object(player.name, (2, 2))[0]
    assert gm.turn_action_state['movement_left'] == 2
    assert sum(t.get('object') == player.name for t in gm.map_data['tiles'].values()) == 1


def test_map_editor_enemy_is_registered_before_actions():
    gm, player = game()
    s, _ = screen(gm, player)
    gm.enemies.clear()
    gm.map_data['enemies'] = [{'name': 'Goblin #1', 'hp': 17, 'ac': 12, 'attacks': [{'name': 'Dolch', 'damage': '1d4'}]}]
    s.register_map_figures()
    assert gm.get_character_or_enemy_by_name('Goblin #1').hp == 17
    gm.enemies[0].hp = 8
    s.register_map_figures()
    assert len(gm.enemies) == 1 and gm.enemies[0].hp == 8


def test_interaction_rejects_out_of_turn_and_out_of_range():
    gm, player = game()
    s, _ = screen(gm, player)
    gm.map_data['tiles'][(2, 3)]['furniture'] = {'type': 'Kiste'}
    assert s.handle_interaction(player.name, (2, 3))[0] is False
    gm.end_turn()
    assert s.handle_interaction(player.name, (1, 0))[0] is False


def test_qr_round_trip():
    payload = make_join_payload('192.168.1.15', 45123, '12345678abcdef90')
    assert parse_join_payload(payload) == ('192.168.1.15', 45123, '12345678ABCDEF90')


@pytest.mark.parametrize('text', ['https://evil.example', 'file:///data/x', 'x' * 513,
    '{"app":"dnd-local","app":"dnd-local"}', 'null', '[]', '[' * 500])
def test_unrelated_or_malformed_qr_is_rejected(text):
    with pytest.raises(ValueError):
        parse_join_payload(text)


@pytest.mark.parametrize('field,value', [('host', '8.8.8.8'), ('host', '127.0.0.1'), ('host', 'evil.example'),
    ('port', True), ('port', 0), ('port', 65536), ('v', True), ('v', 2), ('code', 'invalid')])
def test_qr_rejects_unsafe_or_unsupported_fields(field, value):
    data = json.loads(make_join_payload('192.168.1.15', 45123, '12345678ABCDEF90'))
    data[field] = value
    with pytest.raises(ValueError):
        parse_join_payload(json.dumps(data))
