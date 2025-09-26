import pytest
from unittest.mock import patch
from core.character import Character

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

def test_long_rest(basic_character):
    """Tests the long rest functionality."""
    basic_character.hit_points = 1
    basic_character.max_hit_points = 15
    basic_character.level = 3
    basic_character.initialize_hit_dice() # max_hit_dice = 3, hit_dice = 3
    basic_character.hit_dice = 0
    basic_character.max_spell_slots = {"1": 4, "2": 2}
    basic_character.current_spell_slots = {"1": 0, "2": 1}

    basic_character.long_rest()

    assert basic_character.hit_points == 15
    assert basic_character.current_spell_slots["1"] == 4
    assert basic_character.current_spell_slots["2"] == 2
    # Recovers half hit dice, rounded down, min 1. 3 // 2 = 1.
    assert basic_character.hit_dice == 1

def test_long_rest_min_dice_recovery(basic_character):
    """Tests that at least one hit die is recovered on a long rest."""
    basic_character.level = 1
    basic_character.initialize_hit_dice() # max_hit_dice = 1
    basic_character.hit_dice = 0
    basic_character.long_rest()
    assert basic_character.hit_dice == 1


@patch('random.randint')
def test_short_rest(mock_randint, basic_character):
    """Tests the short rest functionality."""
    # Mock the dice roll to be a consistent 5
    mock_randint.return_value = 5

    basic_character.abilities["Konstitution"] = 14 # Modifier +2
    # The basic_character is a "Kämpfer", which has a d10 hit die in the test data
    basic_character.level = 3
    basic_character.initialize_hit_dice() # hit_dice = 3
    basic_character.max_hit_points = 30
    basic_character.hit_points = 10

    # Spend 2 hit dice
    healed_amount = basic_character.short_rest(2)

    # Each roll is 5, con mod is +2. So 7 HP per die. 2 dice = 14 HP.
    assert healed_amount == 14
    assert basic_character.hit_points == 24 # 10 + 14
    assert basic_character.hit_dice == 1 # 3 - 2
    assert mock_randint.call_count == 2
    # The CLASS_DATA for "Kämpfer" should specify a hit_die of 10
    mock_randint.assert_any_call(1, 10)

def test_short_rest_no_dice(basic_character):
    """Tests that short rest does nothing if there are no hit dice."""
    basic_character.hit_dice = 0
    basic_character.hit_points = 5
    healed_amount = basic_character.short_rest(1)
    assert healed_amount == 0
    assert basic_character.hit_points == 5

@patch('random.randint')
def test_level_up_simple(mock_randint, basic_character):
    """Tests a simple level up."""
    mock_randint.return_value = 6 # HP roll
    basic_character.calculate_initial_hp() # HP = 10
    basic_character.abilities["Konstitution"] = 10 # Mod = 0
    initial_hp = basic_character.max_hit_points

    basic_character.level_up(choices={})

    assert basic_character.level == 2
    # HP increase is roll (6) + con_mod (0) = 6. New HP = 10 + 6 = 16
    assert basic_character.max_hit_points == initial_hp + 6
    assert basic_character.hit_points == basic_character.max_hit_points
    assert basic_character.hit_dice == 2

@patch('random.randint')
def test_level_up_ability_increase(mock_randint, basic_character):
    """Tests leveling up with an ability score increase."""
    mock_randint.return_value = 1 # HP roll, min value
    basic_character.base_abilities["Stärke"] = 15
    basic_character.update_race_bonuses_and_speed() # Stärke = 16 (Human)
    assert basic_character.abilities["Stärke"] == 16

    choices = {"ability_increase": ["Stärke"]}
    basic_character.level_up(choices=choices)

    assert basic_character.level == 2
    assert basic_character.base_abilities["Stärke"] == 16
    assert basic_character.abilities["Stärke"] == 17 # (15 base + 1 level up) + 1 racial = 17

def test_level_up_add_spell():
    """Tests leveling up and adding a new spell."""
    # Using the from_dict character as it's a spellcaster
    char_data = {
        "name": "Lirael", "race": "Elf", "char_class": "Magier", "level": 1,
        "base_abilities": {"Intelligenz": 16, "Konstitution": 10, "Geschicklichkeit": 10},
        "abilities": {"Intelligenz": 16, "Konstitution": 10, "Geschicklichkeit": 10},
        "spells": {"0": ["Feuerstrahl"], "1": ["Magisches Geschoss"]},
        "max_hit_points": 10, "hit_points": 10, "hit_dice": 1,
    }
    char = Character.from_dict(char_data)

    # Assume at level 2, a wizard can add a new 1st level spell
    choices = {"new_spells": ["Schild"]}
    with patch('random.randint', return_value=4):
        char.level_up(choices=choices)

    assert char.level == 2
    assert "Schild" in char.spells[1]
    assert len(char.spells[1]) == 2

