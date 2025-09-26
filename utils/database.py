import sqlite3
import json
import os
import sys
import shutil

# This has to be a relative import for the build script to work standalone
# and for the main app to import it.
if __name__ != 'utils.database':
    from build_database import create_database
else:
    from .build_database import create_database


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

SOURCE_DB = resource_path(os.path.join('utils', 'data', 'dnd.db'))
DEST_DB = ""

def get_dest_db_path():
    """Gets the path to the writable database file."""
    global DEST_DB
    if DEST_DB:
        return DEST_DB
    try:
        from kivy.app import App
        app = App.get_running_app()
        user_data_path = app.user_data_dir
        if not os.path.exists(user_data_path):
            os.makedirs(user_data_path)
        DEST_DB = os.path.join(user_data_path, 'dnd.db')
        return DEST_DB
    except Exception:
        # Fallback for scripts/tests
        return SOURCE_DB

def setup_database():
    """
    Ensures the database is available.
    1. If the source DB is missing, build it from JSON.
    2. If the destination (writable) DB is missing, copy it from the source.
    """
    # 1. Check if the source DB exists, if not, build it.
    if not os.path.exists(SOURCE_DB):
        print(f"Source database not found at {SOURCE_DB}. Building from JSON files...")
        try:
            create_database()
            print("Source database built successfully.")
        except Exception as e:
            print(f"FATAL: Could not build source database: {e}")
            raise e # This is a fatal error

    # 2. Check if the destination DB exists, if not, copy it.
    dest_db_path = get_dest_db_path()
    if not os.path.exists(dest_db_path):
        print(f"Database not found at {dest_db_path}. Copying from source...")
        try:
            shutil.copy2(SOURCE_DB, dest_db_path)
            print("Database copied successfully.")
        except Exception as e:
            print(f"FATAL: Could not copy database from {SOURCE_DB} to {dest_db_path}: {e}")
            raise e

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    db_path = get_dest_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_data_from_db():
    """Fetches all data from the database and reconstructs the dictionaries."""
    conn = get_db_connection()
    cursor = conn.cursor()

    def fetch_all_as_dict(table_name, key_col, val_col=None):
        if val_col:
            cursor.execute(f"SELECT {key_col}, {val_col} FROM {table_name}")
            return {row[key_col]: row[val_col] for row in cursor.fetchall()}
        else:
            cursor.execute(f"SELECT * FROM {table_name}")
            return {row[key_col]: dict(row) for row in cursor.fetchall()}

    ALIGNMENT_DATA = fetch_all_as_dict('alignments', 'name', 'description')
    BACKGROUND_DATA = fetch_all_as_dict('backgrounds', 'name', 'description')
    SKILL_LIST = fetch_all_as_dict('skills', 'name', 'ability')
    FIGHTING_STYLE_DATA = fetch_all_as_dict('fighting_styles', 'name', 'description')

    WEAPON_DATA = {
        row['name']: {
            'damage': row.get('damage'), 'ability': row.get('ability'),
            'type': row.get('type'), 'range': row.get('range')
        } for row in fetch_all_as_dict('weapons', 'name').values()
    }
    SPELL_DATA = {
        row['name']: {
            'level': row.get('level'), 'school': row.get('school'), 'desc': row.get('desc')
        } for row in fetch_all_as_dict('spells', 'name').values()
    }

    RACE_DATA = {}
    for row in fetch_all_as_dict('races', 'name').values():
        RACE_DATA[row['name']] = {
            'speed': row.get('speed'),
            'ability_score_increase': json.loads(row.get('ability_score_increase') or '{}'),
            'languages': json.loads(row.get('languages') or '[]'),
            'proficiencies': json.loads(row.get('proficiencies') or '[]')
        }

    CLASS_DATA = {}
    for row in fetch_all_as_dict('classes', 'name').values():
        CLASS_DATA[row['name']] = {
            'hit_die': row.get('hit_die'),
            'proficiencies': json.loads(row.get('proficiencies') or '[]'),
            'progression': {int(k): v for k, v in json.loads(row.get('progression') or '{}').items()},
            'spell_list': {int(k): v for k, v in json.loads(row.get('spell_list') or '{}').items()},
            'features': {int(k): v for k, v in json.loads(row.get('features') or '{}').items()}
        }

    ENEMY_DATA = {}
    for row in fetch_all_as_dict('enemies', 'name').values():
        ENEMY_DATA[row['name']] = {
            'hp': row.get('hp'), 'ac': row.get('ac'), 'speed': row.get('speed'),
            'attacks': json.loads(row.get('attacks') or '[]')
        }

    return {
        "ALIGNMENT_DATA": ALIGNMENT_DATA, "BACKGROUND_DATA": BACKGROUND_DATA,
        "SKILL_LIST": SKILL_LIST, "FIGHTING_STYLE_DATA": FIGHTING_STYLE_DATA,
        "WEAPON_DATA": WEAPON_DATA, "SPELL_DATA": SPELL_DATA,
        "RACE_DATA": RACE_DATA, "CLASS_DATA": CLASS_DATA,
        "ENEMY_DATA": ENEMY_DATA
    }