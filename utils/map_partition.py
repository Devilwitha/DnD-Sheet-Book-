'''Teilung einfacher Polygone durch eine gezeichnete Schnittlinie (reine Geometrie).

split_boundary() liefert zwei einfache Polygone, die das Original exakt
ausfüllen. Die Originalgrenze wird nie vereinfacht; nur die Schnittlinie darf
bei Überschreitung des Punktlimits vereinfacht werden.
'''
import math

from utils.map_regions import (  # noqa: F401
    validate_boundary, boundary_contains, boundary_center, simplify_gesture,
    MAX_BOUNDARY_POINTS,
)

__all__ = ['split_boundary', 'boundary_area', 'MAX_LINE_POINTS']

MAX_LINE_POINTS = 256
_TOL = 1e-7
_MIN_PIECE_AREA = 0.25

_MSG_TOUCH = ('Die Linie berührt oder streift die Grenze nur (Ecke, Kante oder '
              'Tangente). Bitte die Grenze eindeutig überqueren.')
_MSG_SELF = 'Die Schnittlinie kreuzt oder berührt sich selbst.'


# ---------------------------------------------------------------- Hilfen
def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError('Koordinaten müssen Zahlen sein.')
    try:
        f = float(v)
    except OverflowError:
        raise ValueError('Koordinate ist ungültig.') from None
    if not math.isfinite(f):
        raise ValueError('Koordinate ist nicht endlich.')
    return f


def _same(a, b):
    return abs(a[0] - b[0]) <= _TOL and abs(a[1] - b[1]) <= _TOL


def _dedupe(pts):
    out = []
    for p in pts:
        if not out or not _same(out[-1], p):
            out.append(p)
    return out


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    ll = dx * dx + dy * dy
    t = 0.0 if ll == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ll))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _seg_touch(a, b, c, d):
    d1, d2 = _cross(a, b, c), _cross(a, b, d)
    d3, d4 = _cross(c, d, a), _cross(c, d, b)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return True
    return (_pt_seg(c, a, b) <= _TOL or _pt_seg(d, a, b) <= _TOL or
            _pt_seg(a, c, d) <= _TOL or _pt_seg(b, c, d) <= _TOL)


def _signed_area(pts):
    ox, oy = pts[0]
    s = 0.0
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        s += (p[0] - ox) * (q[1] - oy) - (q[0] - ox) * (p[1] - oy)
    return s / 2.0


def boundary_area(points):
    '''Absolute Fläche eines Polygons (Shoelace).'''
    pts = [(float(p[0]), float(p[1])) for p in points]
    if len(pts) < 3:
        return 0.0
    return abs(_signed_area(pts))


def _strictly_inside(P, x, y):
    if not boundary_contains(P, x, y):
        return False
    n = len(P)
    return all(_pt_seg((x, y), P[i], P[(i + 1) % n]) > _TOL for i in range(n))


def _is_fold(a, b, c):
    ux, uy, vx, vy = b[0] - a[0], b[1] - a[1], c[0] - b[0], c[1] - b[1]
    return (ux * vx + uy * vy < 0 and
            abs(ux * vy - uy * vx) <= 1e-9 * math.hypot(ux, uy) * math.hypot(vx, vy))


# ------------------------------------------------------------ Eingaben
def _prepare_line(line, cols, rows):
    if not isinstance(line, (list, tuple)):
        raise ValueError('Die Schnittlinie muss eine Liste von Punkten sein.')
    if len(line) < 2:
        raise ValueError('Die Schnittlinie braucht mindestens 2 Punkte.')
    if len(line) > MAX_LINE_POINTS:
        raise ValueError('Die Schnittlinie hat zu viele Punkte (maximal %d).' % MAX_LINE_POINTS)
    cols, rows = _num(cols), _num(rows)
    pts = []
    for p in line:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError('Jeder Punkt der Schnittlinie braucht genau x und y.')
        x, y = _num(p[0]), _num(p[1])
        if not (0 <= x <= cols and 0 <= y <= rows):
            raise ValueError('Die Schnittlinie liegt außerhalb der Karte.')
        pts.append((x, y))
    pts = _dedupe(pts)
    if len(pts) < 2:
        raise ValueError('Die Schnittlinie ist zu kurz.')
    return pts


