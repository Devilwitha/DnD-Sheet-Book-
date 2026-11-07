"""Offline sprites, bounded GPU previews and optional white-background display key.

Original image files remain unchanged. Only a 512 px display texture is retained;
the full-resolution JPEG is released after upload. Reload observers restore GPU
textures after Android suspends the graphics context.
"""
from collections import OrderedDict, deque
from functools import partial
from time import monotonic

from kivy.graphics import Color, Rectangle, PushMatrix, PopMatrix, Rotate
from kivy.logger import Logger
from utils.asset_catalog import asset_path

_CACHE = OrderedDict()
# 75 bundled pictures, with and without white key: at most 150 MiB. Covering
# all variants prevents maps with >24 motifs from decoding every image/frame.
_LIMIT = 150
_FAILED = OrderedDict()
_PENDING = deque()
_PUMP = None
_KEY_SHADER = '''$HEADER$
void main(void) {
    vec4 c = texture2D(texture0, tex_coord0);
    float paper = min(c.r, min(c.g, c.b));
    float a = 1.0 - smoothstep(0.94, 0.995, paper);
    vec3 rgb = clamp((c.rgb - vec3(1.0 - a)) / max(a, 0.001), 0.0, 1.0);
    gl_FragColor = vec4(rgb, c.a * a);
}
'''


def _reload(key, remove_white, texture):
    from kivy.core.image import Image
    from kivy.graphics import Fbo, ClearColor, ClearBuffers, Callback
    from kivy.graphics.opengl import GL_BLEND, glDisable, glEnable, glIsEnabled
    source = Image(asset_path(key), nocache=True)
    fbo = Fbo(size=texture.size, texture=texture, noadd=True)
    was_blending = glIsEnabled(GL_BLEND)
    try:
        if remove_white:
            fbo.shader.fs = _KEY_SHADER
            if not fbo.shader.success:
                raise ValueError('Asset-Darstellung wird von dieser Grafikhardware nicht unterstützt.')
        with fbo:
            ClearColor(0, 0, 0, 0)
            ClearBuffers()
            Callback(lambda *_: glDisable(GL_BLEND))
            Color(1, 1, 1, 1)
            Rectangle(texture=source.texture, pos=(0, 0), size=texture.size)
        fbo.draw()
    finally:
        glEnable(GL_BLEND) if was_blending else glDisable(GL_BLEND)
        fbo.clear()


def _queue_reload(key, white, texture):
    # Android may lose its GL context while suspended. Load at most one full
    # JPEG per frame to limit resume-time GPU allocations and catch file errors.
    global _PUMP
    from kivy.clock import Clock
    _PENDING.append((key, white, texture))
    if _PUMP is None:
        _PUMP = Clock.schedule_interval(_pump_reload, 0)


def _pump_reload(_dt):
    global _PUMP
    if _PENDING:
        key, white, texture = _PENDING.popleft()
        try:
            _reload(key, white, texture)
        except Exception:
            texture.blit_buffer(bytes(512 * 512 * 4), colorfmt='rgba', bufferfmt='ubyte')
            Logger.exception('Map asset: context reload failed: %s', key)
        from kivy.core.window import Window
        Window.canvas.ask_update()
    if not _PENDING:
        _PUMP = None
        return False
    return True


def preview_texture(key, remove_white=True):
    cache_key = (key, bool(remove_white))
    if cache_key in _CACHE:
        _CACHE.move_to_end(cache_key)
        return _CACHE[cache_key]
    if cache_key in _FAILED and monotonic() - _FAILED[cache_key] < 60:
        return None
    try:
        from kivy.graphics.texture import Texture
        texture = Texture.create(size=(512, 512), colorfmt='rgba')
        _reload(key, bool(remove_white), texture)
        texture.add_reload_observer(partial(_queue_reload, key, bool(remove_white)))
        _FAILED.pop(cache_key, None)
        _CACHE[cache_key] = texture
        while len(_CACHE) > _LIMIT:
            _CACHE.popitem(last=False)
        return texture
    except Exception:  # Kivy image decoders also raise plain Exception.
        _FAILED[cache_key] = monotonic()
        while len(_FAILED) > 300:
            _FAILED.popitem(last=False)
        Logger.exception('Map asset: image could not be loaded: %s', key)
        return None


def draw_asset(element, cx, cy, size, alpha=1):
    texture = preview_texture(element['asset_id'], element['remove_white'])
    PushMatrix()
    Rotate(angle=-element['rotation'], origin=(cx, cy))
    if texture is not None:
        Color(1, 1, 1, alpha)
        Rectangle(texture=texture, pos=(cx - size / 2, cy - size / 2), size=(size, size))
    else:
        from kivy.graphics import Line
        Color(.8, .3, .3, 1)
        Line(rectangle=(cx - size / 2, cy - size / 2, size, size), width=1.5)
        Line(points=(cx-size/2, cy-size/2, cx+size/2, cy+size/2), width=1.5)
    PopMatrix()
