"""Standalone bounded LAN file transfer (4-byte BE length + JSON frames). No Kivy, no zeroconf."""
import base64
import hashlib
import hmac
import json
import secrets
import socket
import struct
import time
from pathlib import Path

from utils import pairing

MAX_FRAME = 256 * 1024
MAX_FILE = 8 * 1024 * 1024
MAX_FILES = 16
MAX_TOTAL = 32 * 1024 * 1024
CHUNK = 48 * 1024
IDLE_TIMEOUT = 30.0
MAX_ATTEMPTS = 5
DEFAULT_PORT = 65432
MAX_DIM = 8192
MAX_PIXELS = 16 * 1024 * 1024
KINDS = {'characters': '.char', 'maps': '.json', 'enemies': '.enemies', 'sessions': '.json'}
_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
_PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


class TransferError(Exception):
    pass


class ProtocolError(TransferError):
    pass


class PairingError(TransferError):
    pass


class PayloadError(TransferError):
    pass


class TransferTimeout(TransferError):
    pass


class TransferClosed(TransferError):
    pass


class TransferCancelled(TransferError):
    pass


class Payload:
    def __init__(self, kind, data):
        self.kind = kind
        self.data = data


def friendly_message(exc):
    if isinstance(exc, PairingError):
        return 'Falscher Code oder nicht authentifizierte Gegenstelle. Bitte den 16-stelligen Code prüfen.'
    if isinstance(exc, TransferTimeout):
        return 'Zeitüberschreitung: Die Gegenstelle antwortet nicht mehr.'
    if isinstance(exc, TransferClosed):
        return 'Verbindung wurde unterbrochen. Nichts wurde gespeichert.'
    if isinstance(exc, TransferCancelled):
        return 'Übertragung abgebrochen.'
    if isinstance(exc, PayloadError):
        return 'Ungültige oder beschädigte Daten. Nichts wurde gespeichert.'
    if isinstance(exc, ProtocolError):
        return 'Ungültige Antwort der Gegenstelle. Nichts wurde gespeichert.'
    if isinstance(exc, OSError):
        return 'Netzwerk- oder Dateifehler.'
    return 'Übertragung fehlgeschlagen.'


def generate_code():
    return pairing.generate_code()


def normalize_code(code):
    return pairing.normalize_code(code)


def valid_code(code):
    return pairing.valid_code16hex(code)


def parse_endpoint(text, default_port=DEFAULT_PORT):
    text = (text or '').strip()
    host, port = text, default_port
    if text.count(':') == 1:
        host, p = text.split(':')
        if not p.isascii() or not p.isdigit():
            raise ValueError('port')
        port = int(p)
    if not host or len(host) > 255 or any(c.isspace() for c in host) or not 0 < port < 65536:
        raise ValueError('endpoint')
    return host, port


def _storage():
    import utils.storage as st
    return st


def _is_hex(s, n):
    return isinstance(s, str) and len(s) == n and all(c in '0123456789abcdef' for c in s)


def _check(stop):
    if stop is not None and stop.is_set():
        raise TransferCancelled('cancelled')


def encode_frame(obj):
    body = json.dumps(obj, separators=(',', ':')).encode('utf-8')
    if not 0 < len(body) <= MAX_FRAME:
        raise ProtocolError('frame size')
    return struct.pack('>I', len(body)) + body


def send_frame(sock, obj, stop=None, idle=IDLE_TIMEOUT):
    view = memoryview(encode_frame(obj))
    last = time.monotonic()
    sock.settimeout(0.5)
    while len(view):
        _check(stop)
        try:
            n = sock.send(view)
        except socket.timeout:
            if time.monotonic() - last > idle:
                raise TransferTimeout('idle')
            continue
        except OSError as e:
            raise TransferClosed(str(e))
        if n == 0:
            raise TransferClosed('closed')
        view = view[n:]
        last = time.monotonic()


def _recv_exact(sock, n, stop, idle):
    buf = bytearray()
    last = time.monotonic()
    sock.settimeout(0.5)
    while len(buf) < n:
        _check(stop)
        try:
            part = sock.recv(n - len(buf))
        except socket.timeout:
            if time.monotonic() - last > idle:
                raise TransferTimeout('idle')
            continue
        except OSError as e:
            raise TransferClosed(str(e))
        if not part:
            raise TransferClosed('eof')
        buf += part
        last = time.monotonic()
    return bytes(buf)


def recv_frame(sock, stop=None, idle=IDLE_TIMEOUT):
    (n,) = struct.unpack('>I', _recv_exact(sock, 4, stop, idle))
    if not 0 < n <= MAX_FRAME:
        raise ProtocolError('frame length')
    body = _recv_exact(sock, n, stop, idle)
    try:
        obj = _storage().parse_json_bytes(body, MAX_FRAME)
    except (ValueError, RecursionError):
        raise ProtocolError('bad json')
    if not isinstance(obj, dict):
        raise ProtocolError('not object')
    return obj


