import pytest
from unittest.mock import patch, MagicMock, mock_open

# Since these are Kivy screens, we need to be careful with the app instance.
# For now, let's assume we can test the logic without a running app.
# If not, we may need to create a test App class.

from ui.version_screen import VersionScreen
from ui.model_screen import ModelScreen
from ui.system_info_screen import SystemInfoScreen

# We need a basic Kivy App to be able to instantiate screens with ids
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager

class HelperApp(App):
    def build(self):
        return ScreenManager()

@pytest.fixture
def test_app(monkeypatch):
    # Monkeypatch the App.get_running_app method to return our test app instance
    app_instance = HelperApp()
    monkeypatch.setattr(App, 'get_running_app', lambda: app_instance)
    return app_instance

import os
from kivy.uix.label import Label

def test_version_screen(test_app):
    from kivy.lang import Builder

    # Load the kv file associated with the screen
    Builder.load_file('ui/versionscreen.kv')

    screen = VersionScreen()

    with patch('builtins.open', mock_open(read_data="Test Version 1.2.3")):
        # The on_pre_enter method is called when the screen is displayed.
        # We call it manually here to trigger the logic.
        screen.on_pre_enter()

    # Check if the label's text is updated correctly
    assert screen.ids.version_label.text == "Test Version 1.2.3"

@patch('ui.model_screen.ModelScreen.get_model', return_value="Test Model")
@patch('ui.model_screen.ModelScreen.get_os_version', return_value="Test OS")
@patch('ui.model_screen.ModelScreen.get_screen_resolution', return_value="1920x1080")
@patch('ui.model_screen.ModelScreen.get_git_branch', return_value="test-branch")
@patch('ui.model_screen.ModelScreen.get_folder_size', return_value=123.45)
def test_model_screen(mock_get_folder_size, mock_get_git_branch, mock_get_screen_resolution, mock_get_os_version, mock_get_model, test_app):
    from kivy.lang import Builder
    Builder.load_file('ui/modelscreen.kv')

    screen = ModelScreen()
    screen.on_pre_enter()

    assert screen.ids.model.text == "Modell: Test Model"
    assert screen.ids.os_version.text == "Betriebssystem: Test OS"
    assert screen.ids.resolution.text == "Auflösung: 1920x1080"
    assert screen.ids.git_branch.text == "Aktueller Branch: test-branch"
    assert screen.ids.folder_size.text == "Größe des App-Ordners: 123.45 MB"

@patch('ui.system_info_screen.SystemInfoScreen.get_model', return_value="Test Model")
@patch('ui.system_info_screen.SystemInfoScreen.get_os_version', return_value="Test OS")
@patch('ui.system_info_screen.SystemInfoScreen.get_screen_resolution', return_value="1920x1080")
@patch('ui.system_info_screen.SystemInfoScreen.get_folder_size', return_value=123.45)
@patch('ui.system_info_screen.SystemInfoScreen.get_cpu_temperature', return_value="42.0°C")
@patch('psutil.cpu_percent', return_value=50.0)
@patch('psutil.virtual_memory')
@patch('psutil.disk_usage')
def test_system_info_screen(mock_disk_usage, mock_virtual_memory, mock_cpu_percent, mock_get_cpu_temperature, mock_get_folder_size, mock_get_screen_resolution, mock_get_os_version, mock_get_model, test_app):
    # Configure the mocks for psutil
    mock_virtual_memory.return_value = MagicMock(total=8 * 1024**3, used=4 * 1024**3, percent=50)
    mock_disk_usage.return_value = MagicMock(total=500 * 1024**3, used=250 * 1024**3, percent=50)

    from kivy.lang import Builder
    Builder.load_file('ui/systeminfoscreen.kv')

    screen = SystemInfoScreen()
    screen.on_pre_enter()

    assert screen.ids.raspberry_model.text == "Modell: Test Model"
    assert screen.ids.os_version.text == "Betriebssystem: Test OS"
    assert screen.ids.resolution.text == "Auflösung: 1920x1080"
    assert screen.ids.folder_size.text == "Größe des App-Ordners: 123.45 MB"
    assert screen.ids.cpu_usage.text == "CPU-Auslastung: 50.0%"
    assert screen.ids.cpu_temp.text == "CPU-Temperatur: 42.0°C"
    assert screen.ids.memory_usage.text == "RAM-Nutzung: 4.0 GB / 8.0 GB (50%)"
    assert screen.ids.disk_usage.text == "Festplattennutzung: 250.0 GB / 500.0 GB (50%)"
