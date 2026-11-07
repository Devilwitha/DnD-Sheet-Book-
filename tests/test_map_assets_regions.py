"""Storage, geometry and privacy contracts for bundled stamps and linked areas."""
import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

from utils import map_document as md
from utils.asset_catalog import asset_info, asset_path, catalog
from utils.formats import encode_map, decode_map
from utils.map_regions import validate_boundary, boundary_contains, boundary_center, simplify_gesture


AREA = [[2, 2], [20, 2], [20, 16], [2, 16]]


def stamp(art, **changes):
    args = dict(asset_id='BAU-003', rotation=45, remove_white=True)
    args.update(changes)
    return md.add_element(art, 'asset', [[10, 10]], '#ffffff', 4, 'objects', **args)


def test_catalog_images_exist_with_unchanged_hashes():
    entries = catalog()
    assert len(entries) == 75 and len({x['id'] for x in entries}) == 75
    for entry in entries:
        p = Path(asset_path(entry['id']))
        assert p.name == entry['id'] + '.jpg'
        assert hashlib.sha256(p.read_bytes()).hexdigest() == entry['sha256']


@pytest.mark.parametrize('value', ['../BAU-003', 'BAU-003.jpg', 'https://x/a.jpg',
                                 'C:/secret', None, {'id': 'BAU-003'}, 'XYZ-999'])
def test_unknown_asset_cannot_resolve_a_path(value):
    assert asset_info(value) is None
    with pytest.raises(ValueError):
        asset_path(value)


def test_stamp_codec_visibility_and_rotated_selection():
    m = md.new_map()
    art = m['artwork']
    key = stamp(art)
    assert decode_map(encode_map(m))['artwork'] == art
    assert md.hit_element(art, 12.7, 10, 0)['id'] == key
    assert md.hit_element(art, 12, 12, 0) is None  # outside rotated square
    objects = next(l for l in art['layers'] if l['id'] == 'objects')
    objects['locked'] = True
    assert md.hit_element(art, 10, 10, 0) is None
    assert len(md.public_artwork(art)['elements']) == 1
    objects['visible'] = False
    assert md.public_artwork(art)['elements'] == []
    assert art['elements'][0]['asset_id'] == 'BAU-003'  # private original retained


@pytest.mark.parametrize('changes', [dict(asset_id='../BAU-003'), dict(asset_id=True),
    dict(rotation=math.inf), dict(rotation=math.nan), dict(rotation=True),
    dict(rotation=-1), dict(rotation=361), dict(remove_white='yes')])
def test_invalid_stamp_add_is_atomic(changes):
    art = md.new_artwork()
    before = copy.deepcopy(art)
    with pytest.raises(ValueError):
        stamp(art, **changes)
    assert art == before


def test_unknown_valid_id_survives_transfer_without_becoming_a_file_path():
    art = md.new_artwork()
    stamp(art, asset_id='XYZ-999', rotation=360)
    assert md.validate_artwork(art)['elements'][0]['rotation'] == 0
    with pytest.raises(ValueError):
        asset_path('XYZ-999')


def test_old_symbols_remain_unchanged():
    art = md.new_artwork()
    md.add_element(art, 'symbol', [[4, 4]], '#aabbcc', 2, 'objects', symbol='Baum')
    assert md.validate_artwork(art) == art
    assert 'asset_id' not in art['elements'][0]


def test_concave_area_edge_hits_and_normalization():
    points = [[1, 1], [8, 1], [8, 3], [3, 3], [3, 8], [1, 8]]
    result = validate_boundary(points + [points[-1], points[0]], 10, 10)
    assert result == points
    assert boundary_contains(result, 2, 7)
    assert boundary_contains(result, 3, 5)  # boundary counts as in
    assert not boundary_contains(result, 7, 7)  # concave cutout
    assert boundary_contains(result, *boundary_center(result))
    assert not boundary_contains(result, math.nan, 2)


@pytest.mark.parametrize('points', [
    [[0, 0], [1, 1]],
    [[0, 0], [2, 0], [4, 0]],
    [[0, 0], [3, 3], [0, 3], [3, 0]],
    [[1, 1], [5, 1], [3, 1], [5, 5], [1, 5]],
    [[0, 0], [math.inf, 0], [2, 3]],
    [[0, 0], [True, 0], [2, 3]],
    [[0, 0], [33, 0], [0, 10]],
    [[0, 0], [1, 0], [0, 25]],
    [[0, 0], [0.01, 0], [0, 0.01]],
])
def test_invalid_area_does_not_create_or_navigate_to_child(points):
    atlas = md.Atlas()
    before = atlas.encode()
    with pytest.raises(ValueError):
        atlas.add_child('Region', 2, 2, boundary=points)
    assert atlas.encode() == before


def test_boundary_tree_roundtrip_and_independent_copy():
    atlas = md.Atlas(name='Insel')
    atlas.add_child('Küste', 4, 5, boundary=AREA)
    atlas.add_child('Dorf', 2, 2)  # legacy point link mixed with area
    atlas.add_child('Schmiede', 5, 5, boundary=AREA)
    stamp(atlas.map['artwork'])
    restored = md.Atlas.decode(json.loads(json.dumps(atlas.encode())))
    assert restored.encode() == atlas.encode()
    cloned = restored.duplicate()
    assert not (set(cloned.maps) & set(atlas.maps))
    assert [r['level'] for r in cloned.breadcrumbs()] == list(md.LEVELS)
    for rec in cloned.maps.values():
        for pin in rec['pins']:
            assert pin['child_id'] in cloned.maps
    cloned.maps[cloned.root_id]['pins'][0]['boundary'][0][0] = 3
    assert atlas.maps[atlas.root_id]['pins'][0]['boundary'][0][0] == 2


def test_decode_rejects_boundary_outside_parent_size():
    atlas = md.Atlas()
    atlas.add_child('Region', 2, 2, boundary=AREA)
    payload = atlas.encode()
    payload['maps'][0]['pins'][0]['boundary'][1][0] = 40
    with pytest.raises(ValueError):
        md.Atlas.decode(payload)


def test_long_hand_drawn_outline_keeps_shape_and_saves():
    points = [[16 + 12 * math.cos(i * math.tau / 500),
               12 + 10 * math.sin(i * math.tau / 500)] for i in range(501)]
    reduced = validate_boundary(simplify_gesture(points), 32, 24)
    assert 12 < len(reduced) <= 128
    assert boundary_contains(reduced, 16, 12)
    assert not boundary_contains(reduced, 31, 23)
