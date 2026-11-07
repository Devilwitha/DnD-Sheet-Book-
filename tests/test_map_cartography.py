import copy
import math
import random
import pytest
from utils.map_partition import split_boundary, boundary_area
from utils.map_regions import boundary_contains, validate_boundary, boundary_center, _dist
from utils.map_scale import (KEY, parse_scale, validate_scale, suggested_scale,
                             grid_for_scale, display_values)
from utils.map_document import Atlas
from utils.formats import encode_map, decode_map

ISLAND = [[2,2],[28,2],[28,22],[2,22]]


def check_partition(original, parts):
    assert sum(boundary_area(p) for p in parts) == pytest.approx(boundary_area(original), abs=1e-6)
    for p in parts:
        validate_boundary(p,32,24)
    # Sample away from the integer edges/cuts; catches overlap balanced by gaps.
    rng = random.Random(42)
    for _ in range(400):
        x,y = rng.uniform(0,32), rng.uniform(0,24)
        assert sum(boundary_contains(p,x,y) for p in parts) == int(boundary_contains(original,x,y))


@pytest.mark.parametrize('line', [
    [[15,0],[15,24]], [[2.2,12],[10,10],[20,14],[27.9,12]],
    [[2,2],[28,22]], [[2,2],[15,8],[28,22]],
    [[2,8],[5,8],[5,16],[2,16]], # same edge with an interior bend
])
def test_split_fills_original_without_overlap(line):
    before = copy.deepcopy(ISLAND)
    parts = split_boundary(ISLAND,line,32,24)
    check_partition(ISLAND,parts)
    assert ISLAND == before
    check_partition(ISLAND,split_boundary(list(reversed(ISLAND)),list(reversed(line)),32,24))


def test_curved_border_is_identical_and_reversed():
    cut = [[2,12],[8,10],[14,13],[20,11],[28,12]]
    a,b = split_boundary(ISLAND,cut,32,24)
    edges = lambda p: set((tuple(x),tuple(y)) for x,y in zip(p,p[1:]+p[:1]))
    assert {(tuple(y),tuple(x)) for x,y in zip(cut,cut[1:])} <= edges(a)
    assert {(tuple(x),tuple(y)) for x,y in zip(cut,cut[1:])} <= edges(b)


def test_four_regions_and_t_junction_have_no_voids():
    a,b = split_boundary(ISLAND,[[15,2],[15,22]],32,24)
    parts = [p for half in (a,b) for p in split_boundary(half,[[0,12],[32,12]],32,24)]
    check_partition(ISLAND,parts)


def test_concave_coast_preserved():
    coast = [[2,2],[28,2],[28,22],[18,22],[18,15],[12,15],[12,22],[2,22]]
    a,b = split_boundary(coast,[[0,8],[32,8]],32,24)
    check_partition(coast,[a,b])
    assert all(p in a or p in b for p in coast)
    with pytest.raises(ValueError):
        split_boundary(coast,[[0,18],[32,18]],32,24)


def test_cut_through_coast_vertex_and_sampled_line_vertex():
    coast = [[4,2],[28,2],[28,22],[4,22],[2,12]]
    for line in ([[0,12],[32,12]], [[0,12],[2,12],[10,12],[28,12],[32,12]]):
        check_partition(coast, split_boundary(coast,line,32,24))


def test_concave_marker_is_strictly_inside_and_not_on_shared_border():
    coast = [[2,2],[28,2],[28,22],[23,22],[23,7],[7,7],[7,22],[2,22]]
    center = boundary_center(coast)
    assert boundary_contains(coast,*center)
    assert all(_dist(*center,a,b)>1e-7 for a,b in zip(coast,coast[1:]+coast[:1]))


@pytest.mark.parametrize('line', [
    [[2,2],[28,2]], [[10,10],[20,10]], [[0,0],[1,1]],
    [[2,12],[20,18],[10,18],[20,5],[28,12]],
    [[0,12],[30,12],[30,13],[0,13]],
    [[True,1],[2,3]], [[math.nan,1],[2,3]], [[-1,12],[30,12]],
    [[0,12],[10**10000,12]], [[0,12]],
])
def test_invalid_cuts_fail_without_mutation(line):
    before = copy.deepcopy(ISLAND)
    with pytest.raises(ValueError):
        split_boundary(ISLAND,line,32,24)
    assert ISLAND == before


def test_repeated_splits_roundtrip_and_original_coast():
    parts = [ISLAND]
    for x in (6,10,14,18,22,26):
        target = next(p for p in parts if boundary_contains(p,x,11))
        parts.remove(target)
        parts.extend(split_boundary(target,[[x,0],[x,24]],32,24))
    check_partition(ISLAND,parts)
    atlas = Atlas()
    root = atlas.root_id
    for n,p in enumerate(parts):
        atlas.navigate(root)
        atlas.add_child(str(n),p[0][0],p[0][1],boundary=p)
    restored = Atlas.decode(atlas.encode())
    check_partition(ISLAND,[p['boundary'] for p in restored.maps[root]['pins']])


def test_scale_units_grid_and_backward_compatibility():
    assert parse_scale('100','100','km') == dict(width_m=100000.,height_m=100000.)
    assert grid_for_scale(parse_scale('1000','500','km')) == (25,50)
    assert grid_for_scale(parse_scale('300','10','km')) == (1,30)
    assert display_values(parse_scale('12,5','20','m')) == ('12.5','20','m')
    old = Atlas(); old = Atlas.decode(old.encode())
    assert KEY not in old.map
    old.map[KEY] = parse_scale('1000','750','km')
    assert Atlas.decode(old.encode()).map[KEY] == old.map[KEY]
    assert decode_map(encode_map(old.map))[KEY] == old.map[KEY]
    scale = suggested_scale(old.map,[[0,0],[16,0],[16,12],[0,12]],'region')
    assert scale == dict(width_m=500000.,height_m=375000.)
    assert suggested_scale(old.map,None,'interior') == dict(width_m=30.,height_m=30.)


@pytest.mark.parametrize('v', [None, {}, {'width_m':True,'height_m':2},
    {'width_m':math.nan,'height_m':2}, {'width_m':math.inf,'height_m':2},
    {'width_m':-2,'height_m':2}, {'width_m':0,'height_m':2},
    {'width_m':1000000001,'height_m':2}, {'width_m':1000,'height_m':1},
    {'width_m':10**10000,'height_m':2}])
def test_invalid_scale_rejected_in_import(v):
    atlas = Atlas(); atlas.map[KEY] = v
    with pytest.raises(ValueError):
        atlas.encode()
