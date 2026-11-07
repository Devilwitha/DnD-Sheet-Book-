import subprocess
import unittest
from unittest import mock

from utils import wifi


class ParserTests(unittest.TestCase):
    def test_split_escaped_colon_and_backslash(self):
        self.assertEqual(wifi.split_terse('My\\:Net:70'), ['My:Net', '70'])
        self.assertEqual(wifi.split_terse('A\\\\B:5'), ['A\\B', '5'])

    def test_signal_clamp_and_invalid(self):
        self.assertEqual(wifi.parse_signal('150'), 100)
        self.assertEqual(wifi.parse_signal('-5'), 0)
        self.assertEqual(wifi.parse_signal('abc'), 0)
        self.assertEqual(wifi.parse_signal(None), 0)

    def test_scan_skips_empty_hidden_and_malformed(self):
        out = 'Home:80\n:60\n--:50\n\nbroken\nCafe\\:Guest:40\nHome:90\n'
        self.assertEqual(wifi.parse_scan_output(out),
                         [('Home', 90), ('Cafe:Guest', 40)])

    def test_status_active(self):
        out = 'no:Other:30\nyes:Home\\:5G:101\n'
        self.assertEqual(wifi.parse_status_output(out), ('Home:5G', 100))

    def test_status_none(self):
        self.assertIsNone(wifi.parse_status_output('no:Other:30\n'))
        self.assertIsNone(wifi.parse_status_output(''))


class CommandTests(unittest.TestCase):
    def test_timeout_is_passed_and_handled(self):
        with mock.patch('utils.wifi.subprocess.run',
                        side_effect=subprocess.TimeoutExpired('nmcli', 1)) as run:
            with self.assertRaises(wifi.WifiError):
                wifi.run_command(['nmcli'], timeout=3)
            self.assertEqual(run.call_args.kwargs['timeout'], 3)

    def test_missing_executable(self):
        with mock.patch('utils.wifi.subprocess.run', side_effect=FileNotFoundError):
            with self.assertRaises(wifi.WifiError):
                wifi.run_command(['nmcli'])

    def test_error_message_redacts_password(self):
        proc = mock.Mock(returncode=4, stdout='', stderr='bad secret123 given')
        with mock.patch('utils.wifi.subprocess.run', return_value=proc):
            with self.assertRaises(wifi.WifiError) as ctx:
                wifi.run_command(['nmcli'], secrets=['secret123'])
        self.assertNotIn('secret123', str(ctx.exception))

    def test_connect_does_not_leak_password(self):
        proc = mock.Mock(returncode=1, stdout='', stderr='failed with hunter2')
        with mock.patch('utils.wifi.sys.platform', 'linux'), \
                mock.patch('utils.wifi.subprocess.run', return_value=proc) as run:
            with self.assertRaises(wifi.WifiError) as ctx:
                wifi.connect('Home', 'hunter2')
        self.assertNotIn('hunter2', str(ctx.exception))
        self.assertIn('hunter2', run.call_args.args[0])

    def test_scan_uses_mocked_subprocess(self):
        proc = mock.Mock(returncode=0, stdout='A:20\n:10\n', stderr='')
        with mock.patch('utils.wifi.sys.platform', 'linux'), \
                mock.patch('utils.wifi.subprocess.run', return_value=proc):
            self.assertEqual(wifi.scan(), [('A', 20)])

    def test_background_reports_error(self):
        results = []

        def boom():
            raise wifi.WifiError('nope')

        thread = wifi.run_in_background(boom, lambda r, e: results.append((r, e)))
        thread.join(2)
        self.assertEqual(results, [(None, 'nope')])


if __name__ == '__main__':
    unittest.main()
