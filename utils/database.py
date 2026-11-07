import sqlite3
import json
import os
import sys
import shutil

from pathlib import Path
from .build_database import create_database
from .paths import resource_path, user_data_dir
from .storage import atomic_write_bytes

SOURCE_DB = resource_path('utils/data/dnd.db')
DEST_DB = ''


def get_dest_db_path():
    return DEST_DB or str(Path(user_data_dir()) / 'dnd.db')


def setup_database():
    destination = Path(get_dest_db_path())
    if destination.is_file():
        return
    source = Path(SOURCE_DB)
    if source.is_file():
        atomic_write_bytes(destination, source.read_bytes())
    else:
        create_database(destination)


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    db_path = get_dest_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_data_from_db():
    """Fetches all data from the database and reconstructs the dictionaries."""
    conn = get_db_connection()
    try:
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
                'skill_choices': json.loads(row.get('skill_choices') or '{}'),
                'languages': json.loads(row.get('languages') or '[]'),
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
    finally:
        conn.close()
