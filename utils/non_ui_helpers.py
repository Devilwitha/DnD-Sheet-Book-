import random
import re

def parse_dice(dice_string):
    """Return (count, sides, modifier), including fixed damage such as '1'."""
    if not isinstance(dice_string, str) or len(dice_string) > 40:
        raise ValueError('Ungültiger Würfelausdruck.')
    text = dice_string.replace(' ', '').lower()
    if re.fullmatch(r'[+-]?\d{1,5}', text):
        value = int(text)
        if abs(value) <= 10000:
            return 0, 0, value
    match = re.fullmatch(r'(\d{0,3})[dw](\d{1,4})([+-]\d{1,5})?', text)
    if not match:
        raise ValueError('Würfel als 1d8+2 oder festen Wert eingeben.')
    count, sides = int(match[1] or 1), int(match[2])
    modifier = int(match[3] or 0)
    if not (1 <= count <= 100 and 1 <= sides <= 1000 and abs(modifier) <= 10000):
        raise ValueError('Würfelausdruck überschreitet die erlaubten Grenzen.')
    return count, sides, modifier


def roll_dice(dice_string):
    count, sides, modifier = parse_dice(dice_string)
    return sum(random.randint(1, sides) for _ in range(count)) + modifier
