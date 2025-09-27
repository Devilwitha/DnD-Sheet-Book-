import pytest
from core.game_manager import GameManager
from core.character import Character
from core.enemy import Enemy

@pytest.fixture
def setup_gamemanager_with_offline():
    gm = GameManager()
    # Online Spieler
    online = Character('Online1', 'Mensch', 'Kämpfer')
    online.hit_points = 10
    online.max_hit_points = 10
    online.armor_class = 10
    online.speed = 3
    online.initiative = 2
    online.actions_per_turn = 1
    # Offline Spieler
    offline = Character('Offline1', 'Mensch', 'Kämpfer')
    offline.hit_points = 12
    offline.max_hit_points = 12
    offline.armor_class = 11
    offline.speed = 4
    offline.initiative = 1
    offline.actions_per_turn = 1
    gm.online_players = {'addr1': online}
    gm.offline_players = [offline]
    gm.enemies = [Enemy('Enemy1', 8, 9, [{'name': 'Bite', 'damage': '1d4'}])]
    gm.map_data = {
        'rows': 3,
        'cols': 3,
        'tiles': {
            (0,0): {'type': 'Floor', 'object': 'Online1'},
            (0,1): {'type': 'Floor', 'object': None},
            (0,2): {'type': 'Floor', 'object': 'Offline1'},
            (1,0): {'type': 'Floor', 'object': None},
            (1,1): {'type': 'Floor', 'object': None},
            (1,2): {'type': 'Floor', 'object': 'Enemy1'},
            (2,0): {'type': 'Floor', 'object': None},
            (2,1): {'type': 'Floor', 'object': None},
            (2,2): {'type': 'Floor', 'object': None},
        }
    }
    return gm, online, offline

def test_offline_player_in_map(setup_gamemanager_with_offline):
    gm, online, offline = setup_gamemanager_with_offline
    # Offline Spieler ist auf der Map
    found = False
    for tile in gm.map_data['tiles'].values():
        if tile['object'] == offline.name:
            found = True
    assert found

def test_dm_move_offline_player(setup_gamemanager_with_offline):
    gm, online, offline = setup_gamemanager_with_offline
    gm.current_turn_index = 0
    gm.initiative_order = [(15, 'Offline1')]
    gm.turn_action_state = {'movement_left': 4, 'attacks_left': 1}
    # Move Offline1 von (0,2) nach (2,2)
    success, reason = gm.move_object('Offline1', (2,2))
    assert success is True
    assert gm.map_data['tiles'][(2,2)]['object'] == 'Offline1'
    assert gm.map_data['tiles'][(0,2)]['object'] is None

def test_dm_attack_with_offline_player(setup_gamemanager_with_offline):
    gm, online, offline = setup_gamemanager_with_offline
    gm.current_turn_index = 0
    gm.initiative_order = [(15, 'Offline1')]
    gm.turn_action_state = {'movement_left': 4, 'attacks_left': 1}
    # Füge einen Gegner als Ziel hinzu
    gm.map_data['tiles'][(1,2)]['object'] = 'Enemy1'
    result = gm.handle_attack('Offline1', 'Enemy1')
    assert result['success'] is True
    assert 'damage' in result
    assert result['hit'] in (True, False)
    assert gm.turn_action_state['attacks_left'] == 0
