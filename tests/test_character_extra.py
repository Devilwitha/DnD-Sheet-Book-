from core.character import Character


def test_character_to_from_dict_roundtrip():
    c = Character('Test', 'Human', 'Fighter')
    c.base_abilities['Stärke'] = 12
    c.abilities = c.base_abilities.copy()
    c.level = 2
    c.max_hit_points = 20
    c.hit_points = 20
    c.equipment = {'Shield': 2}
    c.spells = {0: ['Light']}

    d = c.to_dict()
    assert d['name'] == 'Test'
    assert d['race'] == 'Human'
    assert d['char_class'] == 'Fighter'
    assert 'spells' in d and isinstance(d['spells'], dict)

    c2 = Character.from_dict(d)
    assert c2.name == c.name
    assert c2.level == c.level
    assert c2.equipment == c.equipment
    assert 0 in c2.spells
