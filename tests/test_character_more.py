import random
from core.character import Character


def test_long_and_short_rest(monkeypatch):
    c = Character('Resty', 'Human', 'Fighter')
    # ensure predictable constitution modifier
    c.base_abilities['Konstitution'] = 14
    c.abilities = c.base_abilities.copy()
    c.max_hit_points = 20
    c.hit_points = 10
    c.level = 3
    c.max_hit_dice = 3
    c.hit_dice = 3

    # Short rest: control random roll to be 4
    monkeypatch.setattr('random.randint', lambda a, b: 4)
    healed = c.short_rest(1)
    # roll 4 + con_mod (14 -> +2) = 6 healed
    assert healed == 6
    assert c.hit_dice == 2

    # Long rest should restore HP and at least 1 hit die
    c.long_rest()
    assert c.hit_points == c.max_hit_points
    assert c.hit_dice >= 1


def test_normalize_spells_and_proficiency_and_ac():
    c = Character('Caster', 'Human', 'Wizard')
    # simulate odd spell key formats
    c.spells = {'cantrips': ['Light'], 'level1': ['Magic Missile'], '2': ['Fireball']}
    c.normalize_spells()
    # keys should be integers 0,1,2
    assert 0 in c.spells and 1 in c.spells and 2 in c.spells

    c.level = 9
    assert c.get_proficiency_bonus() == ((9 - 1) // 4 + 2)

    c.equipment = {'Shield': 2}
    c.abilities['Geschicklichkeit'] = 14
    c.calculate_armor_class()
    # base 10 + dex modifier (14 -> +2) + shield 2 = 14
    assert c.armor_class == 14
