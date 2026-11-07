"""DM state survives level-ups, stale clients, reloads and repeated requests."""
import copy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from core.character import Character
from core.character_actions import apply_character_action, state_token
from core.game_manager import GameManager
from utils.formats import encode_session, decode_session
from tests.test_live_play import game, screen


def setup_host():
    gm, char = game()
    dm, addr = screen(gm, char)
    dm.checkpoint_archive = MagicMock()
    return dm, addr, char


def request(dm, addr, char, action, args=None, request_id='first'):
    data = {'request_id': request_id, 'state': state_token(char), 'action': action, 'args': args or {}}
    dm._handle_network_item((addr, {'type': 'CHARACTER_ACTION', 'payload': data}))
    return data


def result(dm):
    return [c.args[2] for c in dm.network_manager.send_message.call_args_list if c.args[1] == 'CHARACTER_ACTION_RESULT'][-1]


def test_client_snapshot_cannot_change_any_host_field():
    dm, addr, char = setup_host()
    before = copy.deepcopy(char.to_dict())
    malicious = dict(before, level=20, hit_points=999, inventory=[], currency={'GM': 99999})
    dm._handle_network_item((addr, {'type': 'SET_CHARACTER_DATA', 'payload': malicious}))
    assert char.to_dict() == before
    assert dm.game_manager.online_players[char.name] is char
    assert dm.network_manager.send_message.call_args_list[-2].args[1:] == ('SYNC_CHARACTER', before)


def test_client_level_up_intent_is_rejected():
    dm, addr, char = setup_host()
    request(dm, addr, char, 'level_up', {'hp_roll': 10})
    assert not result(dm)['success'] and char.level == 1


def test_healing_uses_host_dice_and_consumes_once_even_on_replay(monkeypatch):
    dm, addr, char = setup_host()
    char.hit_points = 1
    char.inventory = [{'name': 'Trank', 'quantity': 2, 'healing': {'count': 1, 'dice': 4}}]
    monkeypatch.setattr('core.character_actions.random.randint', lambda a, b: b)
    data = request(dm, addr, char, 'healing_item', {'index': 0, 'healed': 9999})
    changed = dm.game_manager.online_players[char.name]
    assert changed.hit_points == 5 and changed.inventory[0]['quantity'] == 1
    assert char.hit_points == 1 and char.inventory[0]['quantity'] == 2  # copy, atomic commit
    dm._handle_network_item((addr, {'type': 'CHARACTER_ACTION', 'payload': data}))
    assert dm.game_manager.online_players[char.name].hit_points == 5
    assert dm.game_manager.online_players[char.name].inventory[0]['quantity'] == 1
    assert dm.network_manager.clients[addr]['character'] is changed


def test_stale_request_cannot_overwrite_new_host_level_or_hp():
    dm, addr, char = setup_host()
    old = state_token(char)
    char.level_up({'hp_roll': 3})
    dm.commit_character(char)
    before = copy.deepcopy(char.to_dict())
    dm._handle_network_item((addr, {'type': 'CHARACTER_ACTION', 'payload': {
        'request_id': 'stale', 'state': old, 'action': 'long_rest', 'args': {}}}))
    assert not result(dm)['success']
    assert char.to_dict() == before


@pytest.mark.parametrize('action,args', [('healing_item', {'index': -1}), ('healing_item', {'index': True}),
    ('equip_weapon', {'weapon': 'Erfunden'}), ('cast_spell', {'spell': 'Erfunden'}),
    ('short_rest', {'dice': 999}), ('level_up', {})])
def test_invalid_actions_are_atomic(action, args):
    _, char = game()
    before = copy.deepcopy(char.to_dict())
    with pytest.raises(ValueError):
        apply_character_action(char, action, args)
    assert char.to_dict() == before


def test_rest_requires_dm_approval_and_rechecks_state(monkeypatch):
    dm, addr, char = setup_host()
    char.hit_points = 1
    approve = MagicMock()
    monkeypatch.setattr('ui.character_authority.ask_dm', approve)
    request(dm, addr, char, 'long_rest')
    assert char.hit_points == 1
    yes = approve.call_args.args[2]
    char.hit_points = 2  # DM adjustment while popup is open
    yes()
    assert not result(dm)['success'] and char.hit_points == 2
    request(dm, addr, char, 'long_rest', request_id='second')
    approve.call_args.args[2]()
    assert result(dm)['success']
    assert dm.game_manager.online_players[char.name].hit_points == char.max_hit_points


