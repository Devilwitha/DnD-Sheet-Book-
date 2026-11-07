"""DM permissions, recoverable figures and the authority boundary to player clients."""
import copy
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from tests.test_live_play import game, screen
from core.game_manager import GameManager
from core.character import Character
from core.enemy import Enemy
from utils.formats import decode_map, encode_map, decode_session, encode_session


@pytest.mark.parametrize('combat', [False, True])
def test_dm_moves_and_attacks_without_turn_budget_or_range(combat):
    gm, p = game()
    gm.current_turn_index = 1 if combat else -1
    gm.turn_action_state = {'movement_left': 0, 'attacks_left': 0}
    state = copy.deepcopy(gm.turn_action_state)
    assert gm.move_object(p.name, (2, 3), dm_override=True)[0]
    result = gm.handle_attack(p.name, 'Goblin #1', attack_roll=100, damage_roll=2, dm_override=True)
    assert result['success'] and result['damage'] == 2
    assert gm.get_current_turn_info()['name'] == ('Goblin #1' if combat else None)
    assert gm.turn_action_state == state
    assert not gm.move_object(p.name, (1, 3))[0]
    assert not gm.handle_attack(p.name, 'Goblin #1')['success']


def test_dm_still_rejects_invalid_targets_without_losing_figure():
    gm, p = game()
    gm.map_data['tiles'][(2, 3)]['type'] = 'Wall'
    before = copy.deepcopy(gm.map_data)
    for target in ((2, 3), (0, 2), (-1, 0), (0, 4)):
        assert not gm.move_object(p.name, target, dm_override=True)[0]
    assert gm.map_data == before


def test_dm_defeats_active_enemy_and_turn_moves_to_next_survivor():
    gm, p = game()
    gm.enemies.append(Enemy('Goblin #2', 20, 8, []))
    gm.initiative_order.append((5, 'Goblin #2'))
    gm.current_turn_index = 1
    gm.turn_action_state = {'movement_left': 0, 'attacks_left': 0}
    result = gm.handle_attack(p.name, 'Goblin #1', attack_roll=100, damage_roll=50, dm_override=True)
    assert result['defeated']
    assert gm.get_current_turn_info()['name'] == 'Goblin #2'
    assert gm.turn_action_state['movement_left'] == gm.enemies[0].speed


def test_player_cannot_request_admin_override_in_network_payload():
    gm, p = game()
    s, addr = screen(gm, p)
    gm.current_turn_index = 1
    before = copy.deepcopy(gm.map_data)
    hp = gm.enemies[0].hp
    s._handle_network_item((addr, {'type': 'MOVE_OBJECT', 'payload': {'to_pos': [2, 3], 'dm_override': True}}))
    s._handle_network_item((addr, {'type': 'PLAYER_ATTACK', 'payload': {
        'type': 'manual', 'enemy_name': 'Goblin #1', 'attack_roll': 100, 'damage': 20, 'dm_override': True}}))
    assert gm.map_data == before and gm.enemies[0].hp == hp


def test_dm_interacts_before_combat_from_any_distance():
    gm, p = game()
    s, _ = screen(gm, p)
    gm.current_turn_index = -1
    gm.map_data['tiles'][(2, 3)]['furniture'] = {'type': 'Kiste'}
    assert s.handle_interaction(p.name, (2, 3), dm_override=True)[0]
    assert not s.handle_interaction(p.name, (2, 3))[0]


def test_disconnected_character_keeps_dm_edits_on_rejoin_and_save():
    gm, p = game()
    s, addr = screen(gm, p)
    s.network_manager.clients.clear()
    s.sync_online_players()
    assert gm.get_character_or_enemy_by_name(p.name) is p
    assert not gm.online_players and gm.disconnected_players[p.name] is p
    p.hit_points = 3
    assert gm.move_object(p.name, (2, 2), dm_override=True)[0]
    s.session_metadata = {}
    s.ids = SimpleNamespace(log_output=SimpleNamespace(text=''))
    saved = decode_session(encode_session(s.session_snapshot()))
    restored = GameManager(lambda m: None)
    restored.apply_session(saved)
    assert restored.get_character_or_enemy_by_name(p.name).hit_points == 3
    assert restored.find_object_pos(p.name) == (2, 2)
    s.network_manager.clients[addr] = {'character': Character.from_dict(dict(p.to_dict(), hit_points=12))}
    s._handle_network_item(('PLAYER_JOINED', {'addr': addr, 'char': p}))
    assert not gm.disconnected_players
    assert gm.online_players[p.name].hit_points == 3
    assert gm.find_object_pos(p.name) == (2, 2)


