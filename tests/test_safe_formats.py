import copy
import json
import pickle
from pathlib import Path

import pytest

from core.character import Character
from utils.formats import decode_map, encode_map, decode_session, encode_session
from utils.storage import CharacterRepository, atomic_write_json, read_json, safe_save_path, validate_transfer
from utils.legacy_character import decode_legacy_character, convert_legacy_character


def test_map_code_is_never_evaluated(tmp_path):
    marker = tmp_path / 'marker'
    key = f"__import__('pathlib').Path({str(marker)!r}).touch()"
    with pytest.raises(ValueError):
        decode_map({'rows': 1, 'cols': 1, 'tiles': {key: {'type': 'Floor'}}})
    assert not marker.exists()


def test_legacy_and_new_map_round_trip():
    old = {'rows': 2, 'cols': 2, 'tiles': {'(0, 1)': {'type': 'Door', 'object': 'Spieler'}}}
    runtime = decode_map(old)
    assert runtime['tiles'][(0, 1)]['object'] == 'Spieler'
    assert decode_map(encode_map(runtime)) == runtime
    assert '(0, 1)' in old['tiles']


@pytest.mark.parametrize('filename', ['../x', '..\\x', 'C:\\x', 'x:stream', 'CON.char', 'LPT1.txt', 'x.', 'x ', '/x'])
def test_paths_reject_escape_and_windows_special_names(tmp_path, filename):
    with pytest.raises(ValueError):
        safe_save_path(tmp_path, filename)


def test_failed_serialization_preserves_file(tmp_path):
    file = tmp_path / 'save.json'
    file.write_bytes(b'original')
    with pytest.raises(TypeError):
        atomic_write_json(file, {(0, 1): object()})
    assert file.read_bytes() == b'original'
    assert not list(tmp_path.glob('*.part'))


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'[' * 40 + b'0' + b']' * 40])
def test_bad_json_is_rejected(tmp_path, raw):
    file = tmp_path / 'bad.json'
    file.write_bytes(raw)
    with pytest.raises(ValueError):
        read_json(file)


def test_session_preserves_legacy_lists_dicts_and_turn_state():
    c = Character('Nara', 'Mensch', 'Barbar')
    c.initialize_character()
    c.hit_points = 3
    for players in ([c.to_dict()], {'old-address': {'character': c.to_dict()}}):
        source = {'online_players': players, 'initiative_order': [[18, 'Nara']],
                  'current_turn_index': 0, 'turn_action_state': {'movement_left': 2, 'attacks_left': 0},
                  'enemies': [{'name': 'Goblin', 'hp': 2, 'ac': 15, 'attacks': []}], 'log': 'Alter Spielverlauf'}
        restored = decode_session(encode_session(source))
        assert restored['online_players'][0]['hit_points'] == 3
        assert restored['enemies'][0]['hp'] == 2
        assert restored['initiative_order'] == [[18, 'Nara']]
        assert restored['current_turn_index'] == 0
        assert restored['turn_action_state']['attacks_left'] == 0
        assert restored['log'] == source['log']


def test_character_repository_identity_and_whitelist(tmp_path):
    repo = CharacterRepository(tmp_path)
    first = Character('Gleicher Name', 'Mensch', 'Barbar')
    second = Character('Gleicher Name', 'Mensch', 'Barbar')
    a, b = repo.save(first), repo.save(second)
    assert a != b
    bad = dict(first.to_dict(), to_dict='overwrite', __class__='overwrite')
    restored = Character.from_dict(bad)
    assert callable(restored.to_dict)
    assert restored.character_id == first.character_id
    assert repo.load(Path(a).name).character_id == first.character_id


def _mark(path):
    Path(path).write_text('executed')


class _Executable:
    def __init__(self, path):
        self.path = str(path)
    def __reduce__(self):
        return _mark, (self.path,)


def test_pickle_exec_rejected_in_regular_import_and_explicit_migration(tmp_path):
    marker = tmp_path / 'marker'
    raw = pickle.dumps(_Executable(marker))
    for action in (decode_legacy_character, lambda value: validate_transfer('characters', value)):
        with pytest.raises(ValueError):
            action(raw)
    assert not marker.exists()


def test_explicit_legacy_conversion_keeps_original(tmp_path):
    character = Character('Alte Nara', 'Mensch', 'Barbar')
    character.initialize_character()
    raw = pickle.dumps(character, protocol=4)
    old = tmp_path / 'original.char'
    old.write_bytes(raw)
    new_name = convert_legacy_character(tmp_path, old.name)
    loaded = CharacterRepository(tmp_path).load(new_name)
    assert loaded.name == character.name
    assert loaded.hit_points == character.hit_points
    assert old.read_bytes() == raw
