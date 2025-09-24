from utils.database import get_data_from_db, init_db

# Set up the database (copy from bundle if needed) and load data
init_db()
_data = get_data_from_db()

ALIGNMENT_DATA = _data["ALIGNMENT_DATA"]
BACKGROUND_DATA = _data["BACKGROUND_DATA"]
CLASS_DATA = _data["CLASS_DATA"]
FIGHTING_STYLE_DATA = _data["FIGHTING_STYLE_DATA"]
RACE_DATA = _data["RACE_DATA"]
SKILL_LIST = _data["SKILL_LIST"]
SPELL_DATA = _data["SPELL_DATA"]
WEAPON_DATA = _data["WEAPON_DATA"]
ENEMY_DATA = _data["ENEMY_DATA"]

def load_test_data():
    """Overwrites global data with a minimal set for testing."""
    global RACE_DATA, CLASS_DATA, SPELL_DATA, WEAPON_DATA

    RACE_DATA = {
        "Mensch": {
            "ability_score_increase": {
                "Stärke": 1, "Geschicklichkeit": 1, "Konstitution": 1,
                "Intelligenz": 1, "Weisheit": 1, "Charisma": 1
            },
            "speed": 9
        },
        "Elf": {
            "ability_score_increase": {"Geschicklichkeit": 2},
            "speed": 9
        }
    }

    CLASS_DATA = {
        "Kämpfer": {
            "hit_die": 10,
            "progression": {
                1: {"spell_slots": {}},
                2: {"spell_slots": {}}
            }
        },
        "Magier": {
            "hit_die": 6,
            "progression": {
                1: {"spell_slots": {"1": 2}},
                2: {"spell_slots": {"1": 3}}
            }
        }
    }

    SPELL_DATA = {
        "Feuerstrahl": {"level": 0},
        "Magisches Geschoss": {"level": 1}
    }

    WEAPON_DATA = {
        "Unbewaffneter Schlag": {"damage": "1d4", "ability": "Stärke"},
        "Stab": {"damage": "1d6", "ability": "Stärke"}
    }
