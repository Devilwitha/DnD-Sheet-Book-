import copy

import pytest
from unittest.mock import patch

import core.character as character_module
from core.character import Character


def make_fighter(level=1):
    # Realistic, fully initialized fighter (resources, HP, hit dice, features, AC, initiative)
    char = Character(name='Testan', race='Mensch', char_class='Kämpfer')
    char.level = level
    char.initialize_character()
    return char


@pytest.fixture
def basic_character():
    '''Provides an initialized level 1 Character instance for testing.'''
    return make_fighter()


def snapshot(char):
    return (
        char.level, char.max_hit_points, char.hit_points, char.hit_dice,
        copy.deepcopy(char.spells), dict(char.base_abilities),
        dict(char.max_spell_slots), dict(char.current_spell_slots),
    )


def test_character_initialization(basic_character):
    assert basic_character.name == 'Testan'
    assert basic_character.race == 'Mensch'
    assert basic_character.char_class == 'Kämpfer'
    assert basic_character.level == 1
    assert basic_character.speed == 6  # 9m -> 6 squares
    assert basic_character.initialization_complete is True
    assert basic_character.max_hit_points > 0
    assert basic_character.hit_points == basic_character.max_hit_points
    assert basic_character.max_hit_dice == 1
    assert basic_character.hit_dice == 1


def test_initialize_character_is_idempotent(basic_character):
    basic_character.hit_points = 3
    basic_character.hit_dice = 0
    basic_character.initialize_character()
    assert basic_character.hit_points == 3
    assert basic_character.hit_dice == 0


def test_racial_ability_bonus(basic_character):
    # Humans get +1 to all abilities
    basic_character.base_abilities['Stärke'] = 10
    basic_character.update_race_bonuses_and_speed()
    assert basic_character.abilities['Stärke'] == 11
    assert basic_character.base_abilities['Stärke'] == 10


def test_initial_hp_calculation(basic_character):
    # Fighter hit die is d10. Base Con 9 + 1 racial = 10 -> modifier 0 -> 10 HP.
    basic_character.base_abilities['Konstitution'] = 9
    basic_character.update_race_bonuses_and_speed()
    basic_character.calculate_initial_hp()
    assert basic_character.max_hit_points == 10
    assert basic_character.hit_points == 10

    # Base Con 15 + 1 racial = 16 -> modifier +3
    basic_character.base_abilities['Konstitution'] = 15
    basic_character.update_race_bonuses_and_speed()
    basic_character.calculate_initial_hp()
    assert basic_character.abilities['Konstitution'] == 16
    assert basic_character.max_hit_points == 13
    assert basic_character.hit_points == 13


def test_character_to_dict_serialization(basic_character):
    char_dict = basic_character.to_dict()
    assert isinstance(char_dict, dict)
    assert char_dict['name'] == 'Testan'
    assert char_dict['level'] == 1
    assert char_dict['initialization_complete'] is True


def test_character_from_dict_deserialization():
    char_data = {
        'name': 'Lirael', 'race': 'Elf', 'char_class': 'Magier', 'level': 2,
        'base_abilities': {'Stärke': 8, 'Geschicklichkeit': 14, 'Konstitution': 12, 'Intelligenz': 16, 'Weisheit': 10, 'Charisma': 10},
        'abilities': {'Stärke': 8, 'Geschicklichkeit': 16, 'Konstitution': 12, 'Intelligenz': 16, 'Weisheit': 10, 'Charisma': 10},
        'hit_points': 12, 'max_hit_points': 12, 'speed': 6, 'armor_class': 13,
        'inventory': [], 'equipment': {}, 'currency': {}, 'equipped_weapon': 'Stab',
        'background': 'Gelehrter', 'alignment': 'Rechtschaffen Gut',
        'personality_traits': '', 'ideals': '', 'bonds': '', 'flaws': '',
        'features': [], 'proficiencies': [], 'languages': [],
        'spells': {'0': ['Feuerstrahl'], '1': ['Magisches Geschoss']},
        'max_spell_slots': {'1': 3}, 'current_spell_slots': {'1': 3},
        'max_hit_dice': 2, 'hit_dice': 2, 'fighting_style': None
    }
    char = Character.from_dict(char_data)
    assert char.name == 'Lirael'
    assert char.level == 2
    assert char.abilities['Geschicklichkeit'] == 16
    assert isinstance(char.spells[1], list)
    assert char.initialization_complete is True


