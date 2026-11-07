import pytest
from utils.non_ui_helpers import parse_dice, roll_dice


def test_fixed_damage_and_dice(monkeypatch):
    monkeypatch.setattr('utils.non_ui_helpers.random.randint', lambda low, high: high)
    assert roll_dice('1') == 1  # SRD blowgun
    assert roll_dice('2d6-1') == 11
    assert roll_dice(' d8 + 2 ') == 10
    assert parse_dice('1w4') == (1, 4, 0)


@pytest.mark.parametrize('value', ['1d0', '0d6', '999d6', '1d9999', '1d6junk', '', None, '1d6+99999'])
def test_invalid_dice_are_rejected(value):
    with pytest.raises(ValueError):
        roll_dice(value)
