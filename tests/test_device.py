import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from app.device import probe_bridge, show_screen


class DeviceTests(unittest.TestCase):
    def test_missing_bridge(self):
        result = probe_bridge(None)
        self.assertFalse(result.connected)
        self.assertEqual(result.code, 127)

    def test_bridge_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = Path(folder) / 'STUCapture.exe'
            bridge.touch()
            for code in (0, 10, 11, 12, 13):
                def run(args, **kwargs):
                    self.assertEqual(args[-1], '--probe')
                    return SimpleNamespace(returncode=code, stdout='', stderr='')
                result = probe_bridge(bridge, runner=run)
                self.assertEqual(result.connected, code == 0)
                self.assertEqual(result.code, code)

    def test_probe_timeout(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = Path(folder) / 'STUCapture.exe'
            bridge.touch()
            def run(*args, **kwargs):
                raise subprocess.TimeoutExpired('STUCapture', 12)
            self.assertEqual(probe_bridge(bridge, runner=run).code, 124)

    def test_only_supported_screens(self):
        with self.assertRaises(ValueError):
            show_screen(None, 'erase')

    def test_welcome(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = Path(folder) / 'STUCapture.exe'
            bridge.touch()
            def run(args, **kwargs):
                self.assertEqual(args[-1], '--welcome')
                return SimpleNamespace(returncode=0, stdout='Screen updated', stderr='')
            self.assertTrue(show_screen(bridge, 'welcome', runner=run).connected)


if __name__ == '__main__':
    unittest.main()
