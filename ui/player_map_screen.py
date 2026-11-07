from kivy.metrics import dp
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup
from utils.formats import decode_map
from utils.map_actions import reachable_tiles, action_reason


class PlayerMapScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.map_data = None
        self.selected_object = None
        self.highlighted_tiles = []
        self.current_turn_name = None
        self.current_turn_pos = None
        self.turn_action_state = {}
        self.is_my_turn = False
        self.action_mode = 'inspect'
        self.interactable_pos = None
        self._map_widget_bound = False
        self._pending = False
        self._feedback = ''

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        if not self._map_widget_bound:
            self.ids.player_map_grid.bind(on_tile_click=self.handle_tile_click)
            self._map_widget_bound = True
        self.update_ui()

    def reset_session(self):
        self.map_data = None
        self.current_turn_name = None
        self.current_turn_pos = None
        self.turn_action_state = {}
        self.is_my_turn = False
        self.action_mode = 'inspect'
        self._pending = False
        self._feedback = ''
        self.update_ui()

    def my_position(self):
        name = getattr(self.app.character, 'name', None)
        return next((pos for pos, tile in (self.map_data or {}).get('tiles', {}).items()
                     if name and tile.get('object') == name), None)

    def set_map_data(self, map_data):
        self.map_data = decode_map(map_data)
        self.update_ui()

    def update_game_state(self, game_state):
        self.current_turn_name = game_state.get('current_turn')
        self.turn_action_state = game_state.get('turn_action_state') or {}
        pos = game_state.get('current_turn_pos')
        self.current_turn_pos = tuple(pos) if pos is not None else None
        self.is_my_turn = bool(self.current_turn_name and self.app.character and
                               self.current_turn_name == self.app.character.name)
        if not self.is_my_turn:
            self.action_mode = 'inspect'
        self.update_ui()

    def show_turn_popup(self):
        # The persistent status bar announces the turn without blocking map touches.
        self.update_ui()

    def update_ui(self):
        self.update_turn_status_ui()
        self.update_map_widget()

    def update_turn_status_ui(self):
        if 'turn_status_label' not in self.ids:
            return
        pos = self.my_position()
        if not self.map_data:
            status = 'Die Spielleitung muss zuerst eine Karte laden.'
        elif not self.current_turn_name:
            status = 'Kampf noch nicht gestartet: Die Spielleitung würfelt Initiative.'
        elif pos is None:
            status = 'Deine Figur fehlt auf der Karte. Die Spielleitung kann sie platzieren.'
        elif self.is_my_turn:
            status = (f"Dein Zug | Bewegung: {self.turn_action_state.get('movement_left', 0)} Felder"
                      f" | Angriffe: {self.turn_action_state.get('attacks_left', 0)}")
        else:
            status = f'Am Zug: {self.current_turn_name}'
        self.ids.turn_status_label.text = status
        active = self.is_my_turn and pos is not None and not self._pending
        self.ids.move_button.disabled = not active or self.turn_action_state.get('movement_left', 0) <= 0
        self.ids.attack_button.disabled = not active or self.turn_action_state.get('attacks_left', 0) <= 0
        self.ids.interact_button.disabled = not active
        self.ids.end_turn_button.disabled = not self.is_my_turn or self._pending
        for ident, mode in (('move_button', 'move'), ('attack_button', 'attack'), ('interact_button', 'interact')):
            self.ids[ident].background_color = (0.25, 0.65, 1, 1) if mode == self.action_mode else (1, 1, 1, 1)
        instructions = {'inspect': 'Aktion wählen oder eine Figur antippen.',
                        'move': 'Bewegen: Ein gelb markiertes Feld antippen.',
                        'attack': 'Angreifen: Die Zielfigur antippen.',
                        'interact': 'Interagieren: Einen benachbarten Gegenstand antippen.'}
        self.ids.action_hint.text = self._feedback or instructions[self.action_mode]

    def update_map_widget(self):
        pos = self.my_position()
        self.highlighted_tiles = list(reachable_tiles(self.map_data, pos,
            self.turn_action_state.get('movement_left', 0))) if self.action_mode == 'move' and self.is_my_turn else []
        self.ids.player_map_grid.set_data(self.map_data, self.highlighted_tiles, self.current_turn_pos, selected_pos=pos)

    def select_action(self, mode):
        if self._pending:
            return
        if not self.is_my_turn or self.my_position() is None:
            self.update_ui()
            return
        self.action_mode = mode
        self._feedback = ''
        self.update_ui()

    def handle_tile_click(self, instance, touch, row, col):
        if getattr(touch, 'button', 'left') in ('left', None):
            self.on_tile_click(row, col)

    def on_tile_click(self, row, col):
        tile = (self.map_data or {}).get('tiles', {}).get((row, col))
        if not tile or self._pending:
            return
        if self.action_mode == 'inspect' or not self.is_my_turn:
            self._feedback = tile.get('object') or (tile.get('furniture') or {}).get('type') or 'Freies Feld'
            self.update_ui()
            return
        pos = self.my_position()
        if pos is None:
            self.update_ui()
            return
        if self.action_mode == 'move':
            self._send('MOVE_OBJECT', {'name': self.app.character.name, 'to_pos': [row, col]})
        elif self.action_mode == 'attack':
            target = tile.get('object')
            if not target or target == self.app.character.name:
                self.show_action_result('Wähle eine andere Figur als Angriffsziel.')
            else:
                self.open_attack_popup(target, pos, (row, col))
        elif self.action_mode == 'interact':
            self._send('INTERACT_WITH_OBJECT', {'pos': [row, col]})

    def _send(self, kind, payload):
        if self._pending:
            return
        from uuid import uuid4
        from kivy.clock import Clock
        request_id = uuid4().hex
        sent = self.app.network_manager.send_to_dm(kind, {**payload, 'request_id': request_id})
        if sent is False:
            self.show_action_result('Nicht verbunden. Bitte erneut der Sitzung beitreten.')
            return
        self._pending = request_id
        def expire(_):
            if self._pending == request_id:
                self.show_action_result('Keine Bestätigung vom DM. Bitte den aktuellen Spielstand prüfen, bevor du die Aktion erneut ausführst.', request_id)
        Clock.schedule_once(expire, 15)
        self._feedback = 'Warte auf die Spielleitung …'
        self.update_ui()

    def show_action_result(self, message, request_id=None):
        if request_id and self._pending and request_id != self._pending:
            return
        self._pending = False
        self._feedback = action_reason(str(message))
        self.update_ui()

    def open_attack_popup(self, enemy_name, player_pos=None, enemy_pos=None):
        from kivy.uix.scrollview import ScrollView
        outer = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8))
        content.bind(minimum_height=content.setter('height'))
        scroll.add_widget(content)
        outer.add_widget(scroll)
        label = Label(text=f'{self.app.character.name} greift {enemy_name} an.\nDer DM-Host rechnet deinen Angriffsbonus hinzu.', size_hint_y=None, height=dp(64))
        label.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)))
        content.add_widget(label)
        auto = Button(text='Angriff automatisch würfeln', size_hint_y=None, height=dp(52))
        content.add_widget(auto)
        roll = TextInput(hint_text='Eigener W20: 1–20, ohne Bonus', multiline=False, size_hint_y=None, height=dp(48))
        damage = TextInput(hint_text='Schaden gesamt (leer = automatisch)', multiline=False, size_hint_y=None, height=dp(48))
        content.add_widget(roll)
        content.add_widget(damage)
        manual = Button(text='Manuelle Würfe senden', size_hint_y=None, height=dp(48))
        content.add_widget(manual)
        error = Label(text='', size_hint_y=None, height=dp(44))
        error.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)))
        content.add_widget(error)
        close = Button(text='Abbrechen', size_hint_y=None, height=dp(48))
        outer.add_widget(close)
        popup = create_styled_popup(title=f'Angriff auf {enemy_name}', content=outer, size_hint=(0.95, 0.85))
        def send_auto(*args):
            popup.dismiss()
            self._send('PLAYER_ATTACK', {'type': 'auto', 'enemy_name': enemy_name})
        def send_manual(*args):
            try:
                a = int(roll.text)
                d = int(damage.text) if damage.text.strip() else None
                if not 1 <= a <= 20 or (d is not None and not 0 <= d <= 1000):
                    raise ValueError
            except ValueError:
                error.text = 'W20: 1–20. Schaden: leer oder 0–1000.'
                return
            popup.dismiss()
            self._send('PLAYER_ATTACK', {'type': 'dice', 'enemy_name': enemy_name, 'd20': a, 'damage': d})
        auto.bind(on_release=send_auto)
        manual.bind(on_release=send_manual)
        close.bind(on_release=popup.dismiss)
        popup.open()

    def end_turn(self):
        if self.is_my_turn:
            self._send('END_TURN', {})

    def interact(self):
        self.select_action('interact')

    def go_back(self):
        self.manager.current = 'player_sheet'
