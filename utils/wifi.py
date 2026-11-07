"""Linux WiFi helpers based on nmcli.

Parsing functions are pure (no I/O) so they can be unit tested.
Passwords are never logged and never included in error messages.
"""
import subprocess
import sys
import threading

DEFAULT_TIMEOUT = 15
SCAN_TIMEOUT = 30
CONNECT_TIMEOUT = 45


class WifiError(Exception):
    """User-presentable WiFi error. Never contains secrets."""


def split_terse(line):
    """Split one nmcli -t line on unescaped ':'; handle '\\:' and '\\\\'."""
    fields = []
    cur = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '\\' and i + 1 < len(line):
            cur.append(line[i + 1])
            i += 2
            continue
        if ch == ':':
            fields.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    fields.append(''.join(cur))
    return fields


def parse_signal(value):
    """Convert a signal value to an int clamped to 0..100 (0 if invalid)."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, number))


def is_hidden(ssid):
    return ssid is None or ssid.strip() in ('', '--')


def parse_scan_output(output):
    """Parse `nmcli -t -f SSID,SIGNAL dev wifi list` into [(ssid, signal)].

    Empty/hidden entries and malformed lines are skipped, duplicates keep the
    strongest signal, result is sorted by signal (descending).
    """
    best = {}
    for line in (output or '').splitlines():
        if not line.strip():
            continue
        fields = split_terse(line)
        if len(fields) < 2:
            continue
        ssid = fields[0]
        if is_hidden(ssid):
            continue
        signal = parse_signal(fields[1])
        if ssid not in best or signal > best[ssid]:
            best[ssid] = signal
    return sorted(best.items(), key=lambda item: (-item[1], item[0]))


def parse_status_output(output):
    """Parse `nmcli -t -f ACTIVE,SSID,SIGNAL dev wifi`.

    Returns (ssid, signal) of the active network or None.
    """
    for line in (output or '').splitlines():
        if not line.strip():
            continue
        fields = split_terse(line)
        if len(fields) < 3:
            continue
        if fields[0].strip().lower() == 'yes' and not is_hidden(fields[1]):
            return fields[1], parse_signal(fields[2])
    return None


def _redact(text, secrets):
    for secret in secrets:
        if secret:
            text = text.replace(secret, '***')
    return text


def run_command(cmd, timeout=DEFAULT_TIMEOUT, secrets=()):
    """Run a command with timeout; raise WifiError with a redacted message."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, check=False)
    except FileNotFoundError:
        raise WifiError("nmcli was not found. Please install NetworkManager.")
    except subprocess.TimeoutExpired:
        raise WifiError("The WiFi command timed out.")
    except OSError:
        raise WifiError("The WiFi command could not be executed.")
    if proc.returncode != 0:
        message = _redact((proc.stderr or '').strip(), secrets)
        if not message:
            message = "nmcli failed (exit code %s)." % proc.returncode
        raise WifiError(message[:200])
    return proc.stdout or ''


def get_status():
    """Return (ssid or None, signal int). ('N/A', None) on non-Linux."""
    if not sys.platform.startswith('linux'):
        return 'N/A', None
    out = run_command(['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL', 'dev', 'wifi'],
                      timeout=DEFAULT_TIMEOUT)
    status = parse_status_output(out)
    if status is None:
        return None, 0
    return status


def scan():
    """Return list of (ssid, signal)."""
    if not sys.platform.startswith('linux'):
        raise WifiError("WiFi scanning is only available on Linux.")
    out = run_command(['nmcli', '-t', '-f', 'SSID,SIGNAL', 'dev', 'wifi', 'list',
                       '--rescan', 'yes'], timeout=SCAN_TIMEOUT)
    return parse_scan_output(out)


def connect(ssid, password=None):
    """Connect to a network. The password is never logged or reported."""
    if not sys.platform.startswith('linux'):
        raise WifiError("WiFi is only available on Linux.")
    if is_hidden(ssid):
        raise WifiError("Invalid network name.")
    cmd = ['nmcli', 'dev', 'wifi', 'connect', ssid]
    if password:
        cmd.extend(['password', password])
    run_command(cmd, timeout=CONNECT_TIMEOUT, secrets=[password])
    return True


def run_in_background(func, callback, *args):
    """Run func(*args) in a daemon thread; call callback(result, error_text).

    The callback runs in the worker thread; UI code must marshal to the main
    thread itself (e.g. with Clock.schedule_once).
    """
    def worker():
        result, error = None, None
        try:
            result = func(*args)
        except WifiError as exc:
            error = str(exc)
        except Exception:
            error = "Unexpected WiFi error."
        callback(result, error)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread
