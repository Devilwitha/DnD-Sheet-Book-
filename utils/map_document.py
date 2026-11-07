'''Map document model: artwork layer, hierarchical Atlas, hit testing.

Pure Python, no Kivy. utils.formats is imported lazily inside Atlas
serialization methods only (formats imports validate_artwork from here).

Assumption to verify on integration: decoded map tiles are a dict keyed by
(row, col) tuples whose values are dicts with keys type/object/furniture/
trigger_message. Change _tile()/_normalize_map if the codec differs.
'''
from __future__ import annotations

import copy
import math
import json
import re
import uuid
from utils.asset_catalog import valid_asset_id
from utils.map_regions import validate_boundary

LAYERS = ('terrain', 'objects', 'labels')
LAYER_NAMES = {'terrain': 'Gelände', 'objects': 'Objekte', 'labels': 'Beschriftungen'}
LEVELS = ('world', 'region', 'site', 'interior')
LEVEL_LABELS = {'world': 'Welt', 'region': 'Region', 'site': 'Ort', 'interior': 'Innenraum'}
KINDS = ('stroke', 'polygon', 'rect', 'ellipse', 'label', 'symbol', 'asset')
SYMBOLS = ('Baum', 'Berg', 'Haus', 'Höhle', 'Felsen', 'Tisch')
TILE_TYPES = ('Floor', 'Wall', 'Door', 'Trigger')

MAX_ELEMENTS = 300
MAX_POINTS = 6000
MAX_STROKE_POINTS = 1024
MAX_TEXT = 160
MAX_MAPS = 32
MAX_ATLAS_NODES = MAX_MAPS * 50000 + 1000
MAX_DIM = 100
MAX_NAME = 80
COORD_MAX = 100.0
WIDTH_MIN = 0.05
WIDTH_MAX = 20.0
CHILD_ROWS = 24
CHILD_COLS = 32

_WATER = '#8fa9b5'
_PARCHMENT = '#e6d8b8'
_ART_KEYS = {'version', 'background', 'grid', 'layers', 'elements'}
_LAYER_KEYS = {'id', 'name', 'visible', 'locked'}
_EL_KEYS = {'id', 'layer', 'kind', 'points', 'color', 'width', 'text', 'symbol'}
_REC_KEYS = {'id', 'name', 'level', 'parent_id', 'map', 'pins'}
_ATLAS_KEYS = {'format', 'version', 'id', 'root_id', 'active_id', 'maps'}


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _num(v, label, lo=-math.inf, hi=math.inf):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f'{label}: Zahl erwartet')
    try:
        f = float(v)
    except OverflowError:
        raise ValueError(f'{label}: Zahl zu gross') from None
    if not math.isfinite(f) or not lo <= f <= hi:
        raise ValueError(f'{label}: Wert ausserhalb des erlaubten Bereichs')
    return f


def _color(v, label='color'):
    if not isinstance(v, str) or re.fullmatch('#[0-9a-fA-F]{6}', v) is None:
        raise ValueError(f'{label}: Farbe im Format #rrggbb erwartet')
    return v.lower()


def _hex_id(v, label):
    if not isinstance(v, str) or re.fullmatch('[0-9a-fA-F]{32}', v) is None:
        raise ValueError(f'{label}: 32-stellige Hex-ID erwartet')
    return v.lower()


def _name(v):
    if not isinstance(v, str) or not 1 <= len(v.strip()) <= MAX_NAME:
        raise ValueError(f'Name muss 1-{MAX_NAME} Zeichen lang sein')
    return v.strip()


def _level(v):
    if v not in LEVELS:
        raise ValueError(f'Unbekannte Ebene: {v!r}')
    return v


def _next_level(level):
    i = LEVELS.index(level)
    return LEVELS[i + 1] if i + 1 < len(LEVELS) else None


# ---------------------------------------------------------------- artwork

