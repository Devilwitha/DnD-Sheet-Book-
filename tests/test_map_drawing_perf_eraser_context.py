from copy import deepcopy
from types import SimpleNamespace

import pytest

import ui.map_editor_drawing as drawing
from ui.map_editor_drawing import DrawingTools
from utils import map_document as md


class Harness(DrawingTools):
    def __init__(self, atlas):
        self.atlas = atlas
        self._undo, self._redo, self._gesture = [], [], None
        self.tool, self.layer, self.brush_width = 'brush', 'terrain', 1.0
        self.color, self.symbol, self.selected_id = '#5f8148', 'Baum', ''
        self.status, self.dirty, self.errors, self.copies = '', False, [], []
        self.ids = SimpleNamespace()

    def _remember(self, snapshot=None):
        if snapshot is None:
            self.copies.append('remember')
            snapshot = deepcopy(self.atlas.current()['map'])
        self._undo.append(snapshot)
        self._redo.clear()

    def _trim_history(self, stack):
        pass

    def _activate(self, reset_view=True):
        pass

    def update_grid_visuals(self):
        pass

    def _sync_ui(self):
        pass

    def _error(self, message):
        self.errors.append(message)


def new_atlas():
    return md.Atlas(md.new_map(24, 32, 'world'), name='Welt')


def count_copies(h, monkeypatch):
    real = drawing.deepcopy

    def spy(value, *a):
        h.copies.append('drawing')
        return real(value, *a)
    monkeypatch.setattr(drawing, 'deepcopy', spy)


def stroke(h):
    h.canvas_down(3, 3)
    h.canvas_move(5, 5)
    h.canvas_up()


def land_and_river(h):
    art = h._art()
    land = md.add_element(art, 'polygon', [[2, 2], [10, 2], [10, 10], [2, 10]], '#5f8148', 1, 'terrain')
    river = md.add_element(art, 'stroke', [[0, 6], [12, 6]], '#3366aa', .5, 'terrain')
    return land, river


def test_stroke_makes_one_snapshot(monkeypatch):
    h = Harness(new_atlas())
    count_copies(h, monkeypatch)
    stroke(h)
    assert h.copies == ['drawing']
    assert len(h._undo) == 1 and h._undo[0]['artwork']['elements'] == []
    assert len(h._art()['elements']) == 1


def test_stroke_commit_encodes_only_edited_map(monkeypatch):
    atlas = new_atlas()
    atlas.add_child('Region', 5, 5)
    seen = []
    real = md.Atlas.encode

    def spy(self):
        seen.append(len(self.maps))
        return real(self)
    monkeypatch.setattr(md.Atlas, 'encode', spy)
    h = Harness(atlas)
    stroke(h)
    assert seen == [1]


def test_failed_commit_rolls_back(monkeypatch):
    h = Harness(new_atlas())

    def boom():
        raise ValueError('too big')
    monkeypatch.setattr(h, '_encode_check', boom)
    stroke(h)
    assert h._art()['elements'] == []
    assert h._undo == []
    assert h.errors == ['too big']


def test_undo_moves_live_map_to_redo_without_copy():
    h = Harness(new_atlas())
    stroke(h)
    live = h.atlas.current()['map']
    h.undo()
    assert h._redo[-1] is live
    assert h._art()['elements'] == []


def test_eraser_cuts_river_but_keeps_land():
    h = Harness(new_atlas())
    land, river = land_and_river(h)
    assert h._erase(6, 6, .5, 'terrain')
    els = h._art()['elements']
    assert any(e['id'] == land for e in els)
    strokes = [e for e in els if e['kind'] == 'stroke']
    assert len(strokes) == 2
    assert all(not 5.5 < p[0] < 6.5 for e in strokes for p in e['points'])


def test_eraser_still_removes_land_away_from_river():
    h = Harness(new_atlas())
    land, river = land_and_river(h)
    h._erase(6, 9, .5, 'terrain')
    ids = {e['id'] for e in h._art()['elements']}
    assert land not in ids and river in ids


def test_eraser_drag_through_new_gap_keeps_underlying_land():
    h = Harness(new_atlas())
    land, _ = land_and_river(h)
    h.tool = 'eraser'
    h.canvas_down(6, 6)
    h.canvas_move(6.1, 6)
    h.canvas_move(6.2, 6.1)
    h.canvas_up()
    assert land in {e['id'] for e in h._art()['elements']}
    assert len(h._undo) == 1


def test_eraser_ignores_other_layers():
    h = Harness(new_atlas())
    land, _ = land_and_river(h)
    sym = md.add_element(h._art(), 'symbol', [[6, 9]], '#000000', 1, 'objects')
    h._erase(6, 9, .5, 'terrain')
    ids = {e['id'] for e in h._art()['elements']}
    assert sym in ids and land not in ids


def test_remember_accepts_prepared_snapshot():
    tools = pytest.importorskip('ui.map_editor_tools')
    snap = {'marker': 1}
    ns = SimpleNamespace(_undo=[], _redo=[1], map_data={'x': 2}, dirty=False,
                         _trim_history=lambda s: None, _sync_ui=lambda: None)
    tools.MapEditorTools._remember(ns, snap)
    assert ns._undo[0] is snap and ns._redo == [] and ns.dirty
    tools.MapEditorTools._remember(ns)
    assert ns._undo[-1] == {'x': 2} and ns._undo[-1] is not ns.map_data
