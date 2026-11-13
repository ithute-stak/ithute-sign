import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ReleasePackageTests(unittest.TestCase):
    def test_all_python_sources_parse(self):
        for folder in ("app", "tests"):
            for path in (ROOT / folder).glob("*.py"):
                with self.subTest(path=path.name):
                    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_windows_release_requires_real_bridge_and_release_marker(self):
        script = (ROOT / "build-windows.bat").read_text(encoding="utf-8").lower()
        self.assertIn('if /i "%~1"=="--release"', script)
        self.assertIn("release-mode.flag", script)
        self.assertIn("interop.wgssstu.dll", script)

    def test_installer_requires_64_bit_and_includes_release_folder(self):
        installer = (ROOT / "installer" / "IthuteSign.iss").read_text(encoding="utf-8").lower()
        self.assertIn("architecturesallowed=x64compatible", installer)
        self.assertIn('source: "..\\dist\\ithutesign\\*"', installer)
        self.assertIn("appversion=", installer)

    def test_source_change_protection_present(self):
        source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("self.source_digest = sha256(path)", source)
        self.assertIn("sha256(self.source) != self.source_digest", source)

    def test_release_preflight_checks_freshness_and_sha256(self):
        script = (ROOT / "preflight-release.ps1").read_text(encoding="utf-8")
        self.assertIn("LastWriteTimeUtc", script)
        self.assertIn("Get-FileHash -Algorithm SHA256", script)

    def test_ui_guards_against_empty_capture_and_confirms_save(self):
        source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("def confirm_capture(self):", source)
        self.assertIn("validate_signature_png(target)", source)
        self.assertIn("Confirm signature placement", source)
        self.assertIn("self.window.signatures[self.drag_index] = replace(", source)

if __name__ == "__main__":
    unittest.main()