def _expect(frame, typ, keys, preauth=False):
    if frame.get('type') == 'error' and set(frame) == {'type', 'reason'}:
        if frame.get('reason') == 'pairing':
            raise PairingError('remote pairing')
        if preauth:
            raise ProtocolError('remote error before authentication')
        raise PayloadError('remote rejected')
    if frame.get('type') != typ or set(frame) != keys:
        raise ProtocolError('unexpected frame')
    return frame


def _mac(code, role, ns, nr):
    return pairing.proof(code, 'file', role, ns, nr)


def _check_payloads(payloads):
    if not 1 <= len(payloads) <= MAX_FILES:
        raise PayloadError('count')
    total = 0
    for p in payloads:
        if p.kind not in KINDS or not isinstance(p.data, bytes) or not 0 < len(p.data) <= MAX_FILE:
            raise PayloadError('payload')
        total += len(p.data)
    if total > MAX_TOTAL:
        raise PayloadError('total')


def prepare_payloads(items, storage=None):
    """Validate (kind, bytes) items into canonical Payloads. Nothing is written."""
    st = storage or _storage()
    out = []
    for kind, data in items:
        if kind not in KINDS or not isinstance(data, bytes) or len(data) > MAX_FILE:
            raise PayloadError('payload')
        try:
            out.append(Payload(kind, bytes(st.validate_transfer(kind, data))))
        except Exception as e:
            raise PayloadError('invalid') from e
    _check_payloads(out)
    return out


def _parse_manifest(frame):
    files, count = frame['files'], frame['count']
    if type(count) is not int or not isinstance(files, list) or count != len(files) or not 1 <= count <= MAX_FILES:
        raise ProtocolError('manifest count')
    total = 0
    out = []
    for f in files:
        if not isinstance(f, dict) or set(f) != {'kind', 'length', 'sha256'}:
            raise ProtocolError('manifest schema')
        k, n, h = f['kind'], f['length'], f['sha256']
        if not isinstance(k, str) or k not in KINDS or type(n) is not int or not 0 < n <= MAX_FILE or not _is_hex(h, 64):
            raise ProtocolError('manifest entry')
        total += n
        out.append({'kind': k, 'length': n, 'sha256': h})
    if total > MAX_TOTAL:
        raise ProtocolError('manifest total')
    return out


def send_payloads(sock, payloads, code, stop=None):
    code = pairing.normalize_code(code)
    if not valid_code(code):
        raise PairingError('code')
    _check_payloads(payloads)
    ns = pairing.new_nonce()
    send_frame(sock, {'type': 'challenge', 'nonce': ns}, stop)
    auth = _expect(recv_frame(sock, stop), 'auth', {'type', 'nonce', 'mac'}, True)
    nr = auth['nonce']
    if not _is_hex(nr, 32) or not pairing.verify(_mac(code, 'receiver', ns, nr), auth['mac']):
        try:
            send_frame(sock, {'type': 'error', 'reason': 'pairing'}, stop)
        except TransferError:
            pass
        raise PairingError('wrong code')
    send_frame(sock, {'type': 'ok', 'mac': _mac(code, 'sender', ns, nr)}, stop)
    files = [{'kind': p.kind, 'length': len(p.data), 'sha256': hashlib.sha256(p.data).hexdigest()} for p in payloads]
    send_frame(sock, {'type': 'manifest', 'count': len(files), 'files': files}, stop)
    for i, p in enumerate(payloads):
        for off in range(0, len(p.data), CHUNK):
            b64 = base64.b64encode(p.data[off:off + CHUNK]).decode('ascii')
            send_frame(sock, {'type': 'chunk', 'i': i, 'data': b64}, stop)
    send_frame(sock, {'type': 'end'}, stop)
    _expect(recv_frame(sock, stop), 'done', {'type'})


