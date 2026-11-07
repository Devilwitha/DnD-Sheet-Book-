import copy
import json

import pytest
from utils.map_document import Atlas, new_map, add_element
from utils.map_region_context import KEY, refresh_region, validate_context, public_context
from utils.formats import encode_map, decode_map


def atlas_with_region():
    atlas = Atlas(new_map(24, 32), name='World')
    atlas.map['cartography_scale'] = dict(width_m=1000000., height_m=1000000.)
    add_element(atlas.map['artwork'], 'polygon', [[2,2],[28,2],[28,22],[2,22]], '#896c4d', .3, 'terrain')
    add_element(atlas.map['artwork'], 'stroke', [[0,10],[32,10]], '#8fa9b5', .5, 'terrain')
    root = atlas.root_id
    child = atlas.add_child('North', 6, 4, [[3,3],[25,3],[25,7],[10,7],[10,18],[3,18]])
    atlas.map['cartography_scale'] = dict(width_m=100000., height_m=100000.)
    return atlas, root, child


def test_legacy_region_gets_world_art_and_correct_boundary_without_mutating_world():
    a, root, child = atlas_with_region()
    world = copy.deepcopy(a.maps[root])
    own = copy.deepcopy(a.map['artwork'])
    assert refresh_region(a, child)
    context = a.map[KEY]
    assert context['artwork'] == world['map']['artwork']
    assert context['boundary'] == world['pins'][0]['boundary']
    assert a.maps[root] == world and a.map['artwork'] == own
    assert a.map['cartography_scale']['width_m'] > 100000
    assert not refresh_region(a, child)
    context['artwork']['elements'][0]['color'] = '#000000'
    assert a.maps[root] == world  # No shared references.


def test_frame_fits_concave_polygon_without_axis_distortion():
    a, _, child = atlas_with_region()
    refresh_region(a, child)
    ox, oy, step = a.map[KEY]['frame']
    assert step > 0
    for x,y in a.map[KEY]['boundary']:
        assert 0 <= (x-ox)/step <= a.map['cols']
        assert 0 <= (y-oy)/step <= a.map['rows']


def test_details_and_frame_stay_fixed_while_world_and_border_update():
    a, root, child = atlas_with_region()
    refresh_region(a, child)
    frame = a.map[KEY]['frame'][:]
    add_element(a.map['artwork'], 'label', [[4,4]], '#ffffff', 1, 'labels', text='My village')
    details = copy.deepcopy(a.map['artwork'])
    a.maps[root]['pins'][0]['boundary'] = [[3,3],[9,3],[9,18],[3,18]]
    a.maps[root]['map']['artwork']['elements'][0]['color'] = '#abcdef'
    assert refresh_region(a, child)
    assert a.map['artwork'] == details and a.map[KEY]['frame'] == frame
    assert a.map[KEY]['artwork']['elements'][0]['color'] == '#abcdef'


def test_explicit_scale_survives_activation_even_without_details():
    a, _, child = atlas_with_region()
    refresh_region(a, child)
    a.map['cartography_scale'] = dict(width_m=900, height_m=800)
    refresh_region(a, child)
    assert a.map['cartography_scale'] == dict(width_m=900, height_m=800)


def test_snapshot_roundtrip_standalone_atlas_and_independent_duplicate():
    a, _, child = atlas_with_region()
    refresh_region(a, child)
    encoded = a.encode()
    assert Atlas.decode(json.loads(json.dumps(encoded))).encode() == encoded
    assert decode_map(encode_map(a.map))[KEY] == a.map[KEY]
    duplicate = a.duplicate()
    duplicate.map[KEY]['artwork']['elements'][0]['color'] = '#ffffff'
    assert a.map[KEY]['artwork']['elements'][0]['color'] != '#ffffff'


def test_hidden_world_notes_never_in_public_snapshot():
    a, root, child = atlas_with_region()
    world = a.maps[root]['map']['artwork']
    add_element(world, 'label', [[4,4]], '#ffffff', 1, 'labels', text='SECRET')
    world['layers'][2].update(visible=False, name='Hidden quest')
    refresh_region(a, child)
    public = public_context(a.map[KEY], a.map['rows'], a.map['cols'])
    assert 'SECRET' not in json.dumps(public) and 'Hidden quest' not in json.dumps(public)
    assert 'SECRET' in json.dumps(a.map[KEY])


@pytest.mark.parametrize('bad', [True, float('nan'), float('inf'), 0, -1, 101])
def test_reject_invalid_frame_scale(bad):
    a, _, child = atlas_with_region()
    refresh_region(a, child)
    a.map[KEY]['frame'][2] = bad
    with pytest.raises(ValueError):
        encode_map(a.map)


def test_reject_recursive_context_and_out_of_world_artwork():
    a, _, child = atlas_with_region()
    refresh_region(a, child)
    value = copy.deepcopy(a.map[KEY])
    value['artwork'][KEY] = {}
    with pytest.raises(ValueError): validate_context(value, a.map['rows'], a.map['cols'])
    value = copy.deepcopy(a.map[KEY])
    value['artwork']['elements'][0]['points'][0] = [90,90]
    with pytest.raises(ValueError): validate_context(value, a.map['rows'], a.map['cols'])


def test_pin_only_and_poi_maps_remain_independent():
    a = Atlas()
    child = a.add_child('Pin only', 3, 3)
    assert not refresh_region(a, child) and KEY not in a.map
    site = a.add_child('Village', 5, 5, [[3,3],[8,3],[8,8],[3,8]])
    assert not refresh_region(a, site) and KEY not in a.map
