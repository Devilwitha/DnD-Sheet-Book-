import sqlite3
import json
import os
import tempfile
from pathlib import Path

try:
    from utils.paths import resource_path
except ModuleNotFoundError:
    from paths import resource_path

def create_database(db_path=None, json_dir=None):
    """
    Creates and populates the dnd.db from the JSON data files.
    This script will overwrite the existing database file.
    """
    db_path = Path(db_path or resource_path('utils/data/dnd.db')).resolve()
    json_dir = Path(json_dir or resource_path('utils/data/json_data')).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.database-', suffix='.tmp', dir=db_path.parent)
    os.close(fd)
    conn = None
    try:
        conn = sqlite3.connect(temporary)
        _populate_database(conn, json_dir)
        conn.commit()
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Datenbankprüfung fehlgeschlagen.')
        conn.close()
        conn = None
        with open(temporary, 'r+b') as built:
            os.fsync(built.fileno())
        os.replace(temporary, db_path)
    finally:
        if conn is not None:
            conn.close()
        if os.path.exists(temporary):
            os.unlink(temporary)
    return str(db_path)


def _populate_database(conn, json_dir):
    cursor = conn.cursor()

    def process_json_file(table_name, file_name, primary_key='name', value_column_name='description'):
        file_path = os.path.join(json_dir, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Erforderliche Regeldaten fehlen: {file_name}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict) or not data:
            raise ValueError(f"Ungültige Regeldaten: {file_name}")

        first_item_value = list(data.values())[0]

        # Handle simple {key: value} structures
        if isinstance(first_item_value, str):
            columns = [f'"{primary_key}" TEXT PRIMARY KEY', f'"{value_column_name}" TEXT']
            create_table_sql = f"CREATE TABLE {table_name} ({', '.join(columns)})"
            cursor.execute(create_table_sql)
            for key, value in data.items():
                cursor.execute(f"INSERT INTO {table_name} VALUES (?, ?)", (key, value))

        # Handle complex {key: {subkey: subvalue}} structures
        elif isinstance(first_item_value, dict):
            all_keys = set()
            for item_values in data.values():
                all_keys.update(item_values.keys())

            sorted_keys = sorted(list(all_keys))

            column_defs = [f'"{primary_key}" TEXT PRIMARY KEY']
            for col_name in sorted_keys:
                col_type = 'TEXT' # Default to TEXT
                for item in data.values():
                    if col_name in item:
                        sample_val = item[col_name]
                        if isinstance(sample_val, int):
                            col_type = 'INTEGER'
                        elif isinstance(sample_val, float):
                            col_type = 'REAL'
                        break
                column_defs.append(f'"{col_name}" {col_type}')

            create_table_sql = f"CREATE TABLE {table_name} ({', '.join(column_defs)})"
            cursor.execute(create_table_sql)

            for item_key, item_values in data.items():
                col_names = [primary_key] + sorted_keys
                placeholders = ', '.join(['?'] * len(col_names))
                # Corrected f-string to be compatible with older Python versions
                cols_for_sql = ', '.join([f'"{c}"' for c in col_names])
                insert_sql = f"INSERT INTO {table_name} ({cols_for_sql}) VALUES ({placeholders})"

                insert_data = [item_key]
                for col_key in sorted_keys:
                    value = item_values.get(col_key)
                    if isinstance(value, (dict, list)):
                        insert_data.append(json.dumps(value))
                    else:
                        insert_data.append(value)

                cursor.execute(insert_sql, tuple(insert_data))

    # Process all JSON files, specifying custom value column for skills
    process_json_file('enemies', 'enemies.json')
    process_json_file('races', 'races.json')
    process_json_file('classes', 'classes.json')
    process_json_file('backgrounds', 'backgrounds.json')
    process_json_file('alignments', 'alignments.json')
    process_json_file('fighting_styles', 'fighting_styles.json')
    process_json_file('skills', 'skills.json', value_column_name='ability')
    process_json_file('spells', 'spells_translated.json', primary_key='name')
    process_json_file('weapons', 'weapons.json')


if __name__ == '__main__':
    create_database()