def test_level_up_replace_spell():
    """Tests leveling up and replacing a spell with mocked spell data."""
    mock_spell_data = {
        "Schild": {"level": 1, "name": "Schild"},
        "Spiegelbilder": {"level": 2, "name": "Spiegelbilder"},
        "Magisches Geschoss": {"level": 1, "name": "Magisches Geschoss"},
        "Unsichtbarkeit": {"level": 2, "name": "Unsichtbarkeit"}
    }
    with patch('core.character.SPELL_DATA', mock_spell_data):
        char_data = {
            "name": "Lirael", "race": "Elf", "char_class": "Magier", "level": 3,
            "base_abilities": {"Intelligenz": 16, "Konstitution": 10, "Geschicklichkeit": 10},
            "abilities": {"Intelligenz": 16, "Konstitution": 10, "Geschicklichkeit": 10},
            "spells": {"1": ["Magisches Geschoss", "Schild"], "2": ["Unsichtbarkeit"]},
            "max_hit_points": 20, "hit_points": 20, "hit_dice": 3,
        }
        char = Character.from_dict(char_data)

        choices = {"replaced_spell": "Schild", "replacement_spell": "Spiegelbilder"}
        with patch('random.randint', return_value=4):
            char.level_up(choices=choices)

        assert char.level == 4
        assert "Schild" not in char.spells[1]
        assert "Spiegelbilder" in char.spells[2]
        assert "Unsichtbarkeit" in char.spells[2]
        assert len(char.spells[2]) == 2

def test_get_proficiency_bonus(basic_character):
    """Tests the proficiency bonus calculation at different levels."""
    basic_character.level = 1
    assert basic_character.get_proficiency_bonus() == 2
    basic_character.level = 4
    assert basic_character.get_proficiency_bonus() == 2
    basic_character.level = 5
    assert basic_character.get_proficiency_bonus() == 3
    basic_character.level = 9
    assert basic_character.get_proficiency_bonus() == 4
    basic_character.level = 13
    assert basic_character.get_proficiency_bonus() == 5
    basic_character.level = 17
    assert basic_character.get_proficiency_bonus() == 6

def test_calculate_initiative(basic_character):
    """Tests that initiative is calculated correctly from Dexterity."""
    basic_character.abilities["Geschicklichkeit"] = 15 # Modifier +2
    basic_character.calculate_initiative()
    assert basic_character.initiative == 2

def test_calculate_armor_class(basic_character):
    """Tests armor class calculation, with and without equipment."""
    basic_character.abilities["Geschicklichkeit"] = 12 # Modifier +1
    basic_character.calculate_armor_class()
    # Base AC is 10 + DEX mod
    assert basic_character.armor_class == 11

    # Add some armor
    basic_character.equipment["Lederrüstung"] = 2 # Assuming this gives +2 AC
    basic_character.calculate_armor_class()
    assert basic_character.armor_class == 13 # 11 + 2

def test_collect_proficiencies_and_languages(basic_character):
    """Tests that proficiencies and languages are merged correctly."""
    # basic_character is Mensch (Human) / Kämpfer (Fighter)
    # Test data should give them some defaults.
    # Mensch: [Gemeinsprache, Elfisch], [Keine]
    # Kämpfer: [Alle Rüstungen, Schilde, Einfache Waffen, Kriegswaffen], [Keine]
    basic_character.collect_proficiencies_and_languages()
    assert "Gemeinsprache" in basic_character.languages
    # The test data for Mensch does not include Elfisch, so this is removed.
    assert "Alle Rüstungen" in basic_character.proficiencies
    # Test for duplicates being removed (if any were present)
    assert len(basic_character.proficiencies) == len(set(basic_character.proficiencies))

def test_update_features_fighter(basic_character):
    """Tests that features are added correctly based on level for a Fighter."""
    # Fighter gets "Aktionsschub (1 Anwendung)" at level 2 in test data
    basic_character.level = 1
    basic_character.update_features()
    assert not any(f['name'] == 'Aktionsschub (1 Anwendung)' for f in basic_character.features)

    basic_character.level = 2
    basic_character.update_features()
    assert any(f['name'] == 'Aktionsschub (1 Anwendung)' for f in basic_character.features)

def test_initialize_spell_slots():
    """Tests that a spellcaster gets the correct spell slots."""
    char = Character("Gandalf", "Mensch", "Magier") # Wizard
    char.level = 3
    # According to test data, a 3rd level wizard has 4 level 1 and 2 level 2 slots
    char.initialize_spell_slots()
    assert char.max_spell_slots.get("1") == 4
    assert char.max_spell_slots.get("2") == 2
    assert char.current_spell_slots.get("1") == 4
