# v0.28 Windows test import fix

Removed accidental Pillow dependency from `tests/test_release_regression.py`. Tests now create PNG fixtures using required PyMuPDF, so `build-windows.bat` can run the test suite with only `requirements.txt` installed. The Wacom bridge is unchanged.

Unzip into `C:\ithute-sign`, preserving folder layout, then run `build-windows.bat` again. The actual Windows build must still be validated on your machine.
