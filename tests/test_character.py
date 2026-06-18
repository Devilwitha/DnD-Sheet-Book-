import pytest
from core.character import Character
from utils.data_manager import load_test_data

# Load test data once for all tests in this module
load_test_data()

@pytest.fixture
def basic_character():
    """Provides a basic Character instance for testing."""
    return Character(name="Testan", race="Mensch", char_class="Kämpfer")

def test_character_initialization(basic_character):
    """Tests basic attributes of a newly created character."""
    assert basic_character.name == "Testan"
    assert basic_character.race == "Mensch"
    assert basic_character.char_class == "Kämpfer"
    assert basic_character.level == 1
    assert basic_character.speed == 6 # Humans get 9m -> 6 squares

def test_racial_ability_bonus(basic_character):
    """Tests if racial bonuses are applied correctly."""
    # Humans get +1 to all stats in the test data
    basic_character.base_abilities["Stärke"] = 10
    basic_character.update_race_bonuses_and_speed()
    assert basic_character.abilities["Stärke"] == 11

def test_initial_hp_calculation(basic_character):
    """Tests the initial HP calculation."""
    # Fighter hit die is 10. Constitution is 10 (modifier 0).
    # So, HP should be 10 + 0 = 10.
    basic_character.abilities["Konstitution"] = 10
    basic_character.calculate_initial_hp()
    assert basic_character.max_hit_points == 10
    assert basic_character.hit_points == 10

    # Test with a high constitution
    basic_character.abilities["Konstitution"] = 16 # Modifier +3
    basic_character.calculate_initial_hp()
    assert basic_character.max_hit_points == 13 # 10 + 3
    assert basic_character.hit_points == 13

def test_character_to_dict_serialization(basic_character):
    """Tests the to_dict method for basic serializability."""
    char_dict = basic_character.to_dict()
    assert isinstance(char_dict, dict)
    assert char_dict['name'] == "Testan"
    assert char_dict['level'] == 1

def test_character_from_dict_deserialization():
    """Tests the from_dict class method."""
    char_data = {
        "name": "Lirael", "race": "Elf", "char_class": "Magier", "level": 2,
        "base_abilities": {"Stärke": 8, "Geschicklichkeit": 14, "Konstitution": 12, "Intelligenz": 16, "Weisheit": 10, "Charisma": 10},
        "abilities": {"Stärke": 8, "Geschicklichkeit": 16, "Konstitution": 12, "Intelligenz": 16, "Weisheit": 10, "Charisma": 10},
        "hit_points": 12, "max_hit_points": 12, "speed": 6, "armor_class": 13,
        "inventory": [], "equipment": {}, "currency": {}, "equipped_weapon": "Stab",
        "background": "Gelehrter", "alignment": "Rechtschaffen Gut",
        "personality_traits": "", "ideals": "", "bonds": "", "flaws": "",
        "features": [], "proficiencies": [], "languages": [],
        "spells": {"0": ["Feuerstrahl"], "1": ["Magisches Geschoss"]},
        "max_spell_slots": {"1": 3}, "current_spell_slots": {"1": 3},
        "max_hit_dice": 2, "hit_dice": 2, "fighting_style": None
    }
    char = Character.from_dict(char_data)
    assert char.name == "Lirael"
    assert char.level == 2
    assert char.abilities["Geschicklichkeit"] == 16
    assert isinstance(char.spells[1], list)
