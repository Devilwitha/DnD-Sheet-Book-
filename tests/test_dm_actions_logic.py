import pytest
from core.game_manager import GameManager
from core.character import Character
from core.enemy import Enemy


def build_tiles(rows, cols, placed):
    tiles = {(r, c): {'type': 'Floor', 'object': None} for r in range(rows) for c in range(cols)}
    for pos, name in placed.items():
        tiles[pos]['object'] = name
    return tiles


@pytest.fixture
def setup_map_and_gamemanager():
    gm = GameManager(logger_func=lambda *args, **kwargs: None)
    # 3x3 map: player at (0,0), enemy at (0,2) -> two squares apart
    gm.map_data = {
        'rows': 3,
        'cols': 3,
        'tiles': build_tiles(3, 3, {(0, 0): 'Player1', (0, 2): 'Enemy1'}),
    }
    player = Character('Player1', 'Mensch', 'Kämpfer')
    player.initialize_character()
    player.hit_points = 10
    player.max_hit_points = 10
    player.armor_class = 10
    player.speed = 3
    player.initiative = 2
    player.actions_per_turn = 1
    enemy = Enemy(name='Enemy1', hp=8, armor_class=9, attacks=[{'name': 'Bite', 'damage': '1d4'}])
    enemy.speed = 3
    enemy.actions_per_turn = 1
    gm.online_players = {'addr1': player}
    gm.enemies = [enemy]
    gm.initiative_order = [(15, 'Player1'), (10, 'Enemy1')]
    gm.current_turn_index = 0
    gm.start_next_turn()  # initializes movement and attacks from the actor
    return gm, player, enemy


def start_turn_of(gm, index):
    gm.current_turn_index = index
    gm.start_next_turn()


def test_turn_state_is_initialized_from_actor(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    assert gm.turn_action_state == {'movement_left': 3, 'attacks_left': 1}
    assert gm.get_current_turn_info()['name'] == 'Player1'


def test_dm_select_actor(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    assert gm.get_character_or_enemy_by_name('Enemy1') is enemy
    assert gm.get_character_or_enemy_by_name('Player1') is player
    assert gm.get_character_or_enemy_by_name('Nobody') is None


def test_attack_out_of_turn_fails(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    result = gm.handle_attack('Enemy1', 'Player1', attack_roll=20, damage_roll=3)
    assert result['success'] is False
    assert player.hit_points == 10
    assert gm.turn_action_state['attacks_left'] == 1


def test_melee_attack_two_squares_away_fails(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    start_turn_of(gm, 1)
    result = gm.handle_attack('Enemy1', 'Player1', attack_roll=20, damage_roll=3)
    assert result['success'] is False
    assert 'range' in result['reason'].lower()
    # A rejected attack must not consume the attack or damage the target
    assert gm.turn_action_state['attacks_left'] == 1
    assert player.hit_points == 10


def test_dm_select_move_adjacent_and_attack(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    start_turn_of(gm, 1)
    success, reason = gm.move_object('Enemy1', (0, 1))
    assert success is True
    assert gm.turn_action_state['movement_left'] == 2

    result = gm.handle_attack('Enemy1', 'Player1', attack_roll=20, damage_roll=3)
    assert result['success'] is True
    assert result['hit'] is True
    assert result['damage'] == 3
    assert result['target_hp'] == 7
    assert player.hit_points == 7
    assert gm.turn_action_state['attacks_left'] == 0

    # No attacks left afterwards
    again = gm.handle_attack('Enemy1', 'Player1', attack_roll=20, damage_roll=3)
    assert again['success'] is False
    assert player.hit_points == 7


def test_adjacent_attack_below_armor_class_misses(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    start_turn_of(gm, 1)
    assert gm.move_object('Enemy1', (0, 1))[0] is True
    result = gm.handle_attack('Enemy1', 'Player1', attack_roll=9, damage_roll=3)  # AC is 10
    assert result['success'] is True
    assert result['hit'] is False
    assert result['damage'] == 0
    assert player.hit_points == 10
    assert gm.turn_action_state['attacks_left'] == 0


def test_diagonal_neighbour_is_in_melee_range(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    start_turn_of(gm, 1)
    assert gm.move_object('Enemy1', (1, 1))[0] is True  # two steps with 4-neighbour movement
    assert gm.turn_action_state['movement_left'] == 1
    result = gm.handle_attack('Enemy1', 'Player1', attack_roll=20, damage_roll=2)
    assert result['success'] is True
    assert result['hit'] is True


def test_dm_move_object(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    start_turn_of(gm, 1)
    success, reason = gm.move_object('Enemy1', (1, 2))
    assert success is True
    assert gm.map_data['tiles'][(1, 2)]['object'] == 'Enemy1'
    assert gm.map_data['tiles'][(0, 2)]['object'] is None
    assert gm.turn_action_state['movement_left'] == 2

    # No movement left: move fails and changes nothing
    gm.turn_action_state['movement_left'] = 0
    success, reason = gm.move_object('Enemy1', (2, 2))
    assert success is False
    assert 'reachable' in reason.lower()
    assert gm.map_data['tiles'][(1, 2)]['object'] == 'Enemy1'
    assert gm.map_data['tiles'][(2, 2)]['object'] is None
    assert gm.turn_action_state['movement_left'] == 0


def test_move_out_of_turn_fails(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    success, reason = gm.move_object('Enemy1', (1, 2))
    assert success is False
    assert gm.map_data['tiles'][(0, 2)]['object'] == 'Enemy1'


def test_move_to_occupied_tile_fails(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    start_turn_of(gm, 1)
    tiles = gm.map_data['tiles']
    tiles[(0, 1)]['object'] = 'Crate'
    success, reason = gm.move_object('Enemy1', (0, 1))
    assert success is False
    assert 'occupied' in reason.lower()
    assert tiles[(0, 2)]['object'] == 'Enemy1'


def test_move_out_of_bounds_fails(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    start_turn_of(gm, 1)
    success, reason = gm.move_object('Enemy1', (0, 3))
    assert success is False
    assert gm.map_data['tiles'][(0, 2)]['object'] == 'Enemy1'
