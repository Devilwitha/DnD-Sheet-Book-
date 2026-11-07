"""Real Kivy dialogs and dispatched pointer clicks; isolated profile, no server."""
import copy
import json
import sys
from pathlib import Path

from verify_map_editor import EditorCheck, OUT
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.tests.common import UnitTestTouch
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from utils.paths import get_user_saves_dir
from utils.map_document import read_atlas, Atlas


class InteractionCheck(EditorCheck):
    def on_start(self):
        self.failure = None
        self.checks = []
        self.sm.transition.duration = 0
        self.steps = iter([self.start, self.save_open, self.save_cancel, self.save_retry,
            self.name_empty, self.name_fill, self.name_saved, self.region_draw,
            self.region_confirm, self.region_stays, self.second_region_confirm,
            self.regions_tab, self.region_choose, self.region_opened,
            self.house_place, self.house_resize, self.house_size_enter,
            self.house_size_check, self.label_place, self.label_confirm,
            self.label_edit_open, self.label_edit_confirm, self.label_check,
            self.rename_open, self.rename_confirm, self.save_copy_open,
            self.save_copy_confirm, self.save_copy_check, self.mobile,
            self.mobile_text, self.mobile_confirm, self.mobile_done,
            self.new_world_open, self.new_world_submit, self.new_world_save,
            self.new_world_named, self.new_world_check])
        Clock.schedule_once(self.step, .3)

    def capture(self, _):
        try:
            self.root.export_to_png(str(OUT / (self.shot + '.png')))
            popup = getattr(self.e, '_input_popup', None)
            if popup is not None and popup.parent:
                popup.export_to_png(str(OUT / (self.shot + '-dialog.png')))
            Clock.schedule_once(self.step, .1)
        except Exception:
            import traceback
            self.failure = traceback.format_exc()
            self.stop()

    def click(self, widget):
        assert not widget.disabled
        x, y = widget.to_window(widget.center_x, widget.center_y)
        assert 0 <= x <= Window.width and 0 <= y <= Window.height, (widget.text, x, y)
        touch = UnitTestTouch(x, y)
        touch.touch_down()
        Clock.schedule_once(lambda _: touch.touch_up(), .07)

    def button(self, text, parent=None):
        return next(w for w in (parent or self.e).walk()
                    if isinstance(w, Button) and w.text == text)

    def fill(self, value):
        details = getattr(self.e, '_details_popup', None)
        if details is not None and details.parent:
            details.ids.name.text = value
            self.click(details.ids.accept)
        else:
            popup = self.e._input_popup
            assert popup.parent and popup.height == 250
            popup.ids.field.text = value
            self.click(popup.ids.accept)

    def start(self):
        Window.size = (1280, 820)
        self.change_screen('dm_spiel')
        self.sm.get_screen('dm_spiel').open_map_workshop()
        self.e = self.sm.get_screen('map_editor')
        self.e._error = lambda msg: (_ for _ in ()).throw(AssertionError(msg))
        self.draft_id = self.e.atlas.id
        self.shot = 'bedienung-01-start'

    def save_open(self):
        self.click(self.button('Speichern'))
        self.shot = 'bedienung-02-erster-name'

    def save_cancel(self):
        assert self.e._input_popup.title == 'Welt vor dem Speichern benennen'
        self.click(self.e._input_popup.ids.cancel)

    def save_retry(self):
        assert self.e.atlas.id == self.draft_id and self.e._needs_name()
        assert not (Path(get_user_saves_dir('map_library')) / (self.draft_id + '.json')).exists()
        self.click(self.button('Speichern'))

    def name_empty(self):
        self.fill('')

    def name_fill(self):
        assert self.e._input_popup.ids.error.text
        self.fill('Insel Morgenrot')

    def name_saved(self):
        assert not self.e._needs_name() and not self.e.dirty
        assert self.e.map_title == 'Insel Morgenrot'
        self.source_path = Path(get_user_saves_dir('map_library')) / (self.e.atlas.id + '.json')
        assert read_atlas(self.source_path).maps[self.e.atlas.root_id]['name'] == 'Insel Morgenrot'
        self.checks.append('First-save name dialog: real pointer click, empty-name rejection, cancel preserves draft, Unicode name saved')

    def region_draw(self):
        self.e.region_shape = 'Rechteck'
        self.drag('region', (3, 3), (14, 15))
        self.shot = 'bedienung-03-regionsname'

    def region_confirm(self):
        self.fill('Westküste')

    def region_stays(self):
        assert self.e.atlas.current()['level'] == 'world'
        assert len(self.e.atlas.current()['pins']) == 1
        self.drag('region', (18, 3), (29, 20))

    def second_region_confirm(self):
        self.fill('Ostgebirge')

    def regions_tab(self):
        assert self.e.atlas.current()['level'] == 'world'
        assert len(self.e.atlas.current()['pins']) == 2
        self.click(self.e._level_buttons['region'])
        self.shot = 'bedienung-04-regionen-tab'

    def region_choose(self):
        popup = self.e._choice_dialog
        self.click(self.button('Westküste · Insel Morgenrot', popup))

    def region_opened(self):
        assert self.e.atlas.current()['name'] == 'Westküste'
        self.checks.append('Two regions defined on main map without leaving it; Regions tab opens chosen detail map')

    def house_place(self):
        assert self.e.select_asset('GEB-009')
        self.drag('asset', (9, 9), (9, 9))
        self.house_id = self.e.selected_id
        self.shot = 'bedienung-05-haus'

    def house_resize(self):
        self.click(self.button('Größer'))

    def house_size_enter(self):
        assert abs(self.e._live(self.house_id)['width'] - 4.8) < 1e-7
        self.click(self.button('Größe eingeben …'))

    def house_size_check(self):
        self.fill('7,5')

    def label_place(self):
        assert self.e._live(self.house_id)['width'] == 7.5
        self.checks.append('After placement, Larger and numeric size edit the existing house, not only the next stamp')
        self.drag('label', (21, 6), (21, 6))
        self.shot = 'bedienung-06-beschriftung'

    def label_confirm(self):
        self.fill('Hauptstadt')

    def label_edit_open(self):
        self.label_id = self.e.selected_id
        assert self.e._live(self.label_id)['text'] == 'Hauptstadt'
        self.click(self.button('Beschriftung bearbeiten …'))

    def label_edit_confirm(self):
        self.fill('Hafen Morgenrot')

    def label_check(self):
        assert self.e._live(self.label_id)['text'] == 'Hafen Morgenrot'
        self.e.undo()
        assert self.e._live(self.label_id)['text'] == 'Hauptstadt'
        self.e.redo()
        assert self.e._live(self.label_id)['text'] == 'Hafen Morgenrot'
        self.checks.append('Label creation and later text edit use real dialogs; undo/redo restores text')

    def rename_open(self):
        self.e.open_level('world')
        self.e.rename_map()
        self.shot = 'bedienung-07-umbenennen'

    def rename_confirm(self):
        self.fill('Insel Morgenrot – Heimat')

    def save_copy_open(self):
        assert self.e.atlas.id == self.draft_id
        self.e.save_map()
        self.saved_source = self.source_path.read_bytes()
        self.e.save_as()

    def save_copy_confirm(self):
        self.fill('Insel Morgenrot – Variante')

    def save_copy_check(self):
        assert self.e.atlas.id != self.draft_id
        assert self.source_path.read_bytes() == self.saved_source
        assert len(self.e.atlas.maps) == 3
        assert not (set(read_atlas(self.source_path).maps) & set(self.e.atlas.maps))
        self.checks.append('Rename preserves atlas ID; Save As copies all regions with independent IDs and unchanged source file')
        self.shot = 'bedienung-08-gespeicherte-kopie'

    def mobile(self):
        Window.size = (360, 640)
        self.e.inspector_open = False

    def mobile_text(self):
        self.drag('label', (14, 12), (14, 12))
        self.shot = 'bedienung-09-smartphone-dialog'

    def mobile_confirm(self):
        self.fill('Kleiner Hafen')

    def mobile_done(self):
        assert self.e._live(self.e.selected_id)['text'] == 'Kleiner Hafen'
        assert self.e.ids.map_canvas.height > 100
        self.e.save_map()
        self.checks.append('360x640: label dialog reachable and confirmed with real pointer input, edit saved')

    def new_world_open(self):
        self.e.new_atlas_popup()
        self.shot = 'bedienung-10-neue-welt'

    def new_world_submit(self):
        popup = next(w for w in Window.children if getattr(w, 'title', '').startswith('Neuer Atlas'))
        self.click(self.button('Atlas erstellen', popup))

    def new_world_save(self):
        assert self.e._needs_name()
        assert len(self.e.atlas.maps) == 1
        self.click(self.button('Speichern'))

    def new_world_named(self):
        self.fill('Zweite Welt')

    def new_world_check(self):
        assert self.e.atlas.current()['name'] == 'Zweite Welt' and not self.e._needs_name()
        self.checks.append('New World dialog opens on narrow screen; blank initial name is requested on first explicit save')


if __name__ == '__main__':
    app = InteractionCheck()
    app.run()
    result = {'checks': app.checks, 'failure': app.failure}
    (OUT / 'real-dialog-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(bool(app.failure))
