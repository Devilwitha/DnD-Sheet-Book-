"""Persistent campaign planning layered onto the existing local journal."""
import json
import sqlite3
import uuid
from utils.session_archive import SessionArchive, NOTE_FIELDS, dump, now, text
from utils.formats import encode_session, decode_session
from utils.storage import _check_chain


class CampaignStore(SessionArchive):
    def __init__(self):
        super().__init__()
        with self.connect() as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='campaigns'").fetchone()
            if not exists and db.execute('SELECT 1 FROM sessions LIMIT 1').fetchone():
                backup = self.path.with_name('vor-kampagnen-' + uuid.uuid4().hex[:12] + '.sqlite3')
                _check_chain(backup)
                target = sqlite3.connect(backup)
                try:
                    db.backup(target)
                finally:
                    target.close()
            db.executescript('''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '', created TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS preparations (
                    id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id),
                    title TEXT NOT NULL, scheduled TEXT NOT NULL DEFAULT '',
                    data TEXT NOT NULL, updated TEXT NOT NULL,
                    source_session_id TEXT REFERENCES sessions(id),
                    session_id TEXT UNIQUE REFERENCES sessions(id));
                CREATE TABLE IF NOT EXISTS campaign_sessions (
                    session_id TEXT PRIMARY KEY REFERENCES sessions(id),
                    campaign_id TEXT NOT NULL REFERENCES campaigns(id));
            ''')
            # Existing journal entries keep their IDs, snapshots and original labels.
            for row in db.execute('''SELECT s.id,s.campaign FROM sessions s LEFT JOIN campaign_sessions c
                                     ON c.session_id=s.id WHERE c.session_id IS NULL''').fetchall():
                cid = self._campaign_id(db, row['campaign'])
                db.execute('INSERT INTO campaign_sessions VALUES(?,?)', (row['id'], cid))

    @staticmethod
    def _campaign_id(db, name):
        row = db.execute('SELECT id FROM campaigns WHERE name=?', (name,)).fetchone()
        if row:
            return row[0]
        cid = str(uuid.uuid4())
        db.execute('INSERT INTO campaigns VALUES(?,?,?,?)', (cid, name, '', now()))
        return cid

    def create_campaign(self, name, description=''):
        name = text(name.strip(), 200)
        if not name:
            raise ValueError('Bitte einen Kampagnennamen eingeben.')
        with self.connect() as db:
            if db.execute('SELECT 1 FROM campaigns WHERE name=?', (name,)).fetchone():
                raise ValueError('Diese Kampagne ist bereits vorhanden.')
            cid = self._campaign_id(db, name)
            db.execute('UPDATE campaigns SET description=? WHERE id=?', (text(description), cid))
        return cid

    def campaign_list(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM campaigns ORDER BY name COLLATE NOCASE')]

    def campaign(self, cid):
        with self.connect() as db:
            row = db.execute('SELECT * FROM campaigns WHERE id=?', (cid,)).fetchone()
        if not row:
            raise ValueError('Kampagne nicht gefunden.')
        return dict(row)

    def campaign_history(self, cid):
        with self.connect() as db:
            return [dict(r) for r in db.execute('''SELECT s.* FROM sessions s JOIN campaign_sessions c
                ON c.session_id=s.id WHERE c.campaign_id=? ORDER BY s.updated DESC,s.id''', (cid,))]

    def plans(self, cid):
        with self.connect() as db:
            return [dict(r) for r in db.execute('''SELECT p.*,s.ended FROM preparations p
                LEFT JOIN sessions s ON p.session_id=s.id WHERE campaign_id=? ORDER BY p.updated DESC,p.id''', (cid,))]

    @staticmethod
    def _payload(data):
        clean = dict(data or {})
        for key in ('archive_id', '_plan_id'):
            clean.pop(key, None)
        normalized = encode_session(clean)
        result = dump(normalized)
        if len(result.encode('utf-8')) > 16 * 1024 * 1024:
            raise ValueError('Die Vorbereitung ist größer als 16 MiB.')
        return result

    def create_plan(self, cid, title='Neuer Spielabend', scheduled='', data=None, source_sid=None):
        self.campaign(cid)
        title = text(title.strip(), 200)
        if not title:
            raise ValueError('Bitte einen Namen für den Spielabend eingeben.')
        payload = self._payload(data)
        pid = str(uuid.uuid4())
        with self.connect() as db:
            db.execute('INSERT INTO preparations VALUES(?,?,?,?,?,?,?,NULL)',
                       (pid, cid, title, text(scheduled, 80), payload, now(), source_sid))
        return pid

    def plan(self, pid):
        with self.connect() as db:
            row = db.execute('SELECT * FROM preparations WHERE id=?', (pid,)).fetchone()
        if not row:
            raise ValueError('Vorbereitung nicht gefunden.')
        result = dict(row)
        result['data'] = decode_session(json.loads(result['data']))
        return result

    def save_plan(self, pid, title, scheduled, data):
        title = text(title.strip(), 200)
        if not title:
            raise ValueError('Bitte den Spielabend benennen.')
        payload = self._payload(data)
        with self.connect() as db:
            changed = db.execute('''UPDATE preparations SET title=?,scheduled=?,data=?,updated=?
                WHERE id=? AND session_id IS NULL''', (title, text(scheduled, 80), payload, now(), pid)).rowcount
            if not changed:
                raise ValueError('Diese Vorbereitung wurde bereits gestartet oder ist nicht mehr vorhanden.')

    def delete_plan(self, pid):
        with self.connect() as db:
            if not db.execute('DELETE FROM preparations WHERE id=? AND session_id IS NULL', (pid,)).rowcount:
                raise ValueError('Nur ungestartete Vorbereitungen können hier gelöscht werden.')

    def start_plan(self, pid):
        # Link and journal creation commit together. Repeated starts return the same journal.
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            p = db.execute('SELECT * FROM preparations WHERE id=?', (pid,)).fetchone()
            if not p:
                raise ValueError('Vorbereitung nicht gefunden.')
            if p['session_id']:
                return p['session_id']
            campaign = db.execute('SELECT name FROM campaigns WHERE id=?', (p['campaign_id'],)).fetchone()[0]
            data = json.loads(p['data'])
            notes = {k: text(data.get(k, '')) for k in NOTE_FIELDS}
            sid, stamp = str(uuid.uuid4()), now()
            db.execute('INSERT INTO sessions(id,campaign,title,started,updated,notes,search) VALUES(?,?,?,?,?,?,?)',
                       (sid, campaign, p['title'], stamp, stamp, dump(notes),
                        '\n'.join([campaign, p['title'], *notes.values()]).casefold()))
            snapshot = dump(encode_session({**data, 'archive_id': sid}))
            db.execute('UPDATE sessions SET latest_snapshot=? WHERE id=?', (snapshot, sid))
            db.execute('INSERT INTO campaign_sessions VALUES(?,?)', (sid, p['campaign_id']))
            db.execute('UPDATE preparations SET session_id=?,updated=? WHERE id=?', (sid, stamp, pid))
        return sid

    def next_plan(self, sid, revision=None):
        source = self.get(sid)
        with self.connect() as db:
            link = db.execute('SELECT campaign_id FROM campaign_sessions WHERE session_id=?', (sid,)).fetchone()
            cid = link[0] if link else self._campaign_id(db, source['campaign'])
            db.execute('INSERT OR IGNORE INTO campaign_sessions VALUES(?,?)', (sid, cid))
        # Only explicitly persistent party state is carried forward, never an old encounter/turn/log.
        data = {}
        if source['latest_snapshot']:
            snapshot = self.load_snapshot(sid, revision)
            data = {k: snapshot[k] for k in ('online_players', 'offline_players') if k in snapshot}
        data.update({k: source['notes'].get(k, '') for k in ('quests', 'npcs', 'next_steps')})
        previous = source['notes'].get('summary', '')
        data['notes'] = ('Rückblick des vorherigen Abends:\n' + previous) if previous else ''
        return self.create_plan(cid, ('Nach ' + source['title'])[:200], data=data, source_sid=sid)