def _snap_endpoint(P, pt, snap):
    '''Projiziert einen randnahen Endpunkt auf die nächste Kante (exakt auf Ecke, wenn nahe).'''
    n = len(P)
    best = None
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        d = _pt_seg(pt, a, b)
        if best is None or d < best[0]:
            best = (d, a, b)
    d, a, b = best
    if d > snap:
        return pt
    if d > _TOL and not boundary_contains(P, pt[0], pt[1]):
        return pt  # Außenpunkt: wird beim Kreuzen der Grenze abgeschnitten
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    q = (a[0] + t * dx, a[1] + t * dy)
    for v in (a, b):
        if math.hypot(q[0] - v[0], q[1] - v[1]) <= _TOL:
            return v
    return q


def _check_line_simple(L):
    K = len(L) - 1
    for i in range(K):
        a, b = L[i], L[i + 1]
        if i + 1 < K and _is_fold(a, b, L[i + 2]):
            raise ValueError(_MSG_SELF)
        for j in range(i + 2, K):
            if _seg_touch(a, b, L[j], L[j + 1]):
                raise ValueError(_MSG_SELF)


# --------------------------------------------------- Schnittpunkte
def _event(p, q, a, b):
    '''Beziehung Linienstück pq zu Kante ab: None, 'cross', 'p', 'q', 'pass' oder 'bad'.'''
    rx, ry = q[0] - p[0], q[1] - p[1]
    sx, sy = b[0] - a[0], b[1] - a[1]
    rl, sl = math.hypot(rx, ry), math.hypot(sx, sy)
    den = rx * sy - ry * sx
    if abs(den) <= 1e-12 * rl * sl:
        if (_pt_seg(p, a, b) <= _TOL or _pt_seg(q, a, b) <= _TOL or
                _pt_seg(a, p, q) <= _TOL or _pt_seg(b, p, q) <= _TOL):
            return ('bad', 0.0)
        return None
    qx, qy = a[0] - p[0], a[1] - p[1]
    t = (qx * sy - qy * sx) / den
    u = (qx * ry - qy * rx) / den
    et, eu = _TOL / rl, _TOL / sl
    if t < -et or t > 1 + et or u < -eu or u > 1 + eu:
        return None
    if t <= et:
        return ('p', t)
    if t >= 1 - et:
        return ('q', t)
    if u <= eu or u >= 1 - eu:
        return ('pass', t)
    return ('cross', t)


def _find_hits(P, L):
    """Boundary events; shared polygon/line vertices count once, tangencies fail."""
    n, K = len(P), len(L) - 1
    events = []
    for k in range(K):
        p, q = L[k], L[k + 1]
        for i in range(n):
            a, b = P[i], P[(i + 1) % n]
            event = _event(p, q, a, b)
            if event is None:
                continue
            tag, t = event
            if tag == 'bad':
                # Collinear edge following has no unambiguous two-sided cut.
                dx, dy = q[0] - p[0], q[1] - p[1]
                ll = dx * dx + dy * dy
                positions = sorted(((v[0]-p[0])*dx + (v[1]-p[1])*dy)/ll for v in (a,b))
                lo, hi = max(0.,positions[0]), min(1.,positions[1])
                if (hi-lo)*math.sqrt(ll) > _TOL:
                    raise ValueError(_MSG_TOUCH)
                # Single endpoint contact with a parallel edge: another edge
                # may form an ordinary crossing through this polygon corner.
                contacts = [v for v in (p,q,a,b) if _pt_seg(v,p,q)<=_TOL and _pt_seg(v,a,b)<=_TOL]
                if not contacts:
                    continue
                v=contacts[0]
                t=((v[0]-p[0])*dx + (v[1]-p[1])*dy)/ll
            t=max(0.,min(1.,t))
            events.append((k+t,(p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1]))))
    events.sort(key=lambda e:e[0])
    unique=[]
    for event in events:
        if not unique or abs(event[0]-unique[-1][0]) > 1e-6 or not _same(event[1],unique[-1][1]):
            unique.append(event)

    def point(position):
        i=min(K-1,int(position))
        t=position-i
        return (L[i][0]+t*(L[i+1][0]-L[i][0]), L[i][1]+t*(L[i+1][1]-L[i][1]))

    hits=[]
    for index,(position,pt) in enumerate(unique):
        if position <= 1e-8:
            kind='start'
        elif position >= K-1e-8:
            kind='end'
        else:
            before=(unique[index-1][0] if index else 0)+position
            after=position+(unique[index+1][0] if index+1<len(unique) else K)
            # Between consecutive events the line cannot cross a boundary.
            # The inside/outside change distinguishes crossings from tangency.
            if _strictly_inside(P,*point(before/2)) == _strictly_inside(P,*point(after/2)):
                raise ValueError(_MSG_TOUCH)
            kind='cross'
        hits.append((position,kind,min(K-1,int(position)),pt))
    return hits