def test_declined_rest_does_not_change_character(monkeypatch):
    dm, addr, char = setup_host()
    approve = MagicMock()
    monkeypatch.setattr('ui.character_authority.ask_dm', approve)
    request(dm, addr, char, 'short_rest', {'dice': 1})
    approve.call_args.args[3]()
    assert not result(dm)['success']
    assert char.hit_dice == char.max_hit_dice


def test_old_rest_popup_cannot_affect_reconnected_character(monkeypatch):
    dm, addr, char = setup_host()
    approve = MagicMock()
    monkeypatch.setattr('ui.character_authority.ask_dm', approve)
    request(dm, addr, char, 'long_rest')
    dm.network_manager.clients[addr] = {'character': char}
    approve.call_args.args[2]()
    dm.checkpoint_archive.assert_not_called()


def test_repeated_dm_level_ups_sync_and_survive_session_reload():
    dm, addr, char = setup_host()
    for level in (2, 3, 4):
        choices = {'hp_roll': 4}
        if level == 4:
            choices['ability_increase'] = ['Stärke', 'Stärke']
        char.level_up(choices)
        dm.commit_character(char, 'Stufenaufstieg')
        updates = [c.args[2] for c in dm.network_manager.send_message.call_args_list if c.args[1] == 'SYNC_CHARACTER']
        assert Character.from_dict(updates[-1]).level == level
        assert dm.session_roster[char.character_id]['level'] == level
    dm.session_metadata = {}
    dm.ids = SimpleNamespace(log_output=SimpleNamespace(text=''))
    saved = decode_session(encode_session(dm.session_snapshot()))
    gm = GameManager(lambda _: None)
    gm.apply_session(saved)
    dm.game_manager = gm
    forged = Character.from_dict(dict(char.to_dict(), name='Lokal umbenannt', level=20))
    dm.network_manager.clients[addr] = {'character': forged, 'approved': True}
    dm.sync_online_players()
    assert list(gm.online_players) == [char.name]
    assert gm.online_players[char.name].level == 4
    assert dm.network_manager.clients[addr]['character'].level == 4


def test_dm_can_level_disconnected_character_then_rejoin_overrides_local_file():
    dm, addr, char = setup_host()
    dm.network_manager.clients.clear()
    dm.sync_online_players()
    char.level_up({'hp_roll': 4})
    dm.commit_character(char, 'Stufenaufstieg')
    forged = Character.from_dict(dict(char.to_dict(), level=19))
    dm.network_manager.clients[addr] = {'character': forged, 'approved': False}
    dm._handle_network_item(('PLAYER_JOINED', {'addr': addr}))
    assert dm.game_manager.online_players[char.name].level == 2
    assert dm.network_manager.clients[addr]['approved']


def test_unknown_character_waits_for_dm_approval_and_cannot_act(monkeypatch):
    dm, addr, char = setup_host()
    dm.game_manager.online_players.clear()
    dm.network_manager.clients[addr]['approved'] = False
    approve = MagicMock()
    monkeypatch.setattr('ui.dm_main_screen.ask_dm', approve)
    dm._handle_network_item(('PLAYER_JOINED', {'addr': addr}))
    assert not dm.game_manager.online_players
    dm.sync_online_players()
    assert not dm.game_manager.online_players
    request(dm, addr, char, 'long_rest')
    dm.checkpoint_archive.assert_not_called()
    approve.call_args.args[2]()
    assert dm.game_manager.online_players[char.name] is char
    assert dm.network_manager.clients[addr]['approved']


def test_level_screen_repeats_and_double_click_does_not_skip_levels(monkeypatch):
    import ui.level_up_screen as module
    dm, addr, char = setup_host()
    app = SimpleNamespace(network_manager=SimpleNamespace(mode='dm'), source_screen='dm_main')
    monkeypatch.setattr(module.App, 'get_running_app', lambda: app)
    level = module.LevelUpScreen()
    level.update_view = MagicMock()
    sheet = MagicMock()
    level.manager = SimpleNamespace(current='level_up', get_screen=lambda n: dm if n == 'dm_main' else sheet)
    for expected in (2, 3):
        level.set_character(char)
        level.hp_roll = 4
        level.confirm_level_up()
        level.confirm_level_up()
        assert char.level == expected
        assert level.manager.current == 'sheet'
        assert dm.session_roster[char.character_id]['level'] == expected


