import pytest
from ui.map_editor_screen import MapEditorScreen
from core.character import Character
from kivy.app import App

class DummyApp(App):
    pass

def make_map_editor_with_players():
    app = DummyApp()
    screen = MapEditorScreen()
    screen.app = app
    screen.map_data = {
        'rows': 3,
        'cols': 3,
        'tiles': {(r, c): {'object': None, 'furniture': None} for r in range(3) for c in range(3)}
    }
    class DummyMapGrid:
        def __init__(self):
            self.children = []
        def clear_widgets(self): self.children.clear()
        def add_widget(self, w): self.children.append(w)
    class Ids:
        player_spinner = type('Dummy', (), {'text': 'None'})()
        enemy_spinner = type('Dummy', (), {'text': 'None'})()
        furniture_spinner = type('Dummy', (), {'text': 'None'})()
        tile_type_spinner = type('Dummy', (), {'text': 'None'})()
        map_grid = DummyMapGrid()
    screen.ids = Ids()
    return screen

def test_player_can_only_be_placed_once():
    screen = make_map_editor_with_players()
    player_name = 'TestPlayer'
    # Mock instance and touch
    class DummyInstance:
        def collide_point(self, *args):
            return True
    class DummyTouch:
        pos = (0, 0)
        button = 'left'
    instance = DummyInstance()
    touch = DummyTouch()
    # Patch create_styled_popup to avoid actual popup in test
    import ui.map_editor_screen as map_editor_mod
    called = {}
    def fake_popup(*args, **kwargs):
        called['popup'] = True
        class Dummy:
            def open(self): called['opened'] = True
        return Dummy()
    orig_popup = map_editor_mod.create_styled_popup
    map_editor_mod.create_styled_popup = fake_popup
    try:
        # Place player at (0,0)
        screen.ids.player_spinner.text = player_name
        screen.on_tile_touch_down(0, 0, instance, touch)
        assert screen.map_data['tiles'][(0,0)]['object'] == player_name
        # Try to place again at (1,1)
        screen.ids.player_spinner.text = player_name
        # Should not overwrite or place again
        screen.on_tile_touch_down(1, 1, instance, touch)
        # Player should still only be at (0,0)
        placed = [(r, c) for (r, c), v in screen.map_data['tiles'].items() if v['object'] == player_name]
        assert placed == [(0,0)]
        # Popup should have been called
        assert called.get('popup') and called.get('opened')
    finally:
        map_editor_mod.create_styled_popup = orig_popup
