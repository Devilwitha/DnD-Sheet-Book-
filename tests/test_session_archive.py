import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from utils.session_archive import SessionArchive
from utils.archive_export import export_archive
from utils.formats import encode_session, decode_session
from utils.paths import get_user_saves_dir


@pytest.fixture
def archive(tmp_path, monkeypatch):
    monkeypatch.setenv('DND_DATA_DIR', str(tmp_path))
    return SessionArchive()


def test_full_journal_survives_restart_beyond_old_limit(archive):
    sid = archive.create('Die Küste', 'Abend 1')
    for i in range(80):
        archive.append(sid, f'Ereignis-{i} ' + 'x'*1200, 'Nara')
    restarted = SessionArchive()
    total, first = restarted.events(sid, limit=1)
    assert total == 80 and first[0]['message'].startswith('Ereignis-0 ')
    assert sum(len(e['message']) for e in restarted.iter_events(sid)) > 64000
    assert first[0]['actor'] == 'Nara' and '+' in first[0]['time']


def test_same_title_saves_are_distinct_and_old_revision_immutable(archive):
    sid = archive.create(title='Dungeon')
    first = archive.snapshot(sid, {'log': 'vorher'}, 'Abend')
    second = archive.snapshot(sid, {'log': 'nachher'}, 'Abend')
    archive.snapshot(sid, {'log': 'autosave'})
    assert first != second and len(archive.revisions(sid)) == 2
    assert archive.load_snapshot(sid, first)['log'] == 'vorher'
    assert archive.load_snapshot(sid, second)['log'] == 'nachher'
    assert archive.load_snapshot(sid)['log'] == 'autosave'
    assert archive.load_snapshot(sid)['archive_id'] == sid


def test_search_includes_old_events_notes_and_campaign_with_unicode(archive):
    sid = archive.create('Küste', 'Abend')
    archive.edit(sid, 'Küste', 'Abend', {'npcs': 'Händlerin Änne', 'next_steps': 'Am Tor warten'})
    archive.append(sid, "100% Beute _ gefunden; ' OR 1=1 --", 'Nara')
    other = archive.create('Berge', 'Abend')
    assert [r['id'] for r in archive.sessions('ÄNNE')] == [sid]
    assert [r['id'] for r in archive.sessions('100%')] == [sid]
    assert archive.sessions('Änne', campaign='Berge') == []
    assert [r['id'] for r in archive.sessions(campaign='Berge')] == [other]
    assert archive.events(sid, 'NARA')[0] == 1
    assert archive.events(sid, '%anything')[0] == 0


def test_notes_are_separate_from_player_session_payload_and_history_retained(archive):
    sid = archive.create()
    archive.edit(sid, 'Kampagne', 'Sitzung', {'notes': 'Geheimer Verräter'})
    archive.edit(sid, 'Kampagne', 'Sitzung', {'notes': 'Geheime Wendung'})
    archive.snapshot(sid, {})
    assert 'Geheime' not in json.dumps(archive.load_snapshot(sid))
    with archive.connect() as db:
        old = db.execute('SELECT metadata FROM note_versions WHERE session_id=? ORDER BY id DESC', (sid,)).fetchone()[0]
    assert 'Geheimer Verräter' in old


def test_import_legacy_is_idempotent_and_original_untouched(archive):
    from pathlib import Path
    path = Path(get_user_saves_dir('sessions')) / 'Alt.json'
    original = json.dumps({'log': 'Alte Heldentat', 'notes': 'Tor geöffnet'})
    path.write_text(original, encoding='utf8')
    assert archive.import_legacy() == (1, [])
    assert archive.import_legacy() == (0, [])
    assert path.read_text(encoding='utf8') == original
    sid = archive.sessions()[0]['id']
    assert 'Alte Heldentat' in ''.join(e['message'] for e in archive.iter_events(sid))
    assert archive.get(sid)['notes']['notes'] == 'Tor geöffnet'