def color_tuple(color, alpha=1.0):
    '''Convert '#rrggbb' into an (r, g, b, a) tuple of floats in 0..1.'''
    c = _color(color)
    a = _num(alpha, 'alpha', 0.0, 1.0)
    return (int(c[1:3], 16) / 255.0, int(c[3:5], 16) / 255.0, int(c[5:7], 16) / 255.0, a)


def new_artwork(level='interior'):
    _level(level)
    interior = level == 'interior'
    return {
        'version': 1,
        'background': _PARCHMENT if interior else _WATER,
        'grid': False,
        'layers': [{'id': i, 'name': LAYER_NAMES[i], 'visible': True, 'locked': False}
                   for i in LAYERS],
        'elements': [],
    }


def _point(p, label):
    if not isinstance(p, (list, tuple)) or len(p) != 2:
        raise ValueError(f'{label}: Punkt [x, y] erwartet')
    return [_num(p[0], label, 0.0, COORD_MAX), _num(p[1], label, 0.0, COORD_MAX)]


def _element(e, layer_ids):
    if not isinstance(e, dict):
        raise ValueError('Element: Objekt erwartet')
    extra = {'asset_id', 'rotation', 'remove_white'} if e.get('kind') == 'asset' else set()
    if set(e) != _EL_KEYS | extra:
        raise ValueError('Element: ungültige oder fehlende Felder')
    eid = _hex_id(e['id'], 'Element-ID')
    if e['layer'] not in layer_ids:
        raise ValueError('Element: unbekannte Ebene')
    kind = e['kind']
    if kind not in KINDS:
        raise ValueError('Element: unbekannte Art')
    pts = e['points']
    if not isinstance(pts, (list, tuple)):
        raise ValueError('Element: points muss eine Liste sein')
    if kind == 'stroke':
        ok = 1 <= len(pts) <= MAX_STROKE_POINTS
    elif kind == 'polygon':
        ok = 3 <= len(pts) <= MAX_STROKE_POINTS
    elif kind in ('rect', 'ellipse'):
        ok = len(pts) == 2
    else:
        ok = len(pts) == 1
    if not ok:
        raise ValueError(f'Element {kind}: falsche Punktanzahl')
    if not isinstance(e['text'], str) or len(e['text']) > MAX_TEXT:
        raise ValueError(f'Element: Text darf höchstens {MAX_TEXT} Zeichen haben')
    if e['symbol'] not in SYMBOLS:
        raise ValueError('Element: unbekanntes Symbol')
    result = {
        'id': eid, 'layer': e['layer'], 'kind': kind,
        'points': [_point(p, 'Punkt') for p in pts],
        'color': _color(e['color']),
        'width': _num(e['width'], 'width', WIDTH_MIN, WIDTH_MAX),
        'text': e['text'], 'symbol': e['symbol'],
    }
    if kind == 'asset':
        if not valid_asset_id(e['asset_id']) or not isinstance(e['remove_white'], bool):
            raise ValueError('Ungültige Asset-ID oder Hintergrundoption.')
        result.update(asset_id=e['asset_id'], rotation=_num(e['rotation'], 'Drehung', 0, 360) % 360,
                      remove_white=e['remove_white'])
    return result


