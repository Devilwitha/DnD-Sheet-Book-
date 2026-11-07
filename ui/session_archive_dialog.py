"""Offline archive browser: readable notes, full-text search and versioned game states."""
from datetime import datetime
import os
import sys
import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from utils.session_archive import NOTE_FIELDS
from utils.campaign_store import CampaignStore
from utils.archive_export import export_archive


def button(text, callback, height=48):
    obj = Button(text=text, size_hint_y=None, height=dp(height), halign='center', valign='middle')
    obj.bind(size=lambda w, s: setattr(w, 'text_size', (s[0]-dp(12), s[1])))
    obj.bind(on_release=callback)
    return obj


def label(text, height=48):
    obj = Label(text=text, size_hint_y=None, height=dp(height), halign='left', valign='middle')
    obj.bind(size=lambda w, s: setattr(w, 'text_size', (s[0]-dp(8), s[1])))
    return obj


def reading_view(text=''):
    obj = TextInput(text=text, readonly=True, font_size=dp(16), padding=(dp(12), dp(12)),
                    background_color=(.13, .14, .16, 1), foreground_color=(.94, .94, .94, 1))
    def top(dt):
        obj.cursor = (0, 0)
        obj.scroll_y = 0
    obj.bind(text=lambda *_: Clock.schedule_once(top, 0))
    Clock.schedule_once(top, 0)
    return obj


