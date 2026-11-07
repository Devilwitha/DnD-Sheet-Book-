"""App-scoped Windows LAN permission. Reads are separate from explicit setup."""
import base64
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import threading

_setup_lock = threading.Lock()


def supported():
    return sys.platform == 'win32' and bool(getattr(sys, 'frozen', False))


def _quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def rule_names(program):
    digest = hashlib.sha256(str(program).casefold().encode('utf-8')).hexdigest()[:12]
    return [f'DnDLocal-LAN-{digest}-TCP', f'DnDLocal-LAN-{digest}-mDNS']


def firewall_script(program, *, configure=False):
    """Only our executable and own rule IDs are interpolated; no user command text."""
    program = str(program)
    if not PureWindowsPath(program).is_absolute() or PureWindowsPath(program).name.casefold() != 'dndlocal.exe':
        raise ValueError('Freigabe ist ausschließlich für DnDLocal.exe vorgesehen.')
    tcp, udp = map(_quote, rule_names(program))
    start = f"""$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$program = {_quote(program)}
$ProgressPreference = 'SilentlyContinue'
$tcpName = {tcp}
$udpName = {udp}
"""
    if configure:
        return start + """
foreach ($entry in @(@($tcpName, 'TCP', 'Any'), @($udpName, 'UDP', '5353'))) {
    $params = @{Name=$entry[0]; DisplayName=('DnD Lokal - lokales Spiel (' + $entry[1] + ')');
        Group='DnD Lokal - LAN'; Program=$program; Direction='Inbound'; Action='Allow';
        Enabled='True'; Protocol=$entry[1]; LocalPort=$entry[2]; RemoteAddress='LocalSubnet';
        Profile='Any'; EdgeTraversalPolicy='Block'; PolicyStore='PersistentStore'}
    if (Get-NetFirewallRule -Name $entry[0] -PolicyStore PersistentStore -ErrorAction SilentlyContinue) {
        $params.Remove('DisplayName')
        $params.Remove('Group')
        Set-NetFirewallRule @params | Out-Null
    } else {
        New-NetFirewallRule @params | Out-Null
    }
}
# Replace only local inbound blocks for this exact application, after creating scoped rules.
$filters = @(Get-NetFirewallApplicationFilter -PolicyStore PersistentStore |
    Where-Object { $_.Program -ieq $program })
foreach ($filter in $filters) {
    $rules = @($filter | Get-NetFirewallRule | Where-Object { $_.Direction -eq 'Inbound' -and $_.Action -eq 'Block' })
    foreach ($rule in $rules) {
        Remove-NetFirewallRule -Name $rule.Name -PolicyStore PersistentStore
    }
}
"""
    return start + """
$rules = @(Get-NetFirewallRule -PolicyStore ActiveStore -Name $tcpName,$udpName -ErrorAction SilentlyContinue)
$ready = 0
foreach ($rule in $rules) {
    $app = $rule | Get-NetFirewallApplicationFilter
    $address = $rule | Get-NetFirewallAddressFilter
    $port = $rule | Get-NetFirewallPortFilter
    $portOK = ($rule.Name -eq $tcpName -and $port.Protocol -eq 'TCP' -and $port.LocalPort -eq 'Any') -or
              ($rule.Name -eq $udpName -and $port.Protocol -eq 'UDP' -and $port.LocalPort -eq '5353')
    if ($app.Program -ieq $program -and $rule.Enabled -eq 'True' -and $rule.Direction -eq 'Inbound' -and
        $rule.Action -eq 'Allow' -and [string]$rule.Profile -eq 'Any' -and
        [string]$address.RemoteAddress -eq 'LocalSubnet' -and $portOK) { $ready++ }
}
$blocks = @(Get-NetFirewallApplicationFilter -PolicyStore ActiveStore |
    Where-Object { $_.Program -ieq $program } | Get-NetFirewallRule |
    Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Block' })
$activeNames = @(Get-NetConnectionProfile | ForEach-Object {
    if ($_.NetworkCategory -eq 'DomainAuthenticated') { 'Domain' } else { [string]$_.NetworkCategory } })
$policyBlocks = @(Get-NetFirewallProfile -PolicyStore ActiveStore | Where-Object {
    [string]$_.Name -in $activeNames -and $_.Enabled -eq 'True' -and
    ($_.AllowInboundRules -eq 'False' -or $_.AllowLocalFirewallRules -eq 'False') })
[pscustomobject]@{configured=($ready -eq 2 -and $blocks.Count -eq 0 -and $policyBlocks.Count -eq 0);
    app_blocks=$blocks.Count; policy_blocks=$policyBlocks.Count} | ConvertTo-Json -Compress
"""


