import math

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import (Canvas, Color, Ellipse, Line, Rectangle, Triangle, Mesh,
                           StencilPush, StencilUse, StencilUnUse, StencilPop)
from kivy.logger import Logger
from kivy.properties import ObjectProperty
from kivy.uix.stencilview import StencilView

from utils.map_document import color_tuple, new_artwork

_ORDER = ('terrain', 'objects', 'labels')
_LABELS = {}
_MAX_CACHE = 256

def _col(v, default=(1, 1, 1, 1)):
    try:
        return tuple(color_tuple(v))
    except Exception:
        return default


def _tex(cache, text, fs):
    # Bounded CoreLabel texture cache (white text, tinted by Color when drawn).
    if cache is None:
        cache = _LABELS
    key = ('artwork', text, fs)
    t = cache.get(key)
    if t is None:
        try:
            lab = CoreLabel(text=text, font_size=fs)
            lab.refresh()
            t = lab.texture
        except Exception:
            return None
        if t is None:
            return None
        while len(cache) >= _MAX_CACHE:
            cache.pop(next(iter(cache)))
        cache[key] = t
    return t


def _rc(c, x, y, w, h):
    Color(*c)
    Rectangle(pos=(x, y), size=(w, h))


def _symbol(name, cx, cy, s, col):
    n = str(name or '').lower().replace('ö', 'oe')
    h = s / 2.0
    lw = 1.2
    if n == 'baum':
        _rc((.4, .26, .13, 1), cx - s * .07, cy - h, s * .14, s * .45)
        g = (cx - s * .36, cy - h + s * .25, s * .72, s * .72)
        Color(.15, .55, .2, 1)
        Ellipse(pos=g[:2], size=g[2:])
        Color(*col)
        Line(ellipse=g, width=lw)
    elif n == 'berg':
        yb = cy - h * .7
        Color(.4, .4, .45, 1)
        Triangle(points=(cx, yb, cx + h, yb, cx + h * .45, cy + h * .2))
        p = (cx - h * .9, yb, cx + h * .7, yb, cx - h * .1, cy + h * .8)
        Color(.55, .55, .6, 1)
        Triangle(points=p)
        Color(1, 1, 1, 1)
        Triangle(points=(cx - h * .1, cy + h * .8, cx - h * .3, cy + h * .45, cx + h * .1, cy + h * .45))
        Color(*col)
        Line(points=p, close=True, width=lw)
    elif n == 'haus':
        _rc((.85, .78, .6, 1), cx - h * .6, cy - h * .7, h * 1.2, h * .9)
        Color(.7, .25, .2, 1)
        Triangle(points=(cx - h * .8, cy + h * .2, cx + h * .8, cy + h * .2, cx, cy + h * .9))
        _rc((.35, .22, .1, 1), cx - h * .12, cy - h * .7, h * .24, h * .5)
        Color(*col)
        Line(rectangle=(cx - h * .6, cy - h * .7, h * 1.2, h * .9), width=lw)
    elif n == 'hoehle':
        m = (cx - h * .9, cy - h * .6, h * 1.8, h * 1.5)
        Color(.45, .42, .4, 1)
        Ellipse(pos=m[:2], size=m[2:])
        Color(.05, .05, .07, 1)
        Ellipse(pos=(cx - h * .35, cy - h * .25), size=(h * .7, h * .7))
        Rectangle(pos=(cx - h * .35, cy - h * .6), size=(h * .7, h * .7))
        Color(*col)
        Line(ellipse=m, width=lw)
    elif n == 'felsen':
        for (ox, oy, ow, oh, g) in ((-.8, -.5, 1.0, .7, .55), (-.1, -.6, .9, .8, .45), (-.4, -.05, .8, .65, .65)):
            Color(g, g, g, 1)
            Ellipse(pos=(cx + h * ox, cy + h * oy), size=(h * ow, h * oh))
            Color(*col)
            Line(ellipse=(cx + h * ox, cy + h * oy, h * ow, h * oh), width=1)
    elif n == 'tisch':
        for lx in (-.8, .65):
            _rc((.3, .2, .1, 1), cx + h * lx, cy - h * .6, h * .15, h * .3)
        _rc((.55, .38, .2, 1), cx - h * .8, cy - h * .4, h * 1.6, h * .8)
        Color(*col)
        Line(rectangle=(cx - h * .8, cy - h * .4, h * 1.6, h * .8), width=lw)
    else:
        Color(*col)
        Ellipse(pos=(cx - h * .5, cy - h * .5), size=(h, h))


