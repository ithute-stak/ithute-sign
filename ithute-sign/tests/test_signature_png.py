import tempfile
import unittest
from pathlib import Path
import fitz
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from device import validate_signature_png


class SignaturePngTests(unittest.TestCase):
    def test_rejects_missing_file(self):
        with self.assertRaises(ValueError):
            validate_signature_png("not-a-real-signature.png")

    def test_rejects_non_png(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fake.png"
            path.write_bytes(b"not a signature" * 20)
            with self.assertRaises(ValueError):
                validate_signature_png(path)

    def test_rejects_blank_transparent_png(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "blank.png"
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 50), True)
            # PyMuPDF clear_with(0) makes RGBA pixels opaque; set alpha explicitly.
            for y in range(50):
                for x in range(50):
                    pix.set_pixel(x, y, (0, 0, 0, 0))
            pix.save(str(path))
            with self.assertRaises(ValueError):
                validate_signature_png(path)

    def test_accepts_visible_transparent_ink(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ink.png"
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 50), True)
            # PyMuPDF clear_with(0) makes RGBA pixels opaque; set alpha explicitly.
            for y in range(50):
                for x in range(50):
                    pix.set_pixel(x, y, (0, 0, 0, 0))
            pix.set_pixel(20, 20, (12, 36, 80, 255))
            pix.save(str(path))
            self.assertEqual(validate_signature_png(path), path)


if __name__ == "__main__":
    unittest.main()