def test_long_rest():
    char = make_fighter(level=3)  # max_hit_dice = 3
    char.hit_points = 1
    char.max_hit_points = 15
    char.hit_dice = 0
    char.max_spell_slots = {'1': 4, '2': 2}
    char.current_spell_slots = {'1': 0, '2': 1}

    char.long_rest()

    assert char.hit_points == 15
    assert char.current_spell_slots['1'] == 4
    assert char.current_spell_slots['2'] == 2
    # Recovers half of the max hit dice, rounded down, min 1: 3 // 2 = 1
    assert char.hit_dice == 1


def test_long_rest_min_dice_recovery(basic_character):
    basic_character.hit_dice = 0
    basic_character.long_rest()
    assert basic_character.hit_dice == 1


def test_long_rest_does_not_exceed_max_hit_dice():
    char = make_fighter(level=4)
    char.hit_dice = 4
    char.long_rest()
    assert char.hit_dice == 4


@patch('random.randint')
def test_short_rest(mock_randint):
    mock_randint.return_value = 5
    char = make_fighter(level=3)
    char.abilities['Konstitution'] = 14  # modifier +2
    char.max_hit_points = 30
    char.hit_points = 10

    healed_amount = char.short_rest(2)

    # Each die: 5 + 2 = 7 HP; two dice = 14 HP
    assert healed_amount == 14
    assert char.hit_points == 24
    assert char.hit_dice == 1
    assert mock_randint.call_count == 2
    mock_randint.assert_any_call(1, 10)  # Fighter uses d10


@patch('random.randint')
def test_short_rest_caps_at_max_hp(mock_randint):
    mock_randint.return_value = 10
    char = make_fighter(level=2)
    char.max_hit_points = 20
    char.hit_points = 19
    char.short_rest(1)
    assert char.hit_points == 20


def test_short_rest_no_dice(basic_character):
    basic_character.hit_dice = 0
    basic_character.hit_points = 5
    healed_amount = basic_character.short_rest(1)
    assert healed_amount == 0
    assert basic_character.hit_points == 5


def test_level_up_simple(basic_character):
    initial_hp = basic_character.max_hit_points
    assert basic_character.abilities['Konstitution'] == 11  # modifier 0

    basic_character.level_up(choices={'hp_roll': 6})

    assert basic_character.level == 2
    assert basic_character.max_hit_points == initial_hp + 6
    assert basic_character.hit_points == basic_character.max_hit_points
    assert basic_character.max_hit_dice == 2
    assert basic_character.hit_dice == 2


@patch('random.randint')
def test_level_up_random_hp_roll(mock_randint, basic_character):
    mock_randint.return_value = 6
    initial_hp = basic_character.max_hit_points
    basic_character.level_up(choices={})
    mock_randint.assert_called_once_with(1, 10)
    assert basic_character.level == 2
    assert basic_character.max_hit_points == initial_hp + 6


def test_level_up_invalid_hp_roll_changes_nothing(basic_character):
    before = snapshot(basic_character)
    with pytest.raises(ValueError):
        basic_character.level_up(choices={'hp_roll': 11})  # d10 maximum is 10
    assert snapshot(basic_character) == before


def test_level_up_ability_increase_not_allowed_at_level_2(basic_character):
    # Fighter has no ability score improvement when reaching level 2
    before = snapshot(basic_character)
    with pytest.raises(ValueError):
        basic_character.level_up(choices={'ability_increase': ['Stärke', 'Stärke'], 'hp_roll': 5})
    assert snapshot(basic_character) == before
    assert basic_character.level == 1


def test_level_up_ability_increase_two_points_at_level_4():
    char = make_fighter(level=3)
    char.base_abilities['Stärke'] = 15
    char.update_race_bonuses_and_speed()
    assert char.abilities['Stärke'] == 16
    hp_before = char.max_hit_points

    char.level_up(choices={'ability_increase': ['Stärke', 'Stärke'], 'hp_roll': 5})

    assert char.level == 4
    assert char.base_abilities['Stärke'] == 17  # two points
    assert char.abilities['Stärke'] == 18  # + racial 1
    assert char.max_hit_points == hp_before + 5


def test_level_up_ability_increase_split_over_two_abilities():
    char = make_fighter(level=3)
    char.level_up(choices={'ability_increase': ['Stärke', 'Geschicklichkeit'], 'hp_roll': 5})
    assert char.base_abilities['Stärke'] == 11
    assert char.base_abilities['Geschicklichkeit'] == 11


def test_level_up_one_ability_point_is_invalid_at_level_4():
    char = make_fighter(level=3)
    before = snapshot(char)
    with pytest.raises(ValueError):
        char.level_up(choices={'ability_increase': ['Stärke'], 'hp_roll': 5})
    assert snapshot(char) == before


def test_level_up_three_ability_points_is_invalid_at_level_4():
    char = make_fighter(level=3)
    before = snapshot(char)
    with pytest.raises(ValueError):
        char.level_up(choices={'ability_increase': ['Stärke', 'Stärke', 'Stärke'], 'hp_roll': 5})
    assert snapshot(char) == before


