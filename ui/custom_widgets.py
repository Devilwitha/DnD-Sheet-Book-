from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line
from kivy.uix.label import Label
from kivy.core.window import Window

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
        self.tile_size = 32  # Default tile size in pixels
        self.register_event_type('on_tile_click')

    def on_tile_click(self, touch, row, col):
        """Custom event dispatched when a tile is clicked."""
        pass

    def set_data(self, map_data, highlighted_tiles, current_turn_pos):
        self.map_data = map_data
        self.highlighted_tiles = highlighted_tiles
        self.current_turn_pos = current_turn_pos
        self.draw_map()

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False

        # Calculate clicked row and column
        col = int((touch.x - self.x) / self.tile_size)
        row = int((self.height - (touch.y - self.y)) / self.tile_size) # Y is inverted

        if self.map_data and 0 <= row < self.map_data['rows'] and 0 <= col < self.map_data['cols']:
            self.dispatch('on_tile_click', touch, row, col)
            return True
        return super().on_touch_down(touch)

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

            # Draw grid lines
            Color(0.1, 0.1, 0.1, 1)
            for r in range(rows + 1):
                y = self.y + self.height - r * self.tile_size
                Line(points=[self.x, y, self.x + self.width, y], width=1)
            for c in range(cols + 1):
                x = self.x + c * self.tile_size
                Line(points=[x, self.y, x, self.y + self.height], width=1)

    def on_size(self, *args):
        # Redraw map when widget size changes
        self.draw_map()
