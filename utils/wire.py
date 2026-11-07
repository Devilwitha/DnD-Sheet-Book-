import ipaddress
import json
import select
import socket
import struct
import time

from utils.pairing import enable_keepalive  # noqa: F401  (re-exported)
from utils.storage import parse_json_bytes

MAX_FRAME = 4 * 1024 * 1024
PARTIAL_TIMEOUT = 5.0  # header (and floor for body) after first byte
MAX_BODY_TIMEOUT = 60.0  # hard cap for a whole frame
MIN_RATE = 128 * 1024.0  # bytes/s assumed for scaling body/send deadlines
SEND_CHUNK = 16 * 1024
POLL = 0.25


class WireError(Exception):
    pass


class WireClosed(WireError):
    pass


class WireTimeout(WireError):
    pass


class WireCancelled(WireError):
    pass


class FrameError(WireError):
    pass


def encode_message(obj):
    try:
        body = json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    except (TypeError, ValueError, RecursionError) as e:
        raise FrameError('message not encodable') from e
    if len(body) > MAX_FRAME:
        raise FrameError('message too large')
    return struct.pack('>I', len(body)) + body


def decode_message(body):
    try:
        return parse_json_bytes(body)  # rejects NaN/Infinity, duplicate keys, bad UTF-8
    except Exception as e:
        raise FrameError('invalid json') from e


def recv_exact(sock, n, deadline=None, stop=None):
    # Survives fragmentation; EOF -> WireClosed; deadline is absolute (monotonic).
    buf = bytearray()
    while len(buf) < n:
        if stop is not None and stop.is_set():
            raise WireCancelled('cancelled')
        wait = POLL
        if deadline is not None:
            rem = deadline - time.monotonic()
            if rem <= 0:
                raise WireTimeout('timeout')
            wait = min(POLL, rem)
        try:
            ready, _, _ = select.select([sock], [], [], wait)
            if not ready:
                continue
            chunk = sock.recv(n - len(buf))
        except (BlockingIOError, InterruptedError):
            continue
        except (OSError, ValueError) as e:
            raise WireClosed('socket error') from e
        if not chunk:
            raise WireClosed('eof')
        buf += chunk
    return bytes(buf)


def read_message(sock, stop=None, deadline=None, partial_timeout=PARTIAL_TIMEOUT, max_frame=MAX_FRAME):
    # deadline given: the whole frame (incl. waiting for its first byte) must arrive by then.
    # deadline None: idle waiting is unbounded (cancellable); after the first byte the 4-byte header
    # gets partial_timeout, and the body a bounded total that scales with the advertised length.
    first = recv_exact(sock, 1, deadline, stop)
    start = time.monotonic()
    header = first + recv_exact(sock, 3, deadline if deadline is not None else start + partial_timeout, stop)
    n = struct.unpack('>I', header)[0]
    if n > min(max_frame, MAX_FRAME):
        raise FrameError('frame too large')
    body_deadline = deadline if deadline is not None else start + body_timeout(n, partial_timeout)
    return decode_message(recv_exact(sock, n, body_deadline, stop))


def body_timeout(n, partial_timeout=PARTIAL_TIMEOUT):
    return min(MAX_BODY_TIMEOUT, partial_timeout + n / MIN_RATE)


def send_frame(sock, frame, stop=None, timeout=None):
    # Explicit total deadline via select on writability; never sets a socket-wide timeout
    # (which would race a concurrent reader on the same socket).
    if timeout is None:
        timeout = body_timeout(len(frame))
    end = time.monotonic() + timeout
    view = memoryview(frame)
    while len(view):
        if stop is not None and stop.is_set():
            raise WireCancelled('cancelled')
        rem = end - time.monotonic()
        if rem <= 0:
            raise WireTimeout('send timeout')
        try:
            _, writable, _ = select.select([], [sock], [], min(POLL, rem))
            if not writable:
                continue
            n = sock.send(view[:SEND_CHUNK])
        except (BlockingIOError, InterruptedError):
            continue
        except (OSError, ValueError) as e:
            raise WireClosed('socket error') from e
        if n == 0:
            raise WireClosed('closed')
        view = view[n:]


def send_message(sock, obj, stop=None, timeout=None):
    send_frame(sock, encode_message(obj), stop, timeout)


def get_local_ipv4s():
    from utils.network_setup import local_interfaces
    return [row['address'] for row in local_interfaces()]
