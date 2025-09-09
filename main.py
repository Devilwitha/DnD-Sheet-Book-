from kivy.config import Config
# Konfiguration für Kivy, bevor andere Module importiert werden
Config.set('kivy', 'keyboard_mode', 'dock')
Config.set('graphics', 'rotation', 0)
# Setzt die Höhe der Bildschirmtastatur auf 600 Pixel
Config.set('kivy', 'keyboard_height', '600')

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window

from ui.main_menu import MainMenu
from ui.character_creator import CharacterCreator
from ui.character_sheet import CharacterSheet
from ui.options_screen import OptionsScreen
from ui.level_up_screen import LevelUpScreen

class DnDApp(App):
    """Haupt-App-Klasse."""
    def build(self):
        Builder.load_file('ui/mainmenu.kv')
        Builder.load_file('ui/charactercreator.kv')
        Builder.load_file('ui/charactersheet.kv')
        Builder.load_file('ui/levelupscreen.kv')
        Builder.load_file('ui/optionsscreen.kv')

        Window.fullscreen = 'auto'
        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        
        root = FloatLayout()

        sm = ScreenManager()
        sm.add_widget(MainMenu(name='main'))
        sm.add_widget(CharacterCreator(name='creator'))
        sm.add_widget(CharacterSheet(name='sheet'))
        sm.add_widget(OptionsScreen(name='options'))
        sm.add_widget(LevelUpScreen(name='level_up'))

        root.add_widget(sm)

        return root

if __name__ == '__main__':
    DnDApp().run()