import hashlib
import json

import pytest

from utils import session_archive as sa
from utils.formats import decode_session

MAP = {'format': 'dnd-map', 'version': 1, 'rows': 2, 'cols': 2,
       'tiles': [{'row': 0, 'col': 0, 'tile': {'type': 'Floor'}}]}


@pytest.fixture
def archive(tmp_path, monkeypatch):
    def saves(name):
        p = tmp_path / name
        p.mkdir(exist_ok=True)
        return str(p)
    monkeypatch.setattr(sa, 'get_user_saves_dir', saves)
    monkeypatch.setattr(sa, '_check_chain', lambda path: None)
    return sa.SessionArchive()


def write(tmp_path, name, data):
    d = tmp_path / 'sessions'
    d.mkdir(exist_ok=True)
    p = d / name
    p.write_text(data if isinstance(data, str) else json.dumps(data), encoding='utf-8')
    return p


def count(archive, table):
    with archive.connect() as db:
        return db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]


def test_map_save_imports_once_and_source_untouched(archive, tmp_path):
    p = write(tmp_path, 'karte.json', {'notes': 'n', 'log': 'hi', 'map_data': MAP})
    before = p.read_bytes()
    assert archive.import_legacy() == (1, [])
    assert archive.import_legacy() == (0, [])
    assert count(archive, 'sessions') == 1
    assert p.read_bytes() == before


def test_previously_imported_mapless_save_is_not_duplicated(archive, tmp_path):
    raw = {'notes': 'x', 'log': 'hello'}
    write(tmp_path, 'alt.json', raw)
    old_fp = hashlib.sha256(json.dumps(decode_session(raw), ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()
    with archive.connect() as db:
        db.execute('INSERT INTO imports VALUES(?,?)', (old_fp, 'legacy-session'))
    assert archive.import_legacy() == (0, [])
    assert count(archive, 'sessions') == 0


def test_failure_rolls_back_whole_import_and_retry_succeeds(archive, tmp_path, monkeypatch):
    write(tmp_path, 'a.json', {'notes': 'x', 'log': 'l'})
    original = sa.SessionArchive._archive_payload

    def boom(sid, data):
        raise ValueError('boom')
    monkeypatch.setattr(sa.SessionArchive, '_archive_payload', staticmethod(boom))
    assert archive.import_legacy() == (0, ['a.json'])
    assert (count(archive, 'sessions'), count(archive, 'events'), count(archive, 'imports')) == (0, 0, 0)
    monkeypatch.setattr(sa.SessionArchive, '_archive_payload', staticmethod(original))
    assert archive.import_legacy() == (1, [])
    assert count(archive, 'sessions') == 1 and count(archive, 'imports') == 1
    assert count(archive, 'revisions') == 1


def test_bad_file_is_reported_without_stopping_others(archive, tmp_path):
    write(tmp_path, 'a-bad.json', '{')
    write(tmp_path, 'b-good.json', {'notes': 'ok'})
    assert archive.import_legacy() == (1, ['a-bad.json'])


def test_edit_and_snapshot_do_not_load_latest_snapshot(archive, monkeypatch):
    sid = archive.create('C', 'T')

    def no_get(self, sid):
        raise AssertionError('get() would fetch latest_snapshot')
    monkeypatch.setattr(sa.SessionArchive, 'get', no_get)
    archive.edit(sid, 'C', 'T2', {})
    assert archive.metadata(sid)['title'] == 'T2'
    archive.snapshot(sid, {'online_players': [{'name': 'Ann', 'race': 'Elf', 'char_class': 'Magier'}],
                           'offline_players': []})
    assert archive.metadata(sid)['participants'] == ['Ann']
    with pytest.raises(ValueError):
        archive.edit('missing', 'C', 'T', {})