def test_map_editor_returns_character_data_without_overwriting_session_hp():
    from ui.map_editor_screen import MapEditorScreen
    gm, p = game()
    offline = Character('Begleiter', 'Mensch', 'Kämpfer')
    gm.offline_players = [offline]
    editor = object.__new__(MapEditorScreen)
    editor.purpose = 'session'
    editor.app = SimpleNamespace(game_manager=gm)
    editor.map_data = gm.map_data
    data = decode_map(encode_map(editor.map_with_characters()))
    empty = GameManager(lambda m: None)
    empty.map_data = data
    s, _ = screen(empty, p)
    s.register_map_figures()
    assert empty.get_character_or_enemy_by_name(p.name).character_id == p.character_id
    assert empty.get_character_or_enemy_by_name(offline.name).name == offline.name
    empty.get_character_or_enemy_by_name(p.name).hit_points = 2
    s.register_map_figures()
    assert empty.get_character_or_enemy_by_name(p.name).hit_points == 2


def test_loading_session_restores_saved_character_even_if_client_already_connected():
    gm, p = game()
    s, addr = screen(gm, p)
    saved = dict(p.to_dict(), hit_points=2)
    gm.apply_session({'online_players': [saved], 'map_data': gm.map_data})
    s.sync_online_players()
    assert gm.online_players[p.name].hit_points == 2
    assert s.network_manager.clients[addr]['character'].hit_points == 2
    assert not gm.disconnected_players


def test_other_character_cannot_replace_disconnected_figure_by_name():
    gm, p = game()
    s, addr = screen(gm, p)
    gm.disconnected_players[p.name] = p
    gm.online_players.clear()
    replacement = Character(p.name, 'Mensch', 'Kämpfer')
    s.network_manager.clients[addr]['character'] = replacement
    s._handle_network_item(('PLAYER_JOINED', {'addr': addr, 'char': replacement}))
    s.network_manager.kick_player.assert_called_once_with(addr)
    assert gm.disconnected_players[p.name] is p and not gm.online_players


def test_visible_unknown_figure_selects_and_moves_without_silent_fallback():
    gm, p = game()
    s, _ = screen(gm, p)
    gm.map_data['tiles'][(2, 0)]['object'] = 'Alte Kartenfigur'
    s.dm_selected_attacker = p.name
    s.action_mode = 'move'
    s._selector_updating = False
    s.handle_left_click(2, 0)
    assert s.dm_selected_attacker == 'Alte Kartenfigur'
    s.handle_left_click(2, 1)
    assert gm.find_object_pos('Alte Kartenfigur') == (2, 1)
    assert gm.find_object_pos(p.name) == (0, 0)


def test_figure_selection_does_not_rebuild_other_pressed_buttons():
    gm, p = game()
    s, _ = screen(gm, p)
    s._selector_updating = False
    s.select_map_actor(p.name)
    s.select_map_action('interact')
    s.update_ui.assert_not_called()
    assert s.update_map_view.call_count == 2


def test_map_controls_keep_orphan_selected_and_enable_dm_without_initiative():
    from ui.dm_main_screen import DMMainScreen
    class IDs(dict):
        __getattr__ = dict.__getitem__
    gm, p = game()
    s, _ = screen(gm, p)
    s.ids = IDs({key: SimpleNamespace() for key in ('actor_selector', 'dm_move_button', 'dm_attack_button',
                'dm_interact_button', 'dm_place_button', 'dm_end_turn_button', 'dm_map_status', 'dm_map_hint')})
    gm.current_turn_index = -1
    s.dm_selected_attacker = p.name
    s.action_mode = 'move'
    s.update_map_controls()
    assert not s.ids.dm_move_button.disabled and not s.ids.dm_interact_button.disabled
    assert not s.ids.dm_attack_button.disabled and s.ids.dm_end_turn_button.disabled
    gm.map_data['tiles'][(1, 0)]['object'] = 'Alte Figur'
    s.dm_selected_attacker = 'Alte Figur'
    s.update_map_controls()
    assert s.dm_selected_attacker == 'Alte Figur'
    assert not s.ids.dm_move_button.disabled and s.ids.dm_attack_button.disabled
