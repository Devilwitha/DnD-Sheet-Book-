"""DM integration for the durable journal, separate from the bounded on-screen preview."""
from datetime import datetime
from pathlib import Path
import sqlite3
from kivy.clock import Clock

from utils.session_archive import now, text
from utils.campaign_store import CampaignStore
from utils.storage import atomic_write_json, safe_save_path
from utils.paths import get_user_saves_dir
from utils.formats import encode_session


class ArchiveController:
    def init_archive(self):
        self.archive_id = None
        self._archive_store = None
        self._archive_timer = None
        self._journal_pending = []
        self._journal_actor = None
        self._archive_error = False

    @property
    def archive(self):
        if self._archive_store is None:
            self._archive_store = CampaignStore()
        return self._archive_store

    def archive_status(self, message, error=False):
        self._archive_error = error
        label = self.ids.get('archive_status') if hasattr(self.ids, 'get') else None
        if label is not None:
            label.text = message
            label.color = (1, .4, .3, 1) if error else (.75, .9, .75, 1)

    def archive_failed(self, exc):
        from utils.diagnostics import record_error
        record_error('session_archive', exc)
        self.archive_status('Archiv konnte nicht gespeichert werden. Bitte Speicherplatz prüfen und erneut speichern.', True)

    def ensure_journal(self, session=None):
        if self.archive_id:
            return
        session = session or {}
        requested = session.get('archive_id')
        planned = session.get('_plan_id')
        if planned and not requested:
            requested = self.archive.start_plan(planned)
        if requested:
            try:
                self.archive.get(requested)
            except ValueError:
                requested = None  # Imported saves must not point to a nonexistent local journal.
        if requested:
            self.archive_id = requested
            self.archive.reopen(requested)
            self.archive.append(requested, 'Vorbereiteter Spielabend gestartet.' if planned else 'Gespeicherte Sitzung wieder aufgenommen.', 'DM', 'Sitzung')
        else:
            title = f'Sitzung {datetime.now():%Y-%m-%d %H:%M}'
            try:
                title = self.app.sm.get_screen('dm_lobby').ids.session_name_input.text.strip() or title
            except (AttributeError, KeyError):
                pass
            self.archive_id = self.archive.create(title=title, notes={k: session.get(k, '') for k in ('notes', 'summary')})
            self.archive.append(self.archive_id, 'Sitzung gestartet.', 'DM', 'Sitzung')
            if session.get('log'):
                self.archive.append(self.archive_id, session['log'], 'Altprotokoll', 'Import ohne Originalzeitstempel')
        self.archive_status('Journal wird automatisch gespeichert. Archiv und DM-Notizen sind unter Leitung verfügbar.')
        if self._archive_timer is None:
            self._archive_timer = Clock.schedule_interval(lambda dt: self.checkpoint_archive(), 20)

    def journal_message(self, message, actor=None):
        # Older test doubles may lack archive initialization; production initializes it in __init__.
        if not hasattr(self, '_journal_pending'):
            return
        self._journal_pending.append((str(message), actor or self._journal_actor or 'Spielleitung', now()))
        try:
            self.ensure_journal()
            self.flush_journal()
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.archive_failed(exc)

    def flush_journal(self):
        while self._journal_pending:
            message, actor, timestamp = self._journal_pending[0]
            try:
                text(message)
                text(actor, 200)
            except ValueError as exc:
                self.archive.quarantine_event(self.archive_id, self._journal_pending[0], exc)
                self._journal_pending.pop(0)
                self.archive_status('Ungültiger Journaleintrag vollständig im Archiv zur Prüfung gesichert.', True)
                continue
            self.archive.append(self.archive_id, message, actor, timestamp=timestamp)
            self._journal_pending.pop(0)

    def session_snapshot(self):
        gm = self.game_manager
        return {**self.session_metadata,
                'online_players': list({**self.session_roster, **{p.character_id: p.to_dict() for p in
                                       list(gm.disconnected_players.values()) + list(gm.online_players.values())}}.values()),
                'offline_players': [p.to_dict() for p in gm.offline_players],
                'enemies': [e.to_dict() for e in gm.enemies], 'map_data': gm.map_data,
                'log': self.ids.log_output.text[-64000:], 'initiative_order': gm.initiative_order,
                'current_turn_index': gm.current_turn_index, 'turn_action_state': gm.turn_action_state}

    def checkpoint_archive(self, label=None, strict=False):
        if not getattr(self, 'archive_id', None):
            if not getattr(self, '_journal_pending', None):
                return
        try:
            self.ensure_journal()
            self.flush_journal()
            rid = self.archive.snapshot(self.archive_id, self.session_snapshot(), label)
            rejected = self.archive.rejected_event_count(self.archive_id)
            if rejected:
                self.archive_status(f'Spielstand gesichert · {rejected} ungültige Journaleinträge separat im Archiv erhalten.', True)
            else:
                self.archive_status(f'Journal dauerhaft gespeichert · Spielstand gesichert: {datetime.now():%H:%M:%S}')
            return rid
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.archive_failed(exc)
            if strict:
                raise

    def save_named_snapshot(self, name):
        self.ensure_journal()
        rid = self.checkpoint_archive(label=name, strict=True)
        # Unique filenames prevent accidental replacement of an earlier manual save.
        filename = f'{name}-{datetime.now():%Y%m%d-%H%M%S}-{rid}.json'
        path = safe_save_path(get_user_saves_dir('sessions'), filename)
        data = encode_session({**self.session_snapshot(), 'archive_id': self.archive_id})
        atomic_write_json(path, data)
        self.log_message(f'Spielstand „{name}“ als neue Version gespeichert.', actor='DM')
        return Path(path)

    def close_journal(self):
        if self._journal_pending and not self.archive_id:
            self.ensure_journal()
        if self.archive_id:
            self.log_message('Sitzung beendet und archiviert.', actor='DM')
            self.checkpoint_archive('Sitzungsende', strict=True)
            self.archive.finish(self.archive_id)
        self.detach_journal()

    def detach_journal(self):
        if self._archive_timer is not None:
            self._archive_timer.cancel()
            self._archive_timer = None
        self.archive_id = None

    def show_archive(self):
        from ui.session_archive_dialog import ArchiveBrowser
        try:
            self.ensure_journal()
            self.checkpoint_archive(strict=True)
            self.archive_browser = ArchiveBrowser(self.app, current_dm=self)
            self.archive_browser.open()
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.archive_failed(exc)

    def start_new_dm_session(self):
        if self.archive_id or self._journal_pending:
            self.checkpoint_archive('Vor neuer Sitzung', strict=True)
        self.detach_journal()
        self.app.dm_session_active = False
        from core.game_manager import GameManager
        self.game_manager = GameManager(logger_func=self.log_message)
        self.session_roster = {}
        self.session_metadata = {}
        self.ids.log_output.text = ''
        self.dm_selected_attacker = None
        self.action_mode = 'inspect'
