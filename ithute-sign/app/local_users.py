"""Local IthuteSign employee credential primitives.

No plaintext password persistence. This module deliberately does not authorize
LoanHub operations or reuse employee signatures without per-document consent.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
_SCHEMA = """
CREATE TABLE IF NOT EXISTS local_users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

class LocalUsers:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == "posix":
            os.chmod(self.path.parent, 0o700)
        self.db = sqlite3.connect(str(self.path))
        self.db.executescript(_SCHEMA)
        self.db.commit()
        if os.name == "posix":
            os.chmod(self.path, 0o600)

    def close(self):
        self.db.close()

    def create(self, username: str, password: str, display_name: str) -> str:
        username = username.strip() if isinstance(username, str) else ""
        display_name = display_name.strip() if isinstance(display_name, str) else ""
        if not (3 <= len(username) <= 64 and username.replace("_", "").replace("-", "").isalnum()):
            raise ValueError("Username must be 3–64 letters, digits, underscores or hyphens")
        if not (1 <= len(display_name) <= 150):
            raise ValueError("A display name is required")
        if not isinstance(password, str) or len(password) < 12 or len(password) > 1024:
            raise ValueError("Password must contain at least 12 characters")
        identifier = str(uuid4())
        with self.db:
            self.db.execute(
                "INSERT INTO local_users(id, username, password_hash, display_name) VALUES (?, ?, ?, ?)",
                (identifier, username, _HASHER.hash(password), display_name))
        return identifier

    def authenticate(self, username: str, password: str) -> dict | None:
        if not isinstance(username, str) or not isinstance(password, str):
            return None
        row = self.db.execute(
            "SELECT id, username, password_hash, display_name FROM local_users "
            "WHERE username = ? AND active = 1", (username.strip(),)).fetchone()
        if row is None:
            return None
        try:
            if not _HASHER.verify(row[2], password):
                return None
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return None
        return {"id": row[0], "username": row[1], "display_name": row[3]}

    def deactivate(self, user_id: str):
        with self.db:
            self.db.execute("UPDATE local_users SET active = 0 WHERE id = ?", (user_id,))