def validate_artwork(value):
    '''Strictly validate artwork; return a normalized deep copy.'''
    if not isinstance(value, dict) or set(value) != _ART_KEYS:
        raise ValueError('Artwork: ungültige oder fehlende Felder')
    if not _is_int(value['version']) or value['version'] != 1:
        raise ValueError('Artwork: Version 1 erwartet')
    if not isinstance(value['grid'], bool):
        raise ValueError('Artwork: grid muss bool sein')
    layers = value['layers']
    if not isinstance(layers, (list, tuple)) or len(layers) != len(LAYERS):
        raise ValueError('Artwork: genau drei Ebenen erwartet')
    out_layers = []
    for l in layers:
        if not isinstance(l, dict) or set(l) != _LAYER_KEYS:
            raise ValueError('Ebene: ungültige oder fehlende Felder')
        if l['id'] not in LAYERS or any(o['id'] == l['id'] for o in out_layers):
            raise ValueError('Ebene: unbekannte oder doppelte ID')
        if not isinstance(l['name'], str) or not 1 <= len(l['name']) <= 40:
            raise ValueError('Ebene: ungültiger Name')
        if not isinstance(l['visible'], bool) or not isinstance(l['locked'], bool):
            raise ValueError('Ebene: visible/locked müssen bool sein')
        out_layers.append({k: l[k] for k in ('id', 'name', 'visible', 'locked')})
    els = value['elements']
    if not isinstance(els, (list, tuple)) or len(els) > MAX_ELEMENTS:
        raise ValueError(f'Artwork: höchstens {MAX_ELEMENTS} Elemente')
    layer_ids = {l['id'] for l in out_layers}
    out_els, ids, total = [], set(), 0
    for e in els:
        el = _element(e, layer_ids)
        if el['id'] in ids:
            raise ValueError('Artwork: doppelte Element-ID')
        ids.add(el['id'])
        total += len(el['points'])
        if total > MAX_POINTS:
            raise ValueError(f'Artwork: höchstens {MAX_POINTS} Punkte insgesamt')
        out_els.append(el)
    return {'version': 1, 'background': _color(value['background'], 'background'),
            'grid': value['grid'], 'layers': out_layers, 'elements': out_els}


def add_element(artwork, kind, points, color, width, layer, text='', symbol='Baum', *, asset_id=None, rotation=0, remove_white=True):
    '''Add an element; validated on a copy first, artwork unchanged on error.'''
    if not isinstance(artwork, dict) or not isinstance(artwork.get('elements'), list):
        raise ValueError('Artwork: ungültig')
    el = {'id': uuid.uuid4().hex, 'layer': layer, 'kind': kind,
          'points': [list(p) if isinstance(p, (list, tuple)) else p for p in points]
          if isinstance(points, (list, tuple)) else points,
          'color': color, 'width': width, 'text': text, 'symbol': symbol}
    if kind == 'asset':
        el.update(asset_id=asset_id, rotation=rotation, remove_white=remove_white)
    candidate = copy.deepcopy(artwork)
    candidate['elements'].append(el)
    validated = validate_artwork(candidate)
    new_el = validated['elements'][-1]
    artwork['elements'].append(new_el)
    return new_el['id']


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _element_distance(el, x, y):
    pts, kind = el['points'], el['kind']
    if kind == 'asset':
        angle = math.radians(el['rotation'])
        dx, dy = x - pts[0][0], y - pts[0][1]
        rx, ry = dx * math.cos(angle) + dy * math.sin(angle), -dx * math.sin(angle) + dy * math.cos(angle)
        half = el['width'] / 2
        return math.hypot(max(0, abs(rx) - half), max(0, abs(ry) - half))
    if kind == 'polygon':
        inside = False
        edges = list(zip(pts, pts[1:] + pts[:1]))
        for a, b in edges:
            if (a[1] > y) != (b[1] > y):
                crossing = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                if x < crossing:
                    inside = not inside
        return 0.0 if inside else min(_seg_dist(x, y, *a, *b) for a, b in edges)
    if kind == 'stroke':
        if len(pts) == 1:
            d = math.hypot(x - pts[0][0], y - pts[0][1])
        else:
            d = min(_seg_dist(x, y, a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:]))
        return max(0.0, d - el['width'] / 2.0)
    if kind == 'ellipse':
        (x1, y1), (x2, y2) = pts
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        rx, ry = abs(x2 - x1) / 2, abs(y2 - y1) / 2
        if min(rx, ry) < 1e-9:
            return _seg_dist(x, y, x1, y1, x2, y2)
        return max(0.0, (math.hypot((x - cx) / rx, (y - cy) / ry) - 1) * min(rx, ry))
    if kind == 'rect':
        (x1, y1), (x2, y2) = pts
        dx = max(min(x1, x2) - x, 0.0, x - max(x1, x2))
        dy = max(min(y1, y2) - y, 0.0, y - max(y1, y2))
        return math.hypot(dx, dy)
    if kind == 'symbol':
        return max(0.0, math.hypot(x - pts[0][0], y - pts[0][1]) - max(1, min(4, el['width'])) / 2)
    # Approximate text extent using the same scale as the vector renderer.
    half_width = max(.3, len(el['text']) * .16) * max(1, min(4, el['width']))
    half_height = .3 * max(1, min(4, el['width']))
    return math.hypot(max(0, abs(x - pts[0][0]) - half_width),
                      max(0, abs(y - pts[0][1]) - half_height))


