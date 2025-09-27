"""
Mock-Konfigurationsdatei für robuste UI-Tests
"""
import sys
from unittest.mock import Mock, MagicMock, patch

# Mock Kivy komplett bevor irgendwas importiert wird
def setup_comprehensive_kivy_mocks():
    """Setzt umfassende Kivy-Mocks auf."""
    
    # Mock alle Kivy-Module
    kivy_modules_to_mock = [
        'kivy', 'kivy.app', 'kivy.uix', 'kivy.uix.screenmanager',
        'kivy.uix.button', 'kivy.uix.label', 'kivy.uix.boxlayout',
        'kivy.uix.gridlayout', 'kivy.uix.popup', 'kivy.uix.textinput',
        'kivy.uix.slider', 'kivy.uix.checkbox', 'kivy.uix.spinner',
        'kivy.uix.filechooser', 'kivy.uix.progressbar', 'kivy.uix.image',
        'kivy.clock', 'kivy.graphics', 'kivy.vector', 'kivy.logger',
        'kivy.config', 'kivy.factory', 'kivy.properties', 'kivy.event',
        'kivy.metrics', 'kivy.utils', 'kivy.animation', 'kivy.base'
    ]
    
    for module_name in kivy_modules_to_mock:
        if module_name not in sys.modules:
            mock_module = Mock()
            
            # Spezielle Mock-Konfigurationen für bestimmte Module
            if module_name == 'kivy.uix.screenmanager':
                mock_module.Screen = Mock()
                mock_module.ScreenManager = Mock()
                
            elif module_name == 'kivy.app':
                mock_app = Mock()
                mock_app.change_screen = Mock()
                mock_app.network_manager = Mock()
                mock_app.game_manager = Mock()
                mock_module.App = Mock()
                mock_module.App.get_running_app = Mock(return_value=mock_app)
                
            elif module_name == 'kivy.uix.button':
                mock_button = Mock()
                mock_button.bind = Mock()
                mock_module.Button = Mock(return_value=mock_button)
                
            elif module_name == 'kivy.factory':
                mock_module.Factory = Mock()
                mock_module.Factory.register = Mock()
                
            elif module_name == 'kivy.clock':
                mock_module.Clock = Mock()
                mock_module.Clock.schedule_once = Mock()
                mock_module.Clock.unschedule = Mock()
            
            sys.modules[module_name] = mock_module
    
    return True

def create_mock_screen_base():
    """Erstellt eine Mock Screen-Basisklasse."""
    mock_screen = Mock()
    mock_screen.name = 'test_screen'
    mock_screen.ids = {}
    mock_screen.manager = Mock()
    mock_screen.add_widget = Mock()
    mock_screen.remove_widget = Mock()
    mock_screen.clear_widgets = Mock()
    
    return mock_screen

def create_robust_ui_component_mock(class_name):
    """Erstellt einen robusten Mock für UI-Komponenten."""
    mock_component = Mock()
    mock_component.__class__.__name__ = class_name
    
    # Standard UI-Eigenschaften
    mock_component.ids = {}
    mock_component.add_widget = Mock()
    mock_component.remove_widget = Mock()
    mock_component.clear_widgets = Mock()
    
    # Screen-spezifische Eigenschaften
    if 'Screen' in class_name:
        mock_component.name = class_name.lower().replace('screen', '')
        mock_component.manager = Mock()
    
    # App-spezifische Mock-Methoden
    if hasattr(mock_component, 'go_to_screen'):
        mock_component.go_to_screen = Mock()
    if hasattr(mock_component, 'change_screen'):
        mock_component.change_screen = Mock()
    
    return mock_component

def patch_ui_imports():
    """Patched UI-Imports für robuste Tests."""
    
    # Setup Kivy Mocks zuerst
    setup_comprehensive_kivy_mocks()
    
    # Dictionary für UI-Klassen-Mocks
    ui_class_mocks = {}
    
    # Liste der UI-Klassen die gemockt werden sollen
    ui_classes = [
        'MainMenu', 'CharacterMenuScreen', 'OptionsScreen', 'SettingsScreen',
        'SystemScreen', 'TransferScreen', 'CharacterSheet', 'CharacterCreator',
        'DMMainScreen', 'BackgroundSettingsScreen', 'InfoMenuScreen',
        'LevelUpScreen'
    ]
    
    for class_name in ui_classes:
        ui_class_mocks[class_name] = create_robust_ui_component_mock(class_name)
    
    return ui_class_mocks

# Automatischer Setup beim Import
if __name__ != '__main__':
    setup_comprehensive_kivy_mocks()