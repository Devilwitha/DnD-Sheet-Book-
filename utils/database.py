import sqlite3
import json
import os
import sys
import shutil
from kivy.app import App

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# The source database, bundled with the app
SOURCE_DB = resource_path(os.path.join('utils', 'data', 'dnd.db'))
# The writable database, located in the user's data directory
DEST_DB = ""

def get_dest_db_path():
    """Gets the path to the writable database file."""
    global DEST_DB
    if DEST_DB:
        return DEST_DB

    try:
        app = App.get_running_app()
        user_data_path = app.user_data_dir
        if not os.path.exists(user_data_path):
            os.makedirs(user_data_path)
        DEST_DB = os.path.join(user_data_path, 'dnd.db')
        return DEST_DB
    except Exception:
        # Fallback for scripts/tests - use in-place DB
        return SOURCE_DB

def create_database_from_json():
    """Creates and populates the database from JSON files."""
    dest_db_path = get_dest_db_path()
    conn = sqlite3.connect(dest_db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''CREATE TABLE alignments (name TEXT, description TEXT)''')
    cursor.execute('''CREATE TABLE backgrounds (name TEXT, description TEXT)''')
    cursor.execute('''CREATE TABLE skills (name TEXT, ability TEXT)''')
    cursor.execute('''CREATE TABLE fighting_styles (name TEXT, description TEXT)''')
    cursor.execute('''CREATE TABLE weapons (name TEXT, damage TEXT, ability TEXT, type TEXT, range TEXT)''')
    cursor.execute('''CREATE TABLE spells (name TEXT, level INTEGER, school TEXT, description TEXT)''')
    cursor.execute('''CREATE TABLE races (name TEXT, speed INTEGER, ability_score_increase TEXT, languages TEXT, proficiencies TEXT)''')
    cursor.execute('''CREATE TABLE classes (name TEXT, hit_die TEXT, proficiencies TEXT, progression TEXT, spell_list TEXT, features TEXT)''')
    cursor.execute('''CREATE TABLE enemies (name TEXT, hp INTEGER, ac INTEGER, speed INTEGER, attacks TEXT)''')

    # Load and insert data from JSON files
    json_path = resource_path('utils/data/json_data')

    with open(os.path.join(json_path, 'alignments.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        for name, desc in data.items():
            cursor.execute("INSERT INTO alignments VALUES (?, ?)", (name, desc))

    with open(os.path.join(json_path, 'backgrounds.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        for name, desc in data.items():
            cursor.execute("INSERT INTO backgrounds VALUES (?, ?)", (name, desc))

    with open(os.path.join(json_path, 'skills.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        for name, ability in data.items():
            cursor.execute("INSERT INTO skills VALUES (?, ?)", (name, ability))

    with open(os.path.join(json_path, 'fighting_styles.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        for name, desc in data.items():
            cursor.execute("INSERT INTO fighting_styles VALUES (?, ?)", (name, desc))

    with open(os.path.join(json_path, 'weapons.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        for name, details in data.items():
            cursor.execute("INSERT INTO weapons VALUES (?, ?, ?, ?, ?)", (name, details.get('damage'), details.get('ability'), details.get('type'), details.get('range')))

    with open(os.path.join(json_path, 'spells_translated.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        for name, details in data.items():
            cursor.execute("INSERT INTO spells VALUES (?, ?, ?, ?)", (name, details['level'], details['school'], details['desc']))

    with open(os.path.join(json_path, 'races.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        for name, details in data.items():
            cursor.execute("INSERT INTO races VALUES (?, ?, ?, ?, ?)", (name, details.get('speed'), json.dumps(details.get('ability_score_increase', {})), json.dumps(details.get('languages', [])), json.dumps(details.get('proficiencies', []))))

    with open(os.path.join(json_path, 'classes.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        for name, details in data.items():
            cursor.execute("INSERT INTO classes VALUES (?, ?, ?, ?, ?, ?)", (name, details.get('hit_die'), json.dumps(details.get('proficiencies', [])), json.dumps(details.get('progression', {})), json.dumps(details.get('spell_list', {})), json.dumps(details.get('features', {}))))

    with open(os.path.join(json_path, 'enemies.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        for name, details in data.items():
            cursor.execute("INSERT INTO enemies VALUES (?, ?, ?, ?, ?)", (name, details.get('hp'), details.get('ac'), details.get('speed'), json.dumps(details.get('attacks', []))))

    conn.commit()
    conn.close()

def setup_database():
    """
    Ensures the database is in a writable location.
    If it doesn't exist in the user_data_dir, it's created from the JSON files.
    """
    dest_db_path = get_dest_db_path()
    if not os.path.exists(dest_db_path):
        print(f"Database not found at {dest_db_path}. Creating from JSON files...")
        try:
            create_database_from_json()
            print("Database created successfully.")
        except Exception as e:
            print(f"FATAL: Could not create database from JSON files: {e}")
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

    WEAPON_DATA = {row['name']: {'damage': row['damage'], 'ability': row['ability'], 'type': row['type'], 'range': row['range']} for row in fetch_all_as_dict('weapons', 'name').values()}
    SPELL_DATA = {row['name']: {'level': row['level'], 'school': row['school'], 'desc': row['description']} for row in fetch_all_as_dict('spells', 'name').values()}

    RACE_DATA = {}
    for row in fetch_all_as_dict('races', 'name').values():
        RACE_DATA[row['name']] = {
            'speed': row['speed'],
            'ability_score_increase': json.loads(row['ability_score_increase']),
            'languages': json.loads(row['languages']),
            'proficiencies': json.loads(row['proficiencies'])
        }

    CLASS_DATA = {}
    for row in fetch_all_as_dict('classes', 'name').values():
        CLASS_DATA[row['name']] = {
            'hit_die': row['hit_die'],
            'proficiencies': json.loads(row['proficiencies']),
            'progression': {int(k): v for k, v in json.loads(row['progression']).items()},
            'spell_list': {int(k): v for k, v in json.loads(row['spell_list']).items()},
            'features': {int(k): v for k, v in json.loads(row['features']).items()}
        }

    ENEMY_DATA = {}
    for row in fetch_all_as_dict('enemies', 'name').values():
        ENEMY_DATA[row['name']] = {
            'hp': row['hp'],
            'ac': row['ac'],
            'speed': row['speed'],
            'attacks': json.loads(row['attacks'])
        }

    return {
        "ALIGNMENT_DATA": ALIGNMENT_DATA,
        "BACKGROUND_DATA": BACKGROUND_DATA,
        "SKILL_LIST": SKILL_LIST,
        "FIGHTING_STYLE_DATA": FIGHTING_STYLE_DATA,
        "WEAPON_DATA": WEAPON_DATA,
        "SPELL_DATA": SPELL_DATA,
        "RACE_DATA": RACE_DATA,
        "CLASS_DATA": CLASS_DATA,
        "ENEMY_DATA": ENEMY_DATA
    }