def test_level_up_missing_ability_increase_at_level_4_is_invalid():
    char = make_fighter(level=3)
    with pytest.raises(ValueError):
        char.level_up(choices={'hp_roll': 5})
    assert char.level == 3


def test_level_up_ability_cannot_exceed_20():
    char = make_fighter(level=3)
    char.base_abilities['Stärke'] = 18
    char.update_race_bonuses_and_speed()  # 19 with racial bonus
    before = snapshot(char)
    with pytest.raises(ValueError):
        char.level_up(choices={'ability_increase': ['Stärke', 'Stärke'], 'hp_roll': 5})
    assert snapshot(char) == before


def test_level_up_constitution_increase_is_retroactive():
    char = make_fighter(level=3)
    assert char.abilities['Konstitution'] == 11  # modifier 0
    hp_before = char.max_hit_points

    char.level_up(choices={'ability_increase': ['Konstitution', 'Konstitution'], 'hp_roll': 5})

    # Con 13 -> modifier +1: new level gives 5 + 1, plus +1 for each of the 3 earlier levels
    assert char.abilities['Konstitution'] == 13
    assert char.max_hit_points == hp_before + 6 + 3


# ---- spell rules, isolated with controlled class/spell data ----

def _progression(base_known, step):
    return {
        1: {'cantrips_known': 3, 'spells_known': base_known, 'spell_slots': {1: 2}},
        2: {'cantrips_known': 3, 'spells_known': base_known + step, 'spell_slots': {1: 3}},
        3: {'cantrips_known': 3, 'spells_known': base_known + 2 * step, 'spell_slots': {1: 4, 2: 2}},
        4: {'cantrips_known': 4, 'spells_known': base_known + 3 * step, 'spell_slots': {1: 4, 2: 3}},
    }


@pytest.fixture
def fake_rules(monkeypatch):
    spell_list = {
        0: ['Feuerstrahl', 'Magierhand'],
        1: ['Magisches Geschoss', 'Schild', 'Nebelwolke', 'Person bezaubern'],
        2: ['Unsichtbarkeit', 'Spiegelbilder', 'Spinnennetz'],
    }
    class_data = {
        'Magier': {'hit_die': 6, 'features': {}, 'progression': _progression(6, 2), 'spell_list': spell_list},
        'Barde': {'hit_die': 8, 'features': {}, 'progression': _progression(4, 1), 'spell_list': spell_list},
    }
    spell_data = {}
    for lvl, names in spell_list.items():
        for n in names:
            spell_data[n] = {'level': lvl, 'name': n}
    monkeypatch.setattr(character_module, 'CLASS_DATA', class_data)
    monkeypatch.setattr(character_module, 'SPELL_DATA', spell_data)


def make_caster(char_class, level, spells):
    char = Character('Lirael', 'Mensch', char_class)
    char.level = level
    char.base_abilities['Intelligenz'] = 15
    char.base_abilities['Charisma'] = 15
    char.initialize_character()
    char.spells = {k: list(v) for k, v in spells.items()}
    return char


def test_level_up_add_spell(fake_rules):
    char = make_caster('Magier', 1, {0: ['Feuerstrahl'], 1: ['Magisches Geschoss']})

    char.level_up(choices={'new_spells': ['Schild'], 'hp_roll': 4})

    assert char.level == 2
    assert 'Schild' in char.spells[1]
    assert len(char.spells[1]) == 2
    assert char.max_spell_slots == {'1': 3}
    assert char.current_spell_slots == {'1': 3}


def test_level_up_add_too_many_spells_is_invalid(fake_rules):
    char = make_caster('Magier', 1, {0: ['Feuerstrahl'], 1: ['Magisches Geschoss']})
    before = snapshot(char)
    # Wizard may add 2 spells for this level, not 3
    with pytest.raises(ValueError):
        char.level_up(choices={'new_spells': ['Schild', 'Nebelwolke', 'Person bezaubern'], 'hp_roll': 4})
    assert snapshot(char) == before


def test_level_up_add_spell_above_available_slot_level_is_invalid(fake_rules):
    char = make_caster('Magier', 1, {0: ['Feuerstrahl'], 1: ['Magisches Geschoss']})
    before = snapshot(char)
    with pytest.raises(ValueError):
        char.level_up(choices={'new_spells': ['Spiegelbilder'], 'hp_roll': 4})  # level 2 spell, only level 1 slots
    assert snapshot(char) == before


