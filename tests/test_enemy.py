import pytest
from core.enemy import Enemy

@pytest.fixture
def basic_enemy_data():
    """Provides a basic dictionary of enemy data."""
    return {
        "name": "Goblin",
        "hp": 7,
        "ac": 15,
        "attacks": [{"name": "Scimitar", "damage": "1d6+2"}],
        "speed": 6,
        "notes": "Ein kleiner, fieser Goblin."
    }

def test_enemy_to_dict(basic_enemy_data):
    """Tests the serialization of an Enemy object."""
    enemy = Enemy(
        name=basic_enemy_data["name"],
        hp=basic_enemy_data["hp"],
        armor_class=basic_enemy_data["ac"],
        attacks=basic_enemy_data["attacks"],
        speed=basic_enemy_data["speed"],
        notes=basic_enemy_data["notes"]
    )

    enemy_dict = enemy.to_dict()

    assert enemy_dict["name"] == "Goblin"
    assert enemy_dict["hp"] == 7
    assert enemy_dict["armor_class"] == 15
    assert enemy_dict["ac"] == 15 # Check for backward compatibility key
    assert len(enemy_dict["attacks"]) == 1
    assert enemy_dict["attacks"][0]["name"] == "Scimitar"

def test_enemy_from_dict(basic_enemy_data):
    """Tests the creation of an Enemy object from a dictionary."""
    enemy = Enemy.from_dict(basic_enemy_data)

    assert enemy.name == "Goblin"
    assert enemy.hp == 7
    assert enemy.armor_class == 15
    assert enemy.speed == 6
    assert enemy.notes == "Ein kleiner, fieser Goblin."

def test_enemy_from_dict_legacy_ac(basic_enemy_data):
    """Tests loading an enemy with the old 'ac' key."""
    legacy_data = basic_enemy_data.copy()
    # 'ac' is already in the data, so this test is a bit redundant,
    # but it ensures the logic prefers 'armor_class' if both were present.
    # Let's test the case where *only* 'ac' is present.
    del legacy_data["ac"]
    legacy_data_only_ac = {"name": "Orc", "hp": 15, "ac": 13, "attacks": []}

    enemy = Enemy.from_dict(legacy_data_only_ac)
    assert enemy.armor_class == 13
