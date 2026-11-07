import copy
import json
import socket
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from core.character import Character
from core.network_manager import NetworkManager, PROTOCOL
from utils.network_setup import local_interfaces, connection_error_kind, connection_help
from utils.join_qr import make_join_payload, parse_join_candidates, parse_join_payload
from utils.windows_network import firewall_script, rule_names

CODE = '12345678ABCDEF90'


def test_physical_interfaces_are_preferred_with_virtual_fallback(monkeypatch):
    import psutil
    addresses = {
        'vEthernet (WSL)': '172.27.0.1', 'VPN': '10.50.0.2', 'WLAN': '192.168.4.22',
        'Ethernet ohne DHCP': '169.254.2.3', 'Disconnected': '192.168.1.1', 'Loopback': '127.0.0.1'}
    monkeypatch.setattr(psutil, 'net_if_stats', lambda: {k: SimpleNamespace(isup=k != 'Disconnected') for k in addresses})
    monkeypatch.setattr(psutil, 'net_if_addrs', lambda: {k: [SimpleNamespace(family=socket.AF_INET, address=v)] for k, v in addresses.items()})
    result = local_interfaces()
    assert result[0]['address'] == '192.168.4.22'
    assert result[-1]['address'] == '169.254.2.3'
    assert {r['address'] for r in result} == {'192.168.4.22', '172.27.0.1', '10.50.0.2', '169.254.2.3'}


def test_qr_multihost_roundtrip_and_legacy_compatibility():
    old = make_join_payload('192.168.4.22', 45555, CODE)
    assert parse_join_candidates(old) == (['192.168.4.22'], 45555, CODE)
    payload = make_join_payload('192.168.4.22', 45555, CODE, ['10.50.0.2', '192.168.4.22'])
    assert parse_join_candidates(payload) == (['192.168.4.22', '10.50.0.2'], 45555, CODE)
    assert parse_join_payload(payload) == ('192.168.4.22', 45555, CODE)


@pytest.mark.parametrize('hosts', [[], ['8.8.8.8'], ['192.168.4.22', '8.8.8.8'],
    ['192.168.4.22', 'example.org'], ['192.168.4.22', 123], ['192.168.4.22'] * 2,
    ['192.168.4.22'] + [f'10.0.0.{i}' for i in range(1, 9)], '192.168.4.22'])
def test_qr_rejects_invalid_secondary_addresses(hosts):
    data = json.loads(make_join_payload('192.168.4.22', 45555, CODE, []))
    data['hosts'] = hosts
    with pytest.raises(ValueError):
        parse_join_candidates(json.dumps(data))


def test_qr_duplicate_keys_and_oversize_are_rejected():
    for data in ('{"app":"dnd-local","app":"dnd-local"}', 'x' * 1025):
        with pytest.raises(ValueError):
            parse_join_candidates(data)


@pytest.mark.parametrize('raw,kind', [('timed out', 'timeout'), ('[WinError 10061]', 'refused'),
    ('Server authentication failed.', 'code'), ('unsupported protocol', 'version'),
    ('duplicate character', 'duplicate'), ('Verbindungsaufbau abgebrochen.', 'cancelled')])
def test_diagnostics_distinguish_actionable_failures(raw, kind):
    assert connection_error_kind(raw) == kind
    assert raw not in connection_help(raw) or kind == 'cancelled'


def test_timeout_does_not_claim_firewall_is_proven_cause():
    message = connection_help('timed out')
    assert 'keine Firewall-Blockade' in message
    assert 'Gast-WLAN' in message and 'QR-Code' in message


def test_candidates_try_next_address_without_sending_code_to_logs(monkeypatch, caplog):
    nm = NetworkManager()
    connect = MagicMock(side_effect=[(False, 'timed out'), (True, 'connected')])
    monkeypatch.setattr(nm, 'connect_to_server', connect)
    progress = MagicMock()
    with caplog.at_level('INFO', logger='dnd.local'):
        ok, _ = nm.connect_to_candidates(['10.0.0.1', '192.168.1.2'], 12345, object(), CODE, progress=progress)
    assert ok
    assert [c.args[0] for c in connect.call_args_list] == ['10.0.0.1', '192.168.1.2']
    assert connect.call_args.kwargs['connect_timeout'] == 2
    assert CODE not in caplog.text
    assert progress.call_count == 2


