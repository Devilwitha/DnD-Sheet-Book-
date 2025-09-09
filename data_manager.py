from database import get_data_from_db, init_db

# Initialize the database if it doesn't exist
init_db()

# Load all data into memory
_data = get_data_from_db()

ALIGNMENT_DATA = _data["ALIGNMENT_DATA"]
BACKGROUND_DATA = _data["BACKGROUND_DATA"]
CLASS_DATA = _data["CLASS_DATA"]
FIGHTING_STYLE_DATA = _data["FIGHTING_STYLE_DATA"]
RACE_DATA = _data["RACE_DATA"]
SKILL_LIST = _data["SKILL_LIST"]
SPELL_DATA = _data["SPELL_DATA"]
WEAPON_DATA = _data["WEAPON_DATA"]
