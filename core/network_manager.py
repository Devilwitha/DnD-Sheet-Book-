import logging
import hashlib
import hmac
import random
import secrets
import select
import socket
import threading
import time
from queue import Empty, Full, Queue
from collections import OrderedDict

from zeroconf import ServiceInfo, Zeroconf

from core.character import Character
from utils import pairing, wire
from utils.wire import get_local_ipv4s

log = logging.getLogger('dnd.local.network')
PROTOCOL = 6  # Individual reconnect proofs; host and clients must use the same version.
MAX_CLIENTS = 16
QUEUE_SIZE = 256
MAX_QUEUE_BYTES = 32 * 1024 * 1024  # per-connection outbound budget (>= 8 MiB background must fit)
HANDSHAKE_MAX_FRAME = 64 * 1024
HANDSHAKE_TIMEOUT = 5.0
CONNECT_TIMEOUT = 5.0
SERVICE_TYPE = '_dndgame._tcp.local.'


class EventQueue(Queue):
    """Reserve a bounded control lane so a full data queue cannot hide departures."""
    def __init__(self, size):
        super().__init__(size)
        self.departures = OrderedDict()

    def put_departure(self, addr):
        with self.not_empty:
            if len(self.departures) >= MAX_CLIENTS:
                # One reconciliation event represents all disconnected peers.
                self.departures.clear()
                addr = None
            self.departures[addr] = None
            self.not_empty.notify()

    def _qsize(self):
        return super()._qsize() + len(self.departures)

    def _get(self):
        if self.departures:
            addr, _ = self.departures.popitem(last=False)
            return ('PLAYER_LEFT', {'addr': addr})
        return super()._get()


def _resume_proof(secret, cid, cn, sn):
    message = '|'.join(('dnd-resume-v1', cid, cn, sn)).encode('ascii')
    return hmac.new(bytes.fromhex(secret), message, hashlib.sha256).hexdigest()


