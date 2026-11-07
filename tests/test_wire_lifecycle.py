import socket
import struct
import threading
import time
import unittest
from unittest import mock

from core import network_manager as nmod
from core.network_manager import NetworkManager
from utils import pairing, wire

CODE = '0123456789ABCDEF'


class FakeChar:
    def __init__(self, cid, name):
        self.character_id = cid
        self.name = name

    @classmethod
    def from_dict(cls, d):
        if set(d) != {'character_id', 'name'}:
            raise ValueError('bad')
        return cls(d['character_id'], d['name'])

    def to_dict(self):
        return {'character_id': self.character_id, 'name': self.name}


class WireTests(unittest.TestCase):
    def pair(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        return a, b

    def test_fragmentation_and_unicode(self):
        a, b = self.pair()
        obj = {'t': 'h\u00e4llo \u20ac \U0001F600'}
        frame = wire.encode_message(obj)

        def drip():
            for i in range(len(frame)):
                b.sendall(frame[i:i + 1])
                time.sleep(0.002)
        threading.Thread(target=drip, daemon=True).start()
        self.assertEqual(wire.read_message(a), obj)

    def test_oversize_header_rejected(self):
        a, b = self.pair()
        b.sendall(struct.pack('>I', wire.MAX_FRAME + 1))
        with self.assertRaises(wire.FrameError):
            wire.read_message(a)

    def test_oversize_and_nan_encode(self):
        with self.assertRaises(wire.FrameError):
            wire.encode_message({'x': 'a' * (wire.MAX_FRAME + 1)})
        with self.assertRaises(wire.FrameError):
            wire.encode_message({'x': float('nan')})

    def test_truncation(self):
        a, b = self.pair()
        frame = wire.encode_message({'k': 'value'})
        b.sendall(frame[:-3])
        b.close()
        with self.assertRaises(wire.WireClosed):
            wire.read_message(a)

    def test_partial_deadline_absolute(self):
        a, b = self.pair()
        frame = wire.encode_message({'k': 'x' * 10})
        stop = threading.Event()

        def drip():
            for i in range(len(frame)):
                if stop.is_set():
                    return
                try:
                    b.send(frame[i:i + 1])
                except OSError:
                    return
                time.sleep(0.15)
        threading.Thread(target=drip, daemon=True).start()
        t0 = time.monotonic()
        with self.assertRaises(wire.WireTimeout):
            wire.read_message(a, partial_timeout=0.5)
        stop.set()
        self.assertLess(time.monotonic() - t0, 2.0)

    def test_idle_indefinite_but_cancellable(self):
        a, b = self.pair()
        stop = threading.Event()
        threading.Timer(0.5, stop.set).start()
        with self.assertRaises(wire.WireCancelled):
            wire.read_message(a, stop, partial_timeout=0.1)

    def test_body_deadline_scales_with_length(self):
        self.assertEqual(wire.PARTIAL_TIMEOUT, 5.0)
        self.assertLessEqual(wire.body_timeout(wire.MAX_FRAME), 60.0)
        self.assertGreater(wire.body_timeout(wire.MAX_FRAME), 20.0)
        self.assertLess(wire.body_timeout(100), 6.0)

    def test_large_frame_body_may_outlast_header_deadline(self):
        a, b = self.pair()
        obj = {'k': 'x' * 1000000}
        frame = wire.encode_message(obj)

        def slow():
            b.sendall(frame[:500000])
            time.sleep(0.6)
            b.sendall(frame[500000:])
        threading.Thread(target=slow, daemon=True).start()
        self.assertEqual(wire.read_message(a, partial_timeout=0.3), obj)

    def test_stalled_body_times_out(self):
        a, b = self.pair()
        frame = wire.encode_message({'k': 'x' * 100})
        b.sendall(frame[:-5])
        with self.assertRaises(wire.WireTimeout):
            wire.read_message(a, partial_timeout=0.3)

    def test_send_frame_total_timeout_keeps_socket_blocking(self):
        a, b = self.pair()
        with self.assertRaises(wire.WireTimeout):
            wire.send_frame(a, b'x' * (64 << 20), timeout=0.5)
        self.assertIsNone(a.gettimeout())

    def test_send_frame_cancel_and_roundtrip(self):
        a, b = self.pair()
        stop = threading.Event()
        stop.set()
        with self.assertRaises(wire.WireCancelled):
            wire.send_frame(a, b'x' * 10, stop)
        wire.send_message(a, {'k': 1})
        self.assertEqual(wire.read_message(b, deadline=time.monotonic() + 2), {'k': 1})

    def test_keepalive_enabled_on_tcp(self):
        srv = socket.socket()
        srv.bind(('127.0.0.1', 0))
        srv.listen(1)
        self.addCleanup(srv.close)
        c = socket.create_connection(srv.getsockname())
        self.addCleanup(c.close)
        self.assertTrue(wire.enable_keepalive(c))
        self.assertNotEqual(c.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE), 0)


