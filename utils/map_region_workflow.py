"""Resolve a drawn political border without a mandatory land-adoption step."""
import math
from utils.map_regions import (validate_boundary, simplify_gesture, boundary_contains,
                               _segments_touch)
from utils.map_partition import split_boundary, boundary_area


def land_areas(map_data):
    art = map_data['artwork']
    visible = {l['id'] for l in art['layers'] if l['visible']}
    result = []
    for el in art['elements']:
        if el['layer'] != 'terrain' or el['layer'] not in visible:
            continue
        pts = el['points']
        if el['kind'] == 'polygon':
            pts = simplify_gesture(pts, .03)
        elif el['kind'] == 'rect':
            (a,b),(c,d) = pts
            pts = [[a,b],[c,b],[c,d],[a,d]]
        elif el['kind'] == 'ellipse':
            (a,b),(c,d) = pts
            pts = [[(a+c)/2 + abs(a-c)/2*math.cos(i*math.tau/64),
                    (b+d)/2 + abs(b-d)/2*math.sin(i*math.tau/64)] for i in range(64)]
        else:
            continue
        try:
            result.append(validate_boundary(pts,map_data['cols'],map_data['rows']))
        except ValueError:
            # An unrelated malformed drawing must not block a valid island.
            continue
    return result


def boundaries_touch_or_overlap(a,b):
    return (any(boundary_contains(a,*p) for p in b) or any(boundary_contains(b,*p) for p in a)
            or any(_segments_touch(p,q,r,s) for p,q in zip(a,a[1:]+a[:1])
                   for r,s in zip(b,b[1:]+b[:1])))


def resolve_cut(record, line, snap):
    """Return (existing child ID or None, two parts, source ring), no mutation."""
    if len(line)<2:
        raise ValueError('Mindestens zwei Grenzpunkte setzen oder eine Linie ziehen.')
    candidates = [(p['child_id'], p['boundary']) for p in record['pins'] if p.get('boundary')]
    assigned = [ring for _,ring in candidates]
    lands = land_areas(record['map'])
    # A pond/rectangle wholly inside another land drawing is not a second
    # continent to split. The original artwork remains untouched.
    outer = [ring for ring in lands if not any(boundary_area(other)>boundary_area(ring)
             and all(boundary_contains(other,*p) for p in ring) for other in lands)]
    candidates += [(None,ring) for ring in outer if not any(boundaries_touch_or_overlap(ring,p) for p in assigned)]
    successes, errors = [], []
    cols,rows = record['map']['cols'],record['map']['rows']
    for child,ring in candidates:
        try:
            parts = split_boundary(ring,line,cols,rows,snap=snap)
            successes.append((child,parts,ring))
        except ValueError as exc:
            score = sum(boundary_contains(ring,*p) for p in line)
            errors.append((score,str(exc)))
    if len(successes)==1:
        return successes[0]
    if successes:
        raise ValueError('Diese Linie teilt mehrere Regionen oder Inseln. Bitte eine davon bis zur nächsten Grenze durchqueren.')
    if not candidates:
        raise ValueError('Keine teilbare Landfläche gefunden. Zuerst eine Landfläche zeichnen.')
    reason = max(errors,key=lambda e:e[0])[1] if errors else 'Die Linie trifft keinen Regionsrand.'
    raise ValueError(reason + ' Die Linie bleibt sichtbar: Punkte ergänzen oder „Linie verwerfen“ wählen.')
