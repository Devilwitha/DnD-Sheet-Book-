import copy
import json
import math

import pytest

from utils import map_document as md


def roundtrip(atlas):
    return md.Atlas.decode(json.loads(json.dumps(atlas.encode())))


def four_levels():
    a = md.Atlas(name='Welt')
    a.add_child('Region', 3, 4)
    a.add_child('Ort', 5.5, 6)
    a.add_child('Halle', 1, 1)
    return a


# ---------------------------------------------------------------- basics

def test_new_map_and_artwork_defaults():
    m = md.new_map()
    assert (m['rows'], m['cols']) == (24, 32) and len(m['tiles']) == 24 * 32
    assert m['tiles'][(0, 0)] == {'type': 'Floor', 'object': None, 'furniture': None,
                                  'trigger_message': None}
    for lvl in md.LEVELS:
        art = md.new_artwork(lvl)
        assert [l['id'] for l in art['layers']] == list(md.LAYERS)
        assert art['grid'] is False
        assert md.validate_artwork(art) == art
    assert md.new_artwork('world')['background'] != md.new_artwork('interior')['background']
    assert md.color_tuple('#FF0000') == (1.0, 0.0, 0.0, 1.0)


# -------------------------------------------------------------- hierarchy

def test_four_level_hierarchy_and_roundtrip():
    a = four_levels()
    assert [r['level'] for r in a.breadcrumbs()] == list(md.LEVELS)
    assert a.breadcrumbs()[0]['id'] == a.root_id
    with pytest.raises(ValueError):
        a.add_child('Zu tief', 1, 1)
    b = roundtrip(a)
    assert b.active_id == a.active_id and b.root_id == a.root_id
    assert [r['name'] for r in b.breadcrumbs()] == ['Welt', 'Region', 'Ort', 'Halle']
    b.navigate(b.root_id)
    assert b.current()['pins'][0]['x'] == 3.0
    with pytest.raises(ValueError):
        b.navigate('0' * 32)


@pytest.mark.parametrize('name,x,y', [('', 1, 1), ('  ', 1, 1), (None, 1, 1), ('A', -1, 1),
                                     ('A', 1, 25), ('A', 33, 1), ('A', math.nan, 1),
                                     ('A', True, 1), ('A', 'x', 1)])
def test_add_child_rejects_bad_input(name, x, y):
    a = md.Atlas()
    with pytest.raises(ValueError):
        a.add_child(name, x, y)
    assert len(a.maps) == 1 and a.current()['pins'] == []


def test_max_maps():
    a = md.Atlas()
    for _ in range(md.MAX_MAPS - 1):
        a.add_child('R', 1, 1)
        a.navigate(a.root_id)
    with pytest.raises(ValueError):
        a.add_child('R', 1, 1)
    assert len(roundtrip(a).maps) == md.MAX_MAPS


def _mutated(fn):
    payload = json.loads(json.dumps(four_levels().encode()))
    fn(payload['maps'])
    return payload


@pytest.mark.parametrize('mutate', [
    lambda m: m[2].update(parent_id=m[0]['id']),           # level skipped
    lambda m: m[0].update(parent_id=m[3]['id']),           # cycle, no root
    lambda m: m[1].update(parent_id=None),                 # two roots
    lambda m: m[0].update(pins=[]),                        # child without pin
    lambda m: m[0]['pins'][0].update(x=1000),              # pin out of bounds
    lambda m: m[0]['pins'].append(dict(m[0]['pins'][0])),  # duplicate pin
    lambda m: m[1].update(id=m[0]['id']),                  # duplicate id
    lambda m: m[1].update(parent_id='f' * 32),             # unknown parent
    lambda m: m[1].update(level='site'),                   # wrong level
    lambda m: m[1]['map']['artwork'].update(grid=1),       # bad artwork
])
def test_decode_rejects_invalid_trees(mutate):
    with pytest.raises(ValueError):
        md.Atlas.decode(_mutated(mutate))


def test_decode_rejects_bad_header():
    p = json.loads(json.dumps(four_levels().encode()))
    for key, val in (('format', 'x'), ('version', True), ('active_id', 'a' * 32)):
        q = dict(p, **{key: val})
        with pytest.raises(ValueError):
            md.Atlas.decode(q)
    with pytest.raises(ValueError):
        md.Atlas.decode(dict(p, extra=1))


