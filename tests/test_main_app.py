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

    @patch('main.save_settings')
    @patch('main.load_settings')
    @patch('os.remove')
    @patch('os.path.exists')
    @patch('main.resource_path')
    def test_on_stop_removes_lock_file(self, mock_resource_path, mock_exists, mock_remove, mock_load_settings, mock_save_settings):
        """Test that on_stop() removes the lock file."""
        mock_resource_path.return_value = self.lock_file
        mock_exists.return_value = True

        with patch.dict('sys.modules', self.mock_modules):
            from main import DnDApp

            app = DnDApp()
            app.on_stop()

        mock_resource_path.assert_called_with(".app_closed_cleanly")
        mock_exists.assert_called_with(self.lock_file)
        mock_remove.assert_called_with(self.lock_file)

    @patch('main.PlayerMapScreen')
    @patch('main.MapEditorScreen')
    @patch('main.PlayerCharacterSheet')
    @patch('main.PlayerWaitingScreen')
    @patch('main.DMMainScreen')
    @patch('main.DMPrepScreen')
    @patch('main.PlayerLobbyScreen')
    @patch('main.DMLobbyScreen')
    @patch('main.DMSpielScreen')
    @patch('main.TransferScreen')
    @patch('main.SystemInfoScreen')
    @patch('main.VersionScreen')
    @patch('main.ModelScreen')
    @patch('main.InfoMenuScreen')
    @patch('main.ChangelogScreen')
    @patch('main.SystemScreen')
    @patch('main.CustomizationSettingsScreen')
    @patch('main.BackgroundSettingsScreen')
    @patch('main.SettingsScreen')
    @patch('main.OptionsScreen')
    @patch('main.LevelUpScreen')
    @patch('main.CharacterEditor')
    @patch('main.CharacterSheet')
    @patch('main.CharacterMenuScreen')
    @patch('main.CharacterCreator')
    @patch('main.MainMenu')
    @patch('main.FloatLayout')
    @patch('main.SplashScreen')
    @patch('main.ScreenManager')
    @patch('main.open', new_callable=unittest.mock.mock_open)
    @patch('main.resource_path')
    def test_build_creates_lock_file(self, mock_resource_path, mock_open, mock_sm, mock_splash, mock_float, *args):
        """Test that build() creates the lock file."""
        mock_resource_path.return_value = self.lock_file

        with patch.dict('sys.modules', self.mock_modules):
            self.mock_modules['utils.helpers'].load_settings.return_value = {}
            with patch('main.Builder', MagicMock()):
                from main import DnDApp
                app = DnDApp()
                app.build()

        mock_resource_path.assert_any_call(".app_closed_cleanly")
        mock_open.assert_called_with(self.lock_file, "w")
        mock_open().write.assert_called_with("running")

if __name__ == '__main__':
    unittest.main()
