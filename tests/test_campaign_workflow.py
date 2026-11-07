import copy
from pathlib import Path
import pytest
from core.character import Character
from core.enemy import Enemy
from core.game_manager import GameManager
from utils.campaign_store import CampaignStore
from utils.session_archive import SessionArchive
from utils.session_recap import build_recap
from utils.formats import decode_session


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv('DND_DATA_DIR', str(tmp_path))
    return CampaignStore()


def test_preparation_restart_map_unicode_and_separate_campaigns(store):
    cid = store.create_campaign('Eigene Welt', 'Beschreibung')
    second = store.create_campaign('Zweite Welt')
    pid = store.create_plan(cid, 'Brücke', data={'notes': 'Privater Hinweis', 'map_data': {
        'rows': 2, 'cols': 2, 'tiles': {(0, 0): {'type': 'Floor', 'object': None, 'furniture': None}}}})
    store.save_plan(pid, 'Brücke II', 'Samstag 19:00', {**store.plan(pid)['data'], 'quests': 'Schlüssel suchen'})
    reopened = CampaignStore()
    plan = reopened.plan(pid)
    assert plan['title'] == 'Brücke II' and plan['scheduled'] == 'Samstag 19:00'
    assert plan['data']['notes'] == 'Privater Hinweis'
    assert (0, 0) in plan['data']['map_data']['tiles']
    assert reopened.plans(second) == [] and reopened.campaign_history(cid) == []
    assert not list(reopened.iter_events('missing'))


def test_legacy_migration_keeps_journal_and_backup(tmp_path, monkeypatch):
    monkeypatch.setenv('DND_DATA_DIR', str(tmp_path))
    legacy = SessionArchive()
    sid = legacy.create('Alte Welt', 'Alter Abend')
    legacy.append(sid, 'Entscheidung behalten')
    legacy.snapshot(sid, {'log': 'unverändert'}, 'Original')
    store = CampaignStore()
    assert len(store.campaign_list()) == 1
    assert store.campaign_history(store.campaign_list()[0]['id'])[0]['id'] == sid
    assert store.load_snapshot(sid)['log'] == 'unverändert'
    assert list(store.iter_events(sid))[0]['message'] == 'Entscheidung behalten'
    assert len(list(store.path.parent.glob('vor-kampagnen-*.sqlite3'))) == 1
    CampaignStore()
    assert len(list(store.path.parent.glob('vor-kampagnen-*.sqlite3'))) == 1


def test_plan_start_idempotent_and_next_evening_only_persistent_state(store):
    cid = store.create_campaign('Welt')
    char = Character('Mira', '', '')
    char.hit_points = 7
    char.max_hit_points = 12
    pid = store.create_plan(cid, 'Abend 1', data={'notes': 'DM-Geheimnis'})
    sid = store.start_plan(pid)
    assert store.start_plan(pid) == sid
    with pytest.raises(ValueError):
        store.save_plan(pid, 'überschreiben', '', {})
    with pytest.raises(ValueError):
        store.delete_plan(pid)
    store.snapshot(sid, {'online_players': [char.to_dict()], 'enemies': [Enemy('Altgegner', 9, 10, []).to_dict()],
        'initiative_order': [(5, 'Mira')], 'current_turn_index': 0, 'log': 'alter Kampf'})
    store.edit(sid, 'Welt', 'Abend 1', {'summary': 'Tor geöffnet', 'quests': 'Brücke finden', 'next_steps': 'Wald'})
    store.finish(sid)
    previous = copy.deepcopy(store.load_snapshot(sid))
    next_id = store.next_plan(sid)
    following = store.plan(next_id)
    assert following['source_session_id'] == sid and following['session_id'] is None
    data = following['data']
    assert data['online_players'][0]['hit_points'] == 7
    assert data['online_players'][0]['character_id'] == char.character_id
    assert data.get('enemies', []) == [] and not data.get('initiative_order')
    assert not data.get('log') and not data.get('archive_id')
    assert 'Tor geöffnet' in data['notes'] and data['quests'] == 'Brücke finden'
    assert store.load_snapshot(sid) == previous and store.get(sid)['ended']
    assert store.start_plan(next_id) != sid


def test_invalid_save_atomic_and_delete_only_draft(store):
    cid = store.create_campaign('Welt')
    pid = store.create_plan(cid, 'Gültig')
    with pytest.raises(ValueError):
        store.save_plan(pid, '', '', {})
    with pytest.raises(ValueError):
        store.save_plan(pid, 'Ungültig', '', {'notes': 'x' * 70000})
    assert store.plan(pid)['title'] == 'Gültig'
    store.delete_plan(pid)
    assert store.plans(cid) == []
    with pytest.raises(ValueError):
        store.plan(pid)


def test_plan_marker_survives_validation_but_no_archive_contamination(store):
    cid = store.create_campaign('Welt')
    pid = store.create_plan(cid)
    assert decode_session({'_plan_id': pid})['_plan_id'] == pid
    store.save_plan(pid, 'Neu', '', {'archive_id': 'wrong', '_plan_id': 'wrong'})
    assert 'archive_id' not in store.plan(pid)['data']
    assert '_plan_id' not in store.plan(pid)['data']


