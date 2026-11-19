"""Offline regression checks for local employee password handling."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from local_users import LocalUsers


class LocalUserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "private" / "users.sqlite3"
        self.store = LocalUsers(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_password_is_hashed_and_login_works(self):
        user_id = self.store.create("employee1", "long-test-password-123", "Test Employee")
        row = self.store.db.execute(
            "SELECT password_hash FROM local_users WHERE id = ?", (user_id,)).fetchone()
        self.assertTrue(row[0].startswith("$argon2id$"))
        self.assertNotIn("long-test-password-123", row[0])
        self.assertEqual(self.store.authenticate("employee1", "long-test-password-123")["id"], user_id)
        self.assertIsNone(self.store.authenticate("employee1", "wrong-password"))

    def test_duplicate_user_and_short_password_rejected(self):
        with self.assertRaises(ValueError):
            self.store.create("employee1", "short", "Test")
        self.store.create("employee1", "long-test-password-123", "Test")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.create("EMPLOYEE1", "another-long-password", "Test")

    def test_deactivated_user_cannot_login(self):
        user_id = self.store.create("employee1", "long-test-password-123", "Test")
        self.store.deactivate(user_id)
        self.assertIsNone(self.store.authenticate("employee1", "long-test-password-123"))

    def test_corrupt_hash_is_not_accepted(self):
        user_id = self.store.create("employee1", "long-test-password-123", "Test")
        with self.store.db:
            self.store.db.execute("UPDATE local_users SET password_hash = ? WHERE id = ?",
                                  ("corrupt", user_id))
        self.assertIsNone(self.store.authenticate("employee1", "long-test-password-123"))


if __name__ == "__main__":
    unittest.main()