def _hits(artwork, x, y, radius, layer):
    '''Touched elements on visible, unlocked layers, topmost first.'''
    x = _num(x, 'x')
    y = _num(y, 'y')
    radius = _num(radius, 'radius', 0.0)
    if layer is not None and layer not in LAYERS:
        raise ValueError('Unbekannte Ebene')
    try:
        found = []
        for l in reversed(artwork['layers']):
            if (layer is not None and l['id'] != layer) or not l['visible'] or l['locked']:
                continue
            for el in reversed(artwork['elements']):
                if el['layer'] == l['id'] and _element_distance(el, x, y) <= radius:
                    found.append(el)
        return found
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise ValueError(f'Artwork: ungültig ({exc})') from exc


def hit_element(artwork, x, y, radius, layer=None):
    '''Topmost visible, unlocked hit element (a copy) or None.'''
    hits = _hits(artwork, x, y, radius, layer)
    return copy.deepcopy(hits[0]) if hits else None


def erase_at(artwork, x, y, radius, layer):
    '''Remove whole touched elements on one layer (not a pixel eraser).

    Hidden or locked layers are left untouched. Returns removed element ids.
    '''
    if layer is None:
        raise ValueError('Ebene erforderlich')
    ids = {el['id'] for el in _hits(artwork, x, y, radius, layer)}
    if ids:
        artwork['elements'] = [e for e in artwork['elements'] if e['id'] not in ids]
    return [i for i in ids]


def _outside_circle(points, x, y, radius):
    """Split a polyline exactly at circle crossings, retaining outside pieces."""
    if len(points) == 1:
        return [points] if math.dist(points[0], (x, y)) > radius else []
    pieces, current = [], []
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        qx, qy = a[0] - x, a[1] - y
        aa = dx * dx + dy * dy
        if aa < 1e-12:
            continue
        bb, cc = 2 * (qx * dx + qy * dy), qx * qx + qy * qy - radius * radius
        cuts = [0.0, 1.0]
        disc = bb * bb - 4 * aa * cc
        if disc > 0:
            for t in ((-bb - math.sqrt(disc)) / (2 * aa), (-bb + math.sqrt(disc)) / (2 * aa)):
                if 0 < t < 1:
                    cuts.append(t)
        cuts.sort()
        for t0, t1 in zip(cuts, cuts[1:]):
            mid = (t0 + t1) / 2
            if math.hypot(qx + mid * dx, qy + mid * dy) > radius:
                p = [a[0] + t0 * dx, a[1] + t0 * dy]
                q = [a[0] + t1 * dx, a[1] + t1 * dy]
                if current and math.dist(current[-1], p) > 1e-7:
                    pieces.append(current)
                    current = []
                if not current:
                    current.append(p)
                current.append(q)
            elif current:
                pieces.append(current)
                current = []
    if current:
        pieces.append(current)
    return pieces


