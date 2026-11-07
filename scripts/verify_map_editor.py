"""Real Kivy editor gestures and storage in an isolated profile, without a server."""
import copy
import json
import os
from pathlib import Path
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = Path(os.environ.get('DND_TEST_OUTPUT', str(ROOT / '.test-output'))) / 'map-editor'
OUT.mkdir(parents=True, exist_ok=True)
os.environ['DND_DATA_DIR'] = str(OUT / ('profile-' + uuid.uuid4().hex[:10]))
from main import DnDApp
from kivy.clock import Clock
from kivy.core.window import Window
from utils.map_document import Atlas, add_element, public_artwork
from utils.formats import decode_map, encode_map
from utils.storage import read_json, safe_save_path
from utils.paths import get_user_saves_dir


class Touch:
    button = 'left'
    is_mouse_scroll = False
    grab_current = None
    def __init__(self, pos):
        self.pos = pos
        self.dx = self.dy = 0
        self.ud = {}
    def grab(self, widget):
        self.grab_current = widget
    def ungrab(self, widget):
        self.grab_current = None
    def move(self, pos):
        self.dx, self.dy = pos[0] - self.pos[0], pos[1] - self.pos[1]
        self.pos = pos


class EditorCheck(DnDApp):
    def on_start(self):
        self.failure = None
        self.checks = []
        self.sm.transition.duration = 0
        self.steps = iter([self.open_editor, self.draw_world, self.gestures,
                           self.region, self.site, self.interior, self.storage,
                           self.phone, self.phone_gestures, self.player_view,
                           self.library_entry, self.library_browse, self.library_use,
                           self.phone_options, self.small_phone])
        Clock.schedule_once(self.step, .3)

    def step(self, _):
        try:
            next(self.steps)()
            Clock.schedule_once(self.capture, .3)
        except StopIteration:
            self.stop()
        except Exception:
            self.failure = traceback.format_exc()
            self.stop()

    def capture(self, _):
        try:
            widget = self.e.library_popup.popup if self.shot == '12-kartenbibliothek' else self.root
            widget.export_to_png(str(OUT / (self.shot + '.png')))
            Clock.schedule_once(self.step, .05)
        except Exception:
            self.failure = traceback.format_exc()
            self.stop()

    def open_editor(self):
        Window.size = (1280, 820)
        self.change_screen('map_editor')
        self.e = self.sm.get_screen('map_editor')
        self.e._error = lambda message: (_ for _ in ()).throw(AssertionError(message))
        self.shot = '01-leerer-editor'

    def drag(self, tool, a, b, steps=10):
        e = self.e
        e.set_tool(tool)
        cv = e.ids.map_canvas
        left, top, unit = cv._geometry()
        def project(p):
            return (left + p[0] * unit, top - p[1] * unit)
        touch = Touch(project(a))
        assert cv.on_touch_down(touch)
        for i in range(1, steps + 1):
            point = (a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
            touch.move(project(point))
            cv.on_touch_move(touch)
        cv.on_touch_up(touch)
        assert touch.grab_current is None

    def draw_world(self):
        e = self.e
        e.atlas.current()['name'] = 'Freie Testwelt'
        art = e.map_data['artwork']
        e.color = '#a3b280'
        e.set_tool('land')
        coast = [(3,11),(4,9),(3.5,7),(5,6),(5,4),(7,4.5),(8,3),(10,4),(11,3.7),
                 (13,5),(14,4),(16,5.5),(17,7),(19,6),(21,7),(22,6.5),(25,8),(26,10),
                 (25,11),(28,12),(28.5,14),(27,15),(27,17),(25,18),(24,17),(23,19),
                 (20,20),(18,19),(17,21),(14,20),(13,21),(11,20),(10,18),(8,19),
                 (7,17),(5,18),(4,16),(5,14),(3,11)]
        e.canvas_down(*coast[0])
        for point in coast[1:]:
            e.canvas_move(*point)
        e.canvas_up(*coast[-1])
        assert art['elements'][0]['kind'] == 'polygon'
        for x, y in [(9, 7), (10, 8), (11, 9), (12, 8), (13, 10)]:
            add_element(art, 'symbol', [[x, y]], '#454c40', 2, 'objects', symbol='Berg')
        for x, y in [(17, 13), (18, 12), (19, 13), (18, 14), (20, 14), (19, 15)]:
            add_element(art, 'symbol', [[x, y]], '#375a35', 1.8, 'objects', symbol='Baum')
        add_element(art, 'label', [[20, 7]], '#304651', 1.6, 'labels', text='Das freie Land')
        e.color, e.brush_width = '#6e97af', .4
        self.drag('brush', (13, 10), (18, 21))
        e._activate(reset_view=False)
        self.shot = '02-welt-desktop'

    def gestures(self):
        e = self.e
        before = copy.deepcopy(e.map_data['artwork'])
        e.color, e.brush_width = '#635746', .3
        self.drag('line', (5, 17), (13, 17))
        assert len(e.map_data['artwork']['elements']) == len(before['elements']) + 1
        e.undo()
        assert e.map_data['artwork'] == before
        e.redo()
        e.brush_width = 1
        self.drag('eraser', (9, 17), (9, 17))
        strokes = [el for el in e.map_data['artwork']['elements'] if el['color'] == '#635746']
        assert len(strokes) == 2
        e.layer = 'terrain'
        e.toggle_layer('locked')
        unchanged = copy.deepcopy(e.map_data)
        self.drag('brush', (3, 3), (4, 4))
        assert e.map_data == unchanged
        e.toggle_layer('locked')
        e.brush_width = .3
        self.drag('select', (5, 17), (6, 16))
        assert e.selected_id
        e.color = '#8d5041'
        e.recolor_selected()
        assert next(el for el in e.map_data['artwork']['elements'] if el['id'] == e.selected_id)['color'] == '#8d5041'
        self.checks.append('Actual canvas gestures: filled land, drawing, line, partial eraser, select/drag, recolor, undo/redo, layer lock')
        self.shot = '03-werkzeuge'

    def child(self, name, x, y):
        e = self.e
        original = e._map_details
        e._map_details = lambda title, initial, scale, callback: callback(name, scale, "")
        try:
            self.drag('pin', (x, y), (x, y))
        finally:
            e._map_details = original
        e._navigate(e.atlas.current()['pins'][-1]['child_id'])
        assert e.atlas.current()['name'] == name

    def region(self):
        self.child('Flusstal', 15, 15)
        add_element(self.e.map_data['artwork'], 'rect', [[2, 2], [30, 22]], '#a6b583', 1, 'terrain')
        add_element(self.e.map_data['artwork'], 'stroke', [[14, 0], [15, 6], [12, 13], [17, 24]], '#688b9e', 1.2, 'terrain')
        add_element(self.e.map_data['artwork'], 'label', [[23, 6]], '#303c31', 2, 'labels', text='Flusstal')
        self.e.ids.map_canvas.refresh()
        self.shot = '04-region'

    def site(self):
        self.child('Dorf an der Brücke', 12, 14)
        self.e.map_data['artwork']['background'] = '#abb891'
        add_element(self.e.map_data['artwork'], 'stroke', [[2, 12], [30, 12]], '#c7b394', 1.5, 'terrain')
        for x, y in [(9, 9), (12, 9), (15, 9), (18, 9), (21, 9), (10, 15), (14, 15), (18, 15)]:
            add_element(self.e.map_data['artwork'], 'symbol', [[x, y]], '#564738', 2, 'objects', symbol='Haus')
        self.e.ids.map_canvas.refresh()
        self.shot = '05-dorf'

    def interior(self):
        self.child('Schmiede', 12, 9)
        e = self.e
        e.atlas.current()['map']['rows'] = 18
        e.atlas.current()['map']['cols'] = 24
        e.map_data['tiles'] = {(r,c):t for (r,c),t in e.map_data['tiles'].items() if r < 18 and c < 24}
        e._activate()
        for r in range(3, 15):
            for c in range(3, 21):
                if r in (3, 14) or c in (3, 20):
                    e.map_data['tiles'][(r, c)]['type'] = 'Wall'
        e.map_data['tiles'][(14, 12)]['type'] = 'Door'
        for x, y in [(7, 6), (16, 6), (16, 10)]:
            add_element(e.map_data['artwork'], 'symbol', [[x, y]], '#5f4937', 3, 'objects', symbol='Tisch')
        add_element(e.map_data['artwork'], 'label', [[11, 2]], '#333333', 2, 'labels', text='Schmiede')
        e.ids.map_canvas.refresh()
        assert [r['level'] for r in e.atlas.breadcrumbs()] == ['world','region','site','interior']
        self.shot = '06-innenraum'

    def storage(self):
        e = self.e
        assert e._persist(current_map=True)
        restored = Atlas.decode(read_json(safe_save_path(get_user_saves_dir('atlases'), e.atlas.id + '.json')))
        assert len(restored.maps) == 4
        assert restored.map == decode_map(encode_map(e.map_data))
        e.load_existing_map(decode_map(encode_map(e.map_data)))
        assert len(e.atlas.breadcrumbs()) == 4
        e.parent_map()
        assert e.map_title == 'Dorf an der Brücke'
        self.drag('select', (12, 9), (12, 9))
        assert e.map_title == 'Schmiede'
        self._on_keyboard(Window, 27)
        assert self.sm.current != 'map_editor'
        assert self.edited_map_data['editor_title'] == 'Schmiede'
        self.change_screen('map_editor')
        e.checkpoint_atlas()
        self.checks.append('Four linked map levels, saved Atlas + current game map, reopening and pin navigation')
        self.shot = '07-gespeichert'

    def phone(self):
        Window.size = (392, 844)
        self.shot = '08-smartphone'

    def phone_gestures(self):
        cv = self.e.ids.map_canvas
        assert cv.height > 200 and cv.width > 300, (cv.size, cv.pos, cv.parent.size, self.e.ids.inspector_scroll.size, self.e.ids.tool_row.parent.size)
        count = len(self.e.map_data['artwork']['elements'])
        self.e.layer, self.e.color = 'terrain', '#998877'
        self.drag('brush', (9, 8), (11, 9))
        assert len(self.e.map_data['artwork']['elements']) == count + 1
        self.e.undo()
        cv.zoom_by(2)
        assert cv.zoom == 2
        anchor = (cv.center_x + 18, cv.center_y - 18)
        before = cv.map_point(anchor)
        wheel = Touch(anchor)
        wheel.button = 'scrolldown'
        wheel.is_mouse_scrolling = True
        cv.on_touch_down(wheel)
        assert cv.zoom > 2
        after = cv.map_point(anchor)
        assert max(abs(a - b) for a, b in zip(before, after)) < .0001
        wheel.button = 'scrollup'
        cv.on_touch_down(wheel)
        assert abs(cv.zoom - 2) < .0001
        self.drag('hand', (10, 9), (11, 10))
        assert cv.pan_x or cv.pan_y
        cv.fit()
        self.checks.append('Phone-sized canvas: touch gesture, undo, zoom/pan/fit with visible inspector and toolbar')
        self.shot = '09-smartphone-werkzeuge'

    def player_view(self):
        data = copy.deepcopy(self.e.map_data)
        add_element(data['artwork'], 'label', [[6, 9]], '#112233', 1, 'labels', text='Geheim')
        data['artwork']['layers'][2]['visible'] = False
        data['artwork'] = public_artwork(data['artwork'])
        assert 'Geheim' not in json.dumps(data['artwork'])
        s = self.sm.get_screen('player_map')
        s.set_map_data(decode_map(encode_map(data)))
        self.change_screen('player_map')
        self.checks.append('Player map renders artwork through production codec; hidden labels stripped')
        self.shot = '10-spielerkarte'


    def library_entry(self):
        from core.character import Character
        Window.size = (1280, 820)
        self.game_manager.offline_players = [Character('Andere Sitzung', 'Mensch', 'Kämpfer')]
        self.change_screen('dm_spiel')
        self.sm.get_screen('dm_spiel').ids.maps_btn.dispatch('on_release')
        e = self.e
        assert self.sm.current == 'map_editor' and e.purpose == 'library'
        assert len(e.atlas.maps) == 1
        assert e.ids.player_spinner.disabled
        assert e.ids.player_spinner.values == ['None']
        e.atlas.current()['name'] = 'Wiederverwendbare Waldkarte'
        add_element(e.map_data['artwork'], 'rect', [[3, 3], [29, 21]], '#8e9f76', 1, 'terrain')
        e._activate()
        e.save_map()
        assert self.edited_map_data is None
        assert not e.map_data.get('offline_players')
        self.library_path = Path(get_user_saves_dir('map_library')) / (e.atlas.id + '.json')
        self.library_bytes = self.library_path.read_bytes()
        self.template_ids = set(e.atlas.maps)
        self.template_atlas = e.atlas.id
        self.checks.append('Direct DM menu entry without campaign; standalone save excludes unrelated session party')
        self.shot = '11-freie-kartenwerkstatt'

    def library_browse(self):
        e = self.e
        e.load_map_popup()
        browser = e.library_popup
        browser.search.text = 'unauffindbar123'
        assert len(browser.list.children) == 1
        browser.search.text = 'Waldkarte'
        assert len(browser.list.children) == 1
        self.shot = '12-kartenbibliothek'

    def library_use(self):
        e = self.e
        e.library_popup.popup.dismiss()
        e.go_back()
        self.change_screen('dm_prep')
        self.sm.get_screen('dm_prep').open_map_editor()
        assert e.purpose == 'preparation'
        e.load_map_popup()
        browser = e.library_popup
        entry = next(v for v in browser.entries if v[0] == 'Wiederverwendbare Waldkarte')
        browser.choose(entry)
        assert e.atlas.id != self.template_atlas
        assert self.template_ids.isdisjoint(e.atlas.maps)
        add_element(e.map_data['artwork'], 'ellipse', [[3, 3], [12, 12]], '#506b46', 1, 'terrain')
        e.save_map()
        assert not e.map_data.get('offline_players')
        assert self.library_path.read_bytes() == self.library_bytes
        e.go_back()
        assert self.sm.get_screen('dm_prep').map_data['editor_origin']['atlas_id'] != self.template_atlas
        self.change_screen('dm_spiel')
        self.sm.get_screen('dm_spiel').open_map_workshop()
        assert e.atlas.id == self.template_atlas
        assert len(e.map_data['artwork']['elements']) == 1
        assert self.edited_map_data is None
        assert [c.name for c in self.game_manager.offline_players] == ['Andere Sitzung']
        self.checks.append('Searchable library; preparation uses separate UUID copy; source file unchanged; original reopens independently')
        self.shot = '13-vorlage-unveraendert'

    def phone_options(self):
        Window.size = (392, 844)
        self.e.set_tool('tile')
        self.e.inspector_open = True
        self.shot = '14-smartphone-optionen'

    def small_phone(self):
        e = self.e
        assert e.ids.map_canvas.height > 240
        assert e.ids.tile_type_spinner.parent == e.ids.inspector
        assert e.ids.hex_input.parent.parent is None  # hidden colour block is detached
        assert not e.grid_visible
        e.ids.tile_type_spinner.text = 'Wand'
        self.drag('tile', (7.2, 7.4), (7.2, 7.4))
        assert e.map_data['tiles'][(7, 7)]['type'] == 'Wall'
        e.set_tool('brush')
        e.brush_width = 2.3
        e.set_tool('symbol')
        e.set_tool('brush')
        assert abs(e.brush_width - 2.3) < .001
        e.inspector_open = False
        Window.size = (360, 640)
        Clock.schedule_once(lambda _: self.checks.append('Phone 360x640 canvas size: ' + str(e.ids.map_canvas.size)), .1)
        self.checks.append('Context controls retain values, detached hidden controls, wall placement on invisible square grid')
        self.shot = '15-kompaktes-smartphone'


if __name__ == '__main__':
    app = EditorCheck()
    app.run()
    report = {'checks': getattr(app, 'checks', []), 'failure': getattr(app, 'failure', 'App did not start')}
    (OUT / 'map-editor-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(bool(report['failure']))
