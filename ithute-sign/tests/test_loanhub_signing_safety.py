"""Regression tests for strict offline LoanHub PDF signing boundaries.

No physical Wacom device or real customer documents are used.
"""
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pymupdf as fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from loanhub import PendingField, detect_loanhub, inspect_loanhub_signatures, save_loanhub_signed


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

    def test_synthetic_pdf_signature_round_trip(self):
        """Exercise real PDF writing and reopening without a real customer contract.

        Only template detection is mocked; image insertion, PDF serialization,
        verification, and preservation of other pages execute normally.
        """
        signature = self.root / "synthetic-signature.png"
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 120, 40), False)
        pixmap.clear_with(0x222222)
        pixmap.save(str(signature))
        field = PendingField(
            "Borrower execution", 6, (57.6, 516.0, 239.0, 533.8),
            None, None, None)
        original = self.source.read_bytes()
        with patch("loanhub.detect_loanhub", return_value=[field]):
            result = save_loanhub_signed(
                self.source, self.output,
                [(field, str(signature), datetime.now(timezone.utc), "Wacom STU-540")])
        self.assertEqual(result, str(self.output.resolve()))
        self.assertEqual(self.source.read_bytes(), original)
        with fitz.open(self.source) as before, fitz.open(self.output) as after:
            self.assertEqual(len(after), 8)
            self.assertEqual(
                [before[i].get_text() for i in range(8) if i != 6],
                [after[i].get_text() for i in range(8) if i != 6])
            region = fitz.Rect(*field.box)
            self.assertTrue(any(
                block.get("type") == 1 and fitz.Rect(block["bbox"]).intersects(region)
                for block in after[6].get_text("dict")["blocks"]))
            self.assertFalse(any(
                block.get("type") == 1 and fitz.Rect(block["bbox"]).intersects(region)
                for block in before[6].get_text("dict")["blocks"]))

    def test_source_is_never_overwritten(self):
        original = self.source.read_bytes()
        with self.assertRaises(ValueError):
            save_loanhub_signed(self.source, self.source, [])
        self.assertEqual(self.source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
