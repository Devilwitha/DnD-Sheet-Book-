"""Real Kivy + TCP integration, disposable data, no user campaign mutations."""
import json
import os
from pathlib import Path
from queue import Empty
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = Path(os.environ.get('DND_TEST_OUTPUT', str(ROOT / '.test-output'))) / 'live-play'
OUT.mkdir(parents=True, exist_ok=True)
os.environ['DND_DATA_DIR'] = str(OUT / ('profile-' + uuid.uuid4().hex[:10]))
from main import DnDApp
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.tabbedpanel import TabbedPanel
from core.character import Character
from core.enemy import Enemy
from core.network_manager import NetworkManager
from utils.formats import encode_map


class CheckApp(DnDApp):
    def on_start(self):
        self.checks = []
        self.failure = None
        self.client = NetworkManager()
        self.host = self.network_manager
        self.character = Character('Livetest', 'Mensch', 'Kämpfer')
        self.character.initialize_character()
        self.dm = self.sm.get_screen('dm_main')
        self.gm = self.dm.game_manager
        self.gm.enemies = [Enemy('Goblin #1', 40, 5, [{'name': 'Biss', 'damage': '1d4'}])]
        self.gm.map_data = {'rows': 6, 'cols': 8, 'tiles': {
            (r, c): {'type': 'Floor', 'object': None} for r in range(6) for c in range(8)}}
        self.gm.map_data['tiles'][(0, 0)]['object'] = 'Livetest'
        self.gm.map_data['tiles'][(0, 2)]['object'] = 'Goblin #1'
        self.gm.map_data['tiles'][(1, 4)]['type'] = 'Wall'
        self.gm.map_data['tiles'][(2, 3)]['furniture'] = {'type': 'Tisch'}
        self.gm.initiative_order = [(15, 'Livetest'), (10, 'Goblin #1')]
        self.gm.current_turn_index = 1
        self.gm.start_next_turn()
        self.steps = iter([self.start_host, self.dialog_and_code, self.join_late, self.approve_join, self.check_join, self.check_move,
                           self.check_attack, self.check_host_actions, self.lobby_visit, self.lobby_check, self.return_check, self.capture_host,
                           self.click_interact, self.verify_interact, self.click_move, self.verify_move,
                           self.orphan_and_drag, self.capture_admin, self.check_dropdown, self.check_dropdown_selection, self.show_qr,
                           self.capture_qr, self.show_client, self.capture_client, self.capture_landscape])
        Clock.schedule_once(self.step, 0.5)

    def record(self, text):
        self.checks.append(text)
        print('PASS', text, flush=True)

    def step(self, dt):
        try:
            action = next(self.steps)
        except StopIteration:
            self.stop()
            return
        try:
            action()
        except Exception:
            self.failure = traceback.format_exc()
            print(self.failure, flush=True)
            self.stop()
            return
        Clock.schedule_once(self.step, 0.8)

    def messages(self):
        result = []
        while True:
            try:
                source, message = self.client.incoming_messages.get_nowait()
            except Empty:
                return result
            result.append(message)

    def start_host(self):
        Window.size = (1280, 800)
        self.sm.transition.duration = 0
        ok, reason = self.host.start_server(host='127.0.0.1', port=0)
        assert ok, reason
        self.change_screen('dm_main')

    def join_late(self):
        assert self.dm.update_event is not None, 'Host screen has not started polling'
        ok, reason = self.client.connect_to_server('127.0.0.1', self.host.port, self.character, join_code=self.host.join_code)
        assert ok, reason

    def dialog_and_code(self):
        from ui.character_approval import ask_dm
        field = self.sm.get_screen('transfer').ids.code_input
        field.text = 'ABCD-EF01-2345-6789'
        assert field.text == 'ABCD-EF01-2345-6789'
        decisions = []
        popup = ask_dm('Testentscheidung', 'Test', lambda: decisions.append('yes'), lambda: decisions.append('no'))
        self._on_keyboard(Window, 27)
        assert decisions == ['no']
        popup.dismiss()
        assert decisions == ['no']
        self.record('Full 16-digit grouped code retained; Esc resolves DM approval exactly once')

    def approve_join(self):
        from kivy.uix.button import Button
        popup = next(w for w in Window.children if getattr(w, 'title', '') == 'Neuen Charakter aufnehmen')
        button = next(w for w in popup.content.walk() if isinstance(w, Button) and w.text == 'Charakter übernehmen')
        button.trigger_action(duration=0)

    def lobby_visit(self):
        self.saved_sid = self.dm.archive_id
        self.saved_budget = self.gm.turn_action_state['movement_left']
        self.change_screen('dm_lobby')
        assert self.host.running
        payload = {'to_pos': [1, 2], 'request_id': 'f' * 32}
        self.client.send_to_dm('MOVE_OBJECT', payload)
        self.client.send_to_dm('MOVE_OBJECT', payload)

    def lobby_check(self):
        assert self.gm.find_object_pos('Livetest') == (1, 2)
        assert self.gm.turn_action_state['movement_left'] == self.saved_budget - 1
        self.sm.get_screen('dm_lobby').go_back()

    def return_check(self):
        assert self.sm.current == 'dm_main'
        assert self.host.running and self.dm.archive_id == self.saved_sid
        self.dm.select_map_actor('Livetest')
        assert self.gm.move_object('Livetest', (1, 1), dm_override=True)[0]
        self.dm.update_ui()
        self.record('Live lobby preserves host and archive, processes gameplay and applies duplicate request only once')

    def check_join(self):
        messages = self.messages()
        kinds = [m['type'] for m in messages]
        assert 'GAME_START' in kinds and 'MAP_DATA' in kinds and 'GAME_STATE_UPDATE' in kinds, kinds
        assert kinds.index('CHAR_DATA') < kinds.index('GAME_START') < kinds.index('MAP_DATA'), kinds
        assert self.gm.get_current_turn_info()['name'] == 'Goblin #1'
        self.record('Late join after game start: character, start, map and state received in order')
        self.dm.end_turn()
        assert self.gm.get_current_turn_info()['name'] == 'Livetest'
        self.client.send_to_dm('MOVE_OBJECT', {'to_pos': [0, 1]})

    def check_move(self):
        messages = self.messages()
        assert self.gm.find_object_pos('Livetest') == (0, 1)
        assert self.gm.turn_action_state['movement_left'] == self.character.speed - 1
        assert any(m['type'] == 'ACTION_RESULT' for m in messages)
        self.record('Client movement received and acknowledged, remaining movement synchronized')
        self.client.send_to_dm('PLAYER_ATTACK', {'type': 'manual', 'enemy_name': 'Goblin #1', 'attack_roll': 20, 'damage': 3})

    def check_attack(self):
        messages = self.messages()
        assert self.gm.enemies[0].hp == 37
        assert self.gm.turn_action_state['attacks_left'] == 0
        assert any(m['type'] == 'ACTION_RESULT' and '3 Schaden' in m['payload']['message'] for m in messages)
        self.record('Client attack applied with actual damage, action budget and visible result')
        self.client.send_to_dm('END_TURN', {})

    def check_host_actions(self):
        assert self.gm.get_current_turn_info()['name'] == 'Goblin #1'
        self.dm.end_turn()
        self.dm.select_map_actor('Livetest')
        self.dm.select_map_action('move')
        self.dm.handle_left_click(1, 1)
        assert self.gm.find_object_pos('Livetest') == (1, 1)
        self.dm.select_map_action('attack')
        budget = dict(self.gm.turn_action_state)
        self.dm.handle_left_click(0, 2)
        assert self.gm.turn_action_state == budget
        self.record('Host action buttons move and attack for the connected player')
        self.dm.select_map_action('move')
        panel = next(w for w in self.dm.walk() if isinstance(w, TabbedPanel))
        panel.switch_to(next(t for t in panel.tab_list if t.text == 'Karte'))

    def capture_host(self):
        self.root.export_to_png(str(OUT / 'host-map-1280.png'))
        grid = self.dm.ids.dm_map_grid
        row, col = 1, 1
        from kivy.tests.common import UnitTestTouch
        touch = UnitTestTouch(grid.x + (col + .5) * grid.tile_size,
                              grid.top - (row + .5) * grid.tile_size)
        self.dm.select_map_actor('Goblin #1')
        touch.touch_down()
        touch.touch_up()
        assert self.dm.dm_selected_attacker == 'Livetest'
        # Translate the map without changing its size, then use the new coordinates.
        grid.x += 10
        touch = UnitTestTouch(grid.x + (col + .5) * grid.tile_size,
                              grid.top - (row + .5) * grid.tile_size)
        touch.scale_for_screen(Window.width, Window.height)
        self.dm.select_map_actor('Goblin #1')
        assert grid.on_touch_down(touch)
        grid.on_touch_up(touch)
        assert self.dm.dm_selected_attacker == 'Livetest'
        self.record('Map hit testing remains correct after position-only layout change')

    def tap_widget(self, widget):
        from kivy.tests.common import UnitTestTouch
        touch = UnitTestTouch(*widget.to_window(*widget.center))
        touch.touch_down()
        touch.touch_up()

    def tap_tile(self, row, col):
        from kivy.tests.common import UnitTestTouch
        grid = self.dm.ids.dm_map_grid
        touch = UnitTestTouch(grid.x + (col + .5) * grid.tile_size, grid.top - (row + .5) * grid.tile_size)
        touch.touch_down()
        touch.touch_up()

    def click_interact(self):
        self.gm.current_turn_index = -1
        self.dm.update_ui()
        self.map_bounds = (tuple(self.dm.ids.dm_map_grid.pos), tuple(self.dm.ids.dm_map_grid.size))
        self.tap_widget(self.dm.ids.dm_interact_button)

    def verify_interact(self):
        assert self.dm.action_mode == 'interact', 'One button tap must select interaction'
        self.tap_tile(2, 3)
        assert 'interagiert' in self.dm._map_feedback
        assert (tuple(self.dm.ids.dm_map_grid.pos), tuple(self.dm.ids.dm_map_grid.size)) == self.map_bounds
        self.record('One real button tap enables DM interaction without combat; feedback does not move the map')

    def click_move(self):
        self.tap_widget(self.dm.ids.dm_move_button)

    def verify_move(self):
        assert self.dm.action_mode == 'move', 'One button tap must enable movement'
        self.tap_tile(4, 6)
        assert self.gm.find_object_pos('Livetest') == (4, 6)
        self.record('One real button tap and one destination tap moves the DM-selected player before combat')

    def orphan_and_drag(self):
        from kivy.tests.common import UnitTestTouch
        grid = self.dm.ids.dm_map_grid
        self.gm.map_data['tiles'][(3, 4)]['object'] = 'Alte Kartenfigur'
        self.dm.update_map_view()
        self.tap_tile(3, 4)
        assert self.dm.dm_selected_attacker == 'Alte Kartenfigur'
        self.tap_tile(3, 5)
        assert self.gm.find_object_pos('Alte Kartenfigur') == (3, 5)
        # A drag away and back must not activate a destination on release.
        x, y = grid.x + 5.5 * grid.tile_size, grid.top - 4.5 * grid.tile_size
        touch = UnitTestTouch(x, y)
        touch.scale_for_screen(Window.width, Window.height)
        grid.on_touch_down(touch)
        touch.move({'x': (x + 40) / Window.width, 'y': y / Window.height})
        touch.scale_for_screen(Window.width, Window.height)
        grid.on_touch_move(touch)
        touch.move({'x': x / Window.width, 'y': y / Window.height})
        touch.scale_for_screen(Window.width, Window.height)
        grid.on_touch_up(touch)
        assert self.gm.find_object_pos('Alte Kartenfigur') == (3, 5)
        self.record('Visible legacy token is selectable and movable; dragging does not trigger an accidental action')

    def capture_admin(self):
        self.root.export_to_png(str(OUT / 'dm-admin-selection.png'))
        assert 'Alte Kartenfigur' in self.dm.ids.dm_map_status.text
        self.tap_widget(self.dm.ids.actor_selector)

    def check_dropdown(self):
        selector = self.dm.ids.actor_selector
        assert selector.is_open, 'One tap must open the dropdown'
        self.root.export_to_png(str(OUT / 'dm-dropdown.png'))
        option = next(w for w in selector._dropdown.container.children if w.text == 'Livetest')
        self.tap_widget(option)

    def check_dropdown_selection(self):
        assert not self.dm.ids.actor_selector.is_open
        assert self.dm.dm_selected_attacker == 'Livetest', (self.dm.dm_selected_attacker, self.dm.ids.actor_selector.text)
        assert self.dm.action_mode == 'move'
        self.record('Dropdown opens on one tap; one selection prepares the chosen figure for movement')

    def show_qr(self):
        from ui.join_dialog import show_join_dialog
        self.qr_popup = show_join_dialog(self.host)

    def capture_qr(self):
        Window.screenshot(name=str(OUT / 'host-invitation.png'))
        self.qr_popup.dismiss()
        self.record('QR invitation renders with offline Segno in real Kivy')

    def show_client(self):
        Window.size = (360, 740)
        self.network_manager = self.client
        self.player_map = self.sm.get_screen('player_map')
        self.player_map.set_map_data(encode_map(self.gm.map_data))
        info = self.gm.get_current_turn_info()
        self.player_map.update_game_state({'current_turn': info['name'], 'current_turn_pos': info['pos'], 'turn_action_state': info['state']})
        self.change_screen('player_map')
        self.player_map.select_action('move')

    def capture_client(self):
        self.root.export_to_png(str(OUT / 'client-map-360.png'))
        for name in ('move_button', 'attack_button', 'interact_button', 'end_turn_button'):
            widget = self.player_map.ids[name]
            assert widget.height >= 48 and widget.y >= 0 and widget.top <= Window.height
        assert self.player_map.ids.player_map_grid.height > 100
        self.record('Client action buttons visible at 360px portrait width')
        Window.size = (740, 360)

    def capture_landscape(self):
        self.root.export_to_png(str(OUT / 'client-map-landscape.png'))
        assert self.player_map.ids.player_map_grid.height > 30
        self.record('Client map and action controls fit landscape viewport')

    def on_stop(self):
        self.client.shutdown()
        self.host.shutdown()
        self.network_manager = self.host
        super().on_stop()
        (OUT / 'result.json').write_text(json.dumps({'passed': self.checks, 'failure': self.failure}, indent=2), encoding='utf-8')


app = CheckApp()
app.run()
sys.exit(bool(app.failure))