# ------------------------------------------------------ sparse and legacy

def test_sparse_encode_and_legacy_tile_objects():
    tiles = {(0, 1): {'type': 'Wall', 'object': None, 'furniture': None, 'trigger_message': None},
             (2, 3): {'type': 'Floor', 'object': 'chest', 'furniture': None, 'trigger_message': None}}
    legacy = {'rows': 3, 'cols': 4, 'tiles': tiles, 'extra': {'a': 1}}
    a = md.Atlas(legacy, name='Alt', level='interior')
    assert a.current()['level'] == 'interior' and len(a.map['tiles']) == 12
    assert 'artwork' not in legacy
    before = copy.deepcopy(a.map)
    enc = a.encode()
    assert len(enc['maps'][0]['map']['tiles']) == 2
    assert a.map == before
    b = roundtrip(a)
    assert len(b.map['tiles']) == 12
    assert b.map['tiles'][(2, 3)]['object'] == 'chest'
    assert b.map['tiles'][(0, 1)]['type'] == 'Wall'
    assert b.map['tiles'][(1, 1)]['type'] == 'Floor'
    assert b.map['extra'] == {'a': 1}
    assert b.map['artwork']['grid'] is False


def test_supported_100_by_100_map_can_be_saved():
    a = md.Atlas(md.new_map(100, 100))
    for t in a.map['tiles'].values():
        t['type'] = 'Wall'
    decoded = md.Atlas.decode(a.encode())
    assert len(decoded.map['tiles']) == 10000
    assert all(t['type'] == 'Wall' for t in decoded.map['tiles'].values())


# ---------------------------------------------------------------- artwork

def test_artwork_roundtrip_through_atlas():
    a = md.Atlas(level='region')
    art = a.map['artwork']
    sid = md.add_element(art, 'stroke', [[1, 1], [5, 5.5]], '#AABBCC', 2, 'terrain')
    md.add_element(art, 'symbol', [[3, 3]], '#000000', 1, 'objects', symbol='Höhle')
    md.add_element(art, 'label', [[4, 4]], '#000000', 1, 'labels', text='Hallo')
    b = roundtrip(a)
    assert b.map['artwork'] == art
    assert art['elements'][0]['id'] == sid and art['elements'][0]['color'] == '#aabbcc'


@pytest.mark.parametrize('points', [[[math.nan, 1]], [[1, math.inf]], [[True, 1]], [[101, 1]],
                                    [[-0.1, 1]], [['1', 1]], [[1]], [[1, 2, 3]], [], 'ab'])
def test_invalid_points(points):
    art = md.new_artwork()
    with pytest.raises(ValueError):
        md.add_element(art, 'label' if points != [] else 'stroke', points, '#000000', 1, 'labels')
    assert art['elements'] == []


@pytest.mark.parametrize('kw', [
    dict(width=0.01), dict(width=21), dict(width=math.nan), dict(width=True),
    dict(color='red'), dict(color='#12345'), dict(layer='sky'), dict(kind='blob'),
    dict(text='x' * 161), dict(symbol='Palme'),
])
def test_invalid_fields(kw):
    args = dict(kind='label', points=[[1, 1]], color='#000000', width=1, layer='labels')
    args.update(kw)
    art = md.new_artwork()
    with pytest.raises(ValueError):
        md.add_element(art, **args)
    assert art['elements'] == []


def test_point_count_rules_per_kind():
    art = md.new_artwork()
    for kind, pts in (('rect', [[1, 1]]), ('ellipse', [[1, 1], [2, 2], [3, 3]]),
                      ('symbol', [[1, 1], [2, 2]]), ('stroke', [[1, 1]] * 1025)):
        with pytest.raises(ValueError):
            md.add_element(art, kind, pts, '#000000', 1, 'objects')
    md.add_element(art, 'stroke', [[1, 1]] * 1024, '#000000', 1, 'terrain')