def test_level_up_add_already_known_spell_is_invalid(fake_rules):
    char = make_caster('Magier', 1, {0: ['Feuerstrahl'], 1: ['Magisches Geschoss']})
    with pytest.raises(ValueError):
        char.level_up(choices={'new_spells': ['Magisches Geschoss'], 'hp_roll': 4})
    assert char.level == 1


def test_level_up_add_cantrip(fake_rules):
    char = make_caster('Magier', 3, {0: ['Feuerstrahl'], 1: ['Magisches Geschoss'], 2: ['Unsichtbarkeit']})
    char.level_up(choices={'new_cantrips': ['Magierhand'], 'hp_roll': 3})
    assert char.level == 4
    assert 'Magierhand' in char.spells[0]


def test_level_up_replace_spell_allowed_for_bard(fake_rules):
    char = make_caster('Barde', 3, {1: ['Magisches Geschoss', 'Schild'], 2: ['Unsichtbarkeit']})

    char.level_up(choices={'replaced_spell': 'Schild', 'replacement_spell': 'Spiegelbilder', 'hp_roll': 4})

    assert char.level == 4
    assert 'Schild' not in char.spells[1]
    assert 'Magisches Geschoss' in char.spells[1]
    assert 'Spiegelbilder' in char.spells[2]
    assert 'Unsichtbarkeit' in char.spells[2]
    assert len(char.spells[2]) == 2


def test_level_up_replace_spell_invalid_for_wizard(fake_rules):
    char = make_caster('Magier', 3, {1: ['Magisches Geschoss', 'Schild'], 2: ['Unsichtbarkeit']})
    before = snapshot(char)
    with pytest.raises(ValueError):
        char.level_up(choices={'replaced_spell': 'Schild', 'replacement_spell': 'Spiegelbilder', 'hp_roll': 4})
    assert snapshot(char) == before


def test_level_up_replace_unknown_spell_invalid_for_bard(fake_rules):
    char = make_caster('Barde', 3, {1: ['Magisches Geschoss', 'Schild'], 2: ['Unsichtbarkeit']})
    before = snapshot(char)
    with pytest.raises(ValueError):
        char.level_up(choices={'replaced_spell': 'Nebelwolke', 'replacement_spell': 'Spiegelbilder', 'hp_roll': 4})
    assert snapshot(char) == before


def test_level_up_replace_needs_both_spells(fake_rules):
    char = make_caster('Barde', 3, {1: ['Magisches Geschoss', 'Schild'], 2: ['Unsichtbarkeit']})
    with pytest.raises(ValueError):
        char.level_up(choices={'replaced_spell': 'Schild', 'hp_roll': 4})
    assert char.level == 3


def test_get_proficiency_bonus(basic_character):
    expected = {1: 2, 4: 2, 5: 3, 8: 3, 9: 4, 13: 5, 17: 6, 20: 6}
    for level, bonus in expected.items():
        basic_character.level = level
        assert basic_character.get_proficiency_bonus() == bonus


def test_calculate_initiative(basic_character):
    basic_character.base_abilities['Geschicklichkeit'] = 14
    basic_character.update_race_bonuses_and_speed()  # 15 -> modifier +2
    basic_character.calculate_initiative()
    assert basic_character.initiative == 2


def test_calculate_armor_class(basic_character):
    basic_character.abilities['Geschicklichkeit'] = 12  # modifier +1
    basic_character.calculate_armor_class()
    assert basic_character.armor_class == 11

    # Equipment values are additive AC bonuses
    basic_character.equipment['Lederrüstung'] = 2
    basic_character.calculate_armor_class()
    assert basic_character.armor_class == 13


def test_collect_proficiencies_and_languages(basic_character):
    basic_character.collect_proficiencies_and_languages()
    assert 'Gemeinsprache' in basic_character.languages
    assert 'Alle Rüstungen' in basic_character.proficiencies
    assert len(basic_character.proficiencies) == len(set(basic_character.proficiencies))
    assert len(basic_character.languages) == len(set(basic_character.languages))


def test_update_features_fighter(basic_character):
    # Fighter gets Aktionsschub at level 2
    basic_character.level = 1
    basic_character.update_features()
    assert not any(f['name'] == 'Aktionsschub (1 Anwendung)' for f in basic_character.features)

    basic_character.level = 2
    basic_character.update_features()
    assert any(f['name'] == 'Aktionsschub (1 Anwendung)' for f in basic_character.features)


def test_initialize_spell_slots():
    char = Character('Gandalf', 'Mensch', 'Magier')
    char.level = 3
    char.initialize_spell_slots()
    # A 3rd level wizard has four 1st level and two 2nd level slots
    assert char.max_spell_slots.get('1') == 4
    assert char.max_spell_slots.get('2') == 2
    assert char.current_spell_slots.get('1') == 4
    assert char.current_spell_slots.get('2') == 2