class NMTests(unittest.TestCase):
    def setUp(self):
        for p in (mock.patch.object(nmod, 'Character', FakeChar),
                  mock.patch.object(nmod, 'Zeroconf'),
                  mock.patch.object(nmod, 'ServiceInfo')):
            p.start()
            self.addCleanup(p.stop)

    def nm(self):
        n = NetworkManager()
        self.addCleanup(n.shutdown)
        return n

    def server(self):
        s = self.nm()
        ok, msg = s.start_server(display_name='T\u00ebst', host='127.0.0.1')
        self.assertTrue(ok, msg)
        return s

    def ev(self, n, kind, timeout=3.0):
        end = time.monotonic() + timeout
        while True:
            src, pl = n.incoming_messages.get(timeout=max(0.01, end - time.monotonic()))
            if src == kind:
                return pl

    def join(self, c, s, cid='a', name='Ann', code=None):
        return c.connect_to_server('127.0.0.1', s.port, FakeChar(cid, name), code or s.join_code)

    def test_advertisement_has_no_secret(self):
        s = self.server()
        kw = nmod.ServiceInfo.call_args.kwargs
        self.assertEqual(kw['properties'], {b'proto': str(nmod.PROTOCOL).encode('ascii'), b'name': 'T\u00ebst'.encode('utf-8')})
        self.assertEqual(kw['port'], s.port)
        self.assertNotIn(s.join_code, repr(nmod.ServiceInfo.call_args))

    def test_failed_attempt_then_legit_connect(self):
        c = self.nm()
        tmp = socket.socket()
        tmp.bind(('127.0.0.1', 0))
        dead = tmp.getsockname()[1]
        tmp.close()
        ok, _ = c.connect_to_server('127.0.0.1', dead, FakeChar('a', 'Ann'), CODE)
        self.assertFalse(ok)
        s = self.server()
        ok, msg = self.join(c, s)
        self.assertTrue(ok, msg)
        joined = self.ev(s, 'PLAYER_JOINED')
        self.assertEqual(joined['char'].name, 'Ann')
        s.clients[joined['addr']]['approved'] = True
        s.broadcast_message('PING', {'n': 1})
        self.assertEqual(self.ev(c, 'DM')['type'], 'PING')

    def test_disconnect_then_reconnect(self):
        s = self.server()
        c = self.nm()
        self.assertTrue(self.join(c, s)[0])
        addr = self.ev(s, 'PLAYER_JOINED')['addr']
        c.shutdown()
        self.assertEqual(self.ev(s, 'PLAYER_LEFT'), {'addr': addr})
        ok, msg = self.join(c, s)
        self.assertTrue(ok, msg)

    def test_duplicate_identity_rejected(self):
        s = self.server()
        c1, c2, c3 = self.nm(), self.nm(), self.nm()
        self.assertTrue(self.join(c1, s)[0])
        self.ev(s, 'PLAYER_JOINED')
        self.assertFalse(self.join(c2, s, cid='a', name='Other')[0])
        self.assertFalse(self.join(c3, s, cid='b', name='Ann')[0])
        self.assertEqual(len(s.clients), 1)

    def test_wrong_code(self):
        s = self.server()
        wrong = '0' * 16 if s.join_code != '0' * 16 else '1' * 16
        self.assertFalse(self.join(self.nm(), s, code=wrong)[0])
        self.assertEqual(len(s.clients), 0)

    def test_slow_first_header_does_not_poison(self):
        s = self.server()
        raw = socket.create_connection(('127.0.0.1', s.port))
        self.addCleanup(raw.close)
        raw.sendall(b'\x00')
        ok, msg = self.join(self.nm(), s)
        self.assertTrue(ok, msg)
        self.assertEqual(self.ev(s, 'PLAYER_JOINED')['char'].name, 'Ann')

    def hello(self, s):
        raw = socket.create_connection(('127.0.0.1', s.port))
        self.addCleanup(raw.close)
        cn = pairing.new_nonce()
        wire.send_message(raw, {'type': 'HELLO', 'payload': {'protocol': nmod.PROTOCOL, 'cnonce': cn}})
        return raw, cn, wire.read_message(raw, deadline=time.monotonic() + 3)

    def test_code_is_16_hex_and_input_normalized(self):
        s = self.server()
        self.assertTrue(pairing.valid_code16hex(s.join_code))
        grouped = '-'.join(s.join_code[i:i + 4].lower() for i in range(0, 16, 4))
        ok, msg = self.join(self.nm(), s, code=grouped)
        self.assertTrue(ok, msg)
        ok, _ = self.join(self.nm(), s, cid='z', name='Zed', code='123456')
        self.assertFalse(ok)

    def test_refused_auth_and_no_plaintext_code(self):
        s = self.server()
        raw, cn, ch = self.hello(s)
        self.assertEqual(ch['type'], 'CHALLENGE')
        p = ch['payload']
        self.assertEqual(set(p), {'snonce', 'proof'})
        self.assertNotIn(s.join_code, repr(ch))
        self.assertTrue(pairing.verify(pairing.proof(s.join_code, 'game', 'server', cn, p['snonce']), p['proof']))
        wire.send_message(raw, {'type': 'AUTH', 'payload': {
            'proof': '0' * 64, 'character': {'character_id': 'a', 'name': 'Ann'}, 'resume': None}})
        reply = wire.read_message(raw, deadline=time.monotonic() + 3)
        self.assertEqual(reply, {'type': 'ERROR', 'payload': {'reason': 'wrong code'}})
        self.assertEqual(len(s.clients), 0)

    def test_legacy_plaintext_hello_rejected(self):
        s = self.server()
        raw = socket.create_connection(('127.0.0.1', s.port))
        self.addCleanup(raw.close)
        wire.send_message(raw, {'type': 'HELLO', 'payload': {
            'protocol': 2, 'code': '123456', 'character': {'character_id': 'a', 'name': 'Ann'}}})
        reply = wire.read_message(raw, deadline=time.monotonic() + 3)
        self.assertEqual(reply['payload'], {'reason': 'bad handshake'})
        self.assertEqual(len(s.clients), 0)

    def test_rogue_server_never_receives_auth(self):
        lsock = socket.socket()
        lsock.bind(('127.0.0.1', 0))
        lsock.listen(1)
        self.addCleanup(lsock.close)
        seen = {}

        def rogue():
            try:
                conn, _ = lsock.accept()
                with conn:
                    seen['hello'] = wire.read_message(conn, deadline=time.monotonic() + 3)
                    wire.send_message(conn, {'type': 'CHALLENGE', 'payload': {
                        'snonce': pairing.new_nonce(), 'proof': '0' * 64}})
                    conn.settimeout(2)
                    try:
                        seen['after'] = conn.recv(65536)
                    except socket.timeout:
                        seen['after'] = None
                    except OSError:
                        seen['after'] = b''
            except Exception as e:
                seen['err'] = e
        t = threading.Thread(target=rogue, daemon=True)
        t.start()
        c = self.nm()
        ok, msg = c.connect_to_server('127.0.0.1', lsock.getsockname()[1], FakeChar('a', 'Ann'),
                                      pairing.generate_code())
        t.join(5)
        self.assertFalse(ok)
        self.assertIn('authentication', msg.lower())
        self.assertNotIn('err', seen)
        self.assertEqual(set(seen['hello']['payload']), {'protocol', 'cnonce'})
        self.assertEqual(seen.get('after'), b'')  # closed; no AUTH/character sent

    def test_handshake_failure_throttle(self):
        s = self.server()
        for _ in range(pairing.MAX_FAILURES):
            raw = socket.create_connection(('127.0.0.1', s.port))
            self.addCleanup(raw.close)
            wire.send_message(raw, {'type': 'HELLO', 'payload': {}})
            self.assertEqual(wire.read_message(raw, deadline=time.monotonic() + 3)['type'], 'ERROR')
        self.assertTrue(s._gen.peer_limiter('127.0.0.1').blocked())
        self.assertFalse(s._gen.peer_limiter('127.0.0.2').blocked())
        ok, _ = self.join(self.nm(), s)
        self.assertFalse(ok)
        base = time.monotonic()
        s._gen.peer_limiter('127.0.0.1').clock = lambda: base + pairing.COOLDOWN + 1
        ok, msg = self.join(self.nm(), s)
        self.assertTrue(ok, msg)

    def test_outbound_byte_budget(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        conn = nmod._Conn(a, ('x', 1))
        frame = b'x' * wire.MAX_FRAME
        for _ in range(8):  # exactly 32 MiB; includes an 8 MiB background burst
            self.assertTrue(conn.put(frame))
        self.assertEqual(conn.qbytes, nmod.MAX_QUEUE_BYTES)
        conn.release(frame)
        self.assertEqual(conn.qbytes, 7 * wire.MAX_FRAME)
        self.assertTrue(conn.put(frame))
        self.assertFalse(conn.put(b'y'))
        self.assertTrue(conn.closed.is_set())


if __name__ == '__main__':
    unittest.main()
