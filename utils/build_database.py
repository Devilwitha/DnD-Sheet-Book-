import sqlite3
import json
import os

def create_database():
    """
    Creates and populates the dnd.db from the JSON data files.
    This script will overwrite the existing database file.
    """
    db_path = os.path.join('utils', 'data', 'dnd.db')
    json_dir = os.path.join('utils', 'data', 'json_data')

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    def process_json_file(table_name, file_name, primary_key='name', value_column_name='description'):
        file_path = os.path.join(json_dir, file_name)
        if not os.path.exists(file_path):
            print(f"Warning: JSON file not found: {file_path}. Skipping table '{table_name}'.")
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not data:
            return

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

    conn.commit()
    conn.close()
    print(f"Database '{db_path}' created successfully.")

if __name__ == '__main__':
    create_database()