def erase_strokes(artwork, x, y, radius, layer):
    """Erase parts of strokes; remove touched shapes, labels and symbols whole.

    Commit only if all fragments fit the document limits. Hidden/locked layers
    cannot be edited. The original remains untouched if a limit is exceeded.
    """
    hits = {e['id'] for e in _hits(artwork, x, y, radius, layer)}
    if not hits:
        return False
    candidate = copy.deepcopy(artwork)
    result = []
    for el in candidate['elements']:
        if el['id'] not in hits:
            result.append(el)
        elif el['kind'] == 'stroke':
            pieces = _outside_circle(el['points'], x, y, radius + el['width'] / 2)
            for index, points in enumerate(pieces):
                part = dict(el, points=points)
                if index:
                    part['id'] = uuid.uuid4().hex
                result.append(part)
    candidate['elements'] = result
    artwork['elements'] = validate_artwork(candidate)['elements']
    return True


def public_artwork(artwork):
    """Only send visible artwork. Hidden DM notes must never reach clients."""
    result = validate_artwork(artwork)
    visible = {l['id'] for l in result['layers'] if l['visible']}
    result['elements'] = [e for e in result['elements'] if e['layer'] in visible]
    for layer in result['layers']:
        layer['name'] = LAYER_NAMES[layer['id']]
    return result


# ------------------------------------------------------------------- maps

def _tile():
    return {'type': 'Floor', 'object': None, 'furniture': None, 'trigger_message': None}


def new_map(rows=24, cols=32, level='world'):
    _level(level)
    for v in (rows, cols):
        if not _is_int(v) or not 1 <= v <= MAX_DIM:
            raise ValueError(f'Kartengrösse muss 1..{MAX_DIM} sein')
    return {'rows': rows, 'cols': cols,
            'tiles': {(r, c): _tile() for r in range(rows) for c in range(cols)},
            'artwork': new_artwork(level)}


def _normalize_map(m, level):
    if not isinstance(m, dict):
        raise ValueError('Karte muss ein Objekt sein')
    out = copy.deepcopy(m)
    rows, cols = out.get('rows'), out.get('cols')
    for v in (rows, cols):
        if not _is_int(v) or not 1 <= v <= MAX_DIM:
            raise ValueError(f'Kartengrösse muss 1..{MAX_DIM} sein')
    raw = out.get('tiles') or {}
    if not isinstance(raw, dict):
        raise ValueError('Kartenfelder ungültig')
    tiles = {(r, c): _tile() for r in range(rows) for c in range(cols)}
    for k, t in raw.items():
        if not isinstance(k, tuple) or k not in tiles:
            raise ValueError('Kartenfeld ausserhalb der Karte')
        if not isinstance(t, dict) or t.get('type', 'Floor') not in TILE_TYPES:
            raise ValueError('Ungültiges Kartenfeld')
        tile = _tile()
        tile.update(t)
        tiles[k] = tile
    out['tiles'] = tiles
    if 'cartography_scale' in out:
        from utils.map_scale import validate_scale
        out['cartography_scale'] = validate_scale(out['cartography_scale'])
    art = out.get('artwork')
    out['artwork'] = new_artwork(level) if art is None else validate_artwork(art)
    if 'region_context' in out:
        from utils.map_region_context import validate_context
        out['region_context'] = validate_context(out['region_context'], rows, cols)
    return out


def _pins(raw):
    if not isinstance(raw, list):
        raise ValueError('Pins müssen eine Liste sein')
    out = []
    for p in raw:
        if not isinstance(p, dict) or set(p) not in ({'x', 'y', 'child_id'}, {'x', 'y', 'child_id', 'boundary'}):
            raise ValueError('Pin: ungültige Felder')
        out.append({'x': _num(p['x'], 'Pin x'), 'y': _num(p['y'], 'Pin y'),
                    'child_id': _hex_id(p['child_id'], 'Pin child_id')})
        if 'boundary' in p:
            out[-1]['boundary'] = validate_boundary(p['boundary'])
    return out