def test_cancelled_attempt_does_not_retry(monkeypatch):
    nm = NetworkManager()
    stopped = False
    def first(*args, **kwargs):
        nonlocal stopped
        stopped = True
        return False, 'timed out'
    connect = MagicMock(side_effect=first)
    monkeypatch.setattr(nm, 'connect_to_server', connect)
    ok, msg = nm.connect_to_candidates(['10.0.0.1', '10.0.0.2'], 12345, object(), CODE, cancelled=lambda: stopped)
    assert not ok and 'abgebrochen' in msg
    connect.assert_called_once()


def test_cancel_during_socket_connect_sends_no_handshake(monkeypatch):
    import core.network_manager as module
    nm = NetworkManager()
    stopped = False
    sock = MagicMock()
    def connect(*args, **kwargs):
        nonlocal stopped
        stopped = True
        return sock
    monkeypatch.setattr(module.socket, 'create_connection', connect)
    send = MagicMock()
    monkeypatch.setattr(module.wire, 'send_message', send)
    ok, msg = nm.connect_to_server('192.168.1.1', 12345, object(), join_code=CODE, cancelled=lambda: stopped)
    assert not ok and nm.mode == 'idle'
    send.assert_not_called()
    sock.close.assert_called_once()


def test_real_tcp_fallback_reaches_correct_host(monkeypatch):
    monkeypatch.setattr(NetworkManager, '_advertise', lambda *args: None)
    host, client = NetworkManager(), NetworkManager()
    try:
        assert host.start_server(host='127.0.0.1', port=0)[0]
        char = Character('Netztest', 'Mensch', 'Kämpfer')
        ok, message = client.connect_to_candidates(['127.0.0.2', '127.0.0.1'], host.port, char, host.join_code)
        assert ok, message
        assert client.mode == 'client' and client.running
        event, data = host.incoming_messages.get(timeout=3)
        assert event == 'PLAYER_JOINED' and data['char'].character_id == char.character_id
    finally:
        client.shutdown()
        host.shutdown()


def test_discovery_keeps_all_lan_addresses_and_current_protocol():
    from ui.player_lobby_screen import build_entry
    info = SimpleNamespace(properties={b'proto': str(PROTOCOL).encode(), b'name': b'Game'}, port=5000,
                           parsed_addresses=lambda: ['10.0.0.2', '192.168.1.3', '8.8.8.8', '::1'])
    assert build_entry(info)['addresses'] == ['10.0.0.2', '192.168.1.3']
    info.properties[b'proto'] = b'3'  # 0.5.7 advertises 3 despite speaking protocol 4
    assert build_entry(info) is not None


def test_selecting_discovered_host_clears_old_qr_endpoint():
    from ui.player_lobby_screen import PlayerLobbyScreen
    screen = object.__new__(PlayerLobbyScreen)
    screen._qr_candidates = (['10.0.0.2'], 1234)
    screen.ids = SimpleNamespace(manual_input=SimpleNamespace(text='10.0.0.2:1234'))
    screen._rebuild_list = MagicMock()
    screen.select_dm('new')
    assert screen.ids.manual_input.text == ''
    assert screen._qr_candidates is None and screen.selected_key == 'new'


def test_qr_preserves_secondary_addresses_for_connect(monkeypatch):
    import ui.player_lobby_screen as module
    screen = object.__new__(module.PlayerLobbyScreen)
    screen._connecting = False
    screen._connect_token = 0
    screen.selected_char_file = 'test.char'
    screen.ids = SimpleNamespace(manual_input=SimpleNamespace(text=''), join_code_input=SimpleNamespace(text=''),
                                 status_label=SimpleNamespace(text=''), connect_button=SimpleNamespace(disabled=False))
    payload = make_join_payload('192.168.4.22', 45555, CODE, ['10.50.0.2'])
    assert screen.accept_join_qr(payload)
    thread = MagicMock()
    monkeypatch.setattr(module.threading, 'Thread', thread)
    screen.connect_to_dm()
    assert thread.call_args.kwargs['args'][2] == ['192.168.4.22', '10.50.0.2']


