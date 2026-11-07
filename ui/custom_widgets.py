from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line, StencilPush, StencilUse, StencilUnUse, StencilPop
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp
import math

class MapGridWidget(Widget):
    """
    A custom widget to display the game map efficiently using direct canvas drawing
    instead of creating thousands of individual Button widgets.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.map_data = None
        self.highlighted_tiles = []
        self.current_turn_pos = None
        self.selected_pos = None
        self._label_cache = {}
        self.tile_size = 32  # Default tile size in pixels
        self.register_event_type('on_tile_click')

    def on_tile_click(self, touch, row, col):
        """Custom event dispatched when a tile is clicked."""
        pass

    def set_data(self, map_data, highlighted_tiles, current_turn_pos, selected_pos=None):
        self.map_data = map_data
        self.highlighted_tiles = highlighted_tiles
        self.current_turn_pos = current_turn_pos
        self.selected_pos = selected_pos
        self.draw_map()

    def on_touch_down(self, touch):
        if self.disabled or getattr(touch, 'is_mouse_scrolling', False):
            return False
        tile = self.tile_at(*touch.pos)
        if tile is None:
            return False
        touch.ud[self] = (tile, touch.pos)
        touch.grab(self)
        return True

    def on_touch_move(self, touch):
        if self in touch.ud:
            tile, start = touch.ud[self]
            if math.dist(start, touch.pos) > dp(14):
                touch.ud[self] = (None, start)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self not in touch.ud:
            return super().on_touch_up(touch)
        tile, _ = touch.ud.pop(self)
        touch.ungrab(self)
        if not self.disabled and tile is not None and self.tile_at(*touch.pos) == tile:
            self.dispatch('on_tile_click', touch, *tile)
        return True

    def tile_at(self, x, y):
        if not self.map_data or self.tile_size <= 0 or not self.collide_point(x, y):
            return None
        col = math.floor((x - self.x) / self.tile_size)
        row = math.floor((self.top - y) / self.tile_size)
        return (row, col) if 0 <= row < self.map_data['rows'] and 0 <= col < self.map_data['cols'] else None

    def draw_map(self):
        self.canvas.clear()
        if not self.map_data:
            return

        rows = self.map_data.get('rows', 10)
        cols = self.map_data.get('cols', 10)

        # Adjust tile_size to fit the widget's bounds
        if cols > 0 and rows > 0:
            self.tile_size = min(self.width / cols, self.height / rows)
        else:
            self.tile_size = 32

        with self.canvas:
            StencilPush()
            Rectangle(pos=(self.x, self.top - rows * self.tile_size),
                      size=(cols * self.tile_size, rows * self.tile_size))
            StencilUse()
            artwork = self.map_data.get('artwork')
            if artwork:
                from ui.map_canvas import draw_artwork
                draw_artwork(artwork, self.x, self.top, self.tile_size, rows, cols, self._label_cache,
                             self.map_data.get('region_context'))
            # Draw tiles
            for r in range(rows):
                for c in range(cols):
                    pos = (r, c)
                    tile_data = self.map_data['tiles'].get(pos, {})

                    # Determine tile color
                    bg_color = [0.5, 0.5, 0.5, 1] # Default floor
                    if pos == self.current_turn_pos:
                        bg_color = [0.2, 0.6, 0.2, 1] # Green for current turn
                    elif pos in self.highlighted_tiles:
                        bg_color = [0.9, 0.9, 0.2, 1] # Yellow for movement range
                    elif tile_data.get('type') == 'Wall': bg_color = [0.2, 0.2, 0.2, 1]
                    elif tile_data.get('type') == 'Door': bg_color = [0.6, 0.3, 0.1, 1]
                    elif tile_data.get('type') == 'Trigger': bg_color = [1, 1, 0, 0.5]

                    Color(*bg_color)

                    draw_x = self.x + c * self.tile_size
                    draw_y = self.y + self.height - (r + 1) * self.tile_size
                    if (not artwork or pos == self.current_turn_pos or pos in self.highlighted_tiles
                            or tile_data.get('type') in ('Wall', 'Door', 'Trigger')):
                        Rectangle(pos=(draw_x, draw_y), size=(self.tile_size, self.tile_size))

                    # Draw object on tile
                    obj = tile_data.get('object')
                    if obj:
                        obj_color = [0.5, 1, 0.5, 1] # Default player color
                        if '#' in obj: # Crude check for enemy
                            obj_color = [1, 0.5, 0.5, 1]

                        Color(*obj_color)
                        Rectangle(pos=(draw_x + self.tile_size * 0.2, draw_y + self.tile_size * 0.2),
                                  size=(self.tile_size * 0.6, self.tile_size * 0.6))
                        if self.tile_size >= 22:
                            key = (obj, round(self.tile_size, 2))
                            texture = self._label_cache.get(key)
                            if texture is None:
                                if len(self._label_cache) > 512:
                                    self._label_cache.clear()
                                label = CoreLabel(text=obj[:7], font_size=min(dp(14), self.tile_size / 4), color=(0, 0, 0, 1))
                                label.refresh()
                                texture = self._label_cache[key] = label.texture
                            Color(1, 1, 1, 1)
                            Rectangle(texture=texture, pos=(draw_x + (self.tile_size - texture.width) / 2,
                                      draw_y + (self.tile_size - texture.height) / 2), size=texture.size)
                    elif tile_data.get('furniture'):
                        Color(0.65, 0.4, 0.15, 1)
                        Rectangle(pos=(draw_x + self.tile_size * 0.2, draw_y + self.tile_size * 0.2),
                                  size=(self.tile_size * 0.6, self.tile_size * 0.6))
                    if pos == self.selected_pos:
                        Color(.1, .65, 1, 1)
                        Line(rectangle=(draw_x + 2, draw_y + 2, self.tile_size - 4, self.tile_size - 4), width=dp(2))

            # Draw grid lines
            Color(0.1, 0.1, 0.1, 1)
            for r in range(rows + 1 if not artwork or artwork.get('grid') else 0):
                y = self.y + self.height - r * self.tile_size
                Line(points=[self.x, y, self.x + cols * self.tile_size, y], width=1)
            for c in range(cols + 1 if not artwork or artwork.get('grid') else 0):
                x = self.x + c * self.tile_size
                Line(points=[x, self.top - rows * self.tile_size, x, self.top], width=1)
            StencilUnUse()
            Rectangle(pos=(self.x, self.top - rows * self.tile_size),
                      size=(cols * self.tile_size, rows * self.tile_size))
            StencilPop()

    def on_size(self, *args):
        # Redraw map when widget size changes
        self.draw_map()

    def on_pos(self, *args):
        # Layout/tab/screen transitions change position without changing size.
        # Keep drawn tiles and their touch coordinates aligned.
        if hasattr(self, 'map_data'):
            self.draw_map()
