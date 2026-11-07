import hashlib
import json
import os
import shutil
import socket
import struct
import tempfile
import threading
import unittest
import uuid
from pathlib import Path

from core import file_transfer as ft

CODE = '0123456789ABCDEF'
OTHER = 'FEDCBA9876543210'


class FS:
    fail_on = None
    writes = 0

    @staticmethod
    def validate_transfer(kind, data):
        obj = json.loads(data.decode('utf-8'))
        if not isinstance(obj, dict):
            raise ValueError('bad')
        return json.dumps(obj, sort_keys=True, ensure_ascii=False).encode('utf-8')

    @staticmethod
    def unique_import_path(folder, suffix):
        return Path(folder) / (uuid.uuid4().hex + suffix)

    @classmethod
    def atomic_write_bytes(cls, path, data):
        cls.writes += 1
        if cls.fail_on == cls.writes:
            raise OSError('disk')
        tmp = str(path) + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)


class Trickle:
    def __init__(self, s):
        self.s = s

    def send(self, data):
        return self.s.send(bytes(data[:3]))

    def __getattr__(self, n):
        return getattr(self.s, n)


def J(**kw):
    return json.dumps(kw, ensure_ascii=False).encode('utf-8')


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        FS.fail_on = None
        FS.writes = 0

    def folder(self, kind):
        return self.tmp / kind

    def files(self):
        return [p for p in self.tmp.rglob('*') if p.is_file()]

    def pair(self, payloads, scode=CODE, rcode=CODE, wrap=None):
        a, b = socket.socketpair()
        res = {}

        def snd():
            try:
                ft.send_payloads(wrap(a) if wrap else a, payloads, scode)
            except Exception as e:
                res['s'] = e
            finally:
                a.close()

        t = threading.Thread(target=snd, daemon=True)
        t.start()
        try:
            res['r'] = ft.receive_and_store(b, rcode, self.folder, None, FS)
        except Exception as e:
            res['r'] = e
        finally:
            b.close()
        t.join(10)
        return res

    def raw(self, script):
        a, b = socket.socketpair()

        def peer():
            try:
                ns = '00' * 16
                ft.send_frame(a, {'type': 'challenge', 'nonce': ns})
                au = ft.recv_frame(a)
                ft.send_frame(a, {'type': 'ok', 'mac': ft._mac(CODE, 'sender', ns, au['nonce'])})
                script(a)
            except Exception:
                pass
            finally:
                a.close()

        threading.Thread(target=peer, daemon=True).start()
        try:
            with self.assertRaises(ft.TransferError) as cm:
                ft.receive_and_store(b, CODE, self.folder, None, FS)
        finally:
            b.close()
        self.assertEqual(self.files(), [])
        return cm.exception

    def manifest(self, n, sha=None, length=None, extra=None):
        f = {'kind': 'maps', 'length': length or n, 'sha256': sha or hashlib.sha256(b'x' * n).hexdigest()}
        if extra:
            f.update(extra)
        return {'type': 'manifest', 'count': 1, 'files': [f]}

    def test_multifile_unicode_fragmented(self):
        pl = ft.prepare_payloads([('maps', J(name='Drachenhöhle ✓')), ('characters', J(name='Ünï', n=1)),
                                  ('maps', J(big='x' * 120000))], FS)
        res = self.pair(pl, wrap=Trickle)
        self.assertNotIn('s', res)
        self.assertEqual(len(res['r']), 3)
        got = sorted(p.read_bytes() for p in self.files())
        self.assertEqual(got, sorted(p.data for p in pl))
        for p in self.files():
            self.assertEqual(p.resolve().parent.parent, self.tmp.resolve())
            uuid.UUID(hex=p.stem)

    def test_malicious_name_in_manifest_rejected(self):
        def script(a):
            ft.send_frame(a, self.manifest(1, extra={'name': '../../evil.json'}))
        self.assertIsInstance(self.raw(script), ft.ProtocolError)

    def test_wrong_code(self):
        res = self.pair(ft.prepare_payloads([('maps', J(a=1))], FS), rcode=OTHER)
        self.assertIsInstance(res['r'], ft.PairingError)
        self.assertIsInstance(res['s'], ft.PairingError)
        self.assertEqual(self.files(), [])

    def test_truncated_chunk_stream(self):
        def script(a):
            ft.send_frame(a, self.manifest(100))
            ft.send_frame(a, {'type': 'chunk', 'i': 0, 'data': 'eHh4eHh4'})
        self.assertIsInstance(self.raw(script), ft.TransferClosed)

    def test_truncated_inside_frame(self):
        def script(a):
            a.sendall(struct.pack('>I', 500) + b'{"type"')
        self.assertIsInstance(self.raw(script), ft.TransferClosed)

    def test_checksum_mismatch(self):
        data = J(a=1)

        def script(a):
            ft.send_frame(a, self.manifest(len(data), sha='0' * 64))
            import base64
            ft.send_frame(a, {'type': 'chunk', 'i': 0, 'data': base64.b64encode(data).decode()})
            ft.send_frame(a, {'type': 'end'})
        self.assertIsInstance(self.raw(script), ft.PayloadError)

    def test_oversize_and_count_rejected(self):
        def s1(a):
            ft.send_frame(a, self.manifest(1, length=ft.MAX_FILE + 1))
        self.assertIsInstance(self.raw(s1), ft.ProtocolError)

        def s2(a):
            m = self.manifest(1)
            m['files'] = m['files'] * 17
            m['count'] = 17
            ft.send_frame(a, m)
        self.assertIsInstance(self.raw(s2), ft.ProtocolError)

    def test_oversize_frame_header(self):
        def script(a):
            a.sendall(struct.pack('>I', ft.MAX_FRAME + 1))
        self.assertIsInstance(self.raw(script), ft.ProtocolError)

    def test_bad_magic_one_invalid_writes_nothing(self):
        good, bad = J(a=1), b'\x00\x01garbage'
        pl = [ft.Payload('maps', good), ft.Payload('maps', bad)]
        res = self.pair(pl)
        self.assertIsInstance(res['r'], ft.PayloadError)
        self.assertEqual(self.files(), [])
        with self.assertRaises(ft.PayloadError):
            ft.prepare_payloads([('maps', bad)], FS)

    def test_rollback_only_new_files(self):
        pre = self.folder('maps')
        pre.mkdir(parents=True)
        (pre / 'keep.json').write_bytes(b'{}')
        FS.fail_on = 2
        items = [ft.Payload('maps', J(a=1)), ft.Payload('maps', J(b=2))]
        with self.assertRaises(OSError):
            ft.publish_batch(items, self.folder, FS)
        self.assertEqual([p.name for p in self.files()], ['keep.json'])

    def test_image_validator(self):
        png = lambda w, h: ft._PNG + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', w, h) + bytes(5)
        self.assertEqual(ft.image_extension(png(100, 100)), '.png')
        for w, h in ((8192, 10), (5000, 4000), (0, 5)):
            with self.assertRaises(ft.PayloadError):
                ft.image_extension(png(w, h))
        jpg = bytes([0xFF, 0xD8, 0xFF, 0xC0, 0, 11, 8, 0, 20, 0, 30, 1, 1, 0, 0])
        self.assertEqual(ft.image_extension(jpg), '.jpg')
        with self.assertRaises(ft.PayloadError):
            ft.image_extension(b'GIF89a' + bytes(30))

    def test_legacy_six_digit_code_rejected(self):
        pl = ft.prepare_payloads([('maps', J(a=1))], FS)
        with self.assertRaises(ft.PairingError):
            ft.send_payloads(None, pl, '123456')
        with self.assertRaises(ft.PairingError):
            ft.receive_payloads(None, '123456')
        self.assertTrue(ft.valid_code(ft.generate_code()))

    def test_normalized_grouped_lowercase_code_works(self):
        pl = ft.prepare_payloads([('maps', J(a=1))], FS)
        res = self.pair(pl, scode='0123-4567-89ab-cdef', rcode=' 0123 4567 89AB CDEF ')
        self.assertNotIn('s', res)
        self.assertEqual(len(res['r']), 1)

    def test_rogue_sender_rejected_before_manifest(self):
        a, b = socket.socketpair()
        seen = {}

        def peer():
            try:
                ft.send_frame(a, {'type': 'challenge', 'nonce': '11' * 16})
                ft.recv_frame(a)
                ft.send_frame(a, {'type': 'ok', 'mac': '0' * 64})
                seen['reply'] = ft.recv_frame(a)
            except Exception as e:
                seen['err'] = e
            finally:
                a.close()
        t = threading.Thread(target=peer, daemon=True)
        t.start()
        try:
            with self.assertRaises(ft.PairingError):
                ft.receive_and_store(b, CODE, self.folder, None, FS)
        finally:
            b.close()
        t.join(5)
        self.assertEqual(seen.get('reply'), {'type': 'error', 'reason': 'pairing'})
        self.assertEqual(self.files(), [])

    def test_preauth_remote_error_is_protocol_error_and_share_survives(self):
        with self.assertRaises(ft.ProtocolError):
            ft._expect({'type': 'error', 'reason': 'invalid'}, 'auth', {'type', 'nonce', 'mac'}, True)
        with self.assertRaises(ft.PayloadError):
            ft._expect({'type': 'error', 'reason': 'invalid'}, 'done', {'type'})
        pl = ft.prepare_payloads([('maps', J(a=1))], FS)
        ready = threading.Event()
        port = []
        res = {}

        def on_ready(p):
            port.append(p)
            ready.set()

        def srv():
            try:
                ft.serve_once(pl, CODE, port=0, on_ready=on_ready, accept_timeout=15, bind_host='127.0.0.1')
            except Exception as e:
                res['s'] = e
        t = threading.Thread(target=srv, daemon=True)
        t.start()
        self.assertTrue(ready.wait(5))
        bad = socket.create_connection(('127.0.0.1', port[0]))
        ft.recv_frame(bad)
        ft.send_frame(bad, {'type': 'error', 'reason': 'invalid'})
        bad.close()
        paths = ft.connect_and_receive('127.0.0.1', port[0], CODE, self.folder, None, FS)
        t.join(10)
        self.assertNotIn('s', res)
        self.assertEqual(len(paths), 1)

    def test_endpoint(self):
        self.assertEqual(ft.parse_endpoint('192.168.0.5:1234'), ('192.168.0.5', 1234))
        self.assertEqual(ft.parse_endpoint('host'), ('host', ft.DEFAULT_PORT))
        with self.assertRaises(ValueError):
            ft.parse_endpoint('h:99999')


if __name__ == '__main__':
    unittest.main()
