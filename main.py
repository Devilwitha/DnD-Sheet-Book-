import sys
from kivy.config import Config
from utils.helpers import load_settings

# Laden der Einstellungen, um die Tastaturkonfiguration zu bestimmen
settings = load_settings()
if settings.get('keyboard_enabled', False):
    Config.set('kivy', 'keyboard_mode', 'dock')
    # Setzt die Höhe der Bildschirmtastatur auf 600 Pixel
    Config.set('kivy', 'keyboard_height', '600')
else:
    Config.set('kivy', 'keyboard_mode', '')

Config.set('graphics', 'rotation', 0)

# Set window size from settings
from kivy.core.window import Window
Window.size = (settings.get('window_width', 1280), settings.get('window_height', 720))


from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window
from utils.helpers import save_settings

from ui.main_menu import MainMenu
from ui.character_creator import CharacterCreator
from ui.character_sheet import CharacterSheet
from ui.options_screen import OptionsScreen
from ui.level_up_screen import LevelUpScreen
from ui.character_editor import CharacterEditor
from ui.info_screen import InfoScreen
from ui.settings_screen import SettingsScreen
from ui.splash_screen import SplashScreen

class DnDApp(App):
    """Haupt-App-Klasse."""
    def build(self):
        Builder.load_file('ui/splashscreen.kv')
        Builder.load_file('ui/mainmenu.kv')
        Builder.load_file('ui/charactercreator.kv')
        Builder.load_file('ui/charactereditor.kv')
        Builder.load_file('ui/charactersheet.kv')
        Builder.load_file('ui/levelupscreen.kv')
        Builder.load_file('ui/optionsscreen.kv')
        Builder.load_file('ui/settingsscreen.kv')
        Builder.load_file('ui/infoscreen.kv')

        if sys.platform.startswith('linux'):
            Window.fullscreen = 'auto'
        else:
            Window.fullscreen = False
            # Window.size wird jetzt am Anfang aus den Settings geladen

        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        
        root = FloatLayout()

        sm = ScreenManager()
        sm.add_widget(SplashScreen(name='splash'))
        sm.add_widget(MainMenu(name='main'))
        sm.add_widget(CharacterCreator(name='creator'))
        sm.add_widget(CharacterEditor(name='editor'))
        sm.add_widget(CharacterSheet(name='sheet'))
        sm.add_widget(OptionsScreen(name='options'))
        sm.add_widget(SettingsScreen(name='settings'))
        sm.add_widget(InfoScreen(name='info'))
        sm.add_widget(LevelUpScreen(name='level_up'))

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