def _element(e, x, top, unit, cache):
    pts = [(x + float(p[0]) * unit, top - float(p[1]) * unit) for p in (e.get('points') or [])]
    if not pts:
        return
    col = _col(e.get('color'))
    try:
        w = float(e.get('width') or 0.2)
    except (TypeError, ValueError):
        w = 0.2
    d = max(1.0, w * unit)
    k = e.get('kind')
    px, py = pts[0]
    if k == 'stroke':
        Color(*col)
        if len(pts) == 1:
            Ellipse(pos=(px - d / 2, py - d / 2), size=(d, d))
        else:
            Line(points=[v for p in pts for v in p], width=d / 2, cap='round', joint='round')
    elif k == 'polygon' and len(pts) >= 3:
        from kivy.graphics.tesselator import Tesselator
        tess = Tesselator()
        flat = [v for p in pts for v in p]
        tess.add_contour(flat)
        if tess.tesselate():
            Color(*col)
            for vertices, indices in tess.meshes:
                Mesh(vertices=vertices, indices=indices, mode='triangle_fan')
        Color(col[0] * .82, col[1] * .82, col[2] * .82, 1)
        Line(points=flat, close=True, width=max(.7, unit * .04))
    elif k in ('rect', 'ellipse') and len(pts) >= 2:
        qx, qy = pts[1]
        bx, by, bw, bh = min(px, qx), min(py, qy), abs(qx - px), abs(qy - py)
        Color(*col)
        if k == 'rect':
            Rectangle(pos=(bx, by), size=(bw, bh))
        else:
            Ellipse(pos=(bx, by), size=(bw, bh))
    elif k == 'label':
        text = str(e.get('text') or '')
        if text:
            fs = int(max(8, min(96, unit * .6 * max(1.0, min(w, 4.0))))) // 2 * 2
            tex = _tex(cache, text, fs)
            if tex:
                Color(*col)
                Rectangle(texture=tex, pos=(px - tex.width / 2, py - tex.height / 2), size=tex.size)
    elif k == 'symbol':
        _symbol(e.get('symbol'), px, py, unit * max(1.0, min(w, 4.0)), col)
    elif k == 'asset':
        from ui.asset_render import draw_asset
        draw_asset(e, px, py, unit * w)


def _region_context(context, x, top, unit, rows, cols, cache):
    """Clip inherited artwork to the exact (possibly concave) political region."""
    from kivy.graphics.tesselator import Tesselator
    ox, oy, step = context['frame']
    world_unit = unit / step
    wx, wt = x - ox * world_unit, top + oy * world_unit
    flat = [v for px, py in context['boundary'] for v in (wx+px*world_unit, wt-py*world_unit)]
    tess = Tesselator()
    tess.add_contour(flat)
    if not tess.tesselate():
        return
    meshes = list(tess.meshes)
    def mask():
        for vertices, indices in meshes:
            Mesh(vertices=vertices, indices=indices, mode='triangle_fan')
    # Both stencil levels are balanced, also when nested in the editor/game view.
    StencilPush()
    Rectangle(pos=(x, top-rows*unit), size=(cols*unit, rows*unit))
    StencilUse()
    try:
        StencilPush()
        mask()
        StencilUse()
        try:
            draw_artwork(context['artwork'], wx, wt, world_unit, context['rows'], context['cols'], cache)
        finally:
            StencilUnUse()
            mask()
            StencilPop()
        Color(.22, .17, .12, 1)
        Line(points=flat, close=True, width=1.5)
    finally:
        StencilUnUse()
        Rectangle(pos=(x, top-rows*unit), size=(cols*unit, rows*unit))
        StencilPop()


