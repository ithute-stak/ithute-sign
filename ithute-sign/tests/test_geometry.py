import unittest
from app.geometry import fit_rectangle


class GeometryTests(unittest.TestCase):
    def test_aspect_ratio_preserved(self):
        x, y, width, height = fit_rectangle(0, 0, 200, 100, 100, 100)
        self.assertEqual((x, y, width, height), (50, 0, 100, 100))

    def test_landscape_signature(self):
        x, y, width, height = fit_rectangle(10, 20, 100, 100, 400, 200)
        self.assertEqual((x, y, width, height), (10, 45, 100, 50))

    def test_invalid_sizes(self):
        for dims in ((0, 0, 0, 4, 1, 1), (0, 0, 10, 10, 0, 1)):
            with self.assertRaises(ValueError):
                fit_rectangle(*dims)


if __name__ == '__main__':
    unittest.main()
