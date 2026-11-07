import json
import os
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from core.enemy import Enemy
from utils.storage import read_json, atomic_write_json, safe_save_path
from utils.helpers import apply_background, apply_styles_to_widget, get_user_saves_dir

from kivy.clock import Clock
from kivy.metrics import dp
from utils.campaign_store import CampaignStore
from kivy.app import App

class DMPrepScreen(Screen):
    """Screen for the DM to prepare the game."""
    def __init__(self, **kwargs):
        super(DMPrepScreen, self).__init__(**kwargs)
        self.plan_id = None
        self.plan_base = {}
        self._loading_plan = False
        self._save_event = None
        self.enemy_list = []
        self.map_data = None
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        if hasattr(self.app, 'edited_map_data') and self.app.edited_map_data:
            self.map_data = self.app.edited_map_data
            self.app.edited_map_data = None # Clear it after use
            self.schedule_save()

    def update_enemy_list_ui(self):
        enemy_list_widget = self.ids.enemy_list_view
        enemy_list_widget.clear_widgets()
        for enemy in self.enemy_list:
            enemy_list_widget.add_widget(Label(text=f'{enemy.name} (HP: {enemy.hp}, AC: {enemy.armor_class})', size_hint_y=None, height=dp(48)))

    def add_enemy_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        name_input = TextInput(hint_text='Name')
        hp_input = TextInput(hint_text='HP', input_filter='int')
        ac_input = TextInput(hint_text='AC', input_filter='int')
        initiative_input = TextInput(hint_text='Initiative Bonus', input_filter='int')
        attacks_input = TextInput(hint_text='Angriffe (z.B. Biss:1d6+2, Klaue:1d4)')
        notes_input = TextInput(hint_text='Notizen')
        for w in (name_input, hp_input, ac_input, initiative_input, attacks_input, notes_input):
            content.add_widget(w)
        save_button = Button(text='Speichern')
        content.add_widget(save_button)
        popup = Popup(title='Gegner hinzufuegen', content=content, size_hint=(0.8, 0.8))

        def save_action(instance):
            name = name_input.text.strip()
            if not name or not hp_input.text.strip() or not ac_input.text.strip():
                self._show_error('Name, HP und AC sind erforderlich.')
                return
            try:
                hp = int(hp_input.text)
                ac = int(ac_input.text)
                init = int(initiative_input.text or 0)
                attacks = self._parse_attacks(attacks_input.text)
            except ValueError as e:
                self._show_error(f'Ungueltige Eingabe: {e}')
                return
            new_enemy = Enemy(name=name, hp=hp, armor_class=ac, attacks=attacks,
                              initiative=init, notes=notes_input.text)
            self.enemy_list.append(new_enemy)
            self.update_enemy_list_ui()
            self.schedule_save()
            popup.dismiss()

        save_button.bind(on_press=save_action)
        popup.open()

    def save_enemy_list(self):
        try:
            path = safe_save_path(get_user_saves_dir('enemies'), 'my_enemies.enemies')
            atomic_write_json(path, [enemy.to_dict() for enemy in self.enemy_list])
        except Exception as e:
            self._show_error(f'Fehler beim Speichern der Gegnerliste:\n{e}')

    def load_enemy_list(self):
        try:
            path = safe_save_path(get_user_saves_dir('enemies'), 'my_enemies.enemies')
            raw = read_json(path)
            if not isinstance(raw, list):
                raise ValueError('Gegnerliste hat ein ungueltiges Format.')
            loaded = [Enemy.from_dict(d) for d in raw]
        except Exception as e:
            self._show_error(f'Fehler beim Laden der Gegnerliste:\n{e}')
            return
        self.enemy_list = loaded
        self.update_enemy_list_ui()
        self.schedule_save()

    def open_map_editor(self):
        map_editor_screen = self.manager.get_screen('map_editor')
        if map_editor_screen.begin_edit('preparation', self.map_data):
            self.app.change_screen('map_editor')

    def load_plan(self, pid):
        if self.plan_id and not self.save_preparation():
            raise ValueError('Bisherige Vorbereitung konnte nicht gespeichert werden.')
        store = CampaignStore()
        plan = store.plan(pid)
        if plan['session_id']:
            raise ValueError('Diese Sitzung bitte über das Archiv fortsetzen.')
        self._loading_plan = True
        self.plan_id = pid
        self.app.edited_map_data = None
        self.plan_base = plan['data']
        self.map_data = self.plan_base.get('map_data')
        self.enemy_list = [Enemy.from_dict(e) for e in self.plan_base.get('enemies', [])]
        self.ids.plan_title.text = plan['title']
        self.ids.plan_date.text = plan['scheduled']
        self.ids.plan_context.text = store.campaign(plan['campaign_id'])['name']
        self.ids.session_notes.text = self.plan_base.get('notes', '')
        self.ids.plan_tasks.text = self.plan_base.get('quests', '')
        self.ids.plan_agenda.text = self.plan_base.get('next_steps', '')
        self.ids.plan_status.text = 'Gespeichert. Änderungen werden automatisch gesichert.'
        self._loading_plan = False
        self.update_enemy_list_ui()

    def preparation_data(self):
        return {**self.plan_base, 'map_data': self.map_data,
                'enemies': [e.to_dict() for e in self.enemy_list],
                'notes': self.ids.session_notes.text,
                'quests': self.ids.plan_tasks.text if 'plan_tasks' in self.ids else '',
                'next_steps': self.ids.plan_agenda.text if 'plan_agenda' in self.ids else '',
                'type': 'prepared'}

    def schedule_save(self, *_):
        if not getattr(self, 'plan_id', None) or self._loading_plan:
            return
        self.ids.plan_status.text = 'Änderungen werden gespeichert …'
        if self._save_event:
            self._save_event.cancel()
        self._save_event = Clock.schedule_once(lambda dt: self.save_preparation(), .6)

    def save_preparation(self):
        if self._save_event:
            self._save_event.cancel()
            self._save_event = None
        if not self.plan_id:
            return True
        try:
            CampaignStore().save_plan(self.plan_id, self.ids.plan_title.text,
                                      self.ids.plan_date.text, self.preparation_data())
            self.ids.plan_status.text = 'Vorbereitung gespeichert.'
            return True
        except Exception as exc:
            self.ids.plan_status.text = f'Nicht gespeichert: {exc}'
            return False

    def on_leave(self, *_):
        self.save_preparation()

    def back_to_campaigns(self):
        if self.save_preparation():
            self.app.change_screen('dm_spiel')
            self.app.sm.get_screen('dm_spiel').prepare_dm()

    def host_session(self, offline=False):
        if not self.save_preparation():
            return
        session_data = self.preparation_data()
        if self.plan_id:
            session_data['_plan_id'] = self.plan_id
        self.plan_id = None  # The saved plan is now launched; do not autosave over its journal.
        self.app.sm.get_screen('dm_main').start_new_dm_session()
        self.app.loaded_session_data = None
        self.app.prepared_session_data = session_data
        self.app.sm.get_screen('dm_lobby').ids.session_name_input.text = self.ids.plan_title.text
        if offline:
            self.app.network_manager.stop_server()
            self.app.network_manager.mode = 'dm'  # DM authority, without opening any listener.
            self.app.change_screen('dm_main')
        else:
            self.app.change_screen('dm_lobby')

    def _show_error(self, msg):
        Popup(title='Fehler', content=Label(text=str(msg)), size_hint=(0.6, 0.4)).open()
    def _parse_attacks(self, text):
        from utils.non_ui_helpers import parse_dice
        attacks = []
        for part in text.replace('\n', ';').replace(',', ';').split(';'):
            part = part.strip()
            if not part:
                continue
            if ':' in part:
                name, dmg = part.split(':', 1)
            else:
                name, dmg = 'Angriff', part
            name = name.strip()
            dmg = dmg.strip().replace(' ', '')
            if not name or not dmg:
                raise ValueError(f'Ungueltiger Angriff: {part}')
            try:
                parsed = parse_dice(dmg)
            except Exception:
                parsed = None
            if parsed is None:
                raise ValueError(f'Ungueltiger Schaden: {dmg}')
            attacks.append({'name': name, 'damage': dmg})
        return attacks
