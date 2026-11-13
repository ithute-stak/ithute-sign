import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import fitz
from document import Placement, sign_pdf_many


def create_test_png(path, width, height):
    """Generate a valid RGB PNG with PyMuPDF, already a required dependency."""
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height), False)
    pixmap.clear_with(0)
    pixmap.save(str(path))


class ReleaseRegression(unittest.TestCase):
    def test_signed_pdf_and_audit_preserve_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "source.pdf"
            with fitz.open() as doc:
                doc.new_page(width=595, height=842)
                doc.new_page(width=595, height=842)
                doc.save(source)
            original = source.read_bytes()
            ink = folder / "signature.png"
            create_test_png(ink, 200, 80)
            out = folder / "signed.pdf"
            audit = sign_pdf_many(str(source),
                [Placement(0, 50, 70, 150, 60, str(ink)),
                 Placement(1, 60, 90, 180, 65, str(ink))], str(out))
            self.assertEqual(source.read_bytes(), original)
            self.assertTrue(Path(audit).is_file())
            with fitz.open(out) as signed:
                self.assertEqual(len(signed), 2)
                self.assertGreaterEqual(len(signed[0].get_images()), 1)
                self.assertGreaterEqual(len(signed[1].get_images()), 1)

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "source.pdf"
            with fitz.open() as doc:
                doc.new_page()
                doc.save(source)
            ink = folder / "sig.png"
            create_test_png(ink, 80, 30)
            out = folder / "existing.pdf"
            out.write_bytes(b"protected")
            with self.assertRaises(FileExistsError):
                sign_pdf_many(str(source), [Placement(0, 10, 10, 80, 30, str(ink))], str(out))
            self.assertEqual(out.read_bytes(), b"protected")

    def test_rejects_signature_outside_page_without_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "source.pdf"
            with fitz.open() as doc:
                doc.new_page(width=200, height=200)
                doc.save(source)
            ink = folder / "sig.png"
            create_test_png(ink, 80, 30)
            out = folder / "out.pdf"
            with self.assertRaises(ValueError):
                sign_pdf_many(str(source), [Placement(0, 190, 190, 80, 30, str(ink))], str(out))
            self.assertFalse(out.exists())

    def test_rejects_nonexistent_signature_without_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "source.pdf"
            with fitz.open() as doc:
                doc.new_page()
                doc.save(source)
            out = folder / "out.pdf"
            with self.assertRaises(FileNotFoundError):
                sign_pdf_many(str(source), [Placement(0, 20, 20, 80, 30, str(folder / "missing.png"))], str(out))
            self.assertFalse(out.exists())

    def test_rejects_output_equal_to_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "source.pdf"
            with fitz.open() as doc:
                doc.new_page()
                doc.save(source)
            ink = folder / "sig.png"
            create_test_png(ink, 80, 30)
            original = source.read_bytes()
            with self.assertRaises(ValueError):
                sign_pdf_many(str(source), [Placement(0, 20, 20, 80, 30, str(ink))], str(source))
            self.assertEqual(source.read_bytes(), original)

    def test_rejects_existing_audit_without_creating_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "source.pdf"
            with fitz.open() as doc:
                doc.new_page()
                doc.save(source)
            ink = folder / "sig.png"
            create_test_png(ink, 80, 30)
            out = folder / "out.pdf"
            audit = Path(str(out) + ".audit.json")
            audit.write_text("protected")
            with self.assertRaises(FileExistsError):
                sign_pdf_many(str(source), [Placement(0, 20, 20, 80, 30, str(ink))], str(out))
            self.assertFalse(out.exists())
            self.assertEqual(audit.read_text(), "protected")


if __name__ == "__main__":
    unittest.main()
