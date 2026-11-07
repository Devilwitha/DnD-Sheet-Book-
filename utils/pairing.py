"""Shared pairing helpers: 64-bit codes, HMAC proofs, failure throttle, TCP keepalive. Stdlib only."""
import hashlib
import hmac
import secrets
import socket
import threading
import time

MAX_FAILURES = 10
COOLDOWN = 30.0
KEEPALIVE_IDLE = 10
KEEPALIVE_INTERVAL = 2
KEEPALIVE_COUNT = 10  # idle + interval*count = ~30s (Windows fixes count at 10)
_HEX_UPPER = frozenset('0123456789ABCDEF')
_HEX_LOWER = frozenset('0123456789abcdef')


def generate_code():
    return secrets.token_hex(8).upper()


def normalize_code(code):
    if not isinstance(code, str) or len(code) > 64 or not code.isascii():
        return ''
    return ''.join(c for c in code if c != '-' and not c.isspace()).upper()


def valid_code16hex(code):
    return isinstance(code, str) and len(code) == 16 and all(c in _HEX_UPPER for c in code)


def new_nonce():
    return secrets.token_hex(16)


def valid_nonce(nonce):
    return isinstance(nonce, str) and len(nonce) == 32 and all(c in _HEX_LOWER for c in nonce)


def proof(code, context, role, first_nonce, second_nonce):
    """HMAC-SHA256 over context, role and both nonces (first=challenger, second=responder)."""
    code = normalize_code(code)
    if not valid_code16hex(code) or not valid_nonce(first_nonce) or not valid_nonce(second_nonce):
        raise ValueError('invalid pairing input')
    msg = b'|'.join((b'dnd-pairing-v1', context.encode('ascii'), role.encode('ascii'),
                     bytes.fromhex(first_nonce), bytes.fromhex(second_nonce)))
    return hmac.new(code.encode('ascii'), msg, hashlib.sha256).hexdigest()


def verify(expected, got):
    return (isinstance(got, str) and len(got) == 64 and got.isascii()
            and hmac.compare_digest(expected.encode('ascii'), got.encode('ascii')))


class FailureLimiter:
    """Total failures per generation; max_failures triggers a bounded cooldown, then resets."""

    def __init__(self, max_failures=MAX_FAILURES, cooldown=COOLDOWN, clock=time.monotonic):
        self.max_failures = max_failures
        self.cooldown = cooldown
        self.clock = clock
        self._lock = threading.Lock()
        self._count = 0
        self._until = None

    def blocked(self):
        with self._lock:
            if self._until is None:
                return False
            if self.clock() < self._until:
                return True
            self._until = None
            self._count = 0
            return False

    def failure(self):
        with self._lock:
            if self._until is not None:
                return
            self._count += 1
            if self._count >= self.max_failures:
                self._until = self.clock() + self.cooldown


def enable_keepalive(sock, idle=KEEPALIVE_IDLE, interval=KEEPALIVE_INTERVAL, count=KEEPALIVE_COUNT):
    """Best-effort TCP keepalive so half-open peers are detected in ~30s. Returns True if enabled."""
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except (OSError, ValueError):
        return False
    try:
        if hasattr(socket, 'SIO_KEEPALIVE_VALS') and hasattr(sock, 'ioctl'):
            sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, int(idle * 1000), int(interval * 1000)))
            return True
    except (OSError, ValueError, AttributeError):
        pass
    opts = (('TCP_KEEPIDLE', idle), ('TCP_KEEPINTVL', interval), ('TCP_KEEPCNT', count))
    if not hasattr(socket, 'TCP_KEEPIDLE') and hasattr(socket, 'TCP_KEEPALIVE'):
        opts = (('TCP_KEEPALIVE', idle),) + opts[1:]
    for name, val in opts:
        opt = getattr(socket, name, None)
        if opt is None:
            continue
        try:
            sock.setsockopt(socket.IPPROTO_TCP, opt, int(val))
        except (OSError, ValueError):
            pass
    return True
