import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# A dummy class to stand in for kivy.app.App, so that DnDApp can inherit from it
# and still have its own methods (`build`, `on_stop`) be real methods.
class MockApp:
    def __init__(self, **kwargs):
        # The super call is needed because DnDApp calls super().__init__
        super().__init__()

class TestAppLifecycle(unittest.TestCase):

    def setUp(self):
        self.lock_file = ".app_closed_cleanly"
        if os.path.exists(self.lock_file):
            os.remove(self.lock_file)

        # A dictionary to act as a mock for sys.modules
        self.mock_modules = {
            'kivy.config': MagicMock(),
            'kivy.core.window': MagicMock(),
            'utils.helpers': MagicMock(),
            'core.character': MagicMock(),
            'core.network_manager': MagicMock(),
            'kivy.app': MagicMock(App=MockApp), # Use our MockApp
            'kivy.lang': MagicMock(),
            'kivy.uix.screenmanager': MagicMock(),
            'kivy.uix.floatlayout': MagicMock(),
            'kivy.clock': MagicMock(),
            'zeroconf': MagicMock(),
            # Mock all the ui elements imported in main
            'ui.main_menu': MagicMock(),
            'ui.character_creator': MagicMock(),
            'ui.character_sheet': MagicMock(),
            'ui.options_screen': MagicMock(),
            'ui.character_menu_screen': MagicMock(),
            'ui.level_up_screen': MagicMock(),
            'ui.character_editor': MagicMock(),
            'ui.info_screen': MagicMock(),
            'ui.settings_screen': MagicMock(),
            'ui.background_settings_screen': MagicMock(),
            'ui.customization_settings_screen': MagicMock(),
            'ui.splash_screen': MagicMock(),
            'ui.system_screen': MagicMock(),
            'ui.changelog_screen': MagicMock(),
            'ui.transfer_screen': MagicMock(),
            'ui.dm_spiel_screen': MagicMock(),
            'ui.dm_lobby_screen': MagicMock(),
            'ui.player_lobby_screen': MagicMock(),
            'ui.dm_prep_screen': MagicMock(),
            'ui.dm_main_screen': MagicMock(),
            'ui.player_character_sheet': MagicMock(),
            'ui.player_waiting_screen': MagicMock(),
            'ui.map_editor_screen': MagicMock(),
            'ui.player_map_screen': MagicMock(),
        }

    def tearDown(self):
        if os.path.exists(self.lock_file):
            os.remove(self.lock_file)
        if 'main' in sys.modules:
            del sys.modules['main']

    def test_on_stop_removes_lock_file(self):
        """Test that on_stop() removes the lock file."""
        # Create a dummy lock file to be removed
        with open(self.lock_file, "w") as f:
            f.write("running")

        with patch.dict('sys.modules', self.mock_modules):
            self.mock_modules['utils.helpers'].load_settings.return_value = {}
            self.mock_modules['utils.helpers'].resource_path.return_value = self.lock_file
            from main import DnDApp

            app = DnDApp()
            app.on_stop()

        self.assertFalse(os.path.exists(self.lock_file), "Lock file was not removed on stop.")

    def test_build_creates_lock_file(self):
        """Test that build() creates the lock file."""
        # Ensure the file doesn't exist before build() is called
        if os.path.exists(self.lock_file):
            os.remove(self.lock_file)

        with patch.dict('sys.modules', self.mock_modules):
            self.mock_modules['utils.helpers'].load_settings.return_value = {}
            self.mock_modules['utils.helpers'].resource_path.return_value = self.lock_file
            # We need to mock the Builder since it loads kv files which we don't have here
            with patch('main.Builder', MagicMock()):
                from main import DnDApp

                app = DnDApp()
                app.build()

        self.assertTrue(os.path.exists(self.lock_file), "Lock file was not created on build.")
        with open(self.lock_file, "r") as f:
            self.assertEqual(f.read(), "running", "Lock file content is incorrect.")

if __name__ == '__main__':
    unittest.main()
