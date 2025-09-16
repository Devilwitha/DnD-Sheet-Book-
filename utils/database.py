import sqlite3
import json
import os
from utils.helpers import resource_path

# Build paths relative to this script's location for robustness
DATA_DIR = resource_path(os.path.join('utils', 'data', 'json_data'))
DATABASE_FILE = resource_path(os.path.join('utils', 'data', 'dnd.db'))

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables(conn):
    """Creates the necessary tables in the database if they don't exist."""
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS alignments (
        name TEXT PRIMARY KEY,
        description TEXT NOT NULL
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS backgrounds (
        name TEXT PRIMARY KEY,
        description TEXT NOT NULL
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS skills (
        name TEXT PRIMARY KEY,
        ability TEXT NOT NULL
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS fighting_styles (
        name TEXT PRIMARY KEY,
        description TEXT NOT NULL
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS weapons (
        name TEXT PRIMARY KEY,
        damage TEXT NOT NULL,
        ability TEXT NOT NULL,
        type TEXT,
        range INTEGER
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS spells (
        name TEXT PRIMARY KEY,
        level INTEGER NOT NULL,
        school TEXT NOT NULL,
        description TEXT NOT NULL
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS races (
        name TEXT PRIMARY KEY,
        speed REAL NOT NULL,
        ability_score_increase TEXT NOT NULL,
        languages TEXT NOT NULL,
        proficiencies TEXT NOT NULL
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS classes (
        name TEXT PRIMARY KEY,
        hit_die INTEGER NOT NULL,
        proficiencies TEXT NOT NULL,
        progression TEXT NOT NULL,
        spell_list TEXT,
        features TEXT NOT NULL
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS enemies (
        name TEXT PRIMARY KEY,
        hp INTEGER NOT NULL,
        ac INTEGER NOT NULL,
        speed REAL NOT NULL,
        attacks TEXT NOT NULL
    )''')

    conn.commit()

def populate_db_from_json(conn):
    """Populates the database from JSON files."""
    cursor = conn.cursor()

    def load_json(filename):
        with open(os.path.join(DATA_DIR, filename), 'r', encoding='utf-8') as f:
            return json.load(f)

    ALIGNMENT_DATA = load_json('alignments.json')
    BACKGROUND_DATA = load_json('backgrounds.json')
    SKILL_LIST = load_json('skills.json')
    FIGHTING_STYLE_DATA = load_json('fighting_styles.json')
    WEAPON_DATA = load_json('weapons.json')
    SPELL_DATA = load_json('spells_translated.json')
    RACE_DATA = load_json('races.json')
    CLASS_DATA = load_json('classes.json')
    ENEMY_DATA = load_json('enemies.json')

    cursor.executemany("INSERT INTO alignments (name, description) VALUES (?, ?)", ALIGNMENT_DATA.items())
    cursor.executemany("INSERT INTO backgrounds (name, description) VALUES (?, ?)", BACKGROUND_DATA.items())
    cursor.executemany("INSERT INTO skills (name, ability) VALUES (?, ?)", SKILL_LIST.items())
    cursor.executemany("INSERT INTO fighting_styles (name, description) VALUES (?, ?)", FIGHTING_STYLE_DATA.items())

    # Augment weapon data with type and range before inserting
    for name, data in WEAPON_DATA.items():
        if name in ["Glefe", "Hellebarde", "Lanze", "Pike", "Peitsche"]:
            data['type'] = "Melee"
            data['range'] = 2
        elif name in ["Leichte Armbrust", "Kurzbogen", "Schleuder", "Blasrohr", "Handarmbrust", "Schwere Armbrust", "Langbogen", "Wurfpfeil"]:
            data['type'] = "Ranged"
            # Setting some default ranges
            if name in ["Leichte Armbrust", "Kurzbogen"]: data['range'] = 20
            elif name in ["Schwere Armbrust"]: data['range'] = 25
            elif name in ["Langbogen"]: data['range'] = 30
            else: data['range'] = 15
        else: # Default to standard Melee
            data['type'] = "Melee"
            data['range'] = 1

    weapon_list = [(name, data['damage'], data['ability'], data['type'], data['range']) for name, data in WEAPON_DATA.items()]
    cursor.executemany("INSERT INTO weapons (name, damage, ability, type, range) VALUES (?, ?, ?, ?, ?)", weapon_list)

    spell_list = [(name, data['level'], data['school'], data['desc']) for name, data in SPELL_DATA.items()]
    cursor.executemany("INSERT INTO spells (name, level, school, description) VALUES (?, ?, ?, ?)", spell_list)

    race_list = [(name, data['speed'], json.dumps(data['ability_score_increase']), json.dumps(data['languages']), json.dumps(data['proficiencies'])) for name, data in RACE_DATA.items()]
    cursor.executemany("INSERT INTO races (name, speed, ability_score_increase, languages, proficiencies) VALUES (?, ?, ?, ?, ?)", race_list)

    class_list = [(name, data['hit_die'], json.dumps(data.get('proficiencies', [])), json.dumps(data.get('progression', {})), json.dumps(data.get('spell_list', {})), json.dumps(data.get('features', {}))) for name, data in CLASS_DATA.items()]
    cursor.executemany("INSERT INTO classes (name, hit_die, proficiencies, progression, spell_list, features) VALUES (?, ?, ?, ?, ?, ?)", class_list)

    enemy_list = [(name, data['hp'], data['ac'], data['speed'], json.dumps(data['attacks'])) for name, data in ENEMY_DATA.items()]
    cursor.executemany("INSERT INTO enemies (name, hp, ac, speed, attacks) VALUES (?, ?, ?, ?, ?)", enemy_list)

    conn.commit()

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

def init_db():
    """Initializes the database. Deletes the old one if it exists to ensure fresh data."""
    os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        # Delete the old database file to ensure it's rebuilt with corrected data sources.
        if os.path.exists(DATABASE_FILE):
            os.remove(DATABASE_FILE)
            print(f"Removed old database file: {DATABASE_FILE}")
    except OSError as e:
        print(f"Error removing database file: {e}")

    if not os.path.exists(DATABASE_FILE):
        conn = get_db_connection()
        create_tables(conn)
        populate_db_from_json(conn)
        conn.close()
        print("Database initialized and populated successfully from JSON files.")
