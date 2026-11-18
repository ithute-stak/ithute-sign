"""Regression tests for strict offline LoanHub PDF signing boundaries.

No physical Wacom device or real customer documents are used.
"""
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pymupdf as fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from loanhub import detect_loanhub, inspect_loanhub_signatures, save_loanhub_signed


class LoanHubSigningSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.pdf"
        self.output = self.root / "signed.pdf"
        with fitz.open() as pdf:
            for _ in range(8):
                pdf.new_page()
            pdf.save(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_unknown_template_fails_closed(self):
        with fitz.open(self.source) as pdf:
            with self.assertRaisesRegex(ValueError, "Unrecognized LoanHub"):
                detect_loanhub(pdf)
            with self.assertRaises(ValueError):
                inspect_loanhub_signatures(pdf)

    def test_missing_capture_provenance_rejected_without_output(self):
        with self.assertRaisesRegex(ValueError, "capture method"):
            save_loanhub_signed(
                self.source, self.output,
                [(object(), "signature.png", datetime.now(timezone.utc))])
        self.assertFalse(self.output.exists())

    def test_unknown_capture_provenance_rejected_without_output(self):
        with self.assertRaisesRegex(ValueError, "Unsupported signature capture method"):
            save_loanhub_signed(
                self.source, self.output,
                [(object(), "signature.png", datetime.now(timezone.utc), "Unverified")])
        self.assertFalse(self.output.exists())

    def test_existing_destination_is_never_overwritten(self):
        self.output.write_bytes(b"DO NOT OVERWRITE")
        with self.assertRaises(ValueError):
            save_loanhub_signed(self.source, self.output, [])
        self.assertEqual(self.output.read_bytes(), b"DO NOT OVERWRITE")

    def test_source_is_never_overwritten(self):
        original = self.source.read_bytes()
        with self.assertRaises(ValueError):
            save_loanhub_signed(self.source, self.source, [])
        self.assertEqual(self.source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
