"""Local IthuteSign login and first-account enrollment dialog."""
from pathlib import Path

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QDialogButtonBox)
from local_users import LocalUsers


def default_user_db():
    return Path.home() / ".local" / "share" / "ithutesign" / "users.sqlite3"


class LocalLoginDialog(QDialog):
    def __init__(self, parent=None, db_path=None):
        super().__init__(parent)
        self.setWindowTitle("IthuteSign | Local employee sign in")
        self.setMinimumWidth(390)
        self.user = None
        self.store = LocalUsers(db_path or default_user_db())
        layout = QVBoxLayout(self)
        self.heading = QLabel()
        layout.addWidget(self.heading)
        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setMaxLength(64)
        self.name = QLineEdit()
        self.name.setMaxLength(150)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.Password)
        form.addRow("Username", self.username)
        form.addRow("Display name", self.name)
        form.addRow("Password", self.password)
        form.addRow("Confirm password", self.confirm)
        layout.addLayout(form)
        self.submit = QPushButton()
        self.submit.clicked.connect(self.submit_credentials)
        layout.addWidget(self.submit)
        cancel = QDialogButtonBox(QDialogButtonBox.Cancel)
        cancel.rejected.connect(self.reject)
        layout.addWidget(cancel)
        self.enrollment = self.store.db.execute("SELECT COUNT(*) FROM local_users").fetchone()[0] == 0
        self.name.setVisible(self.enrollment)
        form.labelForField(self.name).setVisible(self.enrollment)
        self.confirm.setVisible(self.enrollment)
        form.labelForField(self.confirm).setVisible(self.enrollment)
        self.heading.setText("Create the first local administrator account" if self.enrollment
                             else "Sign in with your local IthuteSign credentials")
        self.submit.setText("Create account and sign in" if self.enrollment else "Sign in")
        self.password.returnPressed.connect(self.submit_credentials)

    def submit_credentials(self):
        try:
            if self.enrollment:
                if self.password.text() != self.confirm.text():
                    raise ValueError("Passwords do not match")
                self.store.create(self.username.text(), self.password.text(), self.name.text())
            self.user = self.store.authenticate(self.username.text(), self.password.text())
            if self.user is None:
                raise ValueError("Invalid credentials or inactive account")
        except Exception as exc:
            QMessageBox.warning(self, "Authentication failed", str(exc))
            return
        self.accept()

    def done(self, result):
        self.store.close()
        super().done(result)
