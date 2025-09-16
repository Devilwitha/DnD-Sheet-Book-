import pytest
from unittest.mock import MagicMock, patch, call
from core.game_manager import GameManager
from core.character import Character
from core.enemy import Enemy

@pytest.fixture
def logger():
    """A mock logger function."""
    return MagicMock()

@pytest.fixture
def game_manager(logger):
    """A GameManager instance with a mock logger."""
    return GameManager(logger_func=logger)

@pytest.fixture
def sample_char_aragorn():
    """A sample Character instance."""
    char = Character(name="Aragorn", race="Mensch", char_class="Kämpfer")
    char.initiative = 3
    char.speed = 6
    char.actions_per_turn = 1
    char.hit_points = 20
    char.armor_class = 16
    return char

@pytest.fixture
def sample_char_legolas():
    """Another sample Character instance."""
    char = Character(name="Legolas", race="Elf", char_class="Waldläufer")
    char.initiative = 5
    char.speed = 7
    char.actions_per_turn = 1
    char.hit_points = 18
    char.armor_class = 15
    return char

@pytest.fixture
def sample_enemy_goblin():
    """A sample Enemy instance."""
    return Enemy(name="Goblin #1", hp=7, armor_class=15, attacks=[{"damage": "1d6"}], speed=6)

@pytest.fixture
def sample_enemy_orc():
    """Another sample Enemy instance."""
    return Enemy(name="Orc #1", hp=15, armor_class=13, attacks=[{"damage": "1d12"}], speed=6)

def test_initialization(game_manager):
    """Tests that the game manager initializes with empty state."""
    assert game_manager.online_players == {}
    assert game_manager.enemies == []
    assert game_manager.initiative_order == []
    assert game_manager.current_turn_index == -1

def test_get_character_or_enemy_by_name(game_manager, sample_char_aragorn, sample_enemy_goblin):
    """Tests retrieving a character or enemy by their name."""
    game_manager.online_players = {"Aragorn": sample_char_aragorn}
    game_manager.enemies = [sample_enemy_goblin]

    assert game_manager.get_character_or_enemy_by_name("Aragorn") == sample_char_aragorn
    assert game_manager.get_character_or_enemy_by_name("Goblin #1") == sample_enemy_goblin
    assert game_manager.get_character_or_enemy_by_name("Unknown") is None

@patch('random.randint')
def test_roll_initiative(mock_randint, game_manager, sample_char_aragorn, sample_char_legolas, sample_enemy_goblin):
    """Tests the initiative rolling and sorting logic."""
    # Aragorn (init 3) rolls 10 -> 13
    # Legolas (init 5) rolls 15 -> 20
    # Goblin (init 0) rolls 5 -> 5
    mock_randint.side_effect = [10, 15, 5]

    game_manager.online_players = {"Aragorn": sample_char_aragorn, "Legolas": sample_char_legolas}
    game_manager.enemies = [sample_enemy_goblin]

    order = game_manager.roll_initiative_for_all()

    assert len(order) == 3
    assert order[0] == (20, "Legolas")
    assert order[1] == (13, "Aragorn")
    assert order[2] == (5, "Goblin #1")
    assert game_manager.current_turn_index == 0
    assert game_manager.get_current_turn_info()["name"] == "Legolas"

def test_turn_management(game_manager, sample_char_aragorn, sample_char_legolas):
    """Tests ending a turn and cycling through the initiative order."""
    game_manager.initiative_order = [(20, "Legolas"), (13, "Aragorn")]
    game_manager.online_players = {"Aragorn": sample_char_aragorn, "Legolas": sample_char_legolas}
    game_manager.current_turn_index = 0

    # End Legolas's turn
    turn_info = game_manager.end_turn()
    assert game_manager.current_turn_index == 1
    assert turn_info["name"] == "Aragorn"

    # End Aragorn's turn, should loop back to Legolas
    turn_info = game_manager.end_turn()
    assert game_manager.current_turn_index == 0
    assert turn_info["name"] == "Legolas"