class ArchiveBrowser(Popup):
    def __init__(self, app, current_dm=None, **kwargs):
        super().__init__(title='Sitzungsarchiv', size_hint=(.96, .96), auto_dismiss=False, **kwargs)
        self.app, self.current_dm = app, current_dm
        self.archive = current_dm.archive if current_dm else CampaignStore()
        self.sid = current_dm.archive_id if current_dm else None
        self.offset, self.event_offset = 0, 0
        self.query, self.campaign = '', None
        self.journal_query = ''
        self.export_busy = False
        self.content = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(8))
        self.body = BoxLayout(orientation='vertical', spacing=dp(8))
        self.status = label('', 50)
        self.content.add_widget(self.body)
        self.content.add_widget(self.status)
        self.content.add_widget(button('Zurück zum Spiel' if current_dm else 'Archiv schließen', self.dismiss))
        if self.sid:
            self.detail(self.sid)
        else:
            self.show_list()

    def error(self, exc):
        self.status.text = f'Nicht gespeichert / Aktion fehlgeschlagen: {exc}'
        self.status.color = (1, .45, .35, 1)

    def safely(self, operation):
        try:
            operation()
        except Exception as exc:
            self.error(exc)

    def message(self, text):
        self.status.color = (.8, .92, .8, 1)
        self.status.text = text

    def show_list(self):
        self.body.clear_widgets()
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.search = TextInput(text=self.query, hint_text='Kampagne, Notizen oder Journal durchsuchen', multiline=False)
        row.add_widget(self.search)
        row.add_widget(button('Suchen', lambda *_: self.search_sessions()))
        self.body.add_widget(row)
        self.campaign_choice = Spinner(text=self.campaign or 'Alle Kampagnen',
                                       values=['Alle Kampagnen', *self.archive.campaigns()], size_hint_y=None, height=dp(48))
        self.campaign_choice.bind(text=lambda w, v: self.filter_campaign(v))
        self.body.add_widget(self.campaign_choice)
        self.results = GridLayout(cols=1, size_hint_y=None, spacing=dp(6))
        self.results.bind(minimum_height=self.results.setter('height'))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.results)
        self.body.add_widget(scroll)
        pager = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.previous = button('Vorherige', lambda *_: self.page_sessions(-50))
        self.next = button('Weitere', lambda *_: self.page_sessions(50))
        pager.add_widget(self.previous)
        pager.add_widget(self.next)
        self.body.add_widget(pager)
        self.body.add_widget(button('Ältere gespeicherte Sitzungen ins Archiv übernehmen', lambda *_: self.safely(self.import_old)))
        self.refresh_results()

    def filter_campaign(self, value):
        self.campaign = None if value == 'Alle Kampagnen' else value
        self.offset = 0
        self.safely(self.refresh_results)

    def search_sessions(self):
        self.query = self.search.text.strip()
        self.offset = 0
        self.safely(self.refresh_results)

    def page_sessions(self, delta):
        self.offset = max(0, self.offset+delta)
        self.safely(self.refresh_results)

    def refresh_results(self):
        rows = self.archive.sessions(self.query, self.campaign, self.offset, 51)
        self.results.clear_widgets()
        for item in rows[:50]:
            caption = f"{item['campaign']} · {item['title']}\n{item['started'][:10]} · {'Abgeschlossen' if item['ended'] else 'Offen / vorbereitet'}"
            self.results.add_widget(button(caption, lambda _, sid=item['id']: self.safely(lambda: self.detail(sid)), 76))
        self.previous.disabled = self.offset == 0
        self.next.disabled = len(rows) <= 50
        self.message(f'{len(rows[:50])} Sitzungen angezeigt.' if rows else 'Noch keine Treffer. Ältere Spielstände können unten übernommen werden.')

    def import_old(self):
        count, failures = self.archive.import_legacy()
        self.campaign = None
        self.offset = 0
        self.show_list()
        self.message(f'{count} ältere Sitzungen übernommen. Originaldateien bleiben erhalten.' +
                     (f' {len(failures)} Dateien konnten nicht gelesen werden.' if failures else ''))

    def detail(self, sid, tab='notes'):
        if sid != self.sid:
            self.event_offset, self.journal_query = 0, ''
        self.sid = sid
        item = self.archive.get(sid)
        self.body.clear_widgets()
        self.body.add_widget(label(f"{item['campaign']} · {item['title']}\nBeginn: {item['started']} | {'Abgeschlossen' if item['ended'] else 'Offen / vorbereitet'}", 60))
        tabs = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        for title, view in [('Notizen', 'notes'), ('Journal', 'journal'), ('Spielstände', 'saves')]:
            tabs.add_widget(button(title, lambda _, v=view: self.safely(lambda: self.detail(sid, v))))
        self.body.add_widget(tabs)
        if tab == 'notes':
            notes = '\n\n'.join(f'{label}\n{item["notes"].get(key) or "Noch keine Notizen."}' for key, label in NOTE_FIELDS.items())
            self.body.add_widget(reading_view(notes))
            self.body.add_widget(button('Rückblick und offene Aufgaben bearbeiten', lambda *_: self.edit_notes()))
            self.body.add_widget(button('Rückblick aus Journal vorschlagen', lambda *_: self.safely(self.recap_draft)))
            next_button = button('Nächsten Spielabend vorbereiten', lambda *_: self.safely(self.prepare_next))
            next_button.disabled = self.current_dm is not None
            self.body.add_widget(next_button)
        elif tab == 'journal':
            self.body.add_widget(label('Alle Ereignisse bleiben gespeichert. Zeitangaben enthalten die Zeitzone.', 44))
            row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
            self.journal_search = TextInput(text=self.journal_query, hint_text='Dieses Journal durchsuchen', multiline=False)
            row.add_widget(self.journal_search)
            row.add_widget(button('Suchen', lambda *_: self.search_events()))
            self.body.add_widget(row)
            self.journal_text = reading_view()
            self.body.add_widget(self.journal_text)
            row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
            self.events_previous = button('Vorherige Einträge', lambda *_: self.page_events(-50))
            self.events_next = button('Weitere Einträge', lambda *_: self.page_events(50))
            row.add_widget(self.events_previous)
            row.add_widget(self.events_next)
            self.body.add_widget(row)
            self.show_events()
        else:
            self.body.add_widget(label('Automatische Sicherung: spätestens alle 20 Sekunden. Manuelle Versionen bleiben erhalten.', 55))
            self.versions = {'Letzter automatisch gesicherter Stand': None}
            for rev in self.archive.revisions(sid):
                self.versions[f"{rev['time']} · {rev['label']} · {rev['id'][:8]}"] = rev['id']
            self.revision_choice = Spinner(text=next(iter(self.versions)), values=list(self.versions), size_hint_y=None, height=dp(56))
            self.body.add_widget(self.revision_choice)
            self.body.add_widget(Label(text='Beim Fortsetzen bleibt das bisherige Journal erhalten.\nFür einen neuen Spielabend eine neue Sitzung vorbereiten.', text_size=(dp(310), None)))
            resume = button('Ausgewählten Spielstand fortsetzen', lambda *_: self.safely(lambda: self.load_game(False)))
            prepare = button('Nächste Sitzung mit diesem Spielstand vorbereiten', lambda *_: self.safely(lambda: self.load_game(True)))
            resume.disabled = prepare.disabled = self.current_dm is not None
            self.body.add_widget(resume)
            self.body.add_widget(prepare)
            if self.current_dm:
                self.message('Zum Laden eines anderen Spielstands zuerst die laufende Sitzung beenden.')
        exports = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        self.txt_button = button('Als Text exportieren', lambda *_: self.export('txt'))
        self.pdf_button = button('Als PDF exportieren', lambda *_: self.export('pdf'))
        self.txt_button.disabled = self.export_busy
        self.pdf_button.disabled = self.export_busy or not sys.platform.startswith('win')
        exports.add_widget(self.txt_button)
        exports.add_widget(self.pdf_button)
        self.body.add_widget(exports)
        self.body.add_widget(button('Zur Sitzungsübersicht', lambda *_: self.safely(self.show_list)))

    def search_events(self):
        self.journal_query = self.journal_search.text.strip()
        self.event_offset = 0
        self.safely(self.show_events)

    def page_events(self, delta):
        self.event_offset = max(0, self.event_offset+delta)
        self.safely(self.show_events)

    def show_events(self):
        count, rows = self.archive.events(self.sid, self.journal_query, self.event_offset, 50)
        self.journal_text.text = '\n\n'.join(f"{r['time']} | {r['actor']} | {r['kind']}\n{r['message']}" for r in rows) or 'Keine passenden Einträge.'
        self.events_previous.disabled = self.event_offset == 0
        self.events_next.disabled = self.event_offset + len(rows) >= count
        self.message(f'{count} passende Einträge · Seite {self.event_offset//50+1}')

    def edit_notes(self):
        item = self.archive.get(self.sid)
        form = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(8))
        scroll = ScrollView(do_scroll_x=False)
        fields = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        fields.bind(minimum_height=fields.setter('height'))
        self.note_inputs = {}
        for key, title in [('campaign', 'Kampagne'), ('title', 'Sitzungsname'), *NOTE_FIELDS.items()]:
            fields.add_widget(label(title, 32))
            single = key in ('campaign', 'title')
            entry = TextInput(text=item[key] if single else item['notes'][key], multiline=not single,
                              size_hint_y=None, height=dp(48 if single else 145))
            self.note_inputs[key] = entry
            fields.add_widget(entry)
        scroll.add_widget(fields)
        form.add_widget(scroll)
        hint = label('DM-Notizen bleiben privat und werden nicht an Spieler gesendet.', 48)
        form.add_widget(hint)
        self.notes_popup = Popup(title='Vorbereitung und DM-Notizen', content=form, size_hint=(.95,.95), auto_dismiss=False)
        def save(*_):
            try:
                values = {key: entry.text for key, entry in self.note_inputs.items()}
                self.archive.edit(self.sid, values.pop('campaign'), values.pop('title'), values)
            except Exception as exc:
                hint.text = str(exc)
                return
            self.notes_popup.dismiss()
            self.detail(self.sid)
            self.message('DM-Notizen gespeichert. Frühere Fassungen bleiben in der lokalen Datenbank erhalten.')
        form.add_widget(button('Notizen speichern', save))
        form.add_widget(button('Abbrechen', self.notes_popup.dismiss))
        self.notes_popup.open()

    def load_game(self, new_session):
        selected = self.versions[self.revision_choice.text]
        data = self.archive.load_snapshot(self.sid, selected)
        if new_session:
            self.prepare_next(selected)
            return
        dm = self.app.sm.get_screen('dm_main')
        dm.start_new_dm_session()
        self.app.loaded_session_data = data
        self.dismiss()
        self.app.change_screen('dm_lobby')

    def prepare_next(self, revision=None):
        pid = CampaignStore().next_plan(self.sid, revision)
        self.app.sm.get_screen('dm_prep').load_plan(pid)
        self.dismiss()
        self.app.change_screen('dm_prep')

    def recap_draft(self):
        from utils.session_recap import build_recap
        item = self.archive.get(self.sid)
        draft = build_recap(self.archive.iter_events(self.sid), item['participants'])
        box = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
        box.add_widget(label('Privater Entwurf aus dem Journal. Prüfen und erzählerische Entscheidungen ergänzen.', 66))
        editor = TextInput(text=draft, font_size=dp(16))
        box.add_widget(editor)
        status = label('Ein bestehender Rückblick bleibt erhalten; der Entwurf wird angehängt.', 52)
        box.add_widget(status)
        popup = Popup(title='Nachbereitung', content=box, size_hint=(.96,.96), auto_dismiss=False)
        def save(*_):
            try:
                current = self.archive.get(self.sid)
                notes = dict(current['notes'])
                notes['summary'] = '\n\n'.join(x for x in (notes.get('summary'), editor.text.strip()) if x)
                self.archive.edit(self.sid, current['campaign'], current['title'], notes)
                popup.dismiss()
                self.detail(self.sid)
            except Exception as exc:
                status.text = str(exc)
        box.add_widget(button('Geprüften Entwurf zum Rückblick hinzufügen', save, 56))
        box.add_widget(button('Verwerfen / zurück', popup.dismiss))
        popup.open()

    def export(self, kind):
        if self.export_busy:
            return
        self.export_busy = True
        self.txt_button.disabled = self.pdf_button.disabled = True
        self.message('Export wird erstellt …')
        sid = self.sid
        def work():
            try:
                result = export_archive(self.archive, sid, kind)
                Clock.schedule_once(lambda dt: self.export_done(result))
            except Exception as exc:
                Clock.schedule_once(lambda dt, exc=exc: self.error(exc))
            finally:
                Clock.schedule_once(lambda dt: self.enable_exports())
        threading.Thread(target=work, daemon=True).start()

    def enable_exports(self):
        self.export_busy = False
        self.txt_button.disabled = False
        self.pdf_button.disabled = not sys.platform.startswith('win')

    def export_done(self, path):
        self.message(f'Export gespeichert: {path.name}')
        box = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
        box.add_widget(TextInput(text=str(path), readonly=True))
        popup = Popup(title='Sitzungsprotokoll exportiert', content=box, size_hint=(.85,.5))
        if sys.platform.startswith('win'):
            box.add_widget(button('Exportordner öffnen', lambda *_: os.startfile(str(path.parent))))
        box.add_widget(button('Schließen', popup.dismiss))
        popup.open()
