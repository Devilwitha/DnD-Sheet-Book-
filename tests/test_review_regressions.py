from types import SimpleNamespace
from unittest.mock import MagicMock
import threading
import pytest
from core.character import Character
from core.enemy import Enemy
from core.game_manager import GameManager
from utils.formats import encode_session, decode_session, decode_map, validate_character
from utils.storage import CharacterRepository, atomic_write_json


def test_offline_custom_attack_survives_session_save():
    char = Character('Offline', '', '')
    char.attacks = [{'name': 'Bogen', 'damage': '1d8'}]
    char.attack_bonus, char.proficiency = 3, 2
    session = decode_session(encode_session({'offline_players': [char.to_dict()]}))
    gm = GameManager()
    gm.apply_session(session)
    restored = gm.offline_players[0]
    assert restored.attacks == char.attacks
    assert gm._select_attack(restored)['to_hit'] == 5


@pytest.mark.parametrize('attack', [
    {'name': 'Biss', 'damage': '999999d999999'},
    {'name': 'Biss', 'damage': '1d6', 'damage_modifier': 'x'},
    {'name': 'Biss', 'damage': '1d6', 'range': -1},
])
def test_bad_attacks_rejected_at_all_import_boundaries(attack):
    enemy = {'name': 'Goblin', 'hp': 10, 'ac': 12, 'attacks': [attack]}
    with pytest.raises(ValueError):
        decode_session({'enemies': [enemy]})
    with pytest.raises(ValueError):
        decode_map({'rows': 1, 'cols': 1, 'tiles': {}, 'enemies': [enemy]})
    with pytest.raises(ValueError):
        validate_character(dict(Character('A', '', '').to_dict(), attacks=[attack]))


def test_editing_import_with_duplicate_id_preserves_existing_character(tmp_path):
    repo = CharacterRepository(tmp_path)
    original = Character('Original', 'Mensch', 'Barbar')
    own = repo.save(original)
    envelope = {'format': 'dnd-character', 'version': 1, 'character': dict(original.to_dict(), name='Import')}
    atomic_write_json(tmp_path / 'imported.char', envelope)
    imported = repo.load('imported.char')
    imported.name = 'Edited import'
    repo.save(imported)
    assert repo.load('imported.char').name == 'Edited import'
    assert repo.load(original.character_id + '.char').name == 'Original'


def test_peer_cannot_impersonate_enemy_by_choosing_its_name():
    from ui.dm_main_screen import DMMainScreen
    screen = object.__new__(DMMainScreen)
    screen.game_manager = GameManager()
    screen.game_manager.enemies = [Enemy('Goblin #1', 10, 12, [])]
    peer = Character('Goblin #1', 'Mensch', 'Barbar')
    nm = MagicMock()
    nm.lock = threading.RLock()
    nm.clients = {'peer': {'character': peer}}
    screen.network_manager = nm
    screen.update_ui = MagicMock()
    screen._handle_network_item(('PLAYER_JOINED', {'char': peer, 'addr': 'peer'}))
    assert screen.game_manager.online_players == {}
    nm.kick_player.assert_called_with('peer')
    screen._handle_network_item(('peer', {'type': 'MOVE_OBJECT', 'payload': {'to_pos': [0, 1]}}))
    assert nm.kick_player.call_count == 2


def test_long_ui_log_remains_savable():
    from ui.dm_main_screen import DMMainScreen
    screen = object.__new__(DMMainScreen)
    class Ids(dict):
        __getattr__ = dict.__getitem__
    screen.ids = Ids(log_output=SimpleNamespace(text=''))
    for _ in range(50):
        screen.log_message('x' * 2000)
    assert len(screen.ids.log_output.text) == 64000
    assert decode_session(encode_session({'log': screen.ids.log_output.text}))['log'] == screen.ids.log_output.text


@pytest.mark.parametrize('code,accepted', [('123456', False), ('abcd-1234-efab-5678', True)])
def test_lobby_connect_uses_real_pairing_validator(monkeypatch, code, accepted):
    import ui.player_lobby_screen as module
    screen = object.__new__(module.PlayerLobbyScreen)
    screen._connecting = False
    screen._connect_token = 0
    screen.selected_char_file = 'nara.char'
    screen.ids = SimpleNamespace(manual_input=SimpleNamespace(text='127.0.0.1:5555'),
        join_code_input=SimpleNamespace(text=code), connect_button=SimpleNamespace(disabled=False),
        status_label=SimpleNamespace(text=''))
    screen.show_error_popup = MagicMock()
    worker = MagicMock()
    monkeypatch.setattr(module.threading, 'Thread', worker)
    screen.connect_to_dm()
    if accepted:
        worker.return_value.start.assert_called_once()
        assert worker.call_args.kwargs['args'][-1] == 'ABCD1234EFAB5678'
        assert screen._connecting
    else:
        worker.assert_not_called()
        screen.show_error_popup.assert_called_once()
        assert not screen._connecting


def test_dm_sheet_return_keeps_battle_and_does_not_restart_game():
    from ui.dm_main_screen import DMMainScreen
    screen = object.__new__(DMMainScreen)
    screen._resume_from_sheet = True
    screen.update_event = None
    screen.app = SimpleNamespace(source_screen='dm_main')
    screen.game_manager = GameManager()
    screen.game_manager.current_turn_index = 2
    screen.game_manager.initiative_order = [(18, 'Nara'), (14, 'B'), (9, 'C')]
    screen.network_manager = MagicMock()
    for name in ('sync_online_players', 'update_ui', 'broadcast_game_state', 'load_state_from_manager'):
        setattr(screen, name, MagicMock())
    screen.on_enter()
    assert screen.game_manager.current_turn_index == 2
    assert screen.game_manager.initiative_order[-1] == (9, 'C')
    screen.network_manager.broadcast_message.assert_not_called()
    screen.load_state_from_manager.assert_not_called()
    screen.broadcast_game_state.assert_called_once()
    assert not screen._resume_from_sheet


def test_waiting_restore_keeps_import_filename():
    from ui.player_waiting_screen import PlayerWaitingScreen
    screen = object.__new__(PlayerWaitingScreen)
    char = Character('Nara', 'Mensch', 'Barbar')
    char._local_save_name = 'imported.char'
    screen.app = SimpleNamespace(character=char)
    screen._handle_message('CHAR_DATA', char.to_dict())
    assert screen.app.character._local_save_name == 'imported.char'


def test_lobby_broadcast_lists_only_current_clients():
    from ui.dm_lobby_screen import DMLobbyScreen
    screen = object.__new__(DMLobbyScreen)
    nm = MagicMock()
    nm.lock = threading.Lock()
    nm.clients = {'a': {'character': Character('Nara', '', '')}, 'b': {'character': Character('B', '', '')}}
    screen.network_manager = nm
    screen._broadcast_lobby_players()
    nm.broadcast_message.assert_called_with('GAME_STATE_UPDATE', {'players': ['B', 'Nara']})
    del nm.clients['a']
    screen._broadcast_lobby_players()
    nm.broadcast_message.assert_called_with('GAME_STATE_UPDATE', {'players': ['B']})
