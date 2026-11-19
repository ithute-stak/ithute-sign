"""Offline regression smoke checks for IthuteSign.

Run from the ithute-sign directory:
    python -m unittest discover -s tests -p 'test_regression_smoke.py' -v
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"


class SourceRegressionTests(unittest.TestCase):
    def test_python_sources_compile(self):
        for path in sorted(APP.glob("*.py")):
            with self.subTest(path=path.name):
                compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_loanhub_requires_complete_signing(self):
        tree = ast.parse((APP / "loanhub.py").read_text(encoding="utf-8"))
        functions = {node.name: node for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertIn("detect_loanhub", functions)
        self.assertIn("save_loanhub_signed", functions)
        code = ast.get_source_segment((APP / "loanhub.py").read_text(encoding="utf-8"),
                                      functions["save_loanhub_signed"])
        self.assertIn('destination.open("xb")', code)
        self.assertIn("len(pending) != len(captured)", code)
        self.assertIn("destination.unlink(missing_ok=True)", code)

    def test_review_is_before_pdf_save(self):
        text = (APP / "main.py").read_text(encoding="utf-8")
        workflow = text.split("    def auto_sign_loanhub(self):", 1)[1].split(
            "\n    def ", 1)[0]
        self.assertLess(workflow.index("self.review_loanhub_signatures("),
                        workflow.index("save_loanhub_signed("))
        self.assertLess(workflow.index("save_loanhub_signed("),
                        workflow.index("self.show_loanhub_completion("))


if __name__ == "__main__":
    unittest.main()
