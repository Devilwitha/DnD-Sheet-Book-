import random

import pytest

from core.character import Character
from utils.data_manager import RACE_DATA, CLASS_DATA


def make():
    c = Character('Test', sorted(RACE_DATA)[0], sorted(CLASS_DATA)[0])
    c.initialize_character()
    return c


def hit_die(c):
    return CLASS_DATA.get(c.char_class, {}).get('hit_die', 8)


def test_unique_ids():
    assert Character('a', 'x', 'y').character_id != Character('a', 'x', 'y').character_id


def test_level_up_uses_given_roll_and_does_not_full_heal(monkeypatch):
    c = make()
    c.hit_points = max(1, c.max_hit_points - 3)
    hp_before, max_before = c.hit_points, c.max_hit_points
    mod = (c.abilities['Konstitution'] - 10) // 2
    roll = hit_die(c)

    def boom(*a):
        raise AssertionError('must not roll again')

    monkeypatch.setattr(random, 'randint', boom)
    c.level_up({'hp_roll': roll})
    gain = max(1, roll + mod)
    assert c.level == 2
    assert c.max_hit_points == max_before + gain
    assert c.hit_points == hp_before + gain


def test_level_up_rolls_exactly_once_without_hp_roll(monkeypatch):
    c = make()
    calls = []

    def fake(a, b):
        calls.append((a, b))
        return 1

    monkeypatch.setattr(random, 'randint', fake)
    c.level_up({})
    assert len(calls) == 1


def test_invalid_choices_do_not_mutate():
    c = make()
    snapshot = c.to_dict()
    with pytest.raises(ValueError):
        c.level_up({'ability_increase': ['Unbekannt', 'Stärke']})
    with pytest.raises(ValueError):
        c.level_up({'new_spells': ['Nichtexistent']})
    assert c.to_dict() == snapshot


def test_level_cap():
    c = make()
    c.level = 20
    with pytest.raises(ValueError):
        c.level_up({})
    assert c.level == 20


def test_injured_character_roundtrip_and_recalculate_preserved():
    c = make()
    c.hit_points = max(0, c.max_hit_points - 2)
    c.inventory = [{'name': 'Seil'}]
    c.hit_dice = 0
    restored = Character.from_dict(c.to_dict())
    assert restored.character_id == c.character_id
    restored.initialize_character()  # second call must only recalculate
    restored.recalculate_derived()
    assert restored.hit_points == c.hit_points
    assert restored.max_hit_points == c.max_hit_points
    assert restored.hit_dice == 0
    assert restored.inventory == [{'name': 'Seil'}]


def test_fighting_style_and_half_elf_preserved_without_double_counting():
    c = make()
    before = c.abilities['Stärke']
    c.fighting_style = 'Defense'
    c.half_elf_bonuses = {'abilities': ['Stärke', 'Weisheit'], 'skills': ['Akrobatik']}
    c.recalculate_derived()
    assert c.abilities['Stärke'] == before + 1
    c2 = Character.from_dict(c.to_dict())
    c2.recalculate_derived()
    c2.recalculate_derived()
    assert c2.abilities['Stärke'] == before + 1
    assert c2.fighting_style == 'Defense'
    assert c2.half_elf_bonuses == c.half_elf_bonuses
    assert 'Akrobatik' in c2.proficiencies
    assert any('Defense' in f['name'] for f in c2.features)


def test_level_up_screen_reset_does_not_leak():
    pytest.importorskip('kivy')
    from ui.level_up_screen import LevelUpScreen
    s = LevelUpScreen()
    s.spell_choices = {'new_spells': ['X']}
    s.hp_roll = 4
    s.total_points_allocated = 2
    s.ability_scores_to_increase = {'Stärke': 2}
    s.reset_choices()
    assert s.spell_choices == {}
    assert s.hp_roll is None
    assert s.total_points_allocated == 0
    assert s.ability_scores_to_increase == {}
