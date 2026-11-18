"""Branded, accessible local employee sign-in and initial enrollment."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFrame, QWidget, QCheckBox)
from local_users import LocalUsers


def default_user_db():
    return Path.home() / ".local" / "share" / "ithutesign" / "users.sqlite3"


class LocalLoginDialog(QDialog):
    def __init__(self, parent=None, db_path=None):
        super().__init__(parent)
        self.setWindowTitle("IthuteSign | Secure employee access")
        self.setObjectName("loginDialog")
        self.setMinimumSize(540, 560)
        self.resize(570, 620)
        self.user = None
        self.store = LocalUsers(db_path or default_user_db())
        self.enrollment = self.store.db.execute(
            "SELECT COUNT(*) FROM local_users").fetchone()[0] == 0

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 24)
        root.setSpacing(0)

        brand = QLabel("ITHUTE<span style='color:#21c6bd'>SIGN</span>")
        brand.setObjectName("brand")
        brand.setTextFormat(Qt.RichText)
        root.addWidget(brand)
        tagline = QLabel("SECURE DOCUMENT SIGNING")
        tagline.setObjectName("tagline")
        root.addWidget(tagline)
        root.addSpacing(27)

        panel = QFrame()
        panel.setObjectName("loginCard")
        card = QVBoxLayout(panel)
        card.setContentsMargins(30, 28, 30, 26)
        card.setSpacing(12)
        self.heading = QLabel(
            "Set up your workspace" if self.enrollment else "Welcome back")
        self.heading.setObjectName("heading")
        card.addWidget(self.heading)
        subtitle = QLabel(
            "Create the first local employee account to get started."
            if self.enrollment else
            "Sign in to access documents and your registered signature.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitle")
        card.addWidget(subtitle)
        card.addSpacing(9)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        form.setVerticalSpacing(10)

        self.username = QLineEdit()
        self.username.setObjectName("field")
        self.username.setPlaceholderText("Your employee username")
        self.username.setMaxLength(64)
        self.name = QLineEdit()
        self.name.setObjectName("field")
        self.name.setPlaceholderText("Full name")
        self.name.setMaxLength(150)
        self.password = QLineEdit()
        self.password.setObjectName("field")
        self.password.setPlaceholderText(
            "Create a password (12+ characters)" if self.enrollment else "Enter your password")
        self.password.setEchoMode(QLineEdit.Password)
        self.confirm = QLineEdit()
        self.confirm.setObjectName("field")
        self.confirm.setPlaceholderText("Re-enter your password")
        self.confirm.setEchoMode(QLineEdit.Password)

        form.addRow("Username", self.username)
        if self.enrollment:
            form.addRow("Full name", self.name)
        form.addRow("Password", self.password)
        if self.enrollment:
            form.addRow("Confirm password", self.confirm)
        card.addLayout(form)

        self.show_password = QCheckBox("Show password")
        self.show_password.toggled.connect(self.toggle_password_visibility)
        card.addWidget(self.show_password)
        card.addSpacing(7)

        self.submit = QPushButton(
            "Create account and continue" if self.enrollment else "Sign in securely")
        self.submit.setObjectName("primaryButton")
        self.submit.setMinimumHeight(48)
        self.submit.clicked.connect(self.submit_credentials)
        card.addWidget(self.submit)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(self.reject)
        card.addWidget(self.cancel_button)
        root.addWidget(panel)
        root.addStretch(1)
        footer = QLabel("LOCAL EMPLOYEE ACCESS  •  PASSWORDS PROTECTED WITH ARGON2ID")
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignCenter)
        footer.setWordWrap(True)
        root.addWidget(footer)
        self.username.returnPressed.connect(self.submit_credentials)
        self.password.returnPressed.connect(self.submit_credentials)
        self.confirm.returnPressed.connect(self.submit_credentials)
        self.username.setFocus()

        self.setStyleSheet("""
            QDialog#loginDialog { background: #101f32; color: #f2f7fc; }
            QLabel#brand { font-size: 28px; font-weight: 900; color: white; }
            QLabel#tagline { color: #92a9c1; font-size: 10px; letter-spacing: 2px; }
            QFrame#loginCard { background: #ffffff; border-radius: 16px; }
            QFrame#loginCard QLabel { color: #17324f; }
            QLabel#heading { font-size: 23px; font-weight: 800; }
            QLabel#subtitle { font-size: 12px; color: #63768b; }
            QFrame#loginCard QLabel#subtitle { color: #63768b; }
            QFrame#loginCard QLineEdit {
                background: #f8fafc; color: #142c45; border: 1px solid #cad7e4;
                border-radius: 8px; padding: 11px 12px; min-height: 22px;
                selection-background-color: #087e82;
            }
            QFrame#loginCard QLineEdit:focus { border: 2px solid #087e82; }
            QFrame#loginCard QCheckBox { color: #3c526a; font-size: 12px; }
            QPushButton#primaryButton {
                background: #087e82; color: white; border: 0; border-radius: 9px;
                font-weight: 700; font-size: 14px; padding: 12px;
            }
            QPushButton#primaryButton:hover { background: #096d72; }
            QPushButton#primaryButton:focus { border: 2px solid #25c8bf; }
            QPushButton#cancelButton {
                color: #425a71; background: transparent; border: 0;
                padding: 8px; font-weight: 600;
            }
            QLabel#footer { color: #9bb0c4; font-size: 10px; }
        """)

    def toggle_password_visibility(self, checked):
        mode = QLineEdit.Normal if checked else QLineEdit.Password
        self.password.setEchoMode(mode)
        self.confirm.setEchoMode(mode)

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
