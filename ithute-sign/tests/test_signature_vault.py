"""Tests for encrypted signature enrollment and credential-bound retrieval."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from local_users import LocalUsers
from signature_vault import SignatureVault


class SignatureVaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "users.db"
        self.users = LocalUsers(self.db_path)
        self.user_id = self.users.create("employee1", "strong-password-123", "Employee One")
        self.vault = SignatureVault(self.db_path)

    def tearDown(self):
        self.vault.close()
        self.users.close()
        self.tmp.cleanup()

    def test_encrypted_storage_and_retrieval(self):
        # A signature is a PNG; stub only the image validation so no hardware is required.
        from unittest.mock import patch
        image = Path(self.tmp.name) / "signature.png"
        image.write_bytes(b"signature-test-png-content")
        with patch("device.validate_signature_png", return_value=image):
            self.vault.enroll(self.user_id, "strong-password-123", image)
        self.assertTrue(self.vault.has_signature(self.user_id))
        self.assertEqual(self.vault.decrypt(self.user_id, "strong-password-123"), image.read_bytes())
        ciphertext = self.vault.db.execute(
            "SELECT encrypted_png FROM employee_signatures WHERE user_id=?", (self.user_id,)).fetchone()[0]
        self.assertNotIn(image.read_bytes(), ciphertext)

    def test_wrong_password_and_missing_signature(self):
        from unittest.mock import patch
        image = Path(self.tmp.name) / "signature.png"
        image.write_bytes(b"signature-test-png-content")
        with self.assertRaises(ValueError):
            self.vault.decrypt(self.user_id, "strong-password-123")
        with patch("device.validate_signature_png", return_value=image):
            self.vault.enroll(self.user_id, "strong-password-123", image)
        with self.assertRaises(ValueError):
            self.vault.decrypt(self.user_id, "wrong-password")
        with self.assertRaises(ValueError):
            self.vault.decrypt("another-user", "strong-password-123")


if __name__ == "__main__":
    unittest.main()