def test_client_cannot_bypass_level_screen_guard(monkeypatch):
    import ui.level_up_screen as module
    _, char = game()
    monkeypatch.setattr(module.App, 'get_running_app', lambda: SimpleNamespace(network_manager=SimpleNamespace(mode='client')))
    level = module.LevelUpScreen()
    level.character = char
    level.show_popup = MagicMock()
    level.confirm_level_up()
    assert char.level == 1
    level.show_popup.assert_called_once()


def test_sheet_render_and_client_edits_do_not_send_snapshots(monkeypatch):
    import ui.character_sheet as module
    _, char = game()
    app = SimpleNamespace(network_manager=SimpleNamespace(mode='client'), request_character_action=MagicMock())
    monkeypatch.setattr(module.App, 'get_running_app', lambda: app)
    sheet = module.CharacterSheet()
    sheet.character = char
    sheet.show_popup = MagicMock()
    before = copy.deepcopy(char.to_dict())
    sheet.change_hp(10)
    sheet.change_currency('GM', 100, None)
    sheet.adjust_item_quantity(0, 10, None)
    sheet.open_level_up_screen()
    sheet._rendering_weapon = True
    sheet.update_weapon('Langschwert')
    sheet._rendering_weapon = False
    sheet.update_weapon(char.equipped_weapon)
    assert char.to_dict() == before
    app.request_character_action.assert_not_called()


def test_lobby_waits_for_new_character_approval(monkeypatch):
    import ui.dm_lobby_screen as module
    dm, addr, char = setup_host()
    dm.network_manager.clients[addr]['approved'] = False
    lobby = object.__new__(module.DMLobbyScreen)
    lobby.network_manager = dm.network_manager
    lobby.app = SimpleNamespace(loaded_session_data=None, _popup=MagicMock())
    lobby.add_player_to_list = MagicMock()
    lobby.manager = SimpleNamespace(current='dm_lobby')
    approve = MagicMock()
    monkeypatch.setattr(module, 'ask_dm', approve)
    lobby.handle_new_player_connection(addr)
    lobby.start_game()
    assert lobby.manager.current == 'dm_lobby'
    approve.call_args.args[2]()
    lobby.start_game()
    assert lobby.manager.current == 'dm_main'
    assert dm.network_manager.clients[addr]['approved']


def test_lobby_saved_level_overrides_local_level_without_new_approval(monkeypatch):
    import ui.dm_lobby_screen as module
    dm, addr, char = setup_host()
    saved = copy.deepcopy(char.to_dict())
    char.level = 20
    dm.network_manager.clients[addr]['approved'] = False
    lobby = object.__new__(module.DMLobbyScreen)
    lobby.network_manager = dm.network_manager
    lobby.app = SimpleNamespace(loaded_session_data={'online_players': [saved]})
    lobby.add_player_to_list = MagicMock()
    approve = MagicMock()
    monkeypatch.setattr(module, 'ask_dm', approve)
    lobby.handle_new_player_connection(addr)
    assert dm.network_manager.clients[addr]['character'].level == 1
    assert dm.network_manager.clients[addr]['approved']
    approve.assert_not_called()


def test_spell_uses_known_host_spell_and_slot_not_client_claims():
    from utils.data_manager import SPELL_DATA
    _, char = game()
    spell = next(name for name, data in SPELL_DATA.items() if data.get('level') == 1)
    char.spells = {1: [spell]}
    char.max_spell_slots = char.current_spell_slots = {'1': 1}
    changed, _ = apply_character_action(char, 'cast_spell', {'spell': spell, 'spell_level': 0})
    assert changed.current_spell_slots['1'] == 0
    with pytest.raises(ValueError):
        apply_character_action(changed, 'cast_spell', {'spell': spell})
    assert char.current_spell_slots['1'] == 1
