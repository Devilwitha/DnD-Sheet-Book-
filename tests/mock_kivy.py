"""
Verbesserte Mock-Konfiguration für GUI-Tests
"""
import sys
from unittest.mock import MagicMock, Mock

def setup_kivy_mocks():
    """Setup comprehensive Kivy mocks for testing."""
    
    # Mock Kivy App
    mock_app = MagicMock()
    mock_app.change_screen = MagicMock()
    mock_app.go_back_screen = MagicMock()
    mock_app.platform = 'linux'  # Default platform for tests
    
    # Mock Kivy classes
    mock_screen = MagicMock()
    mock_screen.ids = {}
    mock_screen.manager = mock_app
    
    mock_widget = MagicMock()
    mock_widget.bind = MagicMock()
    mock_widget.unbind = MagicMock()
    mock_widget.add_widget = MagicMock()
    mock_widget.remove_widget = MagicMock()
    mock_widget.clear_widgets = MagicMock()
    
    # Mock UI components
    mock_button = MagicMock()
    mock_button.bind = MagicMock()
    
    mock_label = MagicMock()
    mock_textinput = MagicMock()
    mock_textinput.text = ""
    
    mock_spinner = MagicMock()
    mock_spinner.text = ""
    mock_spinner.values = []
    
    mock_switch = MagicMock() 
    mock_switch.active = False
    
    mock_slider = MagicMock()
    mock_slider.value = 0
    
    mock_filechooser = MagicMock()
    mock_filechooser.path = "/"
    mock_filechooser.selection = []
    
    mock_popup = MagicMock()
    mock_popup.open = MagicMock()
    mock_popup.dismiss = MagicMock()
    
    # Mock Kivy modules and classes
    kivy_mocks = {
        # Core Kivy
        'kivy': MagicMock(),
        'kivy.app': MagicMock(),
        'kivy.app.App': MagicMock(return_value=mock_app),
        'kivy.lang': MagicMock(),
        'kivy.lang.Builder': MagicMock(),
        'kivy.clock': MagicMock(),
        'kivy.clock.Clock': MagicMock(),
        'kivy.properties': MagicMock(),
        'kivy.core': MagicMock(),
        'kivy.core.window': MagicMock(),
        'kivy.core.window.Window': MagicMock(),
        'kivy.utils': MagicMock(),
        
        # Screen Management
        'kivy.uix': MagicMock(),
        'kivy.uix.screenmanager': MagicMock(),
        'kivy.uix.screenmanager.Screen': MagicMock(return_value=mock_screen),
        'kivy.uix.screenmanager.ScreenManager': MagicMock(),
        'kivy.uix.screen': MagicMock(),
        'kivy.uix.screen.Screen': MagicMock(return_value=mock_screen),
        
        # Layouts
        'kivy.uix.boxlayout': MagicMock(),
        'kivy.uix.boxlayout.BoxLayout': MagicMock(return_value=mock_widget),
        'kivy.uix.gridlayout': MagicMock(),
        'kivy.uix.gridlayout.GridLayout': MagicMock(return_value=mock_widget),
        'kivy.uix.stacklayout': MagicMock(),
        'kivy.uix.anchorlayout': MagicMock(),
        'kivy.uix.floatlayout': MagicMock(),
        
        # Widgets
        'kivy.uix.widget': MagicMock(),
        'kivy.uix.widget.Widget': MagicMock(return_value=mock_widget),
        'kivy.uix.button': MagicMock(),
        'kivy.uix.button.Button': MagicMock(return_value=mock_button),
        'kivy.uix.label': MagicMock(),
        'kivy.uix.label.Label': MagicMock(return_value=mock_label),
        'kivy.uix.textinput': MagicMock(),
        'kivy.uix.textinput.TextInput': MagicMock(return_value=mock_textinput),
        'kivy.uix.image': MagicMock(),
        'kivy.uix.image.Image': MagicMock(return_value=mock_widget),
        
        # Interactive Widgets
        'kivy.uix.spinner': MagicMock(),
        'kivy.uix.spinner.Spinner': MagicMock(return_value=mock_spinner),
        'kivy.uix.checkbox': MagicMock(),
        'kivy.uix.checkbox.CheckBox': MagicMock(return_value=mock_widget),
        'kivy.uix.switch': MagicMock(),
        'kivy.uix.switch.Switch': MagicMock(return_value=mock_switch),
        'kivy.uix.slider': MagicMock(),
        'kivy.uix.slider.Slider': MagicMock(return_value=mock_slider),
        'kivy.uix.progressbar': MagicMock(),
        
        # File/Dialog Widgets
        'kivy.uix.filechooser': MagicMock(),
        'kivy.uix.filechooser.FileChooserListView': MagicMock(return_value=mock_filechooser),
        'kivy.uix.filechooser.FileChooserIconView': MagicMock(return_value=mock_filechooser),
        'kivy.uix.popup': MagicMock(),
        'kivy.uix.popup.Popup': MagicMock(return_value=mock_popup),
        
        # Scrolling
        'kivy.uix.scrollview': MagicMock(),
        'kivy.uix.scrollview.ScrollView': MagicMock(return_value=mock_widget),
        
        # External
        'zeroconf': MagicMock(),
        'zeroconf.ServiceBrowser': MagicMock(),
        'zeroconf.ServiceInfo': MagicMock(),
        'zeroconf.Zeroconf': MagicMock(),
    }
    
    # Apply mocks to sys.modules
    for module_name, mock_obj in kivy_mocks.items():
        sys.modules[module_name] = mock_obj
    
    return mock_app

def mock_get_running_app():
    """Return a mock app instance."""
    return setup_kivy_mocks()