def receive_payloads(sock, code, stop=None, storage=None):
    """Receive and fully validate all payloads in memory. Returns canonical Payloads."""
    st = storage or _storage()
    code = pairing.normalize_code(code)
    if not valid_code(code):
        raise PairingError('code')
    ch = _expect(recv_frame(sock, stop), 'challenge', {'type', 'nonce'}, True)
    ns = ch['nonce']
    if not _is_hex(ns, 32):
        raise ProtocolError('nonce')
    nr = pairing.new_nonce()
    send_frame(sock, {'type': 'auth', 'nonce': nr, 'mac': _mac(code, 'receiver', ns, nr)}, stop)
    ok = _expect(recv_frame(sock, stop), 'ok', {'type', 'mac'}, True)
    if not pairing.verify(_mac(code, 'sender', ns, nr), ok['mac']):
        raise PairingError('sender not authenticated')
    metas = _parse_manifest(_expect(recv_frame(sock, stop), 'manifest', {'type', 'count', 'files'}))
    raw = []
    for i, m in enumerate(metas):
        buf = bytearray()
        while len(buf) < m['length']:
            fr = _expect(recv_frame(sock, stop), 'chunk', {'type', 'i', 'data'})
            d = fr['data']
            if type(fr['i']) is not int or fr['i'] != i or not isinstance(d, str) or not 0 < len(d) <= 4 * ((CHUNK + 2) // 3):
                raise ProtocolError('chunk')
            try:
                part = base64.b64decode(d.encode('ascii'), validate=True)
            except ValueError:
                raise ProtocolError('base64')
            if not 0 < len(part) <= CHUNK or len(buf) + len(part) > m['length']:
                raise ProtocolError('chunk size')
            buf += part
        if not hmac.compare_digest(hashlib.sha256(bytes(buf)).hexdigest(), m['sha256']):
            raise PayloadError('checksum')
        raw.append(bytes(buf))
    _expect(recv_frame(sock, stop), 'end', {'type'})
    out = []
    for m, data in zip(metas, raw):
        try:
            out.append(Payload(m['kind'], bytes(st.validate_transfer(m['kind'], data))))
        except Exception as e:
            raise PayloadError('invalid') from e
    return out


def _reserve(st, folder, suffix):
    for _ in range(8):
        dest = Path(st.unique_import_path(folder, suffix))
        try:
            with open(dest, 'xb'):
                pass
            return dest
        except FileExistsError:
            continue
    raise TransferError('no free name')


def publish_batch(items, folder_for, storage=None):
    """Exclusively create new local-UUID files; on any error remove only files created here."""
    st = storage or _storage()
    created = []
    try:
        for p in items:
            folder = Path(folder_for(p.kind))
            folder.mkdir(parents=True, exist_ok=True)
            dest = _reserve(st, folder, KINDS[p.kind])
            created.append(dest)
            st.atomic_write_bytes(dest, p.data)
    except BaseException:
        for d in reversed(created):
            try:
                d.unlink()
            except OSError:
                pass
        raise
    return created


def receive_and_store(sock, code, folder_for, stop=None, storage=None):
    st = storage or _storage()
    try:
        paths = publish_batch(receive_payloads(sock, code, stop, st), folder_for, st)
    except TransferCancelled:
        raise
    except (TransferError, OSError) as e:
        try:
            send_frame(sock, {'type': 'error', 'reason': 'pairing' if isinstance(e, PairingError) else 'invalid'}, stop)
        except Exception:
            pass
        raise
    try:
        send_frame(sock, {'type': 'done'}, stop)
    except TransferError:
        pass
    return paths


def serve_once(payloads, code, stop=None, port=DEFAULT_PORT, on_ready=None, accept_timeout=120.0, bind_host='0.0.0.0'):
    _check_payloads(payloads)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((bind_host, port))
        srv.listen(1)
        srv.settimeout(0.5)
        if on_ready:
            on_ready(srv.getsockname()[1])
        deadline = time.monotonic() + accept_timeout
        attempts = 0
        while True:
            _check(stop)
            if time.monotonic() > deadline:
                raise TransferTimeout('no peer')
            try:
                conn, _addr = srv.accept()
            except socket.timeout:
                continue
            pairing.enable_keepalive(conn)
            with conn:
                try:
                    send_payloads(conn, payloads, code, stop)
                    return
                except (PairingError, TransferClosed, ProtocolError, TransferTimeout):
                    attempts += 1
                    if attempts >= MAX_ATTEMPTS:
                        raise
    finally:
        srv.close()


def connect_and_receive(host, port, code, folder_for, stop=None, storage=None):
    try:
        sock = socket.create_connection((host, port), timeout=10)
    except OSError as e:
        raise TransferClosed('connect failed') from e
    pairing.enable_keepalive(sock)
    with sock:
        return receive_and_store(sock, code, folder_for, stop, storage)


def _jpeg_size(data):
    n = len(data)
    i = 2
    while i + 4 <= n:
        if data[i] != 0xFF:
            raise PayloadError('jpeg')
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            break
        m = data[i]
        i += 1
        if m == 0x01 or 0xD0 <= m <= 0xD8:
            continue
        if m in (0xD9, 0xDA) or i + 2 > n:
            break
        ln = (data[i] << 8) | data[i + 1]
        if ln < 2:
            raise PayloadError('jpeg')
        if m in _SOF and i + 7 <= n:
            return (data[i + 5] << 8) | data[i + 6], (data[i + 3] << 8) | data[i + 4]
        i += ln
    raise PayloadError('jpeg dimensions')


def image_extension(data):
    """Bounded pure-Python PNG/JPEG header check. Returns '.png' or '.jpg'."""
    if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_FILE:
        raise PayloadError('image')
    data = bytes(data)
    if len(data) >= 24 and data[:8] == _PNG and data[12:16] == b'IHDR':
        w, h = struct.unpack('>II', data[16:24])
        ext = '.png'
    elif data[:3] == bytes([0xFF, 0xD8, 0xFF]):
        w, h = _jpeg_size(data)
        ext = '.jpg'
    else:
        raise PayloadError('image type')
    if not (0 < w < MAX_DIM and 0 < h < MAX_DIM and w * h < MAX_PIXELS):
        raise PayloadError('image size')
    return ext