def _check_tree(recs, root_id):
    roots = [r for r in recs.values() if r['parent_id'] is None]
    if len(roots) != 1 or roots[0]['id'] != root_id:
        raise ValueError('Genau eine Wurzelkarte erwartet')
    kids = {i: [] for i in recs}
    for r in recs.values():
        pid = r['parent_id']
        if pid is None:
            continue
        p = recs.get(pid)
        if p is None:
            raise ValueError('Unbekannte Elternkarte')
        if _next_level(p['level']) != r['level']:
            raise ValueError('Ungültige Ebenenfolge')
        kids[pid].append(r['id'])
    for r in recs.values():
        ids = [p['child_id'] for p in r['pins']]
        if len(set(ids)) != len(ids) or set(ids) != set(kids[r['id']]):
            raise ValueError('Pins passen nicht zu den Unterkarten')
        for p in r['pins']:
            if not (0 <= p['x'] <= r['map']['cols'] and 0 <= p['y'] <= r['map']['rows']):
                raise ValueError('Pin ausserhalb der Elternkarte')
            if 'boundary' in p:
                validate_boundary(p['boundary'], r['map']['cols'], r['map']['rows'])
    seen, stack = set(), [root_id]
    while stack:
        i = stack.pop()
        if i in seen:
            raise ValueError('Zyklus im Kartenbaum')
        seen.add(i)
        stack.extend(kids[i])
    if len(seen) != len(recs):
        raise ValueError('Nicht verbundene Karten')


