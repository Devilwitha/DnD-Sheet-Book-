"""Local campaign journal. Events and manual snapshots are never truncated or replaced."""
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

from utils.paths import get_user_saves_dir
from utils.storage import _check_chain, read_json, safe_save_path
from utils.formats import encode_session, decode_session

NOTE_FIELDS = {'summary': 'Zusammenfassung', 'decisions': 'Entscheidungen',
               'quests': 'Offene Aufgaben', 'npcs': 'Wichtige NPCs',
               'next_steps': 'Nächster Spielabend', 'notes': 'Freie DM-Notizen'}


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def dump(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False)


def text(value, limit=65536):
    if not isinstance(value, str) or len(value) > limit or '\x00' in value:
        raise ValueError(f'Text ist ungültig oder länger als {limit} Zeichen.')
    return value


class SessionArchive:
    def __init__(self):
        self.path = Path(get_user_saves_dir('archive')) / 'sitzungsarchiv.sqlite3'
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, campaign TEXT NOT NULL, title TEXT NOT NULL,
                    started TEXT NOT NULL, updated TEXT NOT NULL, ended TEXT,
                    notes TEXT NOT NULL, participants TEXT NOT NULL DEFAULT '[]',
                    search TEXT NOT NULL, latest_snapshot TEXT);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id),
                    time TEXT NOT NULL, actor TEXT NOT NULL, kind TEXT NOT NULL,
                    message TEXT NOT NULL, search TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS events_session ON events(session_id, id);
                CREATE TABLE IF NOT EXISTS revisions (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                    time TEXT NOT NULL, label TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS revisions_session ON revisions(session_id, time);
                CREATE TABLE IF NOT EXISTS note_versions (
                    id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                    time TEXT NOT NULL, metadata TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS imports (fingerprint TEXT PRIMARY KEY, session_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS rejected_events (
                    id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                    time TEXT NOT NULL, payload TEXT NOT NULL, error TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        _check_chain(self.path)
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA synchronous=FULL')
            with db:
                yield db
        finally:
            db.close()

    def create(self, campaign='', title='', notes=None):
        sid, stamp = str(uuid.uuid4()), now()
        campaign = text(campaign.strip() or 'Ohne Kampagne', 200)
        title = text(title.strip() or f'Sitzung {stamp[:10]}', 200)
        notes = {k: text((notes or {}).get(k, '')) for k in NOTE_FIELDS}
        with self.connect() as db:
            db.execute('INSERT INTO sessions(id,campaign,title,started,updated,notes,search) VALUES(?,?,?,?,?,?,?)',
                       (sid, campaign, title, stamp, stamp, dump(notes),
                        '\n'.join([campaign, title, *notes.values()]).casefold()))
        return sid

    def get(self, sid):
        with self.connect() as db:
            row = db.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
        if row is None:
            raise ValueError('Die Sitzung wurde im lokalen Archiv nicht gefunden.')
        out = dict(row)
        out['notes'] = json.loads(out['notes'])
        out['participants'] = json.loads(out['participants'])
        return out

    def edit(self, sid, campaign, title, notes):
        campaign, title = text(campaign.strip(), 200), text(title.strip(), 200)
        if not campaign or not title:
            raise ValueError('Bitte Kampagne und Sitzungsname angeben.')
        notes = {k: text(notes.get(k, '')) for k in NOTE_FIELDS}
        with self.connect() as db:
            previous = self._meta(db, sid)
            if (campaign, title, notes) == (previous['campaign'], previous['title'], previous['notes']):
                return
            db.execute('INSERT INTO note_versions(session_id,time,metadata) VALUES(?,?,?)',
                       (sid, now(), dump({k: previous[k] for k in ('campaign', 'title', 'notes')})))
            db.execute('UPDATE sessions SET campaign=?,title=?,notes=?,search=?,updated=? WHERE id=?',
                       (campaign, title, dump(notes), '\n'.join([campaign, title, *notes.values()]).casefold(), now(), sid))

    def append(self, sid, message, actor='System', kind='Spiel', timestamp=None):
        message, actor, kind = text(message), text(actor, 200), text(kind, 60)
        with self.connect() as db:
            db.execute('INSERT INTO events(session_id,time,actor,kind,message,search) VALUES(?,?,?,?,?,?)',
                       (sid, timestamp or now(), actor, kind, message, (actor+'\n'+message).casefold()))
            db.execute('UPDATE sessions SET updated=? WHERE id=?', (now(), sid))

    def campaigns(self):
        with self.connect() as db:
            return [r[0] for r in db.execute('SELECT DISTINCT campaign FROM sessions ORDER BY campaign')]

    def quarantine_event(self, sid, event, error):
        """Preserve rejected input in full, outside the normal event schema."""
        payload = dump(list(event))
        if len(payload.encode('utf8')) > 16 * 1024 * 1024:
            raise OSError('Journaleintrag zu groß für die Fehlersicherung; bleibt ausstehend.')
        with self.connect() as db:
            db.execute('INSERT INTO rejected_events(session_id,time,payload,error) VALUES(?,?,?,?)',
                       (sid, now(), payload, str(error)[:1000]))

    def rejected_event_count(self, sid):
        with self.connect() as db:
            return db.execute('SELECT count(*) FROM rejected_events WHERE session_id=?', (sid,)).fetchone()[0]

    def sessions(self, query='', campaign=None, offset=0, limit=50):
        query = text(query, 500).casefold()
        with self.connect() as db:
            return [dict(r) for r in db.execute('''SELECT id,campaign,title,started,updated,ended FROM sessions s
                WHERE (? IS NULL OR campaign=?) AND (?='' OR instr(search,?)>0 OR
                EXISTS(SELECT 1 FROM events e WHERE e.session_id=s.id AND instr(e.search,?)>0))
                ORDER BY updated DESC,id LIMIT ? OFFSET ?''',
                (campaign, campaign, query, query, query, limit, offset))]

    def events(self, sid, query='', offset=0, limit=100):
        with self.connect() as db:
            args = (sid, text(query, 500).casefold())
            count = db.execute('SELECT count(*) FROM events WHERE session_id=? AND instr(search,?)>0', args).fetchone()[0]
            rows = db.execute('SELECT * FROM events WHERE session_id=? AND instr(search,?)>0 ORDER BY id LIMIT ? OFFSET ?',
                              (*args, limit, offset)).fetchall()
            return count, [dict(r) for r in rows]

    def iter_events(self, sid):
        with self.connect() as db:
            for row in db.execute('SELECT * FROM events WHERE session_id=? ORDER BY id', (sid,)):
                yield dict(row)

    def snapshot(self, sid, data, label=None):
        payload, names = self._archive_payload(sid, data)
        rid = str(uuid.uuid4()) if label is not None else None
        with self.connect() as db:
            names.update(self._meta(db, sid)['participants'])  # no latest_snapshot fetch
            db.execute('UPDATE sessions SET latest_snapshot=?,participants=?,updated=? WHERE id=?',
                       (payload, dump(sorted(names)), now(), sid))
            if rid:
                db.execute('INSERT INTO revisions VALUES(?,?,?,?,?)', (rid, sid, now(), text(label, 200), payload))
        return rid

    def revisions(self, sid):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,time,label FROM revisions WHERE session_id=? ORDER BY rowid DESC', (sid,))]

    def load_snapshot(self, sid, revision=None):
        with self.connect() as db:
            if revision:
                row = db.execute('SELECT payload FROM revisions WHERE session_id=? AND id=?', (sid, revision)).fetchone()
            else:
                row = db.execute('SELECT latest_snapshot FROM sessions WHERE id=?', (sid,)).fetchone()
        if not row or not row[0]:
            raise ValueError('Für diese Sitzung ist noch kein Spielstand vorhanden.')
        return decode_session(json.loads(row[0]))

    def _meta(self, db, sid):
        """Read only the lightweight metadata columns (never the large snapshot blob)."""
        row = db.execute('SELECT campaign,title,notes,participants FROM sessions WHERE id=?', (sid,)).fetchone()
        if row is None:
            raise ValueError('Die Sitzung wurde im lokalen Archiv nicht gefunden.')
        return {'campaign': row['campaign'], 'title': row['title'],
                'notes': json.loads(row['notes']), 'participants': json.loads(row['participants'])}

    def metadata(self, sid):
        with self.connect() as db:
            return self._meta(db, sid)

    @staticmethod
    def _archive_payload(sid, data):
        payload = dump(encode_session({**data, 'archive_id': sid}))
        if len(payload.encode('utf-8')) > 16 * 1024 * 1024:
            raise ValueError('Der Spielstand ist größer als 16 MiB; das Journal bleibt erhalten.')
        names = {p['name'] for p in data.get('online_players', []) + data.get('offline_players', [])}
        return payload, names

    def _insert_session(self, db, campaign, title, notes):
        sid, stamp = str(uuid.uuid4()), now()
        campaign = text(campaign.strip() or 'Ohne Kampagne', 200)
        title = text(title.strip() or f'Sitzung {stamp[:10]}', 200)
        notes = {k: text((notes or {}).get(k, '')) for k in NOTE_FIELDS}
        db.execute('INSERT INTO sessions(id,campaign,title,started,updated,notes,search) VALUES(?,?,?,?,?,?,?)',
                   (sid, campaign, title, stamp, stamp, dump(notes),
                    '\n'.join([campaign, title, *notes.values()]).casefold()))
        return sid

    def _insert_event(self, db, sid, message, actor='System', kind='Spiel', timestamp=None):
        message, actor, kind = text(message), text(actor, 200), text(kind, 60)
        db.execute('INSERT INTO events(session_id,time,actor,kind,message,search) VALUES(?,?,?,?,?,?)',
                   (sid, timestamp or now(), actor, kind, message, (actor + '\n' + message).casefold()))
        db.execute('UPDATE sessions SET updated=? WHERE id=?', (now(), sid))

    def finish(self, sid):
        with self.connect() as db:
            db.execute('UPDATE sessions SET ended=?,updated=? WHERE id=?', (now(), now(), sid))

    def reopen(self, sid):
        with self.connect() as db:
            db.execute('UPDATE sessions SET ended=NULL WHERE id=?', (sid,))

    def import_legacy(self):
        """Copy older save files into the archive once; never modify their originals."""
        imported, failures = 0, []
        for file in sorted(Path(get_user_saves_dir('sessions')).glob('*.json')):
            try:
                path = safe_save_path(get_user_saves_dir('sessions'), file.name)
                raw = read_json(path)
                data = decode_session(raw)
                # Encoded form is JSON-safe even with maps (tuple tile keys broke the old fingerprint).
                fingerprint = hashlib.sha256(dump(encode_session(raw)).encode('utf-8')).hexdigest()
                known = {fingerprint}
                if data.get('map_data') is None:
                    # Earlier versions hashed the decoded dict; only mapless saves could ever be recorded.
                    known.add(hashlib.sha256(dump(data).encode('utf-8')).hexdigest())
                # One connection == one transaction: either everything is imported or nothing.
                with self.connect() as db:
                    if data.get('archive_id') and db.execute(
                            'SELECT 1 FROM sessions WHERE id=?', (data['archive_id'],)).fetchone():
                        continue
                    marks = ','.join('?' * len(known))
                    if db.execute(f'SELECT 1 FROM imports WHERE fingerprint IN ({marks})', tuple(known)).fetchone():
                        continue
                    sid = self._insert_session(db, 'Importierte Sitzungen', file.stem[:200],
                                               {k: data.get(k, '') for k in NOTE_FIELDS})
                    self._insert_event(db, sid, 'Alter Spielstand importiert. Zeitstempel der alten Einträge sind unbekannt.',
                                       kind='Import')
                    if data.get('log'):
                        self._insert_event(db, sid, data['log'], actor='Altprotokoll', kind='Import')
                    payload, names = self._archive_payload(sid, data)
                    db.execute('UPDATE sessions SET latest_snapshot=?,participants=?,updated=? WHERE id=?',
                               (payload, dump(sorted(names)), now(), sid))
                    db.execute('INSERT INTO revisions VALUES(?,?,?,?,?)',
                               (str(uuid.uuid4()), sid, now(), 'Importierter Spielstand', payload))
                    db.execute('INSERT INTO imports VALUES(?,?)', (fingerprint, sid))
                imported += 1
            except (ValueError, TypeError, OSError, sqlite3.Error):
                failures.append(file.name)
        return imported, failures
