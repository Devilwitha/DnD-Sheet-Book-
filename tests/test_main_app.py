import importlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

UI_MODULES = [
    'main_menu', 'character_creator', 'character_sheet', 'options_screen',
    'character_menu_screen', 'level_up_screen', 'character_editor', 'info_menu_screen',
    'model_screen', 'version_screen', 'settings_screen', 'background_settings_screen',
    'customization_settings_screen', 'splash_screen', 'system_screen', 'changelog_screen',
    'transfer_screen', 'dm_spiel_screen', 'dm_lobby_screen', 'player_lobby_screen',
    'dm_prep_screen', 'dm_main_screen', 'player_character_sheet', 'player_waiting_screen',
    'map_editor_screen', 'player_map_screen', 'system_info_screen',
]

KIVY_MODULES = [
    'kivy', 'kivy.config', 'kivy.core', 'kivy.core.window', 'kivy.lang', 'kivy.uix',
    'kivy.uix.screenmanager', 'kivy.uix.floatlayout', 'kivy.uix.modalview',
    'kivy.uix.label', 'kivy.clock', 'kivy.metrics',
]


class StubApp:
    '''Stands in for kivy.app.App so DnDApp keeps its own real methods.'''
    def __init__(self, **kwargs):
        pass


class FakeScreenManager:
    '''Minimal ScreenManager: tracks current screen and notifies bound callbacks.'''
    def __init__(self, names, current='main'):
        self.names = set(names)
        self._current = current
        self._callbacks = []
        self.transition = SimpleNamespace(direction=None)
        self._screens = {}

    def bind(self, current=None):
        self._callbacks.append(current)

    def has_screen(self, name):
        return name in self.names

    def get_screen(self, name):
        return self._screens.setdefault(name, MagicMock())

    @property
    def current(self):
        return self._current

    @current.setter
    def current(self, value):
        if value == self._current:
            return
        self._current = value
        for cb in self._callbacks:
            cb(self, value)


SCREEN_NAMES = [
    'splash', 'main', 'character_menu', 'creator', 'editor', 'sheet', 'options',
    'settings', 'background_settings', 'system', 'changelog', 'transfer',
    'dm_spiel', 'player_sheet', 'level_up',
]


def _stub_modules():
    stubs = {name: MagicMock() for name in KIVY_MODULES}
    stubs['kivy.metrics'].Metrics = SimpleNamespace(density=1, fontscale=1)
    stubs['kivy.core.window'].Window.dpi = 96
    stubs['kivy.utils'] = MagicMock(platform='linux')
    stubs['kivy.app'] = MagicMock(App=StubApp)
    stubs['utils.helpers'] = MagicMock()
    stubs['utils.helpers'].load_settings.return_value = {}
    stubs['utils.diagnostics'] = MagicMock()
    stubs['core.network_manager'] = MagicMock()
    for name in UI_MODULES:
        stubs['ui.' + name] = MagicMock()
    return stubs


