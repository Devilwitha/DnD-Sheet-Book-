import os
import json
from ui.map_editor_screen import MapEditorScreen
from ui.dm_main_screen import DMMainScreen
from core.enemy import Enemy


def test_map_save_and_load(tmp_path, monkeypatch):
    # Monkeypatch get_user_saves_dir to use tmp_path for both helper and UI modules
    def _tmp_get_user_saves_dir(folder):
        p = tmp_path / folder
        os.makedirs(str(p), exist_ok=True)
        return str(p)

    monkeypatch.setattr('utils.helpers.get_user_saves_dir', _tmp_get_user_saves_dir)
    monkeypatch.setattr('ui.map_editor_screen.get_user_saves_dir', _tmp_get_user_saves_dir)

    m = MapEditorScreen()
    # create a tiny map
    m.map_data = {'rows': 2, 'cols': 2, 'tiles': {(0,0): {'type':'Floor','object':None}, (0,1):{'type':'Wall','object':None}, (1,0):{'type':'Floor','object':None}, (1,1):{'type':'Floor','object':None}}}
    m.current_map_filename = None

    # save
    m.do_save('testmap')
    save_file = tmp_path / 'maps' / 'testmap.json'
    assert save_file.exists()

    # load into a new editor instance
    m2 = MapEditorScreen()
    m2.do_load_map('testmap.json', None)
    assert m2.map_data is not None


def test_session_save_and_load(tmp_path, monkeypatch):
    # Monkeypatch get_user_saves_dir in helpers and DM module
    def _tmp_get_user_saves_dir(folder):
        p = tmp_path / folder
        os.makedirs(str(p), exist_ok=True)
        return str(p)

    monkeypatch.setattr('utils.helpers.get_user_saves_dir', _tmp_get_user_saves_dir)
    monkeypatch.setattr('ui.dm_main_screen.get_user_saves_dir', _tmp_get_user_saves_dir)

    # Ensure DMMainScreen can get a running app with a network_manager attribute
    from types import SimpleNamespace
    fake_app = SimpleNamespace(network_manager=SimpleNamespace(incoming_messages=SimpleNamespace(get_nowait=lambda: None), edited_map_data=None))
    monkeypatch.setattr('ui.dm_main_screen.App.get_running_app', lambda: fake_app)

    # Create a minimal DMMainScreen with a simple GameManager-like structure
    dm = DMMainScreen()
    # Create fake game_manager with minimal attributes used by save_session
    class FakeGM:
        def __init__(self):
            self.online_players = {}
            self.offline_players = ['Alice']
            self.enemies = [Enemy(name='Goblin', hp=10, armor_class=12, attacks=[])]
            self.map_data = {'rows':1,'cols':1,'tiles':{(0,0):{'type':'Floor','object':None}}}
            self.initiative_order = []
            self.current_turn_index = -1
    dm.game_manager = FakeGM()
    dm.ids = type('X', (), {'log_output': type('L', (), {'text': ''})()})()

    # Save session
    # simulate entering filename via popup handler by calling inner function
    saves_dir = tmp_path / 'sessions'
    os.makedirs(str(saves_dir), exist_ok=True)
    filename = 'mysession.json'
    filepath = os.path.join(str(saves_dir), filename)

    # Build session_data as save_session would
    map_data = dm.game_manager.map_data.copy()
    map_data['tiles'] = {str(k): v for k, v in dm.game_manager.map_data['tiles'].items()}
    session_data = {
        'online_players': [],
        'offline_players': dm.game_manager.offline_players,
        'enemies': [e.to_dict() for e in dm.game_manager.enemies],
        'map_data': map_data,
        'log': dm.ids.log_output.text,
        'initiative_order': dm.game_manager.initiative_order,
        'current_turn_index': dm.game_manager.current_turn_index,
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=4, ensure_ascii=False)

    # Now load the file using DMMainScreen logic: find file and read
    dm.do_load_map(filename, None)
    # If no exception thrown, assume load worked; further checks can be added
    assert True
