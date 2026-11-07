"""Campaign -> preparation -> play -> recap, with touch-sized controls."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from ui.session_archive_dialog import button, label, ArchiveBrowser
from utils.campaign_store import CampaignStore


class CampaignBrowser(Popup):
    def __init__(self, app, campaign_id=None, **kwargs):
        super().__init__(title='Kampagnen & Spielabende', size_hint=(.96, .96), auto_dismiss=False, **kwargs)
        self.app, self.store = app, CampaignStore()
        self.cid = campaign_id
        self.content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(8))
        self.body = BoxLayout(orientation='vertical', spacing=dp(8))
        self.status = label('', 48)
        self.content.add_widget(self.body)
        self.content.add_widget(self.status)
        self.content.add_widget(button('Schließen', self.dismiss))
        self.safe(lambda: self.detail(campaign_id) if campaign_id else self.overview())

    def safe(self, action):
        try:
            return action()
        except Exception as exc:
            self.status.text = f'Aktion nicht abgeschlossen: {exc}'
            self.status.color = (1, .45, .35, 1)

    def rows(self):
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(grid)
        self.body.add_widget(scroll)
        return grid

    def overview(self):
        self.cid = None
        self.body.clear_widgets()
        self.body.add_widget(label('1. Kampagne öffnen   →   2. Spielabend vorbereiten   →   3. Gemeinsam spielen', 64))
        self.body.add_widget(button('Neue Kampagne', lambda *_: self.create_campaign()))
        rows = self.rows()
        campaigns = self.store.campaign_list()
        if not campaigns:
            rows.add_widget(label('Noch keine Kampagne. Ein Name genügt für den Anfang.', 80))
        for item in campaigns:
            rows.add_widget(button(item['name'], lambda _, cid=item['id']: self.safe(lambda: self.detail(cid)), 64))
        self.status.text = 'Vorbereitungen und Archiv bleiben lokal gespeichert.'

    def create_campaign(self):
        box = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(8))
        box.add_widget(label('Name deiner eigenen Kampagne', 42))
        name = TextInput(multiline=False, size_hint_y=None, height=dp(52))
        box.add_widget(name)
        box.add_widget(label('Beschreibung (optional)', 42))
        description = TextInput()
        box.add_widget(description)
        error = label('', 48)
        box.add_widget(error)
        popup = Popup(title='Kampagne anlegen', content=box, size_hint=(.95, .85), auto_dismiss=False)
        def save(*_):
            try:
                cid = self.store.create_campaign(name.text, description.text)
                popup.dismiss()
                self.detail(cid)
            except Exception as exc:
                error.text = str(exc)
        box.add_widget(button('Kampagne erstellen', save))
        box.add_widget(button('Zurück', popup.dismiss))
        popup.open()

    def detail(self, cid):
        self.cid = cid
        campaign = self.store.campaign(cid)
        self.title = campaign['name']
        self.body.clear_widgets()
        self.body.add_widget(label(campaign['description'] or 'Vorbereiten, spielen und den nächsten Abend daraus entwickeln.', 60))
        self.body.add_widget(button('Neuen Spielabend vorbereiten', lambda *_: self.safe(self.new_plan)))
        rows = self.rows()
        rows.add_widget(label('Vorbereitete Spielabende', 36))
        plans = [p for p in self.store.plans(cid) if not p['session_id']]
        if not plans:
            rows.add_widget(label('Noch keine Vorbereitung. Du kannst auch ohne Karte starten.', 60))
        for plan in plans:
            rows.add_widget(button(plan['title'] + (' · ' + plan['scheduled'] if plan['scheduled'] else ''),
                                   lambda _, pid=plan['id']: self.safe(lambda: self.edit_plan(pid)), 64))
        rows.add_widget(label('Gespielte / laufende Abende', 40))
        history = self.store.campaign_history(cid)
        for session in history:
            state = 'Abgeschlossen' if session['ended'] else 'Fortsetzbar'
            rows.add_widget(button(f"{session['title']} · {state}",
                                   lambda _, sid=session['id']: self.safe(lambda: self.open_session(sid)), 64))
        if not history:
            rows.add_widget(label('Das Protokoll entsteht beim Spielen automatisch.', 60))
        self.body.add_widget(button('Alle Kampagnen', lambda *_: self.safe(self.overview)))
        self.status.text = 'Karte und Gegner sind optional. Notizen bleiben für die Spielleitung privat.'

    def new_plan(self):
        pid = self.store.create_plan(self.cid)
        self.edit_plan(pid)

    def edit_plan(self, pid):
        self.app.sm.get_screen('dm_prep').load_plan(pid)
        self.dismiss()
        self.app.change_screen('dm_prep')

    def open_session(self, sid):
        browser = ArchiveBrowser(self.app)
        browser.detail(sid)
        self.dismiss()
        browser.open()
