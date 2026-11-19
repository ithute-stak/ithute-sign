"""Encrypted employee signature vault; password-derived keys are never persisted."""
import base64
import hashlib
import os
import sqlite3
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

class SignatureVault:
    def __init__(self, database):
        self.path = Path(database)
        self.db = sqlite3.connect(str(self.path))
        self.db.execute("""CREATE TABLE IF NOT EXISTS employee_signatures (
            user_id TEXT PRIMARY KEY, salt BLOB NOT NULL, encrypted_png BLOB NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        self.db.commit()

    @staticmethod
    def _cipher(password, salt):
        if not isinstance(password, str) or not password:
            raise ValueError("Password is required")
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000)
        return Fernet(base64.urlsafe_b64encode(key))

    def enroll(self, user_id, password, png):
        from device import validate_signature_png
        image = validate_signature_png(png)
        salt = os.urandom(16)
        encrypted = self._cipher(password, salt).encrypt(image.read_bytes())
        with self.db:
            self.db.execute("""INSERT INTO employee_signatures(user_id,salt,encrypted_png)
                VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                salt=excluded.salt,encrypted_png=excluded.encrypted_png,
                updated_at=CURRENT_TIMESTAMP""", (user_id, salt, encrypted))

    def has_signature(self, user_id):
        return self.db.execute("SELECT 1 FROM employee_signatures WHERE user_id=?", (user_id,)).fetchone() is not None

    def decrypt(self, user_id, password):
        row = self.db.execute("SELECT salt,encrypted_png FROM employee_signatures WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            raise ValueError("No enrolled signature")
        try:
            return self._cipher(password, row[0]).decrypt(row[1])
        except InvalidToken:
            raise ValueError("Cannot unlock signature with supplied credentials") from None

    def close(self):
        self.db.close()
