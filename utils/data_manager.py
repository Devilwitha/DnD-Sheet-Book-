from utils.database import get_data_from_db, setup_database

# Initialize globals as empty dictionaries.
# They will be populated by the initialize_data function.
ALIGNMENT_DATA = {}
BACKGROUND_DATA = {}
CLASS_DATA = {}
FIGHTING_STYLE_DATA = {}
RACE_DATA = {}
SKILL_LIST = {}
SPELL_DATA = {}
WEAPON_DATA = {}
ENEMY_DATA = {}

def initialize_data():
    """
    Sets up the database if needed, fetches all data from the database,
    and populates the global data dictionaries in this module.
    This should be called once at application startup.
    """
    global ALIGNMENT_DATA, BACKGROUND_DATA, CLASS_DATA, FIGHTING_STYLE_DATA, \
           RACE_DATA, SKILL_LIST, SPELL_DATA, WEAPON_DATA, ENEMY_DATA

    # This ensures the writable DB exists and is copied if necessary.
    setup_database()

    # This fetches the data from the now-ready database.
    _data = get_data_from_db()

    # Populate the global dictionaries
    ALIGNMENT_DATA.update(_data["ALIGNMENT_DATA"])
    BACKGROUND_DATA.update(_data["BACKGROUND_DATA"])
    CLASS_DATA.update(_data["CLASS_DATA"])
    FIGHTING_STYLE_DATA.update(_data["FIGHTING_STYLE_DATA"])
    RACE_DATA.update(_data["RACE_DATA"])
    SKILL_LIST.update(_data["SKILL_LIST"])
    SPELL_DATA.update(_data["SPELL_DATA"])
    WEAPON_DATA.update(_data["WEAPON_DATA"])
    ENEMY_DATA.update(_data["ENEMY_DATA"])

def load_test_data():
    """
    This function is now deprecated for unit tests, which should use the
    full test database. It's kept for potential legacy use or specific
    integration tests but does nothing by default now.
    """
    pass