@pytest.fixture
def main_module(tmp_path, monkeypatch):
    # Isolated storage; nothing is read from or written to the working directory.
    monkeypatch.setenv('DND_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('KIVY_HOME', str(tmp_path / 'kivy'))
    stubs = _stub_modules()
    import utils
    monkeypatch.setattr(utils, 'diagnostics', stubs['utils.diagnostics'], raising=False)
    with patch.dict(sys.modules, stubs):
        sys.modules.pop('main', None)
        module = importlib.import_module('main')
        yield module
        sys.modules.pop('main', None)


@pytest.fixture
def app(main_module, monkeypatch):
    monkeypatch.setattr(main_module, '_record', MagicMock())
    monkeypatch.setattr(main_module, 'platform', 'linux')
    instance = main_module.DnDApp()
    instance.network_manager = MagicMock()
    instance.sm = FakeScreenManager(SCREEN_NAMES, current='main')
    instance._last_screen = instance.sm.current
    instance.sm.bind(current=instance._on_screen_current)
    return instance


# ---------------- navigation history / back ----------------

def test_forward_navigation_records_history(app):
    app.change_screen('character_menu')
    app.change_screen('sheet')
    assert app.sm.current == 'sheet'
    assert app.screen_history == ['main', 'character_menu']
    assert app.sm.transition.direction == 'left'


def test_go_back_walks_history_in_reverse(app):
    app.change_screen('character_menu')
    app.change_screen('sheet')

    assert app.go_back_screen() is True
    assert app.sm.current == 'character_menu'
    assert app.screen_history == ['main']
    assert app.sm.transition.direction == 'right'

    assert app.go_back_screen() is True
    assert app.sm.current == 'main'
    assert app.screen_history == []


def test_go_back_at_root_returns_false(app):
    assert app.go_back_screen() is False
    assert app.sm.current == 'main'


def test_going_back_does_not_add_history_entries(app):
    app.change_screen('options')
    app.change_screen('settings')
    app.go_back_screen()
    assert app.sm.current == 'options'
    assert app.screen_history == ['main']


def test_splash_is_not_recorded_in_history(app):
    app.sm._current = 'splash'
    app._last_screen = 'splash'
    app.change_screen('character_menu')
    assert app.screen_history == []
    # No history: falls back to the parent map
    assert app.go_back_screen() is True
    assert app.sm.current == 'main'


def test_returning_to_earlier_screen_cuts_loop(app):
    app.change_screen('options')
    app.change_screen('settings')
    assert app.screen_history == ['main', 'options']
    app.change_screen('options')
    assert app.screen_history == ['main']


def test_entering_root_screen_clears_history(app):
    app.change_screen('options')
    app.change_screen('settings')
    app.change_screen('main')
    assert app.screen_history == []


def test_go_back_skips_missing_history_entries_and_uses_parent(app):
    app.sm._current = 'settings'
    app._last_screen = 'settings'
    app.screen_history = ['ghost']
    assert app.go_back_screen() is True
    assert app.sm.current == 'options'
    assert app.screen_history == []


def test_go_back_from_unmapped_non_root_screen_goes_to_main(app, main_module):
    assert 'level_up' in main_module.PARENT_MAP  # sanity: mapped screens exist
    app.sm.names.add('unmapped')
    app.sm._current = 'unmapped'
    app._last_screen = 'unmapped'
    assert app.go_back_screen() is True
    assert app.sm.current == 'main'


def test_change_screen_ignores_unknown_or_current_screen(app):
    app.change_screen('does_not_exist')
    assert app.sm.current == 'main'
    app.change_screen('main')
    assert app.screen_history == []


def test_change_screen_without_screen_manager_is_noop(app):
    app.sm = None
    app.change_screen('options')  # must not raise


# ---------------- on_stop cleanup ----------------

def test_on_stop_cleans_up_network_loop_transfer_and_saves_window(app, main_module, monkeypatch):
    loop = MagicMock()
    app.player_game_loop = loop
    transfer = MagicMock(spec=['cleanup_transfer'])
    app.sm._screens['transfer'] = transfer
    load = MagicMock(return_value={'keyboard_enabled': True})
    save = MagicMock()
    monkeypatch.setattr(main_module, 'load_settings', load)
    monkeypatch.setattr(main_module, 'save_settings', save)
    main_module.Window.width = 800
    main_module.Window.height = 600

    app.on_stop()

    loop.cancel.assert_called_once_with()
    assert app.player_game_loop is None
    app.network_manager.shutdown.assert_called_once_with()
    transfer.cleanup_transfer.assert_called_once_with()
    save.assert_called_once_with({'keyboard_enabled': True, 'window_width': 800, 'window_height': 600})
    main_module._record.assert_not_called()


def test_on_stop_uses_first_available_transfer_cleanup_method(app):
    transfer = MagicMock(spec=['cleanup', 'stop_transfer'])
    app.sm._screens['transfer'] = transfer
    app.on_stop()
    transfer.cleanup.assert_called_once_with()
    transfer.stop_transfer.assert_not_called()


def test_on_stop_continues_when_network_shutdown_fails(app, main_module, monkeypatch):
    app.network_manager.shutdown.side_effect = RuntimeError('boom')
    transfer = MagicMock(spec=['cleanup_transfer'])
    app.sm._screens['transfer'] = transfer
    save = MagicMock()
    monkeypatch.setattr(main_module, 'load_settings', MagicMock(return_value={}))
    monkeypatch.setattr(main_module, 'save_settings', save)

    app.on_stop()

    main_module._record.assert_any_call('stop_network', app.network_manager.shutdown.side_effect)
    transfer.cleanup_transfer.assert_called_once_with()
    save.assert_called_once()


def test_on_stop_continues_when_transfer_cleanup_fails(app, main_module, monkeypatch):
    transfer = MagicMock(spec=['cleanup_transfer'])
    transfer.cleanup_transfer.side_effect = RuntimeError('boom')
    app.sm._screens['transfer'] = transfer
    save = MagicMock()
    monkeypatch.setattr(main_module, 'load_settings', MagicMock(return_value={}))
    monkeypatch.setattr(main_module, 'save_settings', save)

    app.on_stop()

    assert main_module._record.call_args_list[-1][0][0] == 'stop_transfer'
    save.assert_called_once()


def test_on_stop_does_not_save_window_size_on_mobile(app, main_module, monkeypatch):
    save = MagicMock()
    monkeypatch.setattr(main_module, 'platform', 'android')
    monkeypatch.setattr(main_module, 'save_settings', save)
    app.on_stop()
    save.assert_not_called()
    app.network_manager.shutdown.assert_called_once_with()


def test_on_stop_without_screen_manager(app, main_module, monkeypatch):
    app.sm = None
    monkeypatch.setattr(main_module, 'load_settings', MagicMock(return_value={}))
    monkeypatch.setattr(main_module, 'save_settings', MagicMock())
    app.on_stop()  # must not raise
    app.network_manager.shutdown.assert_called_once_with()


def test_quiet_dm_sync_rebinds_open_full_sheet_and_preserves_import_filename(app):
    from core.character import Character
    app.character = Character('Nara', 'Mensch', 'Barbar')
    app.character.initialize_character()
    app.character._local_save_name = 'imported.char'
    incoming = app.character.to_dict()
    incoming['hit_points'] = 3
    app.sm._current = 'sheet'
    app.network_manager.mode = 'client'
    app._popup = MagicMock()
    app._handle_player_message({'type': 'SYNC_CHARACTER', 'payload': incoming})
    assert app.character.hit_points == 3
    assert app.character._local_save_name == 'imported.char'
    app.sm.get_screen('sheet').load_character.assert_called_once_with(app.character)
    assert app.sm.get_screen('player_sheet').character is app.character
    app._popup.assert_not_called()


@pytest.mark.parametrize('current', ['player_sheet', 'sheet', 'level_up'])
def test_multiple_host_levels_replace_all_client_references(app, current):
    from core.character import Character
    app.character = Character('Nara', 'Mensch', 'Kämpfer')
    app.character.initialize_character()
    app.network_manager.mode = 'client'
    app.sm._current = current
    for level in (2, 3, 4):
        incoming = dict(app.character.to_dict(), level=level)
        app._handle_player_message({'type': 'SYNC_CHARACTER', 'payload': incoming})
        assert app.character.level == level
        assert app.sm.get_screen('player_sheet').character is app.character
        assert app.sm.get_screen('sheet').character is app.character
        assert app.sm.get_screen('level_up').character is app.character
    if current == 'level_up':
        assert app.sm.current == 'sheet'


def test_pending_character_action_prevents_duplicate_sends(app):
    from core.character import Character
    app.character = Character('Nara', 'Mensch', 'Kämpfer')
    app.network_manager.mode = 'client'
    app._popup = MagicMock()
    assert app.request_character_action('long_rest')
    assert not app.request_character_action('long_rest')
    app.network_manager.send_to_dm.assert_called_once()
    payload = app.network_manager.send_to_dm.call_args.args[1]
    app._handle_player_message({'type': 'CHARACTER_ACTION_RESULT', 'payload': {
        'request_id': payload['request_id'], 'success': True, 'message': 'Rast bestätigt'}})
    assert app._character_request is None
