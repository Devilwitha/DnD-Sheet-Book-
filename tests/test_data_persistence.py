import os
import json
import shutil
import tempfile
import pytest
from utils.helpers import get_user_saves_dir
from core.character import Character
from core.enemy import Enemy

@pytest.mark.parametrize("folder,filename,content,from_dict,to_dict,ext", [
    ("characters", "testchar.char", Character("Test", "Mensch", "Krieger"), Character.from_dict, Character.to_dict, ".char"),
    ("enemies", "testenemy.enemies", Enemy(name="Goblin", hp=10, armor_class=12, attacks=[]), Enemy.from_dict, Enemy.to_dict, ".enemies"),
    ("maps", "testmap.json", {"tiles": {"(0,0)": {"type": "Floor"}}, "enemies": [], "offline_players": []}, None, None, ".json"),
    ("sessions", "testsession.json", {"map_data": {}, "enemies": [], "offline_players": [], "online_players": []}, None, None, ".json"),
])
def test_save_and_load(folder, filename, content, from_dict, to_dict, ext):
    saves_dir = get_user_saves_dir(folder)
    file_path = os.path.join(saves_dir, filename)
    # Clean up before
    if os.path.exists(file_path):
        os.remove(file_path)
    # Save
    if to_dict:
        data = [to_dict(content)] if folder != "characters" else to_dict(content)
    else:
        data = content
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    assert os.path.exists(file_path)
    # Load
    with open(file_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    # Check content
    if to_dict and from_dict:
        if folder != "characters":
            loaded_obj = from_dict(loaded[0])
            assert to_dict(loaded_obj) == to_dict(content)
        else:
            loaded_obj = from_dict(loaded)
            assert to_dict(loaded_obj) == to_dict(content)
    else:
        assert loaded == content
    # Clean up after
    os.remove(file_path)
