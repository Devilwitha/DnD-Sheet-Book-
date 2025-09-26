import os
import sqlite3
from utils import build_database


def test_create_database_creates_db_and_tables(tmp_path):
    # Ensure a clean environment: remove db if exists
    db_path = os.path.join('utils', 'data', 'dnd.db')
    if os.path.exists(db_path):
        os.remove(db_path)

    # Create database
    build_database.create_database()

    assert os.path.exists(db_path), "Database file was not created."

    # Check that at least some expected tables exist
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    # Expect tables like 'enemies' or 'races' to exist
    assert 'enemies' in tables or 'races' in tables, "Expected tables not found in database."
