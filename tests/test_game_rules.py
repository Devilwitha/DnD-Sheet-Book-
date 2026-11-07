from core.enemy import Enemy
from core.game_manager import GameManager


def make_gm(rows=4, cols=4):
    gm = GameManager(logger_func=lambda m: None)
    tiles = {(r, c): {'type': 'Floor', 'object': None, 'furniture': None}
             for r in range(rows) for c in range(cols)}
    gm.map_data = {'rows': rows, 'cols': cols, 'tiles': tiles}
    gm.enemies = [Enemy('A', 5, 10, []), Enemy('B', 5, 10, [])]
    tiles[(0, 0)]['object'] = 'A'
    tiles[(3, 3)]['object'] = 'B'
    gm.initiative_order = [(15, 'A'), (5, 'B')]
    gm.current_turn_index = 0
    gm.start_next_turn()
    return gm


def test_successful_move_spends_budget():
    gm = make_gm()
    ok, _ = gm.move_object('A', (0, 2))
    assert ok
    assert gm.map_data['tiles'][(0, 0)]['object'] is None
    assert gm.map_data['tiles'][(0, 2)]['object'] == 'A'
    assert gm.turn_action_state['movement_left'] == 4


def test_invalid_move_is_atomic_wall():
    gm = make_gm()
    gm.map_data['tiles'][(0, 1)]['type'] = 'Wall'
    before = gm.turn_action_state['movement_left']
    ok, _ = gm.move_object('A', (0, 1))
    assert not ok
    assert gm.map_data['tiles'][(0, 0)]['object'] == 'A'
    assert gm.turn_action_state['movement_left'] == before


def test_wall_blocks_path():
    gm = make_gm()
    gm.map_data['tiles'][(0, 1)]['type'] = 'Wall'
    gm.map_data['tiles'][(1, 0)]['type'] = 'Wall'
    before = gm.turn_action_state['movement_left']
    ok, _ = gm.move_object('A', (1, 1))
    assert not ok
    assert gm.map_data['tiles'][(0, 0)]['object'] == 'A'
    assert gm.map_data['tiles'][(1, 1)]['object'] is None
    assert gm.turn_action_state['movement_left'] == before


def test_bounds_and_bad_types_rejected():
    gm = make_gm()
    before = gm.turn_action_state['movement_left']
    for bad in [(9, 9), (-1, 0), ('a', 1), (1.5, 1), (1,), None, 'ab']:
        ok, _ = gm.move_object('A', bad)
        assert not ok
    assert gm.map_data['tiles'][(0, 0)]['object'] == 'A'
    assert gm.turn_action_state['movement_left'] == before


def test_occupied_target_rejected():
    gm = make_gm()
    gm.map_data['tiles'][(0, 1)]['object'] = 'B'
    ok, _ = gm.move_object('A', (0, 1))
    assert not ok
    assert gm.map_data['tiles'][(0, 0)]['object'] == 'A'


def test_missing_turn_actors_terminates():
    gm = make_gm()
    gm.initiative_order = [(10, 'ghost1'), (5, 'ghost2')]
    gm.current_turn_index = 0
    assert gm.start_next_turn() is None
    assert gm.current_turn_index == -1
    assert gm.end_turn() is None or gm.current_turn_index in (-1, 0)


def test_enemy_serialization_preserves_hp():
    e = Enemy('X', hp=-3, armor_class=12, attacks=[{'name': 'Biss', 'damage': '1d6'}], initiative=2)
    d = e.to_dict()
    e2 = Enemy.from_dict(d)
    assert e2.hp == -3
    assert e2.armor_class == 12
    assert e2.initiative == 2
    assert e2.attacks == [{'name': 'Biss', 'damage': '1d6'}]
    e3 = Enemy.from_dict({'name': 'Y', 'hp': 4, 'ac': 15, 'evil': 'ignored'})
    assert e3.hp == 4 and e3.armor_class == 15
    assert not hasattr(e3, 'evil')


def test_enemy_death_with_no_map():
    gm = make_gm()
    gm.map_data = None
    outcome = gm.handle_character_death('B')
    assert outcome in ('DEFEATED', 'VICTORY')
    assert all(e.name != 'B' for e in gm.enemies)
