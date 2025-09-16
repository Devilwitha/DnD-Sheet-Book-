import random
import re

def roll_dice(dice_string):
    """
    Rolls dice based on a string like '1d8+2' or '2d6-1'.
    Returns the integer result of the roll.
    """
    if not isinstance(dice_string, str):
        return 0

    match = re.match(r"(\d*)d(\d+)([+-]\d+)?", dice_string.replace(' ', ''))
    if not match:
        raise ValueError(f"Invalid dice string format: {dice_string}")

    num_dice_str = match.group(1)
    num_dice = int(num_dice_str) if num_dice_str else 1
    dice_type = int(match.group(2))
    modifier_str = match.group(3)

    modifier = 0
    if modifier_str:
        modifier = int(modifier_str)

    total = sum(random.randint(1, dice_type) for _ in range(num_dice)) + modifier
    return total
