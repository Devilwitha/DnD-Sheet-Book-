import pytest
from utils.non_ui_helpers import roll_dice


def test_roll_dice_basic():
    # Fixed format 1d1 should always return 1
    assert roll_dice('1d1') == 1


def test_roll_dice_with_modifier():
    # 1d1+2 should always return 3
    assert roll_dice('1d1+2') == 3


def test_roll_dice_multiple_dice():
    # 2d1+1 -> each die is 1, so total is 2 + 1 = 3
    assert roll_dice('2d1+1') == 3


def test_roll_dice_invalid_string():
    with pytest.raises(ValueError):
        roll_dice('not a dice')
