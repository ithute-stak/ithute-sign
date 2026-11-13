import tempfile
import unittest
from pathlib import Path
import fitz
from app.document import sign_pdf_many, Placement

class DocumentTests(unittest.TestCase):
    def test_multiple_signatures_preserve_original(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            original = root / "original.pdf"
            signature = root / "signature.png"
            output = root / "signed.pdf"
            document = fitz.open()
            for _ in range(2):
                document.new_page(width=600, height=800)
            document.save(str(original))
            document.close()
            pixels = fitz.Pixmap(fitz.csRGB, (0, 0, 60, 30), False)
            pixels.clear_with(100)
            pixels.save(str(signature))
            original_content = original.read_bytes()
            placements = [Placement(0, 20, 25, 130, 60, str(signature)),
                          Placement(1, 110, 400, 180, 65, str(signature))]
            audit = sign_pdf_many(original, placements, output)
            self.assertEqual(original.read_bytes(), original_content)
            self.assertTrue(Path(audit).is_file())
            with fitz.open(str(output)) as signed:
                self.assertEqual(len(signed), 2)
                self.assertEqual(len(signed[0].get_images()), 1)
                self.assertEqual(len(signed[1].get_images()), 1)
            with self.assertRaises(FileExistsError):
                sign_pdf_many(original, placements, output)
    def test_outside_page_is_rejected_without_partial_output(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            original = root / "original.pdf"
            document = fitz.open()
            document.new_page(width=100, height=100)
            document.save(str(original))
            document.close()
            signature = root / "signature.png"
            pix = fitz.Pixmap(fitz.csRGB, (0, 0, 30, 30), False)
            pix.clear_with(0)
            pix.save(str(signature))
            output = root / "bad.pdf"
            with self.assertRaises(ValueError):
                sign_pdf_many(original, [Placement(0, 90, 90, 40, 40, str(signature))], output)
            self.assertFalse(output.exists())

if __name__ == "__main__":
    unittest.main()