def test_invalid_legacy_file_reported_without_stopping_good_imports(archive):
    from pathlib import Path
    folder = Path(get_user_saves_dir('sessions'))
    (folder/'bad.json').write_text('not json')
    (folder/'good.json').write_text('{}')
    assert archive.import_legacy() == (1, ['bad.json'])


def test_new_archived_save_not_duplicated_by_legacy_import(archive):
    from pathlib import Path
    sid = archive.create()
    path = Path(get_user_saves_dir('sessions'))/'new.json'
    path.write_text(json.dumps(encode_session({'archive_id': sid})))
    assert archive.import_legacy() == (0, [])
    assert len(archive.sessions()) == 1


def test_export_txt_includes_full_history_notes_and_safe_unique_path(archive):
    sid = archive.create(title='../../Üble: Namen')
    archive.edit(sid, 'Küste', '../../Üble: Namen', {'summary': 'Öl & Feuer', 'quests': 'Suche das Tor'})
    archive.append(sid, 'ERSTER '+ 'x'*64000, 'Nara')
    archive.append(sid, 'LETZTER')
    p = export_archive(archive, sid, 'txt')
    second = export_archive(archive, sid, 'txt')
    out = p.read_text(encoding='utf8')
    assert p != second and p.parent.name == 'Exporte'
    assert all(v in out for v in ['Öl & Feuer', 'Suche das Tor', 'ERSTER', 'LETZTER', 'Nara'])


def test_export_pdf_is_valid_and_escapes_markup(archive):
    from pypdf import PdfReader
    sid = archive.create('Küste', 'Drachen & Höhlen')
    archive.edit(sid, 'Küste', 'Drachen & Höhlen', {'npcs': 'Änne <img src="file:///private"> & Bösewicht'})
    for i in range(120):
        archive.append(sid, f'JOURNAL-{i}: Überquerung der Brücke.', 'Nara')
    output = export_archive(archive, sid, 'pdf')
    reader = PdfReader(output)
    whole = '\n'.join(page.extract_text() for page in reader.pages)
    assert len(reader.pages) >= 3
    assert 'JOURNAL-0:' in whole and 'JOURNAL-119:' in whole and 'Änne' in whole


def test_bad_save_does_not_replace_valid_checkpoint(archive):
    sid = archive.create()
    archive.snapshot(sid, {'log': 'gut'})
    with pytest.raises(ValueError):
        archive.snapshot(sid, {'log': 'x'*70000})
    assert archive.load_snapshot(sid)['log'] == 'gut'


def test_archive_id_validation_and_legacy_compatibility():
    assert 'archive_id' not in decode_session({})
    with pytest.raises(ValueError):
        decode_session({'archive_id': '../../untrusted'})


def test_end_reopen_preserves_history(archive):
    sid = archive.create()
    archive.append(sid, 'Vor langer Zeit')
    archive.finish(sid)
    assert archive.get(sid)['ended']
    archive.reopen(sid)
    assert archive.get(sid)['ended'] is None
    assert archive.events(sid)[1][0]['message'] == 'Vor langer Zeit'


def test_failed_journal_write_keeps_pending_entry_for_retry(archive, monkeypatch):
    from ui.archive_controller import ArchiveController
    controller = ArchiveController()
    controller.init_archive()
    controller._archive_store = archive
    controller.archive_id = archive.create()
    controller.archive_failed = MagicMock()
    append = archive.append
    monkeypatch.setattr(archive, 'append', MagicMock(side_effect=sqlite3.OperationalError('disk full')))
    controller.journal_message('Wichtige Entscheidung', 'Nara')
    assert len(controller._journal_pending) == 1
    assert controller.archive_failed.called
    stamp = controller._journal_pending[0][2]
    monkeypatch.setattr(archive, 'append', append)
    controller.flush_journal()
    assert controller._journal_pending == []
    entry = archive.events(controller.archive_id)[1][0]
    assert entry['message'] == 'Wichtige Entscheidung' and entry['time'] == stamp
