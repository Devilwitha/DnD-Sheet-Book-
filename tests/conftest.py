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
    import types

    # Provide a minimal stub for kivy and specific submodules to allow
    # tests to subclass App and create a ScreenManager without the
    # MagicMock side_effect causing StopIteration on instantiation.
    sys.modules['kivy'] = MagicMock()
    # Minimal kivy.app stub with a simple App class usable for subclassing
    kivy_app = types.ModuleType('kivy.app')
    class App:
        def __init__(self):
            pass
        def build(self):
            return None
        @staticmethod
        def get_running_app():
            return None
    kivy_app.App = App

    # Simple storage for ids parsed from KV files
    BUILDER_ID_MAP = {}

    # Minimal fake Builder that parses kv files for root widgets and ids
    class FakeBuilder:
        @staticmethod
        def load_file(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    current_root = None
                    for line in f:
                        line_strip = line.strip()
                        # Detect root declaration: <ClassName>:
                        if line_strip.startswith('<') and line_strip.endswith('>:'):
                            current_root = line_strip[1:-2].strip()
                            BUILDER_ID_MAP.setdefault(current_root, [])
                        # Detect id lines: id: some_id
                        elif line_strip.startswith('id:') and current_root:
                            parts = line_strip.split(':', 1)
                            if len(parts) == 2:
                                id_name = parts[1].strip()
                                # Remove possible trailing comments
                                id_name = id_name.split('#', 1)[0].strip()
                                BUILDER_ID_MAP[current_root].append(id_name)
            except Exception:
                # If file can't be read, ignore silently for tests
                pass

    fake_builder = FakeBuilder()

    # Minimal kivy.uix.screenmanager stub with a simple ScreenManager
    sm_module = types.ModuleType('kivy.uix.screenmanager')
    class SimpleWidgetStub:
        def __init__(self):
            self.text = ""
            self.height = 0
            self.width = 0

    class Screen:
        def __init__(self, **kwargs):
            # Provide a simple object-like ids container used by tests and a name attribute
            self.ids = types.SimpleNamespace()
            self.name = kwargs.get('name') if isinstance(kwargs, dict) else None
            self.manager = None
            # Populate ids from any previously parsed KV for this class
            class_name = type(self).__name__
            id_list = BUILDER_ID_MAP.get(class_name, [])
            for _id in id_list:
                # set attribute on ids namespace to a simple widget stub
                setattr(self.ids, _id, SimpleWidgetStub())

        def on_pre_enter(self, *args, **kwargs):
            return None

        def on_enter(self, *args, **kwargs):
            return None

    class ScreenManager:
        def __init__(self):
            self._screens = {}
        def add_widget(self, widget):
            # accept widgets in tests; store by name if available
            name = getattr(widget, 'name', None)
            if name:
                self._screens[name] = widget
        def get_screen(self, name):
            return self._screens.get(name)
    sm_module.ScreenManager = ScreenManager
    sm_module.Screen = Screen

    # Simple GridLayout stub module
    grid_module = types.ModuleType('kivy.uix.gridlayout')
    class GridLayout:
        def __init__(self, **kwargs):
            self.cols = kwargs.get('cols', 1)
            self.rows = kwargs.get('rows', 1)
            self.children = []
            self.size_hint_y = None
        def add_widget(self, widget):
            self.children.append(widget)
        def clear_widgets(self):
            self.children.clear()
        def bind(self, *args, **kwargs):
            return None
    grid_module.GridLayout = GridLayout

    # Simple CheckBox stub module
    checkbox_module = types.ModuleType('kivy.uix.checkbox')
    class CheckBox:
        def __init__(self, **kwargs):
            self.active = kwargs.get('active', False)
    checkbox_module.CheckBox = CheckBox

    # Provide the fake Builder via kivy.lang so tests can call Builder.load_file
    kivy_lang = types.ModuleType('kivy.lang')
    kivy_lang.Builder = fake_builder

    mock_modules = {
        'kivy.app': kivy_app,
        'kivy.base': MagicMock(),
        'kivy.clock': MagicMock(),
        'kivy.base': MagicMock(),
        'kivy.clock': MagicMock(),
        'kivy.config': MagicMock(),
        'kivy.core': MagicMock(),
        'kivy.core.window': MagicMock(),
        'kivy.graphics': MagicMock(),
    'kivy.lang': kivy_lang,
        'kivy.properties': MagicMock(),
        'kivy.uix': MagicMock(),
        'kivy.uix.boxlayout': MagicMock(),
        'kivy.uix.button': MagicMock(),
        'kivy.uix.floatlayout': MagicMock(),
        'kivy.uix.image': MagicMock(),
        'kivy.uix.label': MagicMock(),
        'kivy.uix.popup': MagicMock(),
    'kivy.uix.screenmanager': sm_module,
    'kivy.uix.gridlayout': grid_module,
    'kivy.uix.checkbox': checkbox_module,
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
    # Versuche, alle SQLite-Connections zu schließen, bevor gelöscht wird
    try:
        from utils.db_test_helper import close_all_sqlite_connections
        close_all_sqlite_connections(TEST_DB_PATH)
    except Exception:
        pass
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)