def draw_artwork(artwork, x, top, unit, rows, cols, label_cache=None, region_context=None):
    '''Draw background and visible elements. Call inside a canvas context.
    Screen X = x + mx*unit, screen Y = top - my*unit. No tiles/grid drawn.'''
    art = artwork or {}
    Color(*((.16, .20, .22, 1) if region_context else _col(art.get('background') or '#1b1b1f', (.1, .1, .12, 1))))
    Rectangle(pos=(x, top - rows * unit), size=(cols * unit, rows * unit))
    if region_context:
        _region_context(region_context, x, top, unit, rows, cols, label_cache)
    vis = {}
    for lay in art.get('layers') or []:
        try:
            vis[lay.get('id')] = bool(lay.get('visible', True))
        except AttributeError:
            pass
    order = {layer['id']: i for i, layer in enumerate(art.get('layers') or [])}
    els = [e for e in (art.get('elements') or []) if isinstance(e, dict) and vis.get(e.get('layer'), True)]
    els.sort(key=lambda e: order.get(e.get('layer'), 0))
    for e in els:
        try:
            _element(e, x, top, unit, label_cache)
        except Exception:
            continue


def _bounds(e):
    pts = [(float(p[0]), float(p[1])) for p in (e.get('points') or [])]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    try:
        w = float(e.get('width') or 0.2)
    except (TypeError, ValueError):
        w = 0.2
    k = e.get('kind')
    if k == 'stroke':
        px = py = w / 2.0
    elif k == 'asset':
        angle = math.radians(e.get('rotation', 0))
        px = py = w / 2 * (abs(math.cos(angle)) + abs(math.sin(angle)))
    elif k == 'symbol':
        px = py = max(1.0, min(w, 4.0)) / 2.0 + .1
    elif k == 'label':
        px, py = max(.5, len(str(e.get('text') or '')) * .28), .4
    else:
        px = py = 0.05
    return min(xs) - px, min(ys) - py, max(xs) + px, max(ys) + py