def _powershell(script):
    executable = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    return subprocess.run([str(executable), '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                          capture_output=True, encoding='utf-8', errors='replace', timeout=25,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def firewall_status():
    if not supported():
        return {'supported': False, 'configured': False}
    try:
        result = _powershell(firewall_script(sys.executable))
        if result.returncode:
            return {'supported': True, 'configured': False, 'unknown': True}
        data = json.loads(result.stdout.lstrip('\ufeff').strip())
        from utils.diagnostics import logger
        logger.info('firewall_check configured=%s app_blocks=%s policy_blocks=%s',
                    data.get('configured'), data.get('app_blocks'), data.get('policy_blocks'))
        return dict(data, supported=True)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {'supported': True, 'configured': False, 'unknown': True}


def apply_firewall_rules():
    """Entry point of the separately elevated installed app; never runs during normal startup."""
    if not supported():
        return 2
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        return 2
    try:
        result = _powershell(firewall_script(sys.executable, configure=True) + firewall_script(sys.executable))
        if result.returncode:
            return 1
        report = json.loads(result.stdout.lstrip('\ufeff').strip())
        return 0 if report.get('configured') is True else 1
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 1


def request_firewall_setup():
    """Called only by the user's setup button; Windows owns the elevation prompt."""
    if not supported():
        return 'unsupported'
    if not _setup_lock.acquire(blocking=False):
        return 'busy'
    try:
        import ctypes
        from ctypes import wintypes as w
        class ExecuteInfo(ctypes.Structure):
            _fields_ = [('cbSize', w.DWORD), ('fMask', w.ULONG), ('hwnd', w.HWND),
                        ('lpVerb', w.LPCWSTR), ('lpFile', w.LPCWSTR), ('lpParameters', w.LPCWSTR),
                        ('lpDirectory', w.LPCWSTR), ('nShow', ctypes.c_int), ('hInstApp', w.HINSTANCE),
                        ('lpIDList', ctypes.c_void_p), ('lpClass', w.LPCWSTR), ('hkeyClass', w.HKEY),
                        ('dwHotKey', w.DWORD), ('hIcon', w.HANDLE), ('hProcess', w.HANDLE)]
        shell = ctypes.WinDLL('shell32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ExecuteInfo)]
        shell.ShellExecuteExW.restype = w.BOOL
        kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        kernel.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
        kernel.CloseHandle.argtypes = [w.HANDLE]
        info = ExecuteInfo()
        info.cbSize = ctypes.sizeof(info)
        info.fMask = 0x40  # SEE_MASK_NOCLOSEPROCESS
        info.lpVerb, info.lpFile, info.lpParameters = 'runas', sys.executable, '--configure-lan'
        info.nShow = 0
        if not shell.ShellExecuteExW(ctypes.byref(info)):
            return 'cancelled' if ctypes.get_last_error() == 1223 else 'failed'
        try:
            if kernel.WaitForSingleObject(info.hProcess, 0xFFFFFFFF) != 0:
                return 'failed'
            exit_code = w.DWORD(1)
            if not kernel.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code)):
                return 'failed'
            return 'success' if exit_code.value == 0 else 'failed'
        finally:
            kernel.CloseHandle(info.hProcess)
    finally:
        _setup_lock.release()