def _trim(P, L):
    hits = _find_hits(P, L)
    if not hits:
        raise ValueError('Die Linie schneidet die Grenze nicht. Bitte quer über die Region ziehen.')
    if len(hits) == 1:
        raise ValueError('Die Linie muss die Grenze zweimal treffen. Anfang und Ende müssen '
                         'am Rand liegen oder außerhalb der Region.')
    if len(hits) > 2:
        raise ValueError('Die Linie kreuzt die Grenze mehrfach. Bitte nur einmal hinein '
                         'und einmal hinaus zeichnen.')
    (_, _, k1, h1), (_, _, k2, h2) = hits
    return _dedupe([h1] + list(L[k1 + 1:k2 + 1]) + [h2])


def _verify_cut(P, C):
    '''Getrimmte Linie: einfach, nur Endpunkte am Rand, sonst echt im Inneren.'''
    if len(C) < 2:
        raise ValueError('Die Schnittlinie ist zu kurz.')
    _check_line_simple(C)
    hits = _find_hits(P, C)
    if len(hits) != 2 or hits[0][1] != 'start' or hits[1][1] != 'end':
        raise ValueError('Die Linie kreuzt die Grenze mehrfach oder mehrdeutig.')
    mx, my = (C[0][0] + C[1][0]) / 2.0, (C[0][1] + C[1][1]) / 2.0
    if not _strictly_inside(P, mx, my):
        raise ValueError('Ein Teil der Linie zwischen den Schnittpunkten liegt außerhalb '
                         'der Region.')


# ---------------------------------------------------------- Ringbau
def _locate(P, pt):
    n = len(P)
    for i, v in enumerate(P):
        if math.hypot(pt[0] - v[0], pt[1] - v[1]) <= _TOL:
            return ('v', i, 0.0, v)
    best = None
    for i in range(n):
        d = _pt_seg(pt, P[i], P[(i + 1) % n])
        if best is None or d < best[0]:
            best = (d, i)
    d, i = best
    if d > 1e-6:
        raise ValueError('Schnittpunkt liegt nicht auf der Grenze.')
    a, b = P[i], P[(i + 1) % n]
    dx, dy = b[0] - a[0], b[1] - a[1]
    u = ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / (dx * dx + dy * dy)
    return ('e', i, u, pt)


def _plan(P, C):
    '''Fügt die zwei Schnittpunkte in den Originalring ein: (ring, index_a, index_b).'''
    if math.hypot(C[0][0] - C[-1][0], C[0][1] - C[-1][1]) <= _TOL:
        raise ValueError('Anfang und Ende der Schnittlinie fallen zusammen.')
    locs = (_locate(P, C[0]), _locate(P, C[-1]))
    ins = {}
    vtag = {}
    for tag, loc in enumerate(locs):
        if loc[0] == 'e':
            ins.setdefault(loc[1], []).append((loc[2], tag, loc[3]))
        else:
            vtag[loc[1]] = tag
    R, pos = [], [None, None]
    for i, v in enumerate(P):
        R.append(v)
        if i in vtag:
            pos[vtag[i]] = len(R) - 1
        for _u, tag, pt in sorted(ins.get(i, ())):
            R.append(pt)
            pos[tag] = len(R) - 1
    if pos[0] is None or pos[1] is None or pos[0] == pos[1]:
        raise ValueError('Schnittpunkte sind nicht eindeutig.')
    return R, pos[0], pos[1]


