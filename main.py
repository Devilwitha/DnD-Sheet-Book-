import sys
from kivy.config import Config

if sys.platform.startswith('win'):
    Config.set('input', 'mouse', 'mouse,disable_multitouch')
from utils.helpers import load_settings

# Laden der Einstellungen, um die Tastaturkonfiguration zu bestimmen
settings = load_settings()
if settings.get('keyboard_enabled', False):
    Config.set('kivy', 'keyboard_mode', 'dock')
    Config.set('kivy', 'keyboard_height', '600')
else:
    Config.set('kivy', 'keyboard_mode', '')

Config.set('graphics', 'rotation', 0)

from kivy.core.window import Window
Window.size = (settings.get('window_width', 1280), settings.get('window_height', 720))

import socket
import threading
import json
import random
from queue import Queue
from zeroconf import ServiceInfo, Zeroconf
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock
from utils.helpers import save_settings
from core.character import Character
from core.network_manager import NetworkManager

from ui.main_menu import MainMenu
from ui.character_creator import CharacterCreator
from ui.character_sheet import CharacterSheet
from ui.options_screen import OptionsScreen
from ui.character_menu_screen import CharacterMenuScreen
from ui.level_up_screen import LevelUpScreen
from ui.character_editor import CharacterEditor
from ui.info_screen import InfoScreen
from ui.settings_screen import SettingsScreen
from ui.splash_screen import SplashScreen
from ui.system_screen import SystemScreen
from ui.changelog_screen import ChangelogScreen
from ui.transfer_screen import TransferScreen
from ui.dm_spiel_screen import DMSpielScreen
from ui.dm_lobby_screen import DMLobbyScreen
from ui.player_lobby_screen import PlayerLobbyScreen
from ui.dm_prep_screen import DMPrepScreen
from ui.dm_main_screen import DMMainScreen
from ui.player_character_sheet import PlayerCharacterSheet
from ui.player_waiting_screen import PlayerWaitingScreen
from ui.map_editor_screen import MapEditorScreen
from ui.player_map_screen import PlayerMapScreen

class DnDApp(App):
    """Haupt-App-Klasse."""
    def __init__(self, **kwargs):
        super(DnDApp, self).__init__(**kwargs)
        self.network_manager = NetworkManager()
        self.loaded_session_data = None
        self.source_screen = None # For back navigation
        self.edited_map_data = None # To pass map data from editor to DM screen

    def change_screen(self, screen_name, source_screen=None):
        """Changes the screen and sets the source screen for back navigation."""
        if source_screen:
            self.source_screen = source_screen
        # It's a good practice to clear the source screen if not provided,
        # to avoid accidental 'back' to a wrong screen.
        elif screen_name in ['main', 'dm_spiel', 'player_sheet']:
             self.source_screen = None

        self.root.children[0].current = screen_name

    def build(self):
        Builder.load_file('ui/splashscreen.kv')
        Builder.load_file('ui/mainmenu.kv')
        Builder.load_file('ui/charactercreator.kv')
        Builder.load_file('ui/charactereditor.kv')
        Builder.load_file('ui/charactersheet.kv')
        Builder.load_file('ui/charactermenuscreen.kv')
        Builder.load_file('ui/levelupscreen.kv')
        Builder.load_file('ui/optionsscreen.kv')
        Builder.load_file('ui/settingsscreen.kv')
        Builder.load_file('ui/systemscreen.kv')
        Builder.load_file('ui/changelogscreen.kv')
        Builder.load_file('ui/infoscreen.kv')
        Builder.load_file('ui/transferscreen.kv')
        Builder.load_file('ui/dmspielscreen.kv')
        Builder.load_file('ui/dmlobbyscreen.kv')
        Builder.load_file('ui/playerlobbyscreen.kv')
        Builder.load_file('ui/dmprepscreen.kv')
        Builder.load_file('ui/dmmainscreen.kv')
        Builder.load_file('ui/playerwaitingscreen.kv')
        Builder.load_file('ui/playercharactersheet.kv')
        Builder.load_file('ui/mapeditorscreen.kv')
        Builder.load_file('ui/playermapscreen.kv')

        if sys.platform.startswith('win'):
            Window.fullscreen = False
        else:
            Window.fullscreen = 'auto'

        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        
        root = FloatLayout()

        sm = ScreenManager()
        sm.add_widget(SplashScreen(name='splash'))
        sm.add_widget(MainMenu(name='main'))
        sm.add_widget(CharacterMenuScreen(name='character_menu'))
        sm.add_widget(CharacterCreator(name='creator'))
        sm.add_widget(CharacterEditor(name='editor'))
        sm.add_widget(CharacterSheet(name='sheet'))
        sm.add_widget(OptionsScreen(name='options'))
        sm.add_widget(SettingsScreen(name='settings'))
        sm.add_widget(SystemScreen(name='system'))
        sm.add_widget(ChangelogScreen(name='changelog'))
        sm.add_widget(InfoScreen(name='info'))
        sm.add_widget(LevelUpScreen(name='level_up'))
        sm.add_widget(TransferScreen(name='transfer'))
        sm.add_widget(DMSpielScreen(name='dm_spiel'))
        sm.add_widget(DMLobbyScreen(name='dm_lobby'))
        sm.add_widget(PlayerLobbyScreen(name='player_lobby'))
        sm.add_widget(DMPrepScreen(name='dm_prep'))
        sm.add_widget(DMMainScreen(name='dm_main'))
        sm.add_widget(PlayerWaitingScreen(name='player_waiting'))
        sm.add_widget(PlayerCharacterSheet(name='player_sheet'))
        sm.add_widget(MapEditorScreen(name='map_editor'))
        sm.add_widget(PlayerMapScreen(name='player_map'))


        root.add_widget(sm)

        return root

    def on_stop(self):
        """Wird aufgerufen, wenn die App geschlossen wird."""
        settings = load_settings()
        settings['window_width'] = Window.width
        settings['window_height'] = Window.height
        save_settings(settings)

if __name__ == '__main__':
    DnDApp().run()