def test_recap_generator_bounded_chronological_no_input_mutation():
    events = ({'message': f'EREIGNIS-{i}: ' + 'x'*2000, 'actor': 'Mira'} for i in range(45))
    result = build_recap(events, ['Mira'])
    assert '15 frühere Ereignisse' in result
    assert 'EREIGNIS-0:' not in result
    assert result.index('EREIGNIS-15:') < result.index('EREIGNIS-44:')
    assert '[gekürzt]' in result and len(result) <= 12000
    assert 'Noch keine Spielereignisse' in build_recap(iter([]), None)


def test_raw_die_uses_host_bonus_once_and_preserves_manual_total():
    gm = GameManager(logger_func=lambda m: None)
    a = Enemy('A', 99, 10, [{'name': 'Biss', 'to_hit': 5, 'damage': '1d4'}])
    b = Enemy('B', 99, 12, [])
    gm.enemies = [a, b]
    raw = gm.handle_attack('A', 'B', natural_roll=8, damage_roll=2, dm_override=True)
    assert raw['hit'] and raw['attack_total'] == 13 and 'W20: 8' in raw['roll_detail']
    manual = gm.handle_attack('A', 'B', attack_roll=8, damage_roll=2, dm_override=True)
    assert not manual['hit'] and manual['attack_total'] == 8
    hp = b.hp
    for invalid in [True, 0, 21, '12', 1.5]:
        assert not gm.handle_attack('A', 'B', natural_roll=invalid, dm_override=True)['success']
    assert b.hp == hp

def test_prepared_party_uses_saved_lobby_values_and_does_not_share_private_summary(monkeypatch):
    import threading
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    import ui.dm_lobby_screen as module
    char = Character('Mira', '', '')
    saved = char.to_dict()
    char.level = 20
    addr = ('127.0.0.1', 45555)
    nm = SimpleNamespace(lock=threading.RLock(), clients={addr: {'character': char, 'approved': False}},
                         send_message=MagicMock(), kick_player=MagicMock())
    lobby = object.__new__(module.DMLobbyScreen)
    lobby.network_manager = nm
    lobby.app = SimpleNamespace(loaded_session_data=None,
        prepared_session_data={'online_players': [saved], 'summary': 'Privates Geheimnis'})
    lobby.add_player_to_list = MagicMock()
    approval = MagicMock()
    monkeypatch.setattr(module, 'ask_dm', approval)
    lobby.handle_new_player_connection(addr)
    assert nm.clients[addr]['character'].level == 1
    assert nm.clients[addr]['approved']
    approval.assert_not_called()
    assert 'Privates Geheimnis' not in str(nm.send_message.call_args_list)


def test_offline_party_member_rejoining_keeps_host_values():
    import threading
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from ui.dm_main_screen import DMMainScreen
    dm = object.__new__(DMMainScreen)
    gm = GameManager(logger_func=lambda m: None)
    saved = Character('Mira', '', '')
    saved.level = 4
    gm.offline_players = [saved]
    client = Character.from_dict(saved.to_dict())
    client.level = 20
    addr = ('127.0.0.1', 44444)
    dm.game_manager = gm
    dm.session_roster = {}
    dm.network_manager = SimpleNamespace(lock=threading.RLock(),
        clients={addr: {'character': client, 'approved': True}}, kick_player=MagicMock())
    dm.sync_online_players()
    assert gm.online_players['Mira'].level == 4
    assert gm.offline_players == []
    assert dm.session_roster[saved.character_id]['level'] == 4
    dm.network_manager.kick_player.assert_not_called()


def test_next_plan_respects_selected_revision(store):
    cid = store.create_campaign('Revisionen')
    sid = store.start_plan(store.create_plan(cid))
    hero = Character('Mira', '', '')
    hero.hit_points = hero.max_hit_points = 10
    revision = store.snapshot(sid, {'offline_players': [hero.to_dict()]}, 'Vorher')
    hero.hit_points = 2
    store.snapshot(sid, {'offline_players': [hero.to_dict()]})
    pid = store.next_plan(sid, revision)
    assert store.plan(pid)['data']['offline_players'][0]['hit_points'] == 10
    assert store.load_snapshot(sid)['offline_players'][0]['hit_points'] == 2

def test_player_raw_die_message_roundtrip_uses_host_only():
    from tests.test_character_authority import setup_host
    from utils.wire import encode_message
    dm, addr, char = setup_host()
    dm.game_manager.map_data = None
    char.abilities['Stärke'] = 16
    char.level = 5
    char.equipped_weapon = 'Unbewaffneter Schlag'
    message = {'type': 'PLAYER_ATTACK', 'payload': {'type': 'dice', 'd20': 12,
        'enemy_name': 'Goblin #1', 'damage': 1, 'attack_roll': 100, 'bonus': 999}}
    assert encode_message(message)
    dm._handle_network_item((addr, message))
    replies = dm.network_manager.send_message.call_args_list
    result = next(c.args[2] for c in replies if c.args[1] == 'ACTION_RESULT')
    assert 'W20: 12' in result['message'] and 'Angriffsbonus: +6' in result['message']
    assert 'Gesamt: 18' in result['message']
    assert dm.game_manager.enemies[0].hp == 29