def _walk(R, a, b):
    m = len(R)
    out = [R[a]]
    i = a
    while i != b:
        i = (i + 1) % m
        out.append(R[i])
    return out


def _fit_cut(P, C, max_points):
    '''Verifiziert die Linie; vereinfacht nur sie, falls das Punktlimit sonst überschritten wird.'''
    _verify_cut(P, C)
    R, a, b = _plan(P, C)
    m = len(R)
    room = max_points - max((b - a) % m + 1, (a - b) % m + 1)
    if room < 0:
        raise ValueError('Die Teilung würde eine Region mit mehr als %d Punkten erzeugen.'
                         % max_points)
    if len(C) - 2 <= room:
        return C
    tol = .02
    for _ in range(40):
        S = [tuple(p) for p in simplify_gesture(C, tol)]
        if len(S) - 2 <= room and len(S) < len(C):
            try:
                _verify_cut(P, S)
                return S
            except ValueError:
                pass
        tol *= 1.6
    S = [C[0], C[-1]]
    if room >= 0:
        try:
            _verify_cut(P, S)
            return S
        except ValueError:
            pass
    raise ValueError('Die Schnittlinie hat zu viele Punkte für die Teilung.')


def _check_ring(pts):
    n = len(pts)
    if n < 3:
        raise ValueError('Ein Teil hat zu wenige Punkte.')
    for i in range(n):
        if _same(pts[i], pts[(i + 1) % n]):
            raise ValueError('Teilung erzeugt doppelte Punkte. Bitte anders schneiden.')
        if _is_fold(pts[i - 1], pts[i], pts[(i + 1) % n]):
            raise ValueError('Teilung erzeugt eine Spitze. Bitte anders schneiden.')
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _seg_touch(a, b, pts[j], pts[(j + 1) % n]):
                raise ValueError('Teilung erzeugt ein ungültiges Polygon. Bitte anders schneiden.')


def _assemble(P, C):
    R, a, b = _plan(P, C)
    inner = list(C[1:-1])
    A = _walk(R, a, b) + inner[::-1]
    B = _walk(R, b, a) + inner
    sp, sa, sb = _signed_area(P), _signed_area(A), _signed_area(B)
    if min(abs(sa), abs(sb)) < _MIN_PIECE_AREA:
        raise ValueError('Ein Teil wäre zu klein. Bitte weiter von Rand oder Ecken entfernt schneiden.')
    if (sa * sp <= 0 or sb * sp <= 0 or
            abs(abs(sa) + abs(sb) - abs(sp)) > 1e-7 * max(1.0, abs(sp))):
        raise ValueError('Die Teilung ist fehlgeschlagen. Bitte die Linie neu zeichnen.')
    _check_ring(A)
    _check_ring(B)
    return [[x, y] for x, y in A], [[x, y] for x, y in B]


# -------------------------------------------------------- Öffentlich
def split_boundary(boundary, line, cols, rows, snap=.7, *, max_points=MAX_BOUNDARY_POINTS):
    '''Teilt ein einfaches Polygon entlang einer gezeichneten Linie.

    Gibt (polygon_a, polygon_b) als Listen von [x, y] zurück. Beide behalten die
    Orientierung des Originals; a läuft von der ersten zur zweiten Schnittstelle
    entlang des Rings. Die Schnittlinie steht in a rückwärts, in b vorwärts.
    '''
    P = [tuple(p) for p in validate_boundary(boundary, cols, rows)]
    snap = _num(snap)
    if snap < 0:
        raise ValueError('Fangradius darf nicht negativ sein.')
    if isinstance(max_points, bool) or not isinstance(max_points, int) or max_points < 3:
        raise ValueError('Punktlimit ist ungültig.')
    L = _prepare_line(line, cols, rows)
    L[0] = _snap_endpoint(P, L[0], snap)
    L[-1] = _snap_endpoint(P, L[-1], snap)
    L = _dedupe(L)
    if len(L) < 2:
        raise ValueError('Die Schnittlinie ist zu kurz.')
    _check_line_simple(L)
    C = _trim(P, L)
    C = _fit_cut(P, C, max_points)
    return _assemble(P, C)
