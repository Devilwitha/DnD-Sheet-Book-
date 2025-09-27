import sqlite3
import os

def close_all_sqlite_connections(db_path):
    # Versucht, alle offenen SQLite-Connections zu schließen (nur für Tests gedacht)
    try:
        # Unter Windows kann ein offener Connection-Cache bestehen bleiben
        # Wir versuchen, eine Dummy-Connection zu öffnen und zu schließen
        conn = sqlite3.connect(db_path)
        conn.close()
    except Exception:
        pass