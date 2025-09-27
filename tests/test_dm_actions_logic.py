import pytest
from core.game_manager import GameManager
from core.character import Character
from core.enemy import Enemy

@pytest.fixture
def setup_map_and_gamemanager():
    gm = GameManager()
    # Erstelle eine einfache Map mit 3x3 Feldern
    gm.map_data = {
        'rows': 3,
        'cols': 3,
        'tiles': {
            (0,0): {'type': 'Floor', 'object': 'Player1'},
            (0,1): {'type': 'Floor', 'object': None},
            (0,2): {'type': 'Floor', 'object': 'Enemy1'},
            (1,0): {'type': 'Floor', 'object': None},
            (1,1): {'type': 'Floor', 'object': None},
            (1,2): {'type': 'Floor', 'object': None},
            (2,0): {'type': 'Floor', 'object': None},
            (2,1): {'type': 'Floor', 'object': None},
            (2,2): {'type': 'Floor', 'object': None},
        }
    }
    player = Character('Player1', 'Mensch', 'Kämpfer')
    player.hit_points = 10
    player.max_hit_points = 10
    player.armor_class = 10
    player.speed = 3
    player.initiative = 2
    player.actions_per_turn = 1
    enemy = Enemy(name='Enemy1', hp=8, armor_class=9, attacks=[{'name': 'Bite', 'damage': '1d4'}])
    gm.online_players = {'addr1': player}
    gm.enemies = [enemy]
    gm.initiative_order = [(15, 'Player1'), (10, 'Enemy1')]
    gm.current_turn_index = 0
    gm.turn_action_state = {'movement_left': 3, 'attacks_left': 1}
    return gm, player, enemy

def test_dm_select_and_attack(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    # Simuliere DM: Angreifer auswählen
    attacker = gm.get_character_or_enemy_by_name('Enemy1')
    assert attacker is enemy
    # Simuliere DM: Angriff auf Spieler
    result = gm.handle_attack('Enemy1', 'Player1')
    assert result['success'] is False  # Enemy1 ist nicht am Zug
    # Setze Enemy1 als aktuellen Zug
    gm.current_turn_index = 1
    gm.turn_action_state = {'movement_left': 3, 'attacks_left': 1}
    result = gm.handle_attack('Enemy1', 'Player1')
    assert result['success'] is True
    assert 'damage' in result
    assert result['hit'] in (True, False)
    # Nach Angriff: attacks_left reduziert
    assert gm.turn_action_state['attacks_left'] == 0

def test_dm_move_object(setup_map_and_gamemanager):
    gm, player, enemy = setup_map_and_gamemanager
    # Enemy1 ist auf (0,2), bewege zu (1,2)
    gm.current_turn_index = 1
    gm.turn_action_state = {'movement_left': 3, 'attacks_left': 1}
    success, reason = gm.move_object('Enemy1', (1,2))
    assert success is True
    assert gm.map_data['tiles'][(1,2)]['object'] == 'Enemy1'
    assert gm.map_data['tiles'][(0,2)]['object'] is None
    # Bewegung außerhalb der Reichweite
    gm.turn_action_state['movement_left'] = 0
    success, reason = gm.move_object('Enemy1', (2,2))
    assert success is False
    assert 'Not enough movement' in reason
