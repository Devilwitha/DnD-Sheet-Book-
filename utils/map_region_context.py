"""A bounded world-artwork snapshot beneath independently editable region details."""
import math

KEY = 'region_context'


def validate_context(value, rows, cols):
    from utils.map_document import validate_artwork
    from utils.map_regions import validate_boundary
    if not isinstance(value, dict) or set(value) != {'version', 'rows', 'cols', 'artwork', 'boundary', 'frame'}:
        raise ValueError('Regionsgrundlage: ungültige Felder.')
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Regionsgrundlage: unbekannte Version.')
    for key in ('rows', 'cols'):
        if type(value[key]) is not int or not 1 <= value[key] <= 100:
            raise ValueError('Regionsgrundlage: ungültige Kartengröße.')
    frame = value['frame']
    if not isinstance(frame, (list, tuple)) or len(frame) != 3:
        raise ValueError('Regionsgrundlage: ungültiger Ausschnitt.')
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in frame):
        raise ValueError('Regionsgrundlage: ungültige Koordinate.')
    ox, oy, step = map(float, frame)
    if not (-10000 <= ox <= 100 and -10000 <= oy <= 100 and .000001 <= step <= 100):
        raise ValueError('Regionsgrundlage: Ausschnitt außerhalb der Grenzen.')
    boundary = validate_boundary(value['boundary'], value['cols'], value['rows'])
    # A cut may shrink a region with authored details; retain its original frame.
    # The region must still intersect the displayed map; allow clipped edges.
    xs, ys = zip(*boundary)
    if max(xs) < ox or min(xs) > ox + cols * step or max(ys) < oy or min(ys) > oy + rows * step:
        raise ValueError('Regionsgrundlage liegt außerhalb der Detailkarte.')
    artwork = validate_artwork(value['artwork'])
    if any(x > value['cols'] or y > value['rows'] for e in artwork['elements'] for x, y in e['points']):
        raise ValueError('Regionsgrundlage: Zeichnung außerhalb der Weltkarte.')
    return dict(version=1, rows=value['rows'], cols=value['cols'], artwork=artwork,
                boundary=boundary, frame=[ox, oy, step])


def has_details(record):
    data = record['map']
    return bool(record['pins'] or data['artwork']['elements'] or any(
        t.get('type', 'Floor') != 'Floor' or any(t.get(k) for k in ('object', 'furniture', 'trigger_message'))
        for t in data['tiles'].values()))


def refresh_region(atlas, key):
    """Update derived context only. Never copy into or replace authored artwork."""
    record = atlas.maps[key]
    parent = atlas.maps.get(record['parent_id'])
    if record['level'] != 'region' or not parent or parent['level'] != 'world':
        return False
    pin = next((p for p in parent['pins'] if p['child_id'] == key), None)
    data = record['map']
    if not pin or not pin.get('boundary'):
        return data.pop(KEY, None) is not None
    source = parent['map']
    xs, ys = zip(*pin['boundary'])
    # Pad to the existing canvas aspect; one uniform transform preserves shapes.
    step = max((max(xs)-min(xs))/data['cols'], (max(ys)-min(ys))/data['rows']) * 1.06
    frame = [(min(xs)+max(xs)-data['cols']*step)/2,
             (min(ys)+max(ys)-data['rows']*step)/2, step]
    previous = data.get(KEY)
    detailed = has_details(record)
    if previous and detailed:
        frame = previous['frame']  # Do not move authored labels/POIs when splitting.
    context = validate_context(dict(version=1, rows=source['rows'], cols=source['cols'],
        artwork=source['artwork'], boundary=pin['boundary'], frame=frame), data['rows'], data['cols'])
    changed = context != previous
    data[KEY] = context
    # Empty legacy maps had a 100 x 100 km placeholder. Their true extent is
    # the parent crop, including padding. Authored maps retain their chosen scale.
    from utils.map_scale import KEY as SCALE, validate_scale
    placeholder = data.get(SCALE) in (None, {'width_m': 100000., 'height_m': 100000.})
    if previous is None and not detailed and placeholder and SCALE in source:
        scale = dict(width_m=source[SCALE]['width_m'] / source['cols'] * frame[2] * data['cols'],
                     height_m=source[SCALE]['height_m'] / source['rows'] * frame[2] * data['rows'])
        try:
            scale = validate_scale(scale)
        except ValueError:
            pass  # Extreme tiny crops still retain their valid existing scale.
        else:
            changed = changed or data.get(SCALE) != scale
            data[SCALE] = scale
    return changed


def public_context(context, rows, cols):
    from utils.map_document import public_artwork
    result = validate_context(context, rows, cols)
    result['artwork'] = public_artwork(result['artwork'])
    return result
