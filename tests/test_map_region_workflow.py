import copy
import pytest
from utils.map_document import Atlas, new_map, add_element
from utils.map_region_workflow import resolve_cut
from utils.map_partition import boundary_area


def island_map():
    atlas=Atlas(new_map(50,50))
    for points in ([[[2,2],[30,2],[30,24],[2,24]]],):
        for ring in points:
            add_element(atlas.map['artwork'],'polygon',ring,'#8d7050',1,'terrain')
    add_element(atlas.map['artwork'],'polygon',[[32,30],[48,30],[48,48],[32,48]],'#8d7050',1,'terrain')
    return atlas


def test_first_freehand_without_existing_region_is_atomic():
    atlas=island_map(); before=atlas.encode()
    child,parts,source=resolve_cut(atlas.current(),[[14,0],[12,10],[18,15],[16,26]],.7)
    assert child is None
    assert sum(map(boundary_area,parts))==pytest.approx(boundary_area(source))
    assert atlas.encode()==before and not atlas.current()['pins']


def test_other_island_can_be_partitioned_without_adoption():
    atlas=island_map(); parent=atlas.root_id
    key=atlas.add_child('Nord',16,13,boundary=[[2,2],[30,2],[30,24],[2,24]])
    atlas.navigate(parent)
    target,_,_=resolve_cut(atlas.current(),[[40,28],[40,50]],.7)
    assert target is None
    target,_,_=resolve_cut(atlas.current(),[[16,0],[16,26]],.7)
    assert target==key


def test_nested_pond_does_not_hide_island():
    atlas=island_map()
    add_element(atlas.map['artwork'],'ellipse',[[10,10],[18,18]],'#819daa',1,'terrain')
    child,parts,source=resolve_cut(atlas.current(),[[14,0],[14,26]],.7)
    assert child is None and boundary_area(source)==616


def test_partially_assigned_old_region_is_never_overwritten():
    atlas=island_map(); parent=atlas.root_id
    atlas.add_child('Alt',7,7,boundary=[[5,5],[9,5],[9,9],[5,9]])
    atlas.navigate(parent); before=copy.deepcopy(atlas.encode())
    with pytest.raises(ValueError): resolve_cut(atlas.current(),[[16,0],[16,26]],.7)
    assert atlas.encode()==before


def test_ambiguous_and_incomplete_lines_do_not_mutate():
    atlas=island_map(); before=atlas.encode()
    with pytest.raises(ValueError,match='mehrere'):
        resolve_cut(atlas.current(),[[0,0],[50,50]],.7)
    with pytest.raises(ValueError,match='sichtbar'):
        resolve_cut(atlas.current(),[[10,10],[20,15]],.7)
    assert atlas.encode()==before