class EditorCanvas(StencilView):
    controller = ObjectProperty(None, allownone=True)
    map_data = None
    zoom = 1.0
    pan_x = 0.0
    pan_y = 0.0
    pins = []
    MIN_ZOOM = 0.5
    MAX_ZOOM = 8.0

    def __init__(self, **kw):
        # attributes first: on_size/on_pos may fire during super().__init__
        self._trig = None
        self._touch = None
        self._mode = None
        self._labels = {}
        self._hover = None
        self.pins = []
        self._cv = Canvas()
        super().__init__(**kw)
        self.canvas.add(self._cv)  # own sub-canvas: stencil before/after stay untouched
        self._trig = Clock.create_trigger(self._redraw, -1)
        self.bind(size=self._geom_changed, pos=self._geom_changed)
        from kivy.core.window import Window
        Window.bind(mouse_pos=self._mouse_pos)
        self.refresh()

    def _mouse_pos(self, window, pos):
        ctrl = self.controller
        manager = getattr(ctrl, 'manager', None)
        if ctrl is None or (manager and manager.current != ctrl.name):
            return
        value = self.map_point(pos) if self.collide_point(*pos) else None
        if value != self._hover:
            self._hover = value
            self.refresh()

    # ---------- public API ----------
    def set_map(self, data, pins=None, reset_view=True):
        self._end()
        self._hover = None
        if isinstance(data, dict) and not data.get('artwork'):
            data['artwork'] = new_artwork('interior')
        self.map_data = data
        self.pins = list(pins or [])
        if reset_view:
            self.zoom = 1.0
            self.pan_x = self.pan_y = 0.0
        else:
            self._clamp_pan()
        self.refresh()

    def refresh(self):
        t = getattr(self, '_trig', None)
        if t is not None:
            t()

    def fit(self):
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0.0
        self.refresh()

    def zoom_by(self, factor, anchor=None):
        if not self._dims()[0]:
            return
        ax, ay = anchor if anchor else self.center
        x, top, u = self._geometry()
        mx, my = (ax - x) / u, (top - ay) / u
        nz = min(self.MAX_ZOOM, max(self.MIN_ZOOM, self.zoom * factor))
        if nz == self.zoom:
            return
        self.zoom = nz
        x2, t2, u2 = self._geometry()
        self.pan_x += ax - (x2 + mx * u2)
        self.pan_y += ay - (t2 - my * u2)
        self._clamp_pan()
        self.refresh()

    def map_point(self, pos):
        return self._to_map(pos, False)

    def _geometry(self):
        '''Shared projection: (x, top, unit); screen = (x+mx*unit, top-my*unit).'''
        r, c = self._dims()
        if not r:
            return self.x, self.top, 1.0
        w, h = max(1.0, self.width), max(1.0, self.height)
        unit = min(w / c, h / r) * self.zoom
        mw, mh = c * unit, r * unit
        return (self.x + (w - mw) / 2.0 + self.pan_x,
                self.y + (h + mh) / 2.0 + self.pan_y, unit)

    # ---------- internals ----------
    def _dims(self):
        try:
            return max(1, int(self.map_data['rows'])), max(1, int(self.map_data['cols']))
        except Exception:
            return 0, 0

    def _to_map(self, pos, clamp):
        r, c = self._dims()
        if not r:
            return None
        x, top, u = self._geometry()
        mx, my = (pos[0] - x) / u, (top - pos[1]) / u
        if clamp:
            return min(max(mx, 0.0), float(c)), min(max(my, 0.0), float(r))
        if 0 <= mx <= c and 0 <= my <= r:
            return mx, my
        return None

    def _clamp_pan(self):
        r, c = self._dims()
        if not r:
            self.pan_x = self.pan_y = 0.0
            return
        w, h = max(1.0, self.width), max(1.0, self.height)
        u = min(w / c, h / r) * self.zoom
        m = min(40.0, w / 4.0, h / 4.0)
        lx = max(0.0, (c * u + w) / 2.0 - m)
        ly = max(0.0, (r * u + h) / 2.0 - m)
        self.pan_x = min(lx, max(-lx, self.pan_x))
        self.pan_y = min(ly, max(-ly, self.pan_y))

    def _geom_changed(self, *a):
        self._clamp_pan()
        self.refresh()

    def _call(self, name, *args):
        f = getattr(self.controller, name, None)
        if not callable(f):
            return True
        try:
            f(*args)
            return True
        except Exception:
            Logger.exception('EditorCanvas: controller.%s failed' % name)
            return False

    def _end(self, touch=None):
        t = touch or self._touch
        self._touch = None
        self._mode = None
        if t is not None:
            try:
                t.ungrab(self)
            except Exception:
                pass

    # ---------- touch handling ----------
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        btn = getattr(touch, 'button', None)
        if getattr(touch, 'is_mouse_scrolling', False) or btn in ('scrollup', 'scrolldown'):
            if btn in ('scrollup', 'scrolldown'):
                # Kivy's mouse provider names forward wheel motion scrolldown.
                self.zoom_by(1.15 if btn == 'scrolldown' else 1 / 1.15, touch.pos)
            return True
        if self._touch is not None or self.map_data is None:
            return True
        ctrl = self.controller
        if btn == 'right':
            p = self.map_point(touch.pos)
            if p and ctrl is not None:
                self._call('canvas_context', p[0], p[1])
            return True
        hand = ctrl is not None and getattr(ctrl, 'tool', None) == 'hand'
        if btn == 'middle' or (hand and btn in (None, 'left')):
            mode = 'pan'
        elif btn in (None, 'left'):
            mode = 'paint'
        else:
            return True
        p = None
        if mode == 'paint':
            if ctrl is None:
                return True
            p = self.map_point(touch.pos)
            if p is None:
                return True
        self._touch, self._mode = touch, mode
        touch.grab(self)
        if mode == 'paint' and not self._call('canvas_down', p[0], p[1], touch):
            self._end(touch)
        return True

    def on_touch_move(self, touch):
        if touch is not self._touch:
            return False
        if touch.grab_current is not self:
            return True
        if self._mode == 'pan':
            self.pan_x += touch.dx
            self.pan_y += touch.dy
            self._clamp_pan()
            self.refresh()
        else:
            p = self._to_map(touch.pos, True)
            if p and not self._call('canvas_move', p[0], p[1], touch):
                self._end(touch)
        return True

    def on_touch_up(self, touch):
        if touch is not self._touch:
            return False
        if touch.grab_current is not self:
            return True
        mode = self._mode
        try:
            if mode == 'paint':
                p = self._to_map(touch.pos, True)
                if p:
                    self._call('canvas_up', p[0], p[1], touch)
        finally:
            self._end(touch)
        return True

    # ---------- drawing ----------
    def _view_range(self, x, top, u, r, c):
        r0 = max(0, int(math.floor((top - self.top) / u)))
        r1 = min(r, int(math.ceil((top - self.y) / u)))
        c0 = max(0, int(math.floor((self.x - x) / u)))
        c1 = min(c, int(math.ceil((self.right - x) / u)))
        return r0, r1, c0, c1

    def _redraw(self, *a):
        cv = self._cv
        cv.clear()
        d = self.map_data
        r, c = self._dims()
        with cv:
            Color(.07, .07, .09, 1)
            Rectangle(pos=self.pos, size=self.size)
            if not r:
                return
            x, top, u = self._geometry()
            art = d.get('artwork') or {}
            try:
                draw_artwork(art, x, top, u, r, c, self._labels, d.get('region_context'))
            except Exception:
                Logger.exception('EditorCanvas: artwork failed')
            for fn, args in ((self._tiles, (d, x, top, u, r, c)),
                             (self._grid, (art, x, top, u, r, c)),
                             (self._border, (x, top, u, r, c)),
                             (self._draw_pins, (x, top, u)),
                             (self._selection, (art, x, top, u)),
                             (self._preview, (x, top, u, r, c)),
                             (self._scale_bar, (u, c))):
                try:
                    fn(*args)
                except Exception:
                    Logger.exception('EditorCanvas: overlay failed')

    def _preview(self, x, top, u, rows, cols):
        if self._hover is None or self.controller is None:
            return
        mx, my = self._hover
        tool = self.controller.tool
        Color(.94, .97, .91, .9)
        if tool == 'tile' and 0 <= mx < cols and 0 <= my < rows:
            Line(rectangle=(x + math.floor(mx) * u, top - (math.floor(my) + 1) * u, u, u), width=1.3)
        elif tool == 'asset':
            from ui.asset_render import draw_asset
            ctrl = self.controller
            draw_asset({'asset_id': ctrl.asset_id, 'rotation': ctrl.asset_rotation,
                        'remove_white': ctrl.asset_remove_white},
                       x + mx * u, top - my * u, ctrl.asset_size * u, alpha=.55)
        elif tool in ('brush', 'eraser', 'symbol'):
            radius = max(3, self.controller.brush_width * u / 2)
            Line(circle=(x + mx * u, top - my * u, radius), width=1.1)

    def _border(self, x, top, u, r, c):
        Color(1, 1, 1, .5)
        Line(rectangle=(x, top - r * u, c * u, r * u), width=1)

    def _tiles(self, d, x, top, u, r, c):
        tiles = d.get('tiles') or {}
        r0, r1, c0, c1 = self._view_range(x, top, u, r, c)
        walls, doors, trigs, badges = [], [], [], []
        for rr in range(r0, r1):
            for cc in range(c0, c1):
                t = tiles.get((rr, cc))
                if not t:
                    continue
                px, py = x + cc * u, top - (rr + 1) * u
                k = t.get('type')
                if k == 'Wall':
                    walls.append((px, py))
                elif k == 'Door':
                    doors.append((px, py))
                elif k == 'Trigger':
                    trigs.append((px, py))
                if t.get('furniture') or t.get('object'):
                    badges.append((px, py, t.get('furniture'), t.get('object')))
        Color(.12, .12, .15, .92)
        for px, py in walls:
            Rectangle(pos=(px, py), size=(u, u))
        for px, py in doors:
            _rc((.55, .35, .15, .95), px + u * .1, py + u * .1, u * .8, u * .8)
            Color(.95, .8, .4, 1)
            Line(rectangle=(px + u * .1, py + u * .1, u * .8, u * .8), width=1)
        for px, py in trigs:
            _rc((.8, .2, .9, .35), px, py, u, u)
            Color(.9, .4, 1, .9)
            Line(rectangle=(px + u * .15, py + u * .15, u * .7, u * .7), width=1.2)
        if u < 12:
            return
        fs = max(8, int(u * .32) // 2 * 2)
        for px, py, f, o in badges:
            mimic = False
            if isinstance(f, dict):
                txt = str(f.get('type') or '')[:2]
                mimic = bool(f.get('is_mimic'))
            elif f:
                txt = str(f)[:2]
            else:
                txt = str(o or '')[:2]
            if not txt:
                continue
            bs = u * .55
            cx, cy = px + u / 2.0, py + u / 2.0
            _rc((.7, .1, .1, .85) if mimic else (.1, .1, .1, .8), cx - bs / 2, cy - bs / 2, bs, bs)
            tex = _tex(self._labels, txt, fs)
            if tex:
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, pos=(cx - tex.width / 2, cy - tex.height / 2), size=tex.size)

    def _grid(self, art, x, top, u, r, c):
        if not art.get('grid') or u < 4:
            return
        r0, r1, c0, c1 = self._view_range(x, top, u, r, c)
        Color(0, 0, 0, .28)
        for cc in range(c0, c1 + 1):
            Line(points=(x + cc * u, top - r0 * u, x + cc * u, top - r1 * u), width=1)
        for rr in range(r0, r1 + 1):
            Line(points=(x + c0 * u, top - rr * u, x + c1 * u, top - rr * u), width=1)

    @staticmethod
    def _pin_pos(p):
        # dict with x/y (map units) or row/col (tile) keys; sequence = (row, col) tile
        if isinstance(p, dict):
            if 'x' in p and 'y' in p:
                return float(p['x']), float(p['y'])
            for rk, ck in (('row', 'col'), ('r', 'c')):
                if rk in p and ck in p:
                    return float(p[ck]) + .5, float(p[rk]) + .5
            return None
        try:
            return float(p[1]) + .5, float(p[0]) + .5
        except Exception:
            return None

    def _pin_title(self, p):
        if isinstance(p, dict) and p.get('title'):
            return str(p['title'])
        for name in ('pin_title', 'child_title'):
            f = getattr(self.controller, name, None)
            if callable(f):
                try:
                    t = f(p)
                except Exception:
                    return ''
                return str(t) if t else ''
        return ''

    def _draw_pins(self, x, top, u):
        active = getattr(self.controller, 'tool', None) == 'region'
        atlas = getattr(self.controller, 'atlas', None)
        world = bool(atlas and atlas.current()['level'] == 'world')
        for pin in self.pins or []:
            boundary = pin.get('boundary') if isinstance(pin, dict) else None
            if boundary:
                self._draw_boundary(boundary, x, top, u, active, political=world)
        gesture = getattr(self.controller, '_gesture', None)
        if gesture and gesture.get('tool') == 'region':
            self._draw_boundary(gesture['area'], x, top, u, True, closed=not world)
        draft = getattr(self.controller, '_region_draft', [])
        if active and world and draft:
            self._draw_boundary(draft, x, top, u, True, closed=False)
            Color(1, .7, .1, 1)
            for px,py in draft:
                Ellipse(pos=(x+px*u-3,top-py*u-3),size=(6,6))
        for p in self.pins or []:
            pos = self._pin_pos(p)
            if not pos:
                continue
            px, py = x + pos[0] * u, top - pos[1] * u
            dd = max(10.0, min(28.0, u * .6))
            Color(1, .8, .1, 1)
            Ellipse(pos=(px - dd / 2, py - dd / 2), size=(dd, dd))
            Color(.3, .2, 0, 1)
            Line(circle=(px, py, dd / 2), width=1.2)
            title = self._pin_title(p)
            tex = _tex(self._labels, title[:24], 14) if title else None
            if tex:
                Color(0, 0, 0, .65)
                Rectangle(pos=(px - tex.width / 2 - 3, py + dd / 2 + 1), size=(tex.width + 6, tex.height + 2))
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, pos=(px - tex.width / 2, py + dd / 2 + 2), size=tex.size)

    @staticmethod
    def _draw_boundary(points, x, top, unit, active, closed=True, political=False):
        if len(points) < 2:
            return
        flat = [v for px, py in points for v in (x + px * unit, top - py * unit)]
        if active and closed and len(points) >= 3:
            from kivy.graphics.tesselator import Tesselator
            tess = Tesselator()
            tess.add_contour(flat)
            if tess.tesselate():
                Color(.15, .7, .9, .13)
                for vertices, indices in tess.meshes:
                    Mesh(vertices=vertices, indices=indices, mode='triangle_fan')
        if political:
            Color(.22, .17, .12, .95)
            Line(points=flat, close=closed and len(points) >= 3, width=1.5)
        else:
            Color(.3, .85, .96, .95 if active else .6)
            Line(points=flat, close=closed and len(points) >= 3, width=1.5 if active else 1, dash_length=6, dash_offset=3)

    def _scale_bar(self, unit, cols):
        scale = (self.map_data or {}).get('cartography_scale')
        if not scale or unit <= 0:
            return
        meters_per_pixel = scale['width_m'] / (cols * unit)
        target = min(120, self.width * .3) * meters_per_pixel
        power = 10 ** math.floor(math.log10(target))
        distance = max((v * power for v in (1, 2, 5, 10) if v * power <= target), default=power/10)
        length = distance / meters_per_pixel
        text = f'{distance / 1000:g} km' if distance >= 1000 else f'{distance:g} m'
        texture = _tex(self._labels, text, 12)
        xx, yy = self.x + 12, self.y + 14
        Color(.06,.08,.1,.85)
        Rectangle(pos=(xx-6,yy-8),size=(max(length,texture.width)+12,36))
        Color(1,1,1,1)
        Line(points=[xx,yy+4,xx,yy,xx+length,yy,xx+length,yy+4],width=1.2)
        Rectangle(texture=texture,pos=(xx,yy+7),size=texture.size)

    def _selection(self, art, x, top, u):
        sid = getattr(self.controller, 'selected_id', None)
        if not sid:
            return
        for e in art.get('elements') or []:
            if e.get('id') == sid:
                if not any(l['id'] == e['layer'] and l['visible'] for l in art['layers']):
                    return
                b = _bounds(e)
                if b:
                    Color(.2, .8, 1, 1)
                    Line(rectangle=(x + b[0] * u, top - b[3] * u, (b[2] - b[0]) * u, (b[3] - b[1]) * u),
                         width=1.5, dash_length=4, dash_offset=3)
                return
