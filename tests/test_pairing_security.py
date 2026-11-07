import unittest

from utils import pairing

CODE = '0123456789ABCDEF'
N1 = 'a1' * 16
N2 = 'b2' * 16


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


class PairingTests(unittest.TestCase):
    def test_generate_code_format_and_uniqueness(self):
        codes = {pairing.generate_code() for _ in range(50)}
        self.assertEqual(len(codes), 50)
        for c in codes:
            self.assertEqual(len(c), 16)
            self.assertTrue(pairing.valid_code16hex(c))
            self.assertEqual(c, c.upper())

    def test_normalize(self):
        self.assertEqual(pairing.normalize_code(' 0123-4567 89ab-cdef '), CODE)
        self.assertEqual(pairing.normalize_code(None), '')
        self.assertEqual(pairing.normalize_code('\ufb00' * 8), '')  # no unicode-upper tricks

    def test_valid_rejects_legacy_and_malformed(self):
        self.assertTrue(pairing.valid_code16hex(CODE))
        for bad in ('123456', '0123456789abcdef', CODE + '0', CODE[:-1], 'G' * 16, '', None, 1234567890123456,
                    '\u0660' * 16):
            self.assertFalse(pairing.valid_code16hex(bad), bad)

    def test_proof_binds_role_nonces_code_context(self):
        base = pairing.proof(CODE, 'game', 'server', N1, N2)
        self.assertEqual(len(base), 64)
        self.assertTrue(pairing.verify(base, base))
        self.assertNotEqual(base, pairing.proof(CODE, 'game', 'client', N1, N2))
        self.assertNotEqual(base, pairing.proof(CODE, 'game', 'server', N2, N1))
        self.assertNotEqual(base, pairing.proof(CODE, 'file', 'server', N1, N2))
        self.assertNotEqual(base, pairing.proof('FEDCBA9876543210', 'game', 'server', N1, N2))
        self.assertEqual(base, pairing.proof('0123-4567-89ab-cdef', 'game', 'server', N1, N2))
        with self.assertRaises(ValueError):
            pairing.proof('123456', 'game', 'server', N1, N2)
        with self.assertRaises(ValueError):
            pairing.proof(CODE, 'game', 'server', 'zz', N2)

    def test_verify_strict(self):
        good = pairing.proof(CODE, 'game', 'server', N1, N2)
        for bad in (None, 5, good[:-1], good.upper(), '\u00e9' * 64, ''):
            self.assertFalse(pairing.verify(good, bad))

    def test_limiter_cooldown_and_reset(self):
        clk = Clock()
        lim = pairing.FailureLimiter(3, 30.0, clock=clk)
        for _ in range(2):
            lim.failure()
        self.assertFalse(lim.blocked())
        lim.failure()
        self.assertTrue(lim.blocked())
        clk.t += 29
        self.assertTrue(lim.blocked())
        clk.t += 2
        self.assertFalse(lim.blocked())
        lim.failure()
        self.assertFalse(lim.blocked())

    def test_keepalive_budget(self):
        total = pairing.KEEPALIVE_IDLE + pairing.KEEPALIVE_INTERVAL * pairing.KEEPALIVE_COUNT
        self.assertLessEqual(total, 30)
        self.assertEqual(pairing.MAX_FAILURES, 10)


if __name__ == '__main__':
    unittest.main()