def test_move_object(game_manager, sample_char_aragorn):
    """Tests moving a character on the map."""
    game_manager.map_data = {
        'tiles': {
            (0, 0): {'object': "Aragorn"},
            (0, 1): {'object': None},
            (5, 5): {'object': None}
        }
    }
    game_manager.online_players = {"Aragorn": sample_char_aragorn}
    game_manager.initiative_order = [(10, "Aragorn")]
    game_manager.current_turn_index = 0
    game_manager.turn_action_state = {'movement_left': 6, 'attacks_left': 1}

    # Valid move
    success, reason = game_manager.move_object("Aragorn", (0, 1))
    assert success is True
    assert game_manager.map_data['tiles'][(0, 0)]['object'] is None
    assert game_manager.map_data['tiles'][(0, 1)]['object'] == "Aragorn"
    assert game_manager.turn_action_state['movement_left'] == 5

    # Invalid move (too far)
    success, reason = game_manager.move_object("Aragorn", (5, 5))
    assert success is False
    assert reason == "Not enough movement left."
    assert game_manager.map_data['tiles'][(0, 1)]['object'] == "Aragorn" # Should not have moved
    assert game_manager.turn_action_state['movement_left'] == 5 # Should not have changed

def test_handle_attack_hit(game_manager, sample_char_aragorn, sample_enemy_orc):
    """Tests a successful attack that hits."""
    with patch('random.randint') as mock_randint:
        # First call is attack roll (15), second is damage roll for 1d4 (3)
        mock_randint.side_effect = [15, 3]

        game_manager.online_players = {"Aragorn": sample_char_aragorn}
        game_manager.enemies = [sample_enemy_orc]
        game_manager.initiative_order = [(10, "Aragorn")]
        game_manager.current_turn_index = 0
        game_manager.turn_action_state = {'attacks_left': 1}
        game_manager.map_data = {'tiles': {(0, 0): {'object': "Orc #1"}}}

        # Aragorn (Character) attacks Orc (Enemy)
        result = game_manager.handle_attack("Aragorn", "Orc #1")

        assert result["success"] is True
        assert result["hit"] is True
        assert result["damage"] == 3 # From the mocked damage roll
        assert sample_enemy_orc.hp == 12 # 15 - 3
        assert game_manager.turn_action_state['attacks_left'] == 0
        # Check that randint was called for the attack and then for the damage
        mock_randint.assert_has_calls([call(1, 20), call(1, 4)])

def test_handle_attack_miss(game_manager, sample_char_aragorn, sample_enemy_orc):
    """Tests an attack that misses."""
    with patch('random.randint', return_value=5) as mock_randint:
        game_manager.online_players = {"Aragorn": sample_char_aragorn}
        game_manager.enemies = [sample_enemy_orc]
        game_manager.initiative_order = [(10, "Aragorn")]
        game_manager.current_turn_index = 0
        game_manager.turn_action_state = {'attacks_left': 1}

        initial_hp = sample_enemy_orc.hp
        result = game_manager.handle_attack("Aragorn", "Orc #1")

        assert result["success"] is True
        assert result["hit"] is False
        assert sample_enemy_orc.hp == initial_hp
        assert game_manager.turn_action_state['attacks_left'] == 0
        mock_randint.assert_called_once_with(1, 20)

def test_handle_character_death(game_manager, sample_char_aragorn, sample_enemy_goblin):
    """Tests the logic for when a character/enemy is defeated."""
    game_manager.online_players = {"Aragorn": sample_char_aragorn}
    game_manager.enemies = [sample_enemy_goblin]
    game_manager.initiative_order = [(20, "Aragorn"), (10, "Goblin #1")]
    game_manager.current_turn_index = 1
    game_manager.map_data = {'tiles': {(1, 1): {'object': "Goblin #1"}}}

    outcome = game_manager.handle_character_death("Goblin #1")

    assert outcome == "VICTORY"
    assert sample_enemy_goblin not in game_manager.enemies
    assert len(game_manager.initiative_order) == 1
    assert game_manager.initiative_order[0][1] == "Aragorn"
    assert game_manager.map_data['tiles'][(1, 1)]['object'] is None
    assert game_manager.current_turn_index == -1 # Combat ends
