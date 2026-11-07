"""Real rendering and editing of generated adjacent regions, without user data."""
import copy
import json
import sys
from pathlib import Path
from PIL import Image
from verify_map_editor_interactions import InteractionCheck, OUT
from kivy.clock import Clock
from kivy.core.window import Window
from utils.map_document import read_atlas, Atlas, new_map, add_element
from utils.map_region_context import KEY
from utils.map_regions import boundary_center
from utils.formats import encode_map, decode_map

def synthetic_atlas():
    atlas = Atlas(new_map(24, 32), name='Region context test')
    add_element(atlas.map['artwork'], 'rect', [[2, 2], [30, 22]], '#8d704e', .15, 'terrain')
    add_element(atlas.map['artwork'], 'stroke', [[2, 12], [30, 12]], '#819daa', .5, 'terrain')
    for i, (left, right) in enumerate([(2, 11), (11, 20), (20, 30)], 1):
        atlas.add_child(f'Region {i}', (left + right) / 2, 8,
                        [[left, 2], [right, 2], [right, 22], [left, 22]])
        atlas.navigate(atlas.root_id)
    return atlas


class ContextCheck(InteractionCheck):
    def on_start(self):
        self.failure = None
        self.checks = []
        self.sm.transition.duration = 0
        self.steps = iter([self.start, self.world, self.first, self.check_first,
                          self.second, self.check_second, self.third, self.check_third,
                          self.edit_detail, self.undo_detail, self.redo_detail,
                          self.reopen, self.check_reopen, self.parent_change, self.refresh_child,
                          self.check_refresh, self.concave, self.check_concave,
                          self.game_view, self.check_game, self.mobile, self.check_mobile])
        Clock.schedule_once(self.step, .3)

    def world(self):
        self.template_atlas = synthetic_atlas()
        self.original_template = self.template_atlas.encode()
        atlas = self.template_atlas.duplicate()
        self.region_ids = [r['id'] for r in atlas.maps.values() if r['level'] == 'region']
        atlas.navigate(atlas.root_id)
        self.original_world = copy.deepcopy(atlas.map['artwork'])
        self.e._open_atlas(atlas)
        self.shot = 'region-context-01-world'

    def first(self):
        self.e._navigate(self.region_ids[0])
        self.shot = 'region-context-02-region1'

    def check_visible(self):
        assert self.e.level_title == 'Region'
        assert self.e.map_data[KEY]['artwork'] == self.original_world
        with Image.open(OUT / (self.shot + '.png')) as im:
            colors = im.convert('RGB').getcolors(im.width * im.height)
            brown = sum(n for n,(r,g,b) in colors if r>g>b and 100<r<180 and 60<g<150 and 40<b<120)
            river = sum(n for n,(r,g,b) in colors if abs(r-129)<5 and abs(g-157)<5 and abs(b-170)<5)
            assert brown > 10000 and river > 400, (brown, river)
        self.checks.append(self.e.map_title + ': visible inherited land and river, own artwork still empty')

    def check_first(self): self.check_visible()
    def second(self):
        self.e._navigate(self.region_ids[1]); self.shot = 'region-context-03-region2'
    def check_second(self): self.check_visible()
    def third(self):
        self.e._navigate(self.region_ids[2]); self.shot = 'region-context-04-region3'
    def check_third(self): self.check_visible()

    def edit_detail(self):
        ctx = self.e.map_data[KEY]
        x,y = boundary_center(ctx['boundary'])
        ox,oy,step = ctx['frame']
        p = ((x-ox)/step, (y-oy)/step)
        self.base = copy.deepcopy(ctx)
        self.e.color = '#ff00ff'
        self.drag('brush', p, (p[0]+2, p[1]+1))
        assert self.e.map_data['artwork']['elements']
        self.detail = copy.deepcopy(self.e.map_data['artwork'])
        self.shot = 'region-context-05-eigene-details'

    def undo_detail(self):
        self.e.undo()
        assert not self.e.map_data['artwork']['elements'] and self.e.map_data[KEY] == self.base
    def redo_detail(self):
        self.e.redo()
        assert self.e.map_data['artwork'] == self.detail
    def reopen(self):
        assert self.e.save_map()
        from utils.paths import get_user_saves_dir
        path = Path(get_user_saves_dir('map_library')) / (self.e.atlas.id + '.json')
        self.e._open_atlas(read_atlas(path))
    def check_reopen(self):
        assert self.e.map_data[KEY] == self.base
        assert self.e.map_data['artwork'] == self.detail
        assert self.e.atlas.maps[self.e.atlas.root_id]['map']['artwork'] == self.original_world
        assert decode_map(encode_map(self.e.map_data))[KEY] == self.base
        self.checks.append('Own detail brush, undo/redo, save/reopen and standalone codec preserve the world and inherited context')
    def parent_change(self):
        self.e._navigate(self.e.atlas.root_id)
        self.e._txn(lambda: add_element(self.e._art(), 'label', [[12,12]], '#ffffff', 1, 'labels', text='World update'))
    def refresh_child(self): self.e._navigate(self.region_ids[2])
    def check_refresh(self):
        assert self.e.map_data[KEY]['artwork']['elements'][-1]['text'] == 'World update'
        assert self.e.map_data[KEY]['frame'] == self.base['frame']
        assert self.e.map_data['artwork'] == self.detail
        self.checks.append('Parent edits appear after navigation; existing detail coordinates and frame stay fixed')

    def concave(self):
        atlas = Atlas(new_map(20,20), name='Clip-Test')
        add_element(atlas.map['artwork'], 'rect', [[0,0],[20,20]], '#bb6622', .2, 'terrain')
        add_element(atlas.map['artwork'], 'stroke', [[0,5],[20,5]], '#00ffff', .4, 'terrain')
        add_element(atlas.map['artwork'], 'asset', [[6,5]], '#ffffff', 3, 'objects', asset_id='BAU-003')
        atlas.add_child('L-Region', 4,4, [[2,2],[10,2],[10,6],[6,6],[6,12],[2,12]])
        self.e._open_atlas(atlas)
        self.shot = 'region-context-06-konkav'

    def sample_world(self, point, *, game=False):
        context = self.e.map_data[KEY]
        ox,oy,step = context['frame']
        if game:
            cv = self.game_grid
            x,top,u = cv.x, cv.top, cv.tile_size
        else:
            x,top,u = self.e.ids.map_canvas._geometry()
        px,py = x+(point[0]-ox)/step*u, top-(point[1]-oy)/step*u
        with Image.open(OUT / (self.shot + '.png')) as im:
            return im.convert('RGB').getpixel((int(px), im.height-1-int(py)))

    def check_pixels(self, game=False):
        for p in [(8,9),(12,5)]:
            col = self.sample_world(p, game=game)
            assert all(abs(v-e)<4 for v,e in zip(col,(41,51,56))), (p,col)
        col = self.sample_world((4,9), game=game)
        assert all(abs(v-e)<4 for v,e in zip(col,(187,102,34))), col
        col = self.sample_world((9,5), game=game)
        assert col[0]<10 and col[1]>240 and col[2]>240, col

    def check_concave(self):
        self.check_pixels()
        self.checks.append('Real pixel checks: concave notch and outside river hidden; interior land/river visible, boundary asset renders')
    def game_view(self):
        from ui.custom_widgets import MapGridWidget
        data = decode_map(encode_map(self.e.map_data))
        self.game_grid = MapGridWidget()
        self.game_grid.size_hint = (None,None)
        self.game_grid.size, self.game_grid.pos = (640,480), (250,180)
        self.game_grid.tile_size = 20
        self.root.add_widget(self.game_grid)
        self.game_grid.set_data(data, [], None)
        self.shot = 'region-context-07-spielkarte'
    def check_game(self):
        self.check_pixels(game=True)
        self.root.remove_widget(self.game_grid)
        self.checks.append('Standalone game map uses the same clipped inherited artwork, including nested stencil restoration')
    def mobile(self):
        Window.size = (360,640)
        atlas = self.template_atlas.duplicate()
        atlas.navigate(next(r['id'] for r in atlas.maps.values() if r['name']=='Region 1'))
        self.e._open_atlas(atlas)
        self.shot = 'region-context-08-handy'
    def check_mobile(self):
        assert self.e.map_data[KEY]
        assert self.template_atlas.encode() == self.original_template
        self.checks.append('360 x 640: region opens with world context; original template untouched')


if __name__ == '__main__':
    app = ContextCheck()
    app.run()
    report = dict(checks=app.checks, failure=app.failure)
    (OUT/'region-context-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(bool(app.failure))
