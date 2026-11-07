import sqlite3
import pytest
from utils.build_database import create_database


def test_create_database_creates_all_required_tables(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / 'private' / 'dnd.db'
    create_database(db_path)
    with sqlite3.connect(db_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {'enemies','races','classes','backgrounds','alignments','fighting_styles','skills','spells','weapons'}


def test_failed_build_keeps_original_database(tmp_path):
    destination = tmp_path / 'dnd.db'
    create_database(destination)
    before = destination.read_bytes()
    with pytest.raises(FileNotFoundError):
        create_database(destination, tmp_path / 'missing')
    assert destination.read_bytes() == before
    assert not list(tmp_path.glob('.database-*'))