def test_validate_rejects_unknown_fields_and_duplicates():
    art = md.new_artwork()
    md.add_element(art, 'label', [[1, 1]], '#000000', 1, 'labels')
    bad = copy.deepcopy(art)
    bad['extra'] = 1
    with pytest.raises(ValueError):
        md.validate_artwork(bad)
    bad = copy.deepcopy(art)
    bad['elements'][0]['extra'] = 1
    with pytest.raises(ValueError):
        md.validate_artwork(bad)
    bad = copy.deepcopy(art)
    bad['elements'].append(copy.deepcopy(bad['elements'][0]))
    with pytest.raises(ValueError):
        md.validate_artwork(bad)
    bad = copy.deepcopy(art)
    bad['version'] = True
    with pytest.raises(ValueError):
        md.validate_artwork(bad)
    bad = copy.deepcopy(art)
    bad['layers'][1]['id'] = 'terrain'
    with pytest.raises(ValueError):
        md.validate_artwork(bad)
    assert md.validate_artwork(art) is not art


def test_add_element_overflow_is_atomic():
    art = md.new_artwork()
    for _ in range(md.MAX_ELEMENTS):
        md.add_element(art, 'label', [[1, 1]], '#000000', 1, 'labels')
    before = copy.deepcopy(art)
    with pytest.raises(ValueError):
        md.add_element(art, 'label', [[1, 1]], '#000000', 1, 'labels')
    assert art == before


def test_total_point_limit_is_atomic():
    art = md.new_artwork()
    for _ in range(5):
        md.add_element(art, 'stroke', [[1, 1]] * 1024, '#000000', 1, 'terrain')
    before = copy.deepcopy(art)
    with pytest.raises(ValueError):
        md.add_element(art, 'stroke', [[1, 1]] * 1024, '#000000', 1, 'terrain')
    assert art == before
    md.add_element(art, 'stroke', [[1, 1]] * 880, '#000000', 1, 'terrain')


# ---------------------------------------------------------- hit / erase

def test_hit_geometry():
    art = md.new_artwork()
    s = md.add_element(art, 'stroke', [[0, 0], [10, 0], [10, 10]], '#000000', 0.1, 'terrain')
    r = md.add_element(art, 'rect', [[20, 20], [30, 30]], '#000000', 1, 'objects')
    sym = md.add_element(art, 'symbol', [[50, 50]], '#000000', 1, 'objects')
    assert md.hit_element(art, 5, 0.4, 0.5)['id'] == s
    assert md.hit_element(art, 5, 3, 0.5) is None          # near bbox of path, not the line
    assert md.hit_element(art, 10.3, 7, 0.5)['id'] == s
    assert md.hit_element(art, 25, 25, 0)['id'] == r        # inside rect bbox
    assert md.hit_element(art, 31, 25, 0.5) is None
    assert md.hit_element(art, 50.2, 50, 0.5)['id'] == sym
    with pytest.raises(ValueError):
        md.hit_element(art, math.nan, 0, 1)
    with pytest.raises(ValueError):
        md.hit_element(art, 0, 0, -1)


def test_hit_respects_layer_order_hidden_and_locked():
    art = md.new_artwork()
    low = md.add_element(art, 'rect', [[1, 1], [9, 9]], '#000000', 1, 'terrain')
    top = md.add_element(art, 'label', [[5, 5]], '#000000', 1, 'labels')
    assert md.hit_element(art, 5, 5, 0.5)['id'] == top
    assert md.hit_element(art, 5, 5, 0.5, layer='terrain')['id'] == low
    art['layers'][2]['locked'] = True
    assert md.hit_element(art, 5, 5, 0.5)['id'] == low
    art['layers'][0]['visible'] = False
    assert md.hit_element(art, 5, 5, 0.5) is None


def test_erase_removes_whole_elements_only_on_editable_layer():
    art = md.new_artwork()
    s = md.add_element(art, 'stroke', [[0, 0], [10, 0]], '#000000', 0.1, 'terrain')
    keep = md.add_element(art, 'stroke', [[0, 8], [10, 8]], '#000000', 0.1, 'terrain')
    other = md.add_element(art, 'label', [[5, 0]], '#000000', 1, 'labels')
    art['layers'][0]['locked'] = True
    assert md.erase_at(art, 5, 0, 0.5, 'terrain') == []
    art['layers'][0]['locked'] = False
    assert md.erase_at(art, 5, 0, 0.5, 'terrain') == [s]
    assert [e['id'] for e in art['elements']] == [keep, other]
    md.validate_artwork(art)


