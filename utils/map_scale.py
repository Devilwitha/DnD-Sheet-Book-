"""Physical cartographic extents, independent of combat rules and tile count."""
import math

KEY = 'cartography_scale'
DEFAULTS = {'world': (1000, 1000, 'km'), 'region': (100, 100, 'km'),
            'site': (1000, 1000, 'm'), 'interior': (30, 30, 'm')}


def validate_scale(value):
    if not isinstance(value, dict) or set(value) != {'width_m', 'height_m'}:
        raise ValueError('Maßstab braucht reale Breite und Höhe.')
    result = {}
    for key in ('width_m', 'height_m'):
        v = value[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not .01 <= v <= 1e9 or not math.isfinite(v):
            raise ValueError('Kartengröße muss zwischen 0,01 m und 1 Million km liegen.')
        result[key] = float(v)
    ratio = result['width_m'] / result['height_m']
    if not .02 <= ratio <= 50:
        raise ValueError('Breite und Höhe dürfen höchstens im Verhältnis 50:1 stehen.')
    return result


def parse_scale(width, height, unit):
    if unit not in ('m', 'km'):
        raise ValueError('Bitte Meter oder Kilometer wählen.')
    try:
        factor = 1000 if unit == 'km' else 1
        value = dict(width_m=float(width.strip().replace(',', '.')) * factor,
                     height_m=float(height.strip().replace(',', '.')) * factor)
    except (ValueError, OverflowError, TypeError, AttributeError):
        raise ValueError('Bitte gültige Breite und Höhe eingeben.') from None
    return validate_scale(value)


def display_values(scale):
    scale = validate_scale(scale)
    unit = 'km' if min(scale.values()) >= 1000 else 'm'
    factor = 1000 if unit == 'km' else 1
    return (f"{scale['width_m'] / factor:g}", f"{scale['height_m'] / factor:g}", unit)


def scale_title(map_data):
    if KEY not in map_data:
        return 'Maßstab festlegen …'
    w, h, unit = display_values(map_data[KEY])
    return f'{w} × {h} {unit}'


def suggested_scale(parent, boundary, level):
    if boundary and KEY in parent:
        xs, ys = zip(*boundary)
        value = dict(width_m=parent[KEY]['width_m'] * (max(xs) - min(xs)) / parent['cols'],
                     height_m=parent[KEY]['height_m'] * (max(ys) - min(ys)) / parent['rows'])
        try:
            return validate_scale(value)
        except ValueError:
            pass
    w, h, unit = DEFAULTS[level]
    return parse_scale(str(w), str(h), unit)


def grid_for_scale(scale):
    """A bounded drawing resolution, approximately matching the real aspect."""
    ratio = scale['width_m'] / scale['height_m']
    _, _, rows, cols = min((round(abs(math.log((c/r)/ratio)), 12), -r*c, r, c)
                           for r in range(1,51) for c in range(1,51))
    return rows, cols
