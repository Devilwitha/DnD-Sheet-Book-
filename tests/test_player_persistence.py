import os
import json
import tempfile
import shutil
import pytest
from core.character import Character
from core.game_manager import GameManager
from ui.dm_main_screen import DMMainScreen
from kivy.app import App

class DummyApp:
    def __init__(self):
        self.network_manager = None
        self.edited_map_data = None
        self.loaded_session_data = None
        self.prepared_session_data = None

@pytest.fixture
def dummy_dm_screen(monkeypatch):
    # Setup a DMMainScreen with dummy App and GameManager
    app = DummyApp()
    monkeypatch.setattr(App, 'get_running_app', lambda: app)
    screen = DMMainScreen()
    screen.app = app
    screen.game_manager = GameManager(logger_func=lambda x: None)
    return screen

def test_offline_players_save_and_load(tmp_path, dummy_dm_screen):
    # Erstelle Offline-Spieler
    char1 = Character('NPC1', 'Mensch', 'Krieger')
    char2 = Character('NPC2', 'Elf', 'Magier')
    dummy_dm_screen.game_manager.offline_players = [char1, char2]
    # Simuliere Speichern
    map_data = {'tiles': {}, 'enemies': [], 'offline_players': [c.to_dict() for c in dummy_dm_screen.game_manager.offline_players]}
    map_file = tmp_path / 'testmap.json'
    with open(map_file, 'w', encoding='utf-8') as f:
        json.dump(map_data, f)
    # Simuliere Laden
    with open(map_file, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    loaded_offline = [Character.from_dict(d) for d in loaded['offline_players']]
    assert loaded_offline[0].name == 'NPC1'
    assert loaded_offline[1].name == 'NPC2'

def test_online_players_save_and_load(tmp_path, dummy_dm_screen):
    # Erstelle Online-Spieler
    char1 = Character('Player1', 'Zwerg', 'Kleriker')
    dummy_dm_screen.game_manager.online_players = {'Player1': char1}
    # Simuliere Speichern
    session_data = {'online_players': [c.to_dict() for c in dummy_dm_screen.game_manager.online_players.values()]}
    session_file = tmp_path / 'testsession.json'
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(session_data, f)
    # Simuliere Laden
    with open(session_file, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    loaded_online = [Character.from_dict(d) for d in loaded['online_players']]
    assert loaded_online[0].name == 'Player1'

def test_offline_players_persist_after_restart(tmp_path, dummy_dm_screen):
    # Erstelle und speichere Offline-Spieler
    char1 = Character('NPC1', 'Mensch', 'Krieger')
    dummy_dm_screen.game_manager.offline_players = [char1]
    map_data = {'tiles': {}, 'enemies': [], 'offline_players': [c.to_dict() for c in dummy_dm_screen.game_manager.offline_players]}
    map_file = tmp_path / 'testmap.json'
    with open(map_file, 'w', encoding='utf-8') as f:
        json.dump(map_data, f)
    # Simuliere App-Neustart und erneutes Hosten
    with open(map_file, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    dummy_dm_screen.game_manager.offline_players = [Character.from_dict(d) for d in loaded['offline_players']]
    assert dummy_dm_screen.game_manager.offline_players[0].name == 'NPC1'