def test_eraser_splits_long_segments_without_deleting_unaffected_parts():
    art = md.new_artwork()
    md.add_element(art, 'stroke', [[0, 5], [10, 5]], '#000000', .2, 'terrain')
    assert md.erase_strokes(art, 5, 5, 1, 'terrain')
    assert len(art['elements']) == 2
    left, right = art['elements']
    assert left['points'][0] == [0, 5]
    assert left['points'][-1][0] == pytest.approx(3.9)
    assert right['points'][0][0] == pytest.approx(6.1)
    assert right['points'][-1] == [10, 5]
    before = copy.deepcopy(art)
    art['layers'][0]['locked'] = True
    assert not md.erase_strokes(art, 1, 5, 1, 'terrain')
    assert art['elements'] == before['elements']


def test_hidden_artwork_never_enters_player_payload():
    art = md.new_artwork()
    md.add_element(art, 'label', [[2, 2]], '#000000', 1, 'labels', text='Geheime Falle')
    md.add_element(art, 'symbol', [[1, 1]], '#112233', 1, 'objects')
    art['layers'][2].update(visible=False, name='Privates Versteck')
    output = json.dumps(md.public_artwork(art))
    assert 'Geheime Falle' not in output and 'Privates Versteck' not in output
    assert 'symbol' in output
    assert len(art['elements']) == 2


def test_real_codec_preserves_artwork_and_rejects_outside_map():
    from utils.formats import encode_map, decode_map, ValidationError
    m = md.new_map(4, 4)
    md.add_element(m['artwork'], 'stroke', [[0, 0], [4, 4]], '#778899', 1, 'terrain')
    assert decode_map(encode_map(m))['artwork'] == m['artwork']
    m['artwork']['elements'][0]['points'][1] = [5, 5]
    with pytest.raises(ValidationError):
        encode_map(m)


def test_filled_polygon_concave_hit_and_storage(tmp_path):
    from utils.storage import atomic_write_json, read_json
    a = md.Atlas()
    eid = md.add_element(a.map['artwork'], 'polygon', [[1,1], [8,1], [8,3], [3,3], [3,8], [1,8]],
                         '#334455', 1, 'terrain')
    assert md.hit_element(a.map['artwork'], 2, 6, .1)['id'] == eid
    assert md.hit_element(a.map['artwork'], 6, 6, .1) is None
    path = tmp_path / 'atlas.json'
    atomic_write_json(path, a.encode())
    assert md.Atlas.decode(read_json(path)).map['artwork'] == a.map['artwork']


def test_host_broadcast_filters_private_atlas_and_hidden_artwork():
    from tests.test_live_play import game, screen
    gm, char = game()
    s, _ = screen(gm, char)
    art = md.new_artwork()
    md.add_element(art, 'label', [[1,1]], '#112233', 1, 'labels', text='Secret notes')
    md.add_element(art, 'symbol', [[2,2]], '#112233', 1, 'objects')
    art['layers'][2]['visible'] = False
    gm.map_data.update(artwork=art, editor_origin={'atlas_id': 'private'}, pins=['private'])
    s.broadcast_map_data()
    event, payload = s.network_manager.broadcast_message.call_args.args
    assert event == 'MAP_DATA'
    assert 'Secret notes' not in json.dumps(payload)
    assert 'editor_origin' not in payload and 'pins' not in payload
    assert len(payload['artwork']['elements']) == 1
    assert len(gm.map_data['artwork']['elements']) == 2


def test_large_atlas_roundtrip_and_explicit_node_budget(tmp_path):
    from utils.storage import atomic_write_json, read_json, parse_json_bytes
    a = md.Atlas()
    for i in range(12):
        a.add_child('Region ' + str(i), 1, 1)
        for t in a.map['tiles'].values():
            t['type'] = 'Wall'
        a.navigate(a.root_id)
    payload = a.encode()
    path = tmp_path / 'large-atlas.json'
    atomic_write_json(path, payload)
    assert len(md.read_atlas(path).maps) == 13
    assert read_json(path)['format'] == 'dnd-atlas'
    assert parse_json_bytes(path.read_bytes())['format'] == 'dnd-atlas'
    with pytest.raises(ValueError):
        parse_json_bytes(path.read_bytes(), max_nodes=50000)
