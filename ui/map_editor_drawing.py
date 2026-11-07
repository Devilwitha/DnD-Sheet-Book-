import math
from copy import deepcopy

from utils import map_document as md

TOOLS = ('brush', 'land', 'line', 'rect', 'ellipse', 'eraser', 'label', 'symbol', 'select', 'pin', 'tile', 'hand', 'settings', 'asset', 'region')
_NONE = ('', 'none', 'keine', 'keiner', 'kein', '-', '--', 'nichts', 'leer')
_PAINT = ('floor', 'wall', 'door', 'boden', 'wand', 'tuer', 'tür')
_KIND = {'brush': 'stroke', 'land': 'polygon', 'line': 'stroke', 'rect': 'rect', 'ellipse': 'ellipse', 'symbol': 'symbol'}


class _Touch:
    """Minimal touch/widget proxy for legacy tile handlers."""
    button = 'left'
    is_double_tap = False
    is_mouse_scrolling = False
    is_touch = True

    def __init__(self, x, y):
        self.x, self.y, self.pos, self.ud = x, y, (x, y), {}

    def collide_point(self, *a):
        return True


class DrawingTools:
    ART_KEY = 'artwork'  # key of the artwork dict inside the map (assumption)

    # ---- helpers -------------------------------------------------------
    def _m(self):
        return self.atlas.current()['map']

    def _art(self):
        return self._m().setdefault(self.ART_KEY, {'elements': [], 'layers': {}})

    def _els(self):
        return self._art().setdefault('elements', [])

    def _live(self, eid):
        return next((e for e in self._els() if e.get('id') == eid), None)

    def _total(self):
        return sum(len(e.get('points') or []) for e in self._els())

    def _size(self):
        m = self._m()
        w = m.get('width') or m.get('cols')
        h = m.get('height') or m.get('rows')
        g = m.get('tiles') or m.get('grid')
        if not (w and h) and isinstance(g, list) and g:
            h = h or len(g)
            w = w or len(g[0])
        return float(w or 0), float(h or 0)

    def _linfo(self, layer):
        ls = self._art().get('layers') or {}
        if isinstance(ls, dict):
            i = ls.get(layer)
        else:
            i = next((l for l in ls if isinstance(l, dict) and layer in (l.get('id'), l.get('name'))), None)
        if not isinstance(i, dict):
            return False, False
        return bool(i.get('hidden') or i.get('visible') is False), bool(i.get('locked'))

    def _blocked(self, layer):
        if any(self._linfo(layer)):
            self.status = 'Ebene ist ausgeblendet oder gesperrt - keine Aenderung moeglich.'
            return True
        return False

    def _w(self, name):
        return getattr(self.ids, name, None)

    def _picked(self, w):
        if w is None:
            return False
        t = str(getattr(w, 'text', '') or '').strip().lower()
        return t not in _NONE

    def _hit(self, x, y, r):
        try:
            return md.hit_element(self._art(), x, y, r, None)
        except TypeError:
            return md.hit_element(self._art(), x, y, r)

    def _restore(self, snap, cur, pop):
        if self.atlas.current() is not cur:
            return
        cur['map'] = snap
        if pop and self._undo:
            self._undo.pop()
        self._activate(reset_view=False)

    def _start(self, tool, x, y, **kw):
        cur = self.atlas.current()
        g = dict(tool=tool, cur=cur, snap=deepcopy(cur['map']), rem=False,
                 x0=x, y0=y, last=(x, y), moved=False, **kw)
        self._gesture = g
        return g

    def _mark(self, g):
        if not g['rem']:
            self._remember(g['snap'])  # Reuse the gesture snapshot: one deepcopy per stroke.
            g['rem'] = True

    def _fail(self, e):
        g = self._gesture
        self._gesture = None
        if g and g['cur'] is self.atlas.current():
            self._restore(g['snap'], g['cur'], g['rem'])
        self._error(str(e))

    def _txn(self, fn):
        """Single non-gesture edit: snapshot, apply, validate, rollback on failure."""
        cur = self.atlas.current()
        snap = deepcopy(cur['map'])
        self._remember(snap)  # Same object is the undo entry and the rollback snapshot.
        try:
            fn()
            md.validate_artwork(self._art())
            self._encode_check()
        except Exception as e:
            self._restore(snap, cur, True)
            self._error(str(e))
            return False
        self.update_grid_visuals()
        self._sync_ui()
        return True

    def _encode_check(self):
        # Re-encode only the edited map record with the same validators as Atlas.encode().
        # A stroke cannot change other maps or the tree; whole-atlas checks (tree, total size)
        # still run in _save_atlas()/_persist().
        atlas = self.atlas
        if type(atlas) is not md.Atlas:
            atlas.encode()
            return
        cur = atlas.current()
        probe = md.Atlas.__new__(md.Atlas)
        probe.id, probe.root_id, probe.active_id = atlas.id, cur['id'], cur['id']
        probe.maps = {cur['id']: dict(cur, parent_id=None, pins=[])}
        probe.encode()

    def _erase(self, x, y, r, layer):
        # Active layer only. md.erase_strokes removes every touched fill whole, so a river
        # drawn over land would delete the land below it. If the topmost hit is linework,
        # cut only the strokes of this layer and leave fills untouched.
        art = self._art()
        top = md.hit_element(art, x, y, r, layer)
        if top is None:
            return False
        strokes_only = bool(self._gesture and self._gesture.get('erase_strokes_only'))
        if not strokes_only and top['kind'] != 'stroke':
            return md.erase_strokes(art, x, y, r, layer)
        strokes = [e for e in art['elements'] if e['layer'] == layer and e['kind'] == 'stroke']
        view = dict(art, elements=strokes)
        if not md.erase_strokes(view, x, y, r, layer):
            return False
        known = {e['id'] for e in strokes}
        groups, key = {}, None
        for e in view['elements']:
            if e['id'] in known:
                key = e['id']
            groups.setdefault(key, []).append(e)
        merged = []
        for e in art['elements']:
            if e['layer'] == layer and e['kind'] == 'stroke':
                merged.extend(groups.get(e['id'], []))
            else:
                merged.append(e)
        md.validate_artwork(dict(art, elements=merged))  # Whole-document limits before commit.
        art['elements'] = merged
        return True

    def _cell(self, x, y):
        w, h = self._size()
        c, r = int(math.floor(x)), int(math.floor(y))
        if c < 0 or r < 0 or (w and c >= w) or (h and r >= h):
            return None
        return r, c

    # ---- tools ---------------------------------------------------------
    def set_tool(self, tool, *_):
        if tool not in TOOLS:
            return
        self.tool = tool
        if tool == 'label':
            self.layer = 'labels'
        elif tool in ('symbol', 'asset'):
            self.layer = 'objects'
        elif tool in ('brush', 'land', 'line', 'rect', 'ellipse'):
            self.layer = 'terrain'
        self.status = {'asset': 'Asset: auf die Karte tippen. Auswahl verschiebt; Optionen ändern Größe und Drehung.', 'region': 'Regionen: freie Grenze über die Insel ziehen oder einzelne Grenzpunkte setzen. Tab 2 öffnet die Detailkarten.', 'settings': 'Karteneinstellungen: Name, Hintergrund und Bibliothek.', 'land': 'Landfläche: Umriss ziehen; beim Loslassen wird er geschlossen und gefüllt.', 'brush': 'Pinsel: ziehen, um Gelände zu malen.', 'line': 'Linie: Start und Ende ziehen.', 'rect': 'Rechteck: Fläche aufziehen.', 'ellipse': 'Ellipse: Fläche aufziehen.', 'eraser': 'Radierer: Linien kürzen; Formen und Symbole ganz löschen.', 'label': 'Text: Position antippen.', 'symbol': 'Symbol: Position antippen.', 'select': 'Auswahl: Element antippen und ziehen; gelbe Markierung öffnet Unterkarte.', 'pin': 'Unterkarte: Position antippen oder gelbe Markierung öffnen.', 'tile': 'Spielfelder: Feldtyp oder Figur wählen, dann Karte antippen.', 'hand': 'Hand: Ansicht verschieben. Mausrad oder +/− zum Zoomen.'}[tool]
        self._sync_ui()
        if hasattr(self.ids, 'map_canvas'):
            self.ids.map_canvas.refresh()

    # ---- canvas events -------------------------------------------------
    def canvas_down(self, x, y, touch=None):
        if self._gesture:
            self.canvas_up()
        try:
            return self._down(x, y)
        except Exception as e:
            self._fail(e)
            return False

    def canvas_move(self, x, y, touch=None):
        try:
            return self._move(x, y)
        except Exception as e:
            self._fail(e)
            return False

    def canvas_up(self, x=None, y=None, touch=None):
        g = self._gesture
        if not g:
            return False
        try:
            if g['cur'] is not self.atlas.current():
                self._gesture = None
                return False
            if x is not None and y is not None:
                self._move(x, y)
            if g['tool'] == 'region':
                self._finish_region(g)
                return True
            if g['rem']:
                md.validate_artwork(self._art())
                self._encode_check()  # Reject an unsavable gesture while undo can restore it.
        except Exception as e:
            self._fail(e)
            return False
        self._gesture = None
        self.update_grid_visuals()
        self._sync_ui()
        if g['tool'] in ('select', 'pin') and not g['moved']:
            if g.get('child'):
                self._navigate(g['child'])
            elif g['tool'] == 'pin':
                px, py = g.get('pos') or (g['x0'], g['y0'])
                self._add_child_at(px, py)
        return True

    def canvas_context(self, x, y, touch=None):
        if self._gesture:
            return False
        rc = self._cell(x, y)
        if rc is None:
            return False
        self._remember()
        self.show_tile_context_menu(*rc)
        return True

    # ---- gesture internals ---------------------------------------------
    def _down(self, x, y):
        t = self.tool
        if t in ('hand', 'settings'):
            return False
        if t == 'asset':
            return self._place_asset(x, y)
        if t == 'region':
            return self._region_down(x, y)
        if t == 'tile':
            return self._tile_down(x, y)
        if t in ('select', 'pin'):
            return self._sel_down(t, x, y)
        if t == 'label':
            return self._label(x, y)
        layer = self.layer
        if self._blocked(layer):
            return True
        g = self._start(t, x, y, layer=layer, r=max(.25, float(self.brush_width) / 2))
        if t == 'eraser':
            top = md.hit_element(self._art(), x, y, g['r'], layer)
            g['erase_strokes_only'] = bool(top and top['kind'] == 'stroke')
            self._mark(g)
            self._erase(x, y, g['r'], layer)
        else:
            pts = [[x, y]] if t in ('brush', 'symbol') else [[x, y], [x, y]]
            if t == 'land':
                pts.append([x, y])
            if self._total() + len(pts) > md.MAX_POINTS:
                self._gesture = None
                self.status = 'Punktelimit erreicht.'
                return True
            self._mark(g)
            g['id'] = md.add_element(self._art(), _KIND[t], pts, self.color, self.brush_width,
                                     layer, symbol=self.symbol)
        self.update_grid_visuals()
        return True

    def _label(self, x, y):
        layer, color, width = self.layer, self.color, self.brush_width
        if self._blocked(layer):
            return True
        cur = self.atlas.current()
        nid = cur.get('id')

        def done(text):
            text = (text or '').strip()
            if not text:
                return
            if self.atlas.current() is not cur or cur.get('id') != nid:
                self._error('Karte hat gewechselt - Beschriftung verworfen.')
                return
            if self._blocked(layer):
                return
            if len(text) > md.MAX_TEXT:
                raise ValueError(f'Beschriftung darf höchstens {md.MAX_TEXT} Zeichen haben.')
            def add():
                self.selected_id = md.add_element(self._art(), 'label', [[x, y]], color, width, layer, text=text)
            if self._txn(add):
                self.set_tool('select')
                self.inspector_open = True
                self.status = 'Beschriftung gesetzt. Auswahl verschiebt; Optionen ändern Text, Größe und Farbe.'
        self._prompt('Beschriftung', '', done)
        return True

    def _tile_down(self, x, y):
        rc = self._cell(x, y)
        if rc is None:
            return True
        placing = any(self._picked(self._w(n)) for n in
                      ('enemy_spinner', 'player_spinner', 'furniture_spinner'))
        g = self._start('tile', x, y, placing=placing, seen={rc})
        self._mark(g)
        t = _Touch(x, y)
        self.on_tile_touch_down(rc[0], rc[1], t, t)
        return True

    def _sel_down(self, t, x, y):
        r = max(.5, float(self.brush_width) / 2)
        pin = next((p for p in self.atlas.current()['pins']
                    if math.hypot(p['x'] - x, p['y'] - y) <= .8), None)
        live = None
        if t == 'select' and pin is None:
            hit = self._hit(x, y, r)
            live = self._live(hit['id']) if hit else None
        self.selected_id = live['id'] if live else ''
        self._start(t, x, y, id=live['id'] if live else None,
                    child=pin['child_id'] if pin else None,
                    pos=(pin['x'], pin['y']) if pin else None,
                    pts0=deepcopy(live['points']) if live else None)
        self._sync_ui()
        if live:
            self.inspector_open = True
        return True

    def edit_label(self):
        element = self._live(self.selected_id)
        if not element or element['kind'] != 'label' or self._blocked(element['layer']):
            return
        cur = self.atlas.current()
        def edit(text):
            if self.atlas.current() is not cur or self._live(element['id']) is not element:
                raise ValueError('Die Auswahl hat gewechselt.')
            if not 1 <= len(text) <= md.MAX_TEXT:
                raise ValueError(f'Bitte 1 bis {md.MAX_TEXT} Zeichen eingeben.')
            if not self._blocked(element['layer']):
                return self._txn(lambda: element.__setitem__('text', text))
            raise ValueError('Die Beschriftungsebene ist gesperrt oder ausgeblendet.')
        self._prompt('Beschriftung bearbeiten', element['text'], edit)

    def resize_label(self, factor):
        element = self._live(self.selected_id)
        if element and element['kind'] == 'label' and not self._blocked(element['layer']):
            self._txn(lambda: element.__setitem__('width', max(.5, min(4, element['width'] * factor))))

    def _move(self, x, y):
        g = self._gesture
        if not g:
            return False
        if g['cur'] is not self.atlas.current():
            self._gesture = None
            return False
        t = g['tool']
        lx, ly = g['last']
        if t == 'region':
            if g['shape'] == 'Grenzpunkte setzen':
                g['last'] = (x, y)
                return True
            if math.hypot(x - g['x0'], y - g['y0']) > .2:
                g['moved'] = True
            if g['shape'] == 'Rechteck':
                g['area'] = [[g['x0'], g['y0']], [x, g['y0']], [x, y], [g['x0'], y]]
            elif math.hypot(x - lx, y - ly) > .25:
                if len(g['area']) >= 256:
                    from utils.map_regions import simplify_gesture
                    g['area'] = simplify_gesture(g['area'])
                g['area'].append([x, y])
                g['last'] = (x, y)
            self.ids.map_canvas.refresh()
            return True
        if t == 'tile':
            tt = str(getattr(self._w('tile_type_spinner'), 'text', '')).strip().lower()
            rc = self._cell(x, y)
            if g['placing'] or tt not in _PAINT or rc is None or rc in g['seen']:
                return True
            g['seen'].add(rc)
            tc = _Touch(x, y)
            self.on_tile_touch_down(rc[0], rc[1], tc, tc)
            return True
        if t == 'eraser':
            d = math.hypot(x - lx, y - ly)
            n = max(1, min(400, int(math.ceil(d / (g['r'] / 2)))))
            for i in range(1, n + 1):
                k = i / n
                self._erase(lx + (x - lx) * k, ly + (y - ly) * k, g['r'], g['layer'])
            g['last'] = (x, y)
        elif t in ('brush', 'land'):
            if math.hypot(x - lx, y - ly) < max(.12, min(.4, float(self.brush_width) / 5)):
                return True
            el = self._live(g['id'])
            if el is None:
                return True
            if len(el['points']) >= md.MAX_STROKE_POINTS or self._total() >= md.MAX_POINTS:
                raise ValueError('Der Strich ist zu lang oder die Karte zu voll. Bitte kürzere Abschnitte zeichnen. Der letzte Strich wurde zurückgenommen.')
            el['points'].append([x, y])
            g['last'] = (x, y)
        elif t in ('line', 'rect', 'ellipse'):
            el = self._live(g['id'])
            if el is None:
                return True
            el['points'][1] = [x, y]
        elif t == 'select' and g.get('pts0'):
            dx, dy = x - g['x0'], y - g['y0']
            if not g['moved']:
                if math.hypot(dx, dy) < .2:
                    return True
                g['moved'] = True
                self._mark(g)
            el = self._live(g['id'])
            if el is None:
                return True
            p0 = g['pts0']
            xs, ys = [p[0] for p in p0], [p[1] for p in p0]
            w, h = self._size()
            if w:
                dx = max(-min(xs), min(w - max(xs), dx))
            if h:
                dy = max(-min(ys), min(h - max(ys), dy))
            el['points'] = [[p[0] + dx, p[1] + dy] + list(p[2:]) for p in p0]
        else:
            if t in ('select', 'pin') and math.hypot(x - g['x0'], y - g['y0']) >= .2:
                g['moved'] = True
            return True
        self.update_grid_visuals()
        return True

    # ---- history / selection edits ---------------------------------------
    def _step(self, src, dst):
        if self._gesture or not src:
            return
        if isinstance(src[-1], md.Atlas):
            dst.append(deepcopy(self.atlas))
            self.atlas = src.pop()
        else:
            cur = self.atlas.current()
            dst.append(cur['map'])  # The old live map is dropped here; no copy needed.
            cur['map'] = src.pop()
        self._trim_history(dst)
        self.dirty = True
        self._activate(reset_view=False)
        if self.selected_id and not self._live(self.selected_id):
            self.selected_id = ''
        self._sync_ui()

    def undo(self, *_):
        self._step(self._undo, self._redo)

    def redo(self, *_):
        self._step(self._redo, self._undo)

    def delete_selected(self, *_):
        if self._gesture or not self.selected_id:
            return
        e = self._live(self.selected_id)
        if e is None:
            self.selected_id = ''
            return
        if self._blocked(e.get('layer')):
            return

        def rm():
            els = self._els()
            els[:] = [i for i in els if i is not e]
        if self._txn(rm):
            self.selected_id = ''
            self._sync_ui()

    def recolor_selected(self, *_):
        if self._gesture or not self.selected_id:
            return
        e = self._live(self.selected_id)
        if e is None:
            self.selected_id = ''
            return
        if self._blocked(e.get('layer')):
            return
        color = self.color
        self._txn(lambda: e.__setitem__('color', color))
