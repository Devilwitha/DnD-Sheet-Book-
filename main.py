import sys
import os
from utils.helpers import resource_path, load_settings
from kivy.config import Config
from kivy.utils import platform

if platform == 'win':
    Config.set('input', 'mouse', 'mouse,disable_multitouch')

# Laden der Einstellungen, um die Tastaturkonfiguration zu bestimmen
settings = load_settings()
if settings.get('keyboard_enabled', False):
    Config.set('kivy', 'keyboard_mode', 'dock')
    Config.set('kivy', 'keyboard_height', '600')
else:
    Config.set('kivy', 'keyboard_mode', '')

Config.set('graphics', 'rotation', 0)

from kivy.core.window import Window
if platform not in ('android', 'ios'):
    Window.size = (settings.get('window_width', 1280), settings.get('window_height', 720))

import socket
import threading
import json
import random
from queue import Queue
from zeroconf import ServiceInfo, Zeroconf
from utils.data_manager import initialize_data
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
from ui.info_menu_screen import InfoMenuScreen
from ui.model_screen import ModelScreen
from ui.version_screen import VersionScreen
from ui.settings_screen import SettingsScreen
from ui.background_settings_screen import BackgroundSettingsScreen
from ui.customization_settings_screen import CustomizationSettingsScreen
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
        self.screen_history = [] # For back navigation
        self.edited_map_data = None # To pass map data from editor to DM screen
        self.player_game_loop = None
        # GameManager für Map-Editor und offline Spieler
        from core.game_manager import GameManager
        self.game_manager = GameManager()

    def start_player_gameloop(self):
        if self.player_game_loop:
            self.player_game_loop.cancel()
        self.player_game_loop = Clock.schedule_interval(self.check_for_player_updates, 0.5)

    def stop_player_gameloop(self):
        if self.player_game_loop:
            self.player_game_loop.cancel()
            self.player_game_loop = None

    def check_for_player_updates(self, dt):
        from utils.helpers import create_styled_popup
        from kivy.uix.label import Label
        from queue import Empty

        if not self.network_manager.running and self.network_manager.mode == 'idle':
            self.handle_disconnect("Verbindung zum DM verloren.")
            return

        try:
            while True:
                source, message = self.network_manager.incoming_messages.get_nowait()
                msg_type = message.get('type')
                payload = message.get('payload')
                sm = self.root.children[0]

                if msg_type == 'KICK':
                    self.handle_disconnect("Du wurdest vom DM gekickt.")
                    return
                elif msg_type == 'MAP_DATA':
                    if sm.has_screen('player_map'):
                        sm.get_screen('player_map').set_map_data(payload)
                    if sm.has_screen('player_sheet'):
                        sm.get_screen('player_sheet').map_data = payload
                        sm.get_screen('player_sheet').ids.view_map_button.disabled = False
                elif msg_type == 'TRIGGER_MESSAGE':
                    create_styled_popup(
                        title="!",
                        content=Label(text=payload.get('message', '...')),
                        size_hint=(0.7, 0.5)
                    ).open()
                elif msg_type == 'GAME_STATE_UPDATE':
                    if sm.has_screen('player_sheet'):
                        sm.get_screen('player_sheet').update_player_list(payload.get('players', []))
                        sm.get_screen('player_sheet').update_initiative_order(payload.get('initiative', []))
                    if sm.has_screen('player_map'):
                        sm.get_screen('player_map').update_game_state(payload)
                elif msg_type == 'VICTORY':
                    create_styled_popup(
                        title="Sieg!",
                        content=Label(text=payload),
                        size_hint=(0.7, 0.5)
                    ).open()
                elif msg_type == 'ERROR':
                    print(f"CLIENT_ERROR: {payload}")
                    # create_styled_popup(
                    #    title="Fehler",
                    #    content=Label(text=payload),
                    #    size_hint=(0.7, 0.5)
                    # ).open()
                elif msg_type == 'SET_CHARACTER_DATA':
                    self.character = Character.from_dict(payload)
                    if sm.has_screen('player_sheet'):
                        sm.get_screen('player_sheet').character = self.character
                        sm.get_screen('player_sheet').update_sheet()
                    create_styled_popup(title="Update", content=Label(text="Dein Charakter wurde vom DM aktualisiert."), size_hint=(0.6, 0.4)).open()
                elif msg_type == 'SAVE_YOUR_CHARACTER':
                    if sm.has_screen('player_sheet'):
                        sm.get_screen('player_sheet').save_character()
        except Empty:
            pass

    def handle_disconnect(self, message):
        from utils.helpers import create_styled_popup
        from kivy.uix.label import Label

        self.stop_player_gameloop()
        if self.network_manager.running:
            self.network_manager.shutdown()

        create_styled_popup(title="Verbindung getrennt", content=Label(text=message), size_hint=(0.7, 0.4)).open()
        self.change_screen('main')

    def change_screen(self, screen_name, transition_direction='left', is_go_back=False):
        """Changes the screen and manages the navigation history."""
        current_screen = self.root.children[0].current
        if screen_name != current_screen:
            if not is_go_back:
                # Add the current screen to history if it's not already at the top
                if not self.screen_history or self.screen_history[-1] != current_screen:
                    self.screen_history.append(current_screen)

            # Reset history for main screens
            if screen_name in ['main', 'dm_spiel', 'player_sheet']:
                self.screen_history = []

            self.root.children[0].transition.direction = transition_direction
            self.root.children[0].current = screen_name

    def go_back_screen(self):
        """Navigates to the previous screen in the history."""
        if self.screen_history:
            previous_screen = self.screen_history.pop()
            self.change_screen(previous_screen, transition_direction='right', is_go_back=True)

    def build(self):
        # Initialize all game data from the database
        initialize_data()

        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])

        # Create a lock file to indicate the app is running
        with open(resource_path(".app_closed_cleanly"), "w") as f:
            f.write("running")

        Builder.load_file(resource_path('ui/splashscreen.kv'))
        Builder.load_file(resource_path('ui/mainmenu.kv'))
        Builder.load_file(resource_path('ui/charactercreator.kv'))
        Builder.load_file(resource_path('ui/charactereditor.kv'))
        Builder.load_file(resource_path('ui/charactersheet.kv'))
        Builder.load_file(resource_path('ui/charactermenuscreen.kv'))
        Builder.load_file(resource_path('ui/levelupscreen.kv'))
        Builder.load_file(resource_path('ui/optionsscreen.kv'))
        Builder.load_file(resource_path('ui/settingsscreen.kv'))
        Builder.load_file(resource_path('ui/backgroundsettingsscreen.kv'))
        Builder.load_file(resource_path('ui/customizationsettingsscreen.kv'))
        Builder.load_file(resource_path('ui/systemscreen.kv'))
        Builder.load_file(resource_path('ui/changelogscreen.kv'))
        Builder.load_file(resource_path('ui/infomenuscreen.kv'))
        Builder.load_file(resource_path('ui/modelscreen.kv'))
        Builder.load_file(resource_path('ui/versionscreen.kv'))
        Builder.load_file(resource_path('ui/systeminfoscreen.kv'))
        Builder.load_file(resource_path('ui/transferscreen.kv'))
        Builder.load_file(resource_path('ui/dmspielscreen.kv'))
        Builder.load_file(resource_path('ui/dmlobbyscreen.kv'))
        Builder.load_file(resource_path('ui/playerlobbyscreen.kv'))
        Builder.load_file(resource_path('ui/dmprepscreen.kv'))
        Builder.load_file(resource_path('ui/dmmainscreen.kv'))
        Builder.load_file(resource_path('ui/playerwaitingscreen.kv'))
        Builder.load_file(resource_path('ui/playercharactersheet.kv'))
        Builder.load_file(resource_path('ui/mapeditorscreen.kv'))
        Builder.load_file(resource_path('ui/playermapscreen.kv'))

        if platform == 'win':
            Window.fullscreen = False
            Window.set_icon(resource_path('logo/logo.png'))
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
        sm.add_widget(BackgroundSettingsScreen(name='background_settings'))
        sm.add_widget(CustomizationSettingsScreen(name='customization_settings'))
        sm.add_widget(SystemScreen(name='system'))
        sm.add_widget(ChangelogScreen(name='changelog'))
        sm.add_widget(InfoMenuScreen(name='info_menu'))
        sm.add_widget(ModelScreen(name='model'))
        sm.add_widget(VersionScreen(name='version'))
        if platform not in ('android', 'ios'):
            from ui.system_info_screen import SystemInfoScreen
            sm.add_widget(SystemInfoScreen(name='system_info'))
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
        # Remove the lock file to indicate a clean shutdown
        lock_file = resource_path(".app_closed_cleanly")
        if os.path.exists(lock_file):
            os.remove(lock_file)

        settings = load_settings()
        settings['window_width'] = Window.width
        settings['window_height'] = Window.height
        save_settings(settings)

if __name__ == '__main__':
    DnDApp().run()