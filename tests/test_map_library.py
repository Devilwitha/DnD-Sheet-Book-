import copy
import pytest
from types import SimpleNamespace

from core.character import Character
from utils.map_document import Atlas, add_element, read_atlas
from utils.storage import atomic_write_json
from ui.map_editor_screen import MapEditorScreen


def tree():
    atlas = Atlas(name='Vorlage')
    for name in ('Region', 'Dorf', 'Schmiede'):
        atlas.add_child(name, 3, 4)
    add_element(atlas.map['artwork'], 'stroke', [[1, 1], [2, 2]], '#223344', 1, 'terrain')
    atlas.map['tiles'][(1, 1)]['type'] = 'Wall'
    atlas.map['tiles'][(2, 2)]['object'] = 'Begleiter'
    atlas.map['tiles'][(3, 3)]['object'] = 'Goblin#1'
    atlas.map['offline_players'] = [Character('Begleiter', 'Mensch', 'Kämpfer').to_dict()]
    atlas.map['online_players'] = [Character('Spieler', 'Mensch', 'Kämpfer').to_dict()]
    atlas.maps[atlas.root_id]['map']['tiles'][(4, 4)]['object'] = 'Begleiter'
    return atlas


def test_copy_remaps_entire_tree_and_cannot_change_source(tmp_path):
    source = tree()
    path = tmp_path / 'source.json'
    atomic_write_json(path, source.encode())
    before = path.read_bytes()
    result = source.duplicate()
    assert result.id != source.id
    assert set(result.maps).isdisjoint(source.maps)
    assert [r['name'] for r in result.breadcrumbs()] == ['Vorlage', 'Region', 'Dorf', 'Schmiede']
    assert result.map['tiles'][(1, 1)]['type'] == 'Wall'
    assert result.map['tiles'][(2, 2)]['object'] is None
    assert result.map['tiles'][(3, 3)]['object'] == 'Goblin#1'
    assert not result.map.get('offline_players')
    assert not result.map.get('online_players')
    assert result.maps[result.root_id]['map']['tiles'][(4, 4)]['object'] is None
    for key, rec in result.maps.items():
        assert rec['map']['editor_origin'] == {'atlas_id': result.id, 'node_id': key}
        assert all(p['child_id'] in result.maps for p in rec['pins'])
    result.map['tiles'][(1, 1)]['type'] = 'Door'
    result.map['artwork']['elements'][0]['color'] = '#ffffff'
    atomic_write_json(tmp_path / 'copy.json', result.encode())
    assert path.read_bytes() == before
    assert source.map['tiles'][(1, 1)]['type'] == 'Wall'
    assert read_atlas(path).map['artwork']['elements'][0]['color'] == '#223344'


def editor(purpose):
    obj = object.__new__(MapEditorScreen)
    obj.purpose = purpose
    obj.atlas = Atlas(name='Testwelt')
    obj.map_data = obj.atlas.map
    obj._undo, obj._redo = [], []
    obj._gesture = None
    obj._editing = False
    obj._library_last_id = None
    obj.dirty = False
    obj.app = SimpleNamespace(edited_map_data={'old': True}, game_manager=object(), go_back_screen=lambda: None)
    return obj


def test_standalone_save_and_back_do_not_hand_map_to_campaign_or_read_party():
    obj = editor('library')
    obj.app.edited_map_data = None
    obj._persist = lambda **kwargs: True
    before = copy.deepcopy(obj.map_data)
    assert obj.map_with_characters() == before  # game_manager has no attributes at all
    obj.save_map()
    obj.go_back()
    assert obj.app.edited_map_data is None
    assert not obj._editing


def test_preparation_keeps_its_party_instead_of_using_unrelated_game_manager():
    obj = editor('preparation')
    obj.map_data['offline_players'] = [{'name': 'Eigene Gruppe'}]
    data = obj.map_with_characters()
    data['offline_players'][0]['name'] = 'Verändert'
    assert obj.map_data['offline_players'][0]['name'] == 'Eigene Gruppe'


def test_entry_clears_previous_atlas_and_pending_handoff():
    obj = editor('session')
    obj._undo = [{'old': True}]
    incoming = Atlas(name='Vorbereitung').map
    assert obj.begin_edit('preparation', incoming)
    assert obj.atlas is None
    assert obj.preloaded_map_data == incoming
    assert obj.preloaded_map_data is not incoming
    assert obj.app.edited_map_data is None
    assert obj._undo == []
    assert obj._atlas_folder() == 'atlases'
    assert obj.begin_edit('library')
    assert obj.preloaded_map_data is None
    assert obj._atlas_folder() == 'map_library'