class _Reject(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _close(sock):
    if sock is None:
        return
    for fn in (lambda: sock.shutdown(socket.SHUT_RDWR), sock.close):
        try:
            fn()
        except (OSError, ValueError):
            pass


def _valid_code(code):
    return pairing.valid_code16hex(pairing.normalize_code(code))


def _hs_read(sock, stop, end, typ, keys):
    msg = wire.read_message(sock, stop, deadline=end, max_frame=HANDSHAKE_MAX_FRAME)
    if not isinstance(msg, dict) or set(msg) != {'type', 'payload'} or msg['type'] != typ:
        raise _Reject('bad handshake')
    p = msg['payload']
    if not isinstance(p, dict) or set(p) != keys:
        raise _Reject('bad handshake')
    return p


def _client_read(sock, stop, end, typ, keys):
    msg = wire.read_message(sock, stop, deadline=end, max_frame=HANDSHAKE_MAX_FRAME)
    if isinstance(msg, dict) and msg.get('type') == 'ERROR':
        p = msg.get('payload')
        reason = str(p.get('reason', ''))[:100] if isinstance(p, dict) else ''
        if reason == 'unsupported protocol':
            reason = 'Unterschiedliche App-Versionen. Bitte Host und Spieler gemeinsam auf dieselbe aktuelle Version aktualisieren.'
        raise ConnectionError(reason or 'Connection refused.')
    if (not isinstance(msg, dict) or set(msg) != {'type', 'payload'} or msg['type'] != typ
            or not isinstance(msg['payload'], dict) or set(msg['payload']) != keys):
        raise ConnectionError('Invalid handshake reply.')
    return msg['payload']


class _Gen:
    # Everything owned by one start/connect attempt; stale workers only touch their own.
    def __init__(self, kind):
        self.kind = kind
        self.stop = threading.Event()
        self.server_socket = None
        self.code = None
        self.limiters = OrderedDict()
        self.limiter_lock = threading.Lock()
        self.resumes = {}
        self.revoked = set()
        self.pending = 0
        self.pending_sockets = set()
        self.incoming = EventQueue(QUEUE_SIZE)
        self.conn = None
        self.zc = None
        self.info = None
        self.accept_thread = None

    def peer_limiter(self, host):
        with self.limiter_lock:
            stamp = time.monotonic()
            for key, (seen, _) in list(self.limiters.items()):
                if stamp - seen > 120:
                    del self.limiters[key]
            entry = self.limiters.pop(host, None)
            limiter = entry[1] if entry else pairing.FailureLimiter()
            self.limiters[host] = (stamp, limiter)
            while len(self.limiters) > 128:
                self.limiters.popitem(last=False)
            return limiter


class _Conn:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.q = Queue(QUEUE_SIZE)
        self.qlock = threading.Lock()
        self.qbytes = 0
        self.closed = threading.Event()
        self.character = None
        self.threads = []

    def close(self):
        self.closed.set()
        _close(self.sock)

    def put(self, frame):
        if self.closed.is_set():
            return False
        size = len(frame) if frame else 0
        with self.qlock:
            if self.qbytes + size <= MAX_QUEUE_BYTES:
                try:
                    self.q.put_nowait(frame)
                    self.qbytes += size
                    return True
                except Full:
                    pass
        log.warning('send queue overflow; disconnecting peer')
        self.close()
        return False

    def release(self, frame):
        with self.qlock:
            self.qbytes = max(0, self.qbytes - (len(frame) if frame else 0))

    def send(self, msg_type, payload):
        try:
            frame = wire.encode_message({'type': msg_type, 'payload': payload})
        except wire.WireError:
            return False
        return self.put(frame)


class NetworkManager:
    def __init__(self):
        self.mode = 'idle'  # idle, dm, client
        self.lock = threading.RLock()
        self.incoming_messages = Queue(QUEUE_SIZE)
        self.running = False
        self.clients = {}  # addr -> {socket, character, thread, conn}
        self.port = None
        self.local_addresses = []
        self.join_code = None  # shown locally only; never logged or advertised
        self._gen = None
        self._resume_credentials = OrderedDict()  # Memory only, keyed by session code and character ID.

    # ------------------------------------------------------------ server
    def start_server(self, display_name="DM's Spiel", host='0.0.0.0', port=0):
        with self.lock:
            if self.running:
                return (True, 'Already hosting.') if self.mode == 'dm' else (False, 'Network manager is busy.')
        self._teardown()  # clear stale state (e.g. a lost client connection)
        ssock = None
        try:
            ssock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ssock.bind((host, int(port)))
            ssock.listen(MAX_CLIENTS)
        except (OSError, ValueError, OverflowError) as e:
            _close(ssock)
            return False, str(e)
        gen = _Gen('dm')
        gen.server_socket = ssock
        gen.code = pairing.generate_code()
        real_port = ssock.getsockname()[1]
        try:
            addrs = list(get_local_ipv4s()) if host in ('', '0.0.0.0') else [host]
        except Exception:
            addrs = []
        with self.lock:
            if self.running:
                _close(ssock)
                return (True, 'Already hosting.') if self.mode == 'dm' else (False, 'Network manager is busy.')
            self._gen = gen
            self.incoming_messages = gen.incoming
            self.mode = 'dm'
            self.running = True
            self.port = real_port
            self.local_addresses = addrs
            self.join_code = gen.code
        gen.accept_thread = threading.Thread(target=self._accept_loop, args=(gen,), daemon=True)
        gen.accept_thread.start()
        threading.Thread(target=self._advertise, args=(gen, display_name, addrs, real_port), daemon=True).start()
        return True, 'Server started on port %d.' % real_port

    @staticmethod
    def _make_info(addrs, port, display_name, name=None):
        name = name or 'DnD_DM_Server_%d.%s' % (random.randint(1000, 9999), SERVICE_TYPE)
        dn = str(display_name).encode('utf-8')[:200].decode('utf-8', 'ignore').encode('utf-8')
        return ServiceInfo(SERVICE_TYPE, name, addresses=[socket.inet_aton(a) for a in addrs],
                           port=port, properties={b'proto': str(PROTOCOL).encode('ascii'), b'name': dn})

    def _advertise(self, gen, display_name, addrs, port):
        if not addrs:
            return
        zc = None
        try:
            info = self._make_info(addrs, port, display_name)
            zc = Zeroconf()
            zc.register_service(info)
        except Exception as e:
            log.warning('service discovery unavailable: %s', type(e).__name__)
            try:
                if zc:
                    zc.close()
            except Exception:
                pass
            return
        with self.lock:
            keep = self._gen is gen and not gen.stop.is_set()
            if keep:
                gen.zc, gen.info = zc, info
        if not keep:
            try:
                zc.close()
            except Exception:
                pass

    def update_service_name(self, new_display_name):
        with self.lock:
            gen = self._gen
            if not gen or gen.kind != 'dm' or not gen.zc or not gen.info:
                return False
            zc, old, addrs, port = gen.zc, gen.info, list(self.local_addresses), self.port
        try:
            new = self._make_info(addrs, port, new_display_name, old.name)
            zc.unregister_service(old)
            zc.register_service(new)
            gen.info = new
            return True
        except Exception as e:
            log.warning('service rename failed: %s', type(e).__name__)
            return False

    def _accept_loop(self, gen):
        ssock = gen.server_socket
        while not gen.stop.is_set():
            try:
                ready, _, _ = select.select([ssock], [], [], 0.25)
                if not ready:
                    continue
                sock, addr = ssock.accept()
            except (OSError, ValueError):
                if gen.stop.is_set():
                    break
                time.sleep(0.05)
                continue
            if gen.peer_limiter(addr[0]).blocked():
                _close(sock)
                continue
            wire.enable_keepalive(sock)
            sock.setblocking(False)
            with self.lock:
                ok = self._gen is gen and len(self.clients) + gen.pending < MAX_CLIENTS
                if ok:
                    gen.pending += 1
                    gen.pending_sockets.add(sock)
            if not ok:
                _close(sock)
                continue
            try:
                threading.Thread(target=self._pending, args=(gen, sock, addr), daemon=True).start()
            except RuntimeError:
                with self.lock:
                    gen.pending -= 1
                gen.pending_sockets.discard(sock)
                _close(sock)

    def _pending(self, gen, sock, addr):
        conn = None
        try:
            conn = self._admit(gen, sock, addr)
        except _Reject as r:
            if r.reason in ('wrong code', 'bad handshake', 'invalid character', 'invalid resume proof'):
                gen.peer_limiter(addr[0]).failure()
            log.info('handshake rejected: %s', r.reason)
            try:
                wire.send_message(sock, {'type': 'ERROR', 'payload': {'reason': r.reason}})
            except Exception:
                pass
        except Exception as e:
            if not gen.stop.is_set():
                gen.peer_limiter(addr[0]).failure()
            log.info('handshake failed: %s', type(e).__name__)
        finally:
            with self.lock:
                gen.pending -= 1
                gen.pending_sockets.discard(sock)
        if conn is None:
            _close(sock)
            return
        if not self._emit(gen, ('PLAYER_JOINED', {'addr': addr, 'char': conn.character})):
            self._drop(gen, conn, quiet=True)
            return
        self._launch(gen, conn, addr)

    def _admit(self, gen, sock, addr):
        # Mutual HMAC challenge: no code ever crosses the wire; server proves knowledge first.
        end = time.monotonic() + HANDSHAKE_TIMEOUT
        hello = _hs_read(sock, gen.stop, end, 'HELLO', {'protocol', 'cnonce'})
        if type(hello['protocol']) is not int or hello['protocol'] != PROTOCOL:
            raise _Reject('unsupported protocol')
        cn = hello['cnonce']
        if not pairing.valid_nonce(cn):
            raise _Reject('bad handshake')
        sn = pairing.new_nonce()
        wire.send_message(sock, {'type': 'CHALLENGE', 'payload': {
            'snonce': sn, 'proof': pairing.proof(gen.code, 'game', 'server', cn, sn)}}, gen.stop)
        auth = _hs_read(sock, gen.stop, end, 'AUTH', {'proof', 'character', 'resume'})
        if not pairing.verify(pairing.proof(gen.code, 'game', 'client', cn, sn), auth['proof']):
            raise _Reject('wrong code')
        cdict = auth['character']
        if not isinstance(cdict, dict):
            raise _Reject('invalid character')
        try:
            ch = Character.from_dict(cdict)  # validates/whitelists fields
        except Exception:
            raise _Reject('invalid character') from None
        cid = getattr(ch, 'character_id', None)
        cname = str(ch.name).casefold()
        conn = _Conn(sock, addr)
        conn.character = ch
        replaced = None
        with self.lock:
            if self._gen is not gen or gen.stop.is_set():
                raise _Reject('server closed')
            if cid in gen.revoked:
                raise _Reject('Charakter wurde aus dieser Sitzung entfernt. Bitte den DM ansprechen.')
            previous = gen.resumes.get(cid)
            resumed = previous is not None
            if previous:
                if not pairing.verify(_resume_proof(previous['secret'], cid, cn, sn), auth['resume']):
                    raise _Reject('invalid resume proof')
                active = next((i for i in self.clients.values()
                               if getattr(i['character'], 'character_id', None) == cid), None)
                if active:
                    previous.update(character=active['character'], approved=active.get('approved', False))
                cname = str(previous['character'].name).casefold()
            elif auth['resume'] is not None:
                raise _Reject('invalid resume proof')
            if any(key != cid and str(record['character'].name).casefold() == cname
                   for key, record in gen.resumes.items()):
                raise _Reject('duplicate character')
            for other_addr, info in list(self.clients.items()):
                other = info['character']
                if getattr(other, 'character_id', None) == cid and previous:
                    replaced = info['conn']
                elif str(other.name).casefold() == cname:
                    raise _Reject('duplicate character')
            if previous is None:
                if len(gen.resumes) >= 128:
                    raise _Reject('Sitzung hat zu viele verschiedene Teilnehmer.')
                previous = dict(secret=secrets.token_hex(32), character=ch, approved=False)
                gen.resumes[cid] = previous
            if replaced:
                del self.clients[replaced.addr]
            conn.character = previous['character']
            self.clients[addr] = {'socket': sock, 'character': conn.character, 'thread': None,
                                  'conn': conn, 'approved': previous['approved'], 'resumed': resumed,
                                  'action_results': previous.setdefault('action_results', OrderedDict())}
        if replaced:
            replaced.close()
            gen.incoming.put_departure(replaced.addr)
        try:
            wire.send_message(sock, {'type': 'ACCEPT', 'payload': {'resume_token': previous['secret']}})
        except Exception:
            self._unregister(conn)
            raise
        return conn

    def _launch(self, gen, conn, source):
        reader = threading.Thread(target=self._serve, args=(gen, conn, source), daemon=True)
        sender = threading.Thread(target=self._sender, args=(conn,), daemon=True)
        conn.threads = [reader, sender]
        with self.lock:
            info = self.clients.get(conn.addr)
            if info and info['conn'] is conn:
                info['thread'] = reader
        sender.start()
        reader.start()

    def _sender(self, conn):
        # One serial writer per socket, so frames never interleave. Bounded total time per frame.
        try:
            while not conn.closed.is_set():
                try:
                    frame = conn.q.get(timeout=0.25)
                except Empty:
                    continue
                if frame is None:  # flush-then-close sentinel
                    break
                try:
                    wire.send_frame(conn.sock, frame, conn.closed)
                finally:
                    conn.release(frame)
        except (OSError, ValueError, wire.WireError):
            pass
        finally:
            conn.close()

    def _serve(self, gen, conn, source):
        try:
            while not conn.closed.is_set():
                msg = wire.read_message(conn.sock, conn.closed)  # idle waits are indefinite, cancellable
                if not isinstance(msg, dict) or not isinstance(msg.get('type'), str):
                    break
                if not self._emit(gen, (source, msg)):
                    break
        except Exception as e:
            log.debug('connection ended: %s', type(e).__name__)
        finally:
            self._drop(gen, conn)

    def _emit(self, gen, item):
        if gen.stop.is_set():
            return False
        try:
            gen.incoming.put_nowait(item)
            return True
        except Full:
            log.warning('incoming queue overflow; disconnecting peer')
            return False

    def _unregister(self, conn):
        with self.lock:
            info = self.clients.get(conn.addr)
            if info and info['conn'] is conn:
                gen = self._gen
                cid = getattr(info['character'], 'character_id', None)
                if gen and cid in gen.resumes:
                    gen.resumes[cid].update(character=info['character'], approved=info.get('approved', False),
                                            action_results=info.get('action_results', OrderedDict()))
                del self.clients[conn.addr]
                return True
        return False

    def _drop(self, gen, conn, quiet=False):
        conn.close()
        was = self._unregister(conn)
        if gen.kind == 'client':
            with self.lock:
                if self._gen is gen:
                    self.running = False
                    self.mode = 'idle'
        elif was and not quiet:
            if not gen.stop.is_set():
                gen.incoming.put_departure(conn.addr)

    def _conn_for(self, addr):
        with self.lock:
            info = self.clients.get(addr)
            return info['conn'] if info else None

    def send_message(self, client_address, msg_type, payload):
        conn = self._conn_for(client_address)
        return bool(conn and conn.send(msg_type, payload))

    def broadcast_message(self, msg_type, payload):
        try:
            frame = wire.encode_message({'type': msg_type, 'payload': payload})
        except wire.WireError:
            return False
        with self.lock:
            conns = [i['conn'] for i in self.clients.values() if i.get('approved', False)]
        for c in conns:
            c.put(frame)
        return True

    def kick_player(self, client_address):
        conn = self._conn_for(client_address)
        if not conn:
            return False
        with self.lock:
            if self._gen:
                cid = getattr(conn.character, 'character_id', None)
                self._gen.resumes.pop(cid, None)
                if cid is not None:
                    self._gen.revoked.add(cid)
        if conn.send('KICK', 'You have been kicked.'):
            try:
                conn.q.put_nowait(None)
            except Full:
                conn.close()
        else:
            conn.close()
        return True

    def get_client_addr_by_name(self, char_name):
        with self.lock:
            for addr, info in self.clients.items():
                if info['character'].name == char_name:
                    return addr
        return None

    def stop_server(self):
        self._teardown('dm')

    # ------------------------------------------------------------ client
    def connect_to_candidates(self, addresses, port, character, join_code, cancelled=None, progress=None):
        from utils.network_setup import MAX_ADDRESSES, connection_error_kind
        candidates = list(dict.fromkeys(addresses))[:MAX_ADDRESSES]
        if not candidates:
            return False, 'Keine erreichbare lokale Adresse angegeben.'
        errors = []
        for index, address in enumerate(candidates):
            if cancelled and cancelled():
                return False, 'Verbindungsaufbau abgebrochen.'
            if progress:
                progress(index + 1, len(candidates))
            ok, message = self.connect_to_server(address, port, character, join_code=join_code,
                                                 cancelled=cancelled, connect_timeout=2.0 if len(candidates) > 1 else CONNECT_TIMEOUT)
            kind = 'connected' if ok else connection_error_kind(message)
            # Never log the join code, QR content, character or peer's raw error text.
            from utils.diagnostics import logger
            logger.info('connect_attempt candidate=%d total=%d result=%s', index + 1, len(candidates), kind)
            if ok or kind in ('cancelled', 'duplicate'):
                return ok, message
            errors.append((kind, message))
        for preferred in ('version', 'code', 'timeout', 'refused', 'unreachable'):
            for kind, message in errors:
                if kind == preferred:
                    return False, message
        return False, errors[-1][1]

    def connect_to_server(self, ip, port, character, code=None, join_code=None, cancelled=None, connect_timeout=CONNECT_TIMEOUT):
        code = pairing.normalize_code(join_code if join_code is not None else code)
        with self.lock:
            busy = self.running
            previous = self._gen
        if busy:
            return False, 'Network manager is busy.'
        if previous is not None:
            self._teardown(only=previous)
        gen = _Gen('client')
        with self.lock:
            if cancelled and cancelled():
                return False, 'Verbindungsaufbau abgebrochen.'
            if self.running:
                return False, 'Network manager is busy.'
            self._gen = gen
            self.incoming_messages = gen.incoming
            self.mode = 'client'
            self.running = True
        sock = None
        try:
            if not _valid_code(code):
                raise ValueError('A 16-digit hex join code is required.')
            sock = socket.create_connection((ip, port), timeout=connect_timeout)
            if gen.stop.is_set() or (cancelled and cancelled()):
                raise ConnectionError('Verbindungsaufbau abgebrochen.')
            sock.settimeout(None)
            wire.enable_keepalive(sock)
            sock.setblocking(False)
            end = time.monotonic() + HANDSHAKE_TIMEOUT
            cn = pairing.new_nonce()
            wire.send_message(sock, {'type': 'HELLO', 'payload': {'protocol': PROTOCOL, 'cnonce': cn}}, gen.stop)
            ch = _client_read(sock, gen.stop, end, 'CHALLENGE', {'snonce', 'proof'})
            sn = ch['snonce']
            if not pairing.valid_nonce(sn) or not pairing.verify(
                    pairing.proof(code, 'game', 'server', cn, sn), ch['proof']):
                raise ConnectionError('Server authentication failed.')
            if gen.stop.is_set() or (cancelled and cancelled()):
                raise ConnectionError('Verbindungsaufbau abgebrochen.')
            resume_key = (code, character.character_id)
            secret = self._resume_credentials.get(resume_key)
            wire.send_message(sock, {'type': 'AUTH', 'payload': {
                'proof': pairing.proof(code, 'game', 'client', cn, sn),
                'character': character.to_dict(),
                'resume': _resume_proof(secret, character.character_id, cn, sn) if secret else None}}, gen.stop)
            accepted = _client_read(sock, gen.stop, end, 'ACCEPT', {'resume_token'})
            token = accepted['resume_token']
            if not isinstance(token, str) or len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
                raise ConnectionError('Invalid reconnect credential.')
            self._resume_credentials[resume_key] = token
            while len(self._resume_credentials) > 16:
                self._resume_credentials.popitem(last=False)
            conn = _Conn(sock, (ip, port))
            with self.lock:
                if self._gen is not gen or gen.stop.is_set() or (cancelled and cancelled()):
                    raise ConnectionError('Verbindungsaufbau abgebrochen.')
                gen.conn = conn
            self._launch(gen, conn, 'DM')
            return True, 'Connection successful.'
        except Exception as e:
            _close(sock)
            self._teardown(only=gen)
            return False, str(e) or type(e).__name__

    def send_to_dm(self, msg_type, payload):
        with self.lock:
            gen = self._gen
            conn = gen.conn if gen and gen.kind == 'client' and self.running else None
        return bool(conn and conn.send(msg_type, payload))

    # ---------------------------------------------------------- lifecycle
    def shutdown(self):
        self._teardown()

    def _teardown(self, kind=None, only=None):
        # Runs even when running is False. Never holds the lock during network IO or joins.
        with self.lock:
            gen = only or self._gen
            if gen is None or (kind and gen.kind != kind):
                return
            conns = []
            reset = gen is self._gen
            if reset:
                conns = [i['conn'] for i in self.clients.values()]
                self.clients.clear()
                self._gen = None
                self.running = False
                self.mode = 'idle'
                self.port = None
                self.local_addresses = []
                self.join_code = None
                self.incoming_messages = Queue(QUEUE_SIZE)
            pending = list(gen.pending_sockets)
        gen.stop.set()
        for sock in pending:
            _close(sock)
        if gen.conn:
            conns.append(gen.conn)
        for c in conns:
            c.close()
        _close(gen.server_socket)
        if gen.zc:
            try:
                if gen.info:
                    gen.zc.unregister_service(gen.info)
                gen.zc.close()
            except Exception:
                pass
        me = threading.current_thread()
        end = time.monotonic() + 2.0
        for t in [gen.accept_thread] + [t for c in conns for t in c.threads]:
            if t is not None and t is not me and t.is_alive():
                t.join(max(0.0, end - time.monotonic()))
        if reset:
            while True:
                try:
                    gen.incoming.get_nowait()
                except Empty:
                    break
