import json
import os
from core.character import Character


def test_character_to_from_dict_roundtrip(tmp_path):
    c = Character('Test', 'Human', 'Warrior')
    c.level = 3
    c.base_abilities['Stärke'] = 15
    c.spells = {0: ['light'], 1: ['magic_missile']}
    c.initialize_character()

    d = c.to_dict()
    # write/read to json to simulate persistence
    p = tmp_path / 'char.json'
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False)

    with open(p, 'r', encoding='utf-8') as f:
        d2 = json.load(f)

    c2 = Character.from_dict(d2)

    assert c2.name == c.name
    assert c2.race == c.race
    assert c2.char_class == c.char_class
    assert c2.level == c.level
    assert isinstance(c2.spells, dict)