class Atlas:
    '''Tree of maps (world > region > site > interior) with child pins.'''

    def __init__(self, root_map=None, name='Neue Welt', level='world'):
        _level(level)
        name = _name(name)
        m = new_map(level=level) if root_map is None else _normalize_map(root_map, level)
        self.id = uuid.uuid4().hex
        self.root_id = self.active_id = uuid.uuid4().hex
        self.maps = {self.root_id: {'id': self.root_id, 'name': name, 'level': level,
                                    'parent_id': None, 'map': m, 'pins': []}}

    @property
    def map(self):
        return self.current()['map']

    def current(self):
        return self.maps[self.active_id]

    def add_child(self, name, x, y, boundary=None):
        parent = self.current()
        child_level = _next_level(parent['level'])
        if child_level is None:
            raise ValueError('Innenräume können keine Unterkarten haben')
        if len(self.maps) >= MAX_MAPS:
            raise ValueError(f'Höchstens {MAX_MAPS} Karten erlaubt')
        name = _name(name)
        px = _num(x, 'x', 0.0, parent['map']['cols'])
        py = _num(y, 'y', 0.0, parent['map']['rows'])
        region = validate_boundary(boundary, parent['map']['cols'], parent['map']['rows']) if boundary is not None else None
        cid = uuid.uuid4().hex
        child = {'id': cid, 'name': name, 'level': child_level, 'parent_id': parent['id'],
                 'map': new_map(CHILD_ROWS, CHILD_COLS, child_level), 'pins': []}
        self.maps[cid] = child
        parent['pins'].append({'x': px, 'y': py, 'child_id': cid})
        if region is not None:
            parent['pins'][-1]['boundary'] = region
        self.active_id = cid
        return cid

    def navigate(self, map_id):
        if map_id not in self.maps:
            raise ValueError('Unbekannte Karte')
        self.active_id = map_id

    def breadcrumbs(self):
        chain, rec = [], self.current()
        while rec is not None and len(chain) <= MAX_MAPS:
            chain.append(rec)
            rec = self.maps.get(rec['parent_id'])
        return chain[::-1]

    def duplicate(self, *, strip_party=True):
        """Independent reusable copy, including child maps and all origin links."""
        result = Atlas.decode(self.encode())
        ids = {key: uuid.uuid4().hex for key in result.maps}
        result.id = uuid.uuid4().hex
        result.root_id, result.active_id = ids[result.root_id], ids[result.active_id]
        records = {}
        names = {char['name'] for rec in result.maps.values()
                 for key in ('offline_players', 'online_players')
                 for char in rec['map'].get(key, [])
                 if isinstance(char, dict) and isinstance(char.get('name'), str)} if strip_party else set()
        for old_id, rec in result.maps.items():
            rec['id'] = ids[old_id]
            rec['parent_id'] = ids.get(rec['parent_id'])
            for pin in rec['pins']:
                pin['child_id'] = ids[pin['child_id']]
            data = rec['map']
            data['editor_origin'] = {'atlas_id': result.id, 'node_id': rec['id']}
            if strip_party:
                for key in ('offline_players', 'online_players'):
                    data.pop(key, None)
                for tile in data['tiles'].values():
                    if tile.get('object') in names:
                        tile['object'] = None
            records[rec['id']] = rec
        result.maps = records
        result.encode()
        return result

    def encode(self):
        from utils.formats import encode_map, validate_primitive
        maps = []
        for rec in self.maps.values():
            src = rec['map']
            m = {k: copy.deepcopy(v) for k, v in src.items() if k not in ('tiles', 'artwork')}
            default = _tile()
            m['tiles'] = {k: copy.deepcopy(t) for k, t in src['tiles'].items()
                          if {**default, **t} != default}
            m['artwork'] = validate_artwork(src.get('artwork'))
            record = {'id': rec['id'], 'name': rec['name'], 'level': rec['level'],
                         'parent_id': rec['parent_id'], 'map': encode_map(m),
                         'pins': copy.deepcopy(rec['pins'])}
            validate_primitive(record)  # Each map keeps the existing bounded document limit.
            maps.append(record)
        payload = {'format': 'dnd-atlas', 'version': 1, 'id': self.id,
                   'root_id': self.root_id, 'active_id': self.active_id, 'maps': maps}
        _check_tree(self.maps, self.root_id)
        if len(json.dumps(payload, ensure_ascii=False).encode('utf-8')) > 16 * 1024 * 1024:
            raise ValueError('Atlas ist zu gross zum Speichern (maximal 16 MiB).')
        return payload

    @classmethod
    def decode(cls, data):
        from utils.formats import decode_map, validate_primitive
        if not isinstance(data, dict) or set(data) != _ATLAS_KEYS:
            raise ValueError('Atlas: ungültige oder fehlende Felder')
        if data['format'] != 'dnd-atlas' or not _is_int(data['version']) or data['version'] != 1:
            raise ValueError('Atlas: unbekanntes Format')
        aid = _hex_id(data['id'], 'id')
        root_id = _hex_id(data['root_id'], 'root_id')
        active_id = _hex_id(data['active_id'], 'active_id')
        raw = data['maps']
        if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_MAPS:
            raise ValueError(f'Atlas: 1..{MAX_MAPS} Karten erwartet')
        recs = {}
        for r in raw:
            validate_primitive(r)
            if not isinstance(r, dict) or set(r) != _REC_KEYS:
                raise ValueError('Karteneintrag: ungültige oder fehlende Felder')
            rid = _hex_id(r['id'], 'Karten-ID')
            if rid in recs:
                raise ValueError('Doppelte Karten-ID')
            pid = r['parent_id']
            pid = None if pid is None else _hex_id(pid, 'parent_id')
            level = _level(r['level'])
            try:
                m = _normalize_map(decode_map(r['map']), level)
            except (TypeError, KeyError, AttributeError) as exc:
                raise ValueError(f'Karte ungültig: {exc}') from exc
            recs[rid] = {'id': rid, 'name': _name(r['name']), 'level': level,
                         'parent_id': pid, 'map': m, 'pins': _pins(r['pins'])}
        if active_id not in recs:
            raise ValueError('Aktive Karte unbekannt')
        _check_tree(recs, root_id)
        atlas = cls.__new__(cls)
        atlas.id, atlas.root_id, atlas.active_id, atlas.maps = aid, root_id, active_id, recs
        return atlas


def read_atlas(path):
    """Local atlas files have up to 32 bounded maps; network JSON limits stay unchanged."""
    from utils.storage import read_json
    return Atlas.decode(read_json(path, max_nodes=MAX_ATLAS_NODES))
