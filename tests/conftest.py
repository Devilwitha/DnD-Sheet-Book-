import pytest
import os
import shutil
import importlib
from unittest.mock import MagicMock
import sys

def pytest_configure(config):
    """
    Hook that runs before test collection.
    Mocks Kivy and other modules to prevent import errors.
    """
    sys.modules['kivy'] = MagicMock()
    mock_modules = {
        'kivy.app': MagicMock(),
        'kivy.base': MagicMock(),
        'kivy.clock': MagicMock(),
        'kivy.config': MagicMock(),
        'kivy.core': MagicMock(),
        'kivy.core.window': MagicMock(),
        'kivy.graphics': MagicMock(),
        'kivy.lang': MagicMock(),
        'kivy.properties': MagicMock(),
        'kivy.uix': MagicMock(),
        'kivy.uix.boxlayout': MagicMock(),
        'kivy.uix.button': MagicMock(),
        'kivy.uix.floatlayout': MagicMock(),
        'kivy.uix.image': MagicMock(),
        'kivy.uix.label': MagicMock(),
        'kivy.uix.popup': MagicMock(),
        'kivy.uix.screenmanager': MagicMock(),
        'kivy.uix.scrollview': MagicMock(),
        'kivy.uix.textinput': MagicMock(),
        'kivy.utils': MagicMock(),
        'zeroconf': MagicMock(),
        'psutil': MagicMock(), # Added the missing mock
    }
    sys.modules.update(mock_modules)

# Define paths
SOURCE_DB_PATH = os.path.join('utils', 'data', 'dnd.db')
TEST_DB_PATH = os.path.join('tests', 'test_dnd.db')

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Pytest fixture for the entire test session.
    - Mocks Kivy (via pytest_configure).
    - Creates a temporary, clean database for tests.
    - Patches the DB path and explicitly initializes data for the test session.
    """
    if not os.path.exists(SOURCE_DB_PATH):
        # Attempt to build the database automatically so tests can run in CI
        try:
            from utils import build_database
            build_database.create_database()
        except Exception as e:
            pytest.fail(f"Source database not found at {SOURCE_DB_PATH}. Run utils/build_database.py first. Build attempt failed: {e}")

    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    shutil.copy2(SOURCE_DB_PATH, TEST_DB_PATH)

    # Import the modules now that mocks are in place
    from utils import database, data_manager

    # Patch the function that provides the database path to point to our test DB
    original_get_path = database.get_dest_db_path
    database.get_dest_db_path = lambda: TEST_DB_PATH

    # Explicitly initialize data using the patched path
    data_manager.initialize_data()

    # Let the tests run
    yield

    # --- Teardown ---
    # Restore the original function and remove the test database
    database.get_dest_db_path = original_get_path
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)