def test_firewall_scripts_are_app_scoped_and_quote_paths():
    program = "C:\\Users\\O'Neil\\DnDLocal.exe"
    read = firewall_script(program)
    change = firewall_script(program, configure=True)
    assert "O''Neil" in read and "O''Neil" in change
    assert 'New-NetFirewallRule' not in read and 'Remove-NetFirewallRule' not in read
    assert "RemoteAddress='LocalSubnet'" in change and "Profile='Any'" in change
    assert 'Set-NetFirewallProfile' not in change
    assert "Where-Object { $_.Program -ieq $program }" in change
    assert "$_.Direction -eq 'Inbound' -and $_.Action -eq 'Block'" in change
    assert 'PolicyStore PersistentStore' in change
    assert rule_names(program) != rule_names('C:\\Elsewhere\\DnDLocal.exe')
    assert rule_names(program) == rule_names(program.upper())


@pytest.mark.parametrize('program', ['python.exe', r'C:\Apps\python.exe', r'C:\Apps\EvilDnDLocal.exe', 'DnDLocal.exe'])
def test_firewall_rejects_generic_or_relative_executables(program):
    with pytest.raises(ValueError):
        firewall_script(program, configure=True)


def test_source_run_never_offers_or_changes_windows_firewall(monkeypatch):
    from utils import windows_network as module
    monkeypatch.setattr(module, 'supported', lambda: False)
    run = MagicMock()
    monkeypatch.setattr(module, '_powershell', run)
    assert module.firewall_status()['supported'] is False
    assert module.request_firewall_setup() == 'unsupported'
    assert module.apply_firewall_rules() == 2
    run.assert_not_called()


def test_firewall_read_failure_is_unknown_not_success(monkeypatch):
    from utils import windows_network as module
    monkeypatch.setattr(module, 'supported', lambda: True)
    monkeypatch.setattr(module.sys, 'executable', r'C:\Apps\DnDLocal.exe')
    monkeypatch.setattr(module, '_powershell', lambda script: SimpleNamespace(returncode=1, stdout=''))
    report = module.firewall_status()
    assert report['unknown'] and not report['configured']


def test_firewall_powershell_behavior_without_changing_os(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path
    if sys.platform != 'win32':
        pytest.skip('Windows PowerShell verification')
    program = "C:\\Users\\O'Neil\\DnDLocal.exe"
    configure = tmp_path / 'configure.ps1'
    read = tmp_path / 'read.ps1'
    configure.write_text(firewall_script(program, configure=True), encoding='utf-8-sig')
    read.write_text(firewall_script(program), encoding='utf-8-sig')
    executable = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    result = subprocess.run([str(executable), '-NoProfile', '-NonInteractive', '-File',
                             str(Path(__file__).with_name('firewall_mock.ps1')),
                             '-ConfigureFile', str(configure), '-ReadFile', str(read)],
                            capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS:' in result.stdout


@pytest.mark.parametrize('output,expected', [('{"configured":true}', 0), ('{"configured":false}', 1), ('invalid', 1)])
def test_elevated_helper_only_succeeds_after_effective_rules_verified(monkeypatch, output, expected):
    import ctypes
    from utils import windows_network as module
    monkeypatch.setattr(module, 'supported', lambda: True)
    monkeypatch.setattr(module.sys, 'executable', r'C:\Apps\DnDLocal.exe')
    monkeypatch.setattr(ctypes, 'windll', SimpleNamespace(shell32=SimpleNamespace(IsUserAnAdmin=lambda: True)), raising=False)
    run = MagicMock(return_value=SimpleNamespace(returncode=0, stdout=output))
    monkeypatch.setattr(module, '_powershell', run)
    assert module.apply_firewall_rules() == expected
    assert 'ConvertTo-Json' in run.call_args.args[0]


def test_stale_preflight_cannot_start_host_or_skip_next_check(monkeypatch):
    import ui.network_help as module
    screen = SimpleNamespace(app=SimpleNamespace(), network_manager=object(), _enter_gen=1,
                             manager=SimpleNamespace(current='dm_lobby'))
    monkeypatch.setattr(module.windows_network, 'supported', lambda: True)
    monkeypatch.setattr(module.windows_network, 'firewall_status', lambda: {'configured': True})
    callbacks = []
    monkeypatch.setattr(module.Clock, 'schedule_once', lambda fn: callbacks.append(fn))
    monkeypatch.setattr(module.threading, 'Thread', lambda target, **kwargs: SimpleNamespace(start=target))
    start = MagicMock()
    module.prepare_host(screen, start)
    start.assert_not_called()
    screen._enter_gen += 1
    callbacks.pop()(0)
    start.assert_not_called()
    assert not getattr(screen.app, '_network_setup_checked', False)
    module.prepare_host(screen, start)
    callbacks.pop()(0)
    start.assert_called_once()
