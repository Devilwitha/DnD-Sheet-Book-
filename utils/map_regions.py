'''Reine Hilfsfunktionen für polygonale Kartenregionen (ohne Kivy/Storage/Netzwerk).'''
import math

MAX_BOUNDARY_POINTS = 128
_TOL = 1e-7
_MIN_AREA = 0.1


def _coord(v):
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


def _dist(px, py, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    ll = dx * dx + dy * dy
    t = 0.0 if ll == 0 else max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / ll))
    return math.hypot(px - a[0] - t * dx, py - a[1] - t * dy)


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _area2(pts):
    # doppelte vorzeichenbehaftete Fläche (Shoelace, relativ zum ersten Punkt)
    ox, oy = pts[0]
    s = 0.0
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        s += (p[0] - ox) * (q[1] - oy) - (q[0] - ox) * (p[1] - oy)
    return s


def _segments_touch(a, b, c, d):
    d1, d2 = _cross(a, b, c), _cross(a, b, d)
    d3, d4 = _cross(c, d, a), _cross(c, d, b)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return True
    return any(_dist(p[0], p[1], s, t) <= _TOL
               for p, s, t in ((c, a, b), (d, a, b), (a, c, d), (b, c, d)))


def validate_boundary(points, cols=100, rows=100):
    '''Prüft ein einfaches Polygon und gibt normalisierte [[x, y], ...] zurück.'''
    cols, rows = _coord(cols), _coord(rows)
    if cols <= 0 or rows <= 0:
        raise ValueError('Kartengröße ist ungültig.')
    if not isinstance(points, (list, tuple)):
        raise ValueError('Grenze muss eine Liste von Punkten sein.')
    if not 3 <= len(points) <= MAX_BOUNDARY_POINTS:
        raise ValueError('Grenze braucht 3 bis %d Punkte.' % MAX_BOUNDARY_POINTS)
    pts = []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError('Jeder Punkt braucht genau x und y.')
        x, y = _coord(p[0]), _coord(p[1])
        if not (0 <= x <= cols and 0 <= y <= rows):
            raise ValueError('Punkt liegt außerhalb der Karte.')
        pts.append((x, y))
    out = []
    for p in pts:
        if not out or not _same(out[-1], p):
            out.append(p)
    while len(out) > 1 and _same(out[0], out[-1]):
        out.pop()  # Schlusspunkt entfernen
    n = len(out)
    if n < 3:
        raise ValueError('Grenze hat zu wenige verschiedene Punkte.')
    if abs(_area2(out)) / 2.0 < _MIN_AREA:
        raise ValueError('Fläche ist zu klein.')
    # Benachbarte Kanten dürfen nicht auf sich selbst zurückfalten (Spitze)
    for i in range(n):
        a, b, c = out[i - 1], out[i], out[(i + 1) % n]
        ux, uy, vx, vy = b[0] - a[0], b[1] - a[1], c[0] - b[0], c[1] - b[1]
        if (ux * vx + uy * vy < 0 and
                abs(ux * vy - uy * vx) <= 1e-9 * math.hypot(ux, uy) * math.hypot(vx, vy)):
            raise ValueError('Grenze kehrt auf sich selbst zurück.')
    # Nicht benachbarte Kanten dürfen sich weder schneiden noch berühren
    for i in range(n):
        a, b = out[i], out[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue  # benachbart (inkl. Schlusskante)
            if _segments_touch(a, b, out[j], out[(j + 1) % n]):
                raise ValueError('Grenze überschneidet oder berührt sich selbst.')
    return [[x, y] for x, y in out]


def boundary_contains(points, x, y):
    '''True, wenn (x, y) im Polygon oder auf dessen Rand liegt.'''
    try:
        x, y = _coord(x), _coord(y)
        pts = [(float(p[0]), float(p[1])) for p in points]
    except (ValueError, TypeError, IndexError, OverflowError):
        return False
    n = len(pts)
    if n < 3:
        return False
    for i in range(n):
        if _dist(x, y, pts[i], pts[(i + 1) % n]) <= _TOL:
            return True
    inside = False
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def boundary_center(points):
    '''Innenliegender Markerpunkt, auch bei konkaven Küsten ohne Randkollision.'''
    pts = [(float(p[0]), float(p[1])) for p in points]
    if not pts:
        raise ValueError('Grenze ist leer.')
    ox, oy = pts[0]
    fallback = [ox, oy]
    a = cx = cy = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i][0] - ox, pts[i][1] - oy
        x2, y2 = pts[(i + 1) % len(pts)][0] - ox, pts[(i + 1) % len(pts)][1] - oy
        c = x1 * y2 - x2 * y1
        a += c
        cx += (x1 + x2) * c
        cy += (y1 + y2) * c
    if abs(a) < 1e-12:
        return fallback
    center = [ox + cx / (3.0 * a), oy + cy / (3.0 * a)]
    if (all(math.isfinite(v) for v in center) and boundary_contains(pts, *center)
            and all(_dist(*center, pts[i], pts[(i+1)%len(pts)]) > _TOL for i in range(len(pts)))):
        return center
    ys = sorted(set(p[1] for p in pts))
    best = (0, fallback)
    for low, high in zip(ys, ys[1:]):
        y = (low + high) / 2
        xs = sorted(p[0] + (y-p[1])*(q[0]-p[0])/(q[1]-p[1])
                    for p,q in zip(pts,pts[1:]+pts[:1]) if (p[1]>y) != (q[1]>y))
        for left,right in zip(xs[::2],xs[1::2]):
            if right-left > best[0]:
                best = (right-left, [(left+right)/2,y])
    return best[1]


def simplify_gesture(points, tolerance=.08):
    """Reduce a locally drawn outline before strict storage validation.

    Incoming atlas files still go directly through validate_boundary. Iterative
    RDP preserves bends and bounds memory; it does not accept crossed outlines.
    """
    if len(points) < 3:
        return points
    tolerance = max(.01, tolerance)
    while True:
        keep = {0, len(points) - 1}
        pending = [(0, len(points) - 1)]
        while pending:
            start, end = pending.pop()
            if end <= start + 1:
                continue
            index = max(range(start + 1, end),
                        key=lambda i: _dist(*points[i], points[start], points[end]))
            if _dist(*points[index], points[start], points[end]) > tolerance:
                keep.add(index)
                pending.extend(((start, index), (index, end)))
        out = [points[i] for i in sorted(keep)]
        if len(out) <= MAX_BOUNDARY_POINTS:
            return out
        tolerance *= 1.5