def test_failed_save_does_not_switch_context():
    obj = editor('session')
    obj._editing = True
    previous = obj.atlas
    obj._persist = lambda: False
    assert not obj.begin_edit('library')
    assert obj.purpose == 'session' and obj.atlas is previous


def test_preparation_party_survives_map_replacement_and_navigation():
    obj = editor('preparation')
    incoming = Atlas().map
    incoming['offline_players'] = [Character('Eigene Gruppe', 'Mensch', 'Kämpfer').to_dict()]
    obj.begin_edit('preparation', incoming)
    obj.atlas = tree().duplicate()
    obj.map_data = obj.atlas.map
    assert obj.map_with_characters()['offline_players'][0]['name'] == 'Eigene Gruppe'
    obj.atlas.navigate(obj.atlas.root_id)
    obj.map_data = obj.atlas.map
    assert obj.map_with_characters()['offline_players'][0]['name'] == 'Eigene Gruppe'


def test_missing_last_template_does_not_block_library():
    obj = editor('session')
    obj._library_last_id = 'f' * 32
    errors = []
    obj._error = errors.append
    assert obj.begin_edit('library')
    assert errors and obj._library_last_id is None
    assert obj.atlas is None and obj.purpose == 'library'


def test_bad_preload_returns_without_replacing_campaign(monkeypatch):
    obj = editor('preparation')
    obj.preloaded_map_data = {'invalid': True}
    obj._build_controls = lambda: None
    errors, queued = [], []
    obj._error = errors.append
    obj.load_existing_map = lambda _: (_ for _ in ()).throw(ValueError('beschädigt'))
    monkeypatch.setattr('ui.map_editor_tools.Clock.schedule_once', lambda action, delay: queued.append(action))
    obj.on_pre_enter()
    assert errors and queued
    assert obj.atlas is None and obj.preloaded_map_data is None
    assert obj.app.edited_map_data is None and not obj._editing


def test_unused_draft_is_not_saved_but_explicit_save_is_allowed(tmp_path, monkeypatch):
    obj = editor('library')
    monkeypatch.setattr('ui.map_editor_tools.get_user_saves_dir', lambda _: str(tmp_path))
    assert obj._persist()
    assert not list(tmp_path.iterdir())
    assert obj._persist(current_map=True)
    assert (tmp_path / (obj.atlas.id + '.json')).exists()


def test_first_save_requests_name_without_mutating_cancelled_draft():
    obj = editor('library')
    obj.atlas.current()['name'] = 'Unbenannte Welt'
    before = obj.atlas.encode()
    prompts = []
    obj._prompt = lambda title, initial, callback: prompts.append(callback)
    obj._map_details = lambda title, initial, scale, callback: prompts.append(lambda name: callback(name, scale, ''))
    obj._persist = lambda **kwargs: pytest.fail('Must wait for a name')
    assert obj.save_map() is False
    assert prompts and obj.atlas.encode() == before


def test_failed_first_save_restores_name_and_keeps_draft():
    obj = editor('library')
    obj.atlas.current()['name'] = 'Unbenannte Welt'
    obj.selected_id = ''
    obj._activate = lambda **kwargs: None
    obj._live = lambda _: None
    obj._persist = lambda **kwargs: False
    prompts = []
    obj._prompt = lambda title, initial, callback: prompts.append(callback)
    obj._map_details = lambda title, initial, scale, callback: prompts.append(lambda name: callback(name, scale, ''))
    obj.save_map()
    with pytest.raises(ValueError, match='Speichern fehlgeschlagen'):
        prompts[0]('Gewünschter Name')
    assert obj.atlas.current()['name'] == 'Unbenannte Welt'
    assert obj._needs_name()


def test_save_as_write_error_keeps_source_identity_and_content(monkeypatch):
    obj = editor('library')
    before = obj.atlas.encode()
    original = obj.atlas
    prompts = []
    obj._prompt = lambda title, initial, callback: prompts.append(callback)
    obj._map_details = lambda title, initial, scale, callback: prompts.append(lambda name: callback(name, scale, ''))
    monkeypatch.setattr('ui.map_editor_tools.atomic_write_json',
                        lambda *args: (_ for _ in ()).throw(OSError('Datenträger voll')))
    obj.save_as()
    with pytest.raises(OSError):
        prompts[0]('Kopie')
    assert obj.atlas is original and obj.atlas.encode() == before
