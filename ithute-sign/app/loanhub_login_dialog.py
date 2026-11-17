"""Polished LoanHub sign-in dialog for IthuteSign."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QPushButton, QLabel, QWidget, QFrame,
                               QCheckBox)
from loanhub_auth import LoanHubLoginTransport


class LoanHubLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IthuteSign — Sign in to LoanHub")
        self.setMinimumSize(510, 570)
        self.resize(540, 610)
        self.setObjectName("loanhubLoginDialog")
        self.response = None
        self.access_token = None
        self.verified_user = None
        self.setStyleSheet("""
            QDialog#loanhubLoginDialog { background: #0b1424; color: #edf4ff; }
            QLabel { color: #e8f0fa; background: transparent; }
            QLabel#eyebrow { color: #5ed6ca; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
            QLabel#headline { color: #ffffff; font-size: 26px; font-weight: 750; }
            QLabel#subheading { color: #a4b5cb; font-size: 13px; }
            QLabel#fieldLabel { color: #dce8f5; font-size: 12px; font-weight: 650; }
            QLabel#hint { color: #8da3bc; font-size: 11px; }
            QLabel#status { color: #a8c0d7; font-size: 12px; }
            QFrame#formCard { background: #122239; border: 1px solid #28405a; border-radius: 16px; }
            QLineEdit { color: #f8fbff; background: #0c1b30; border: 1px solid #35516e;
                        border-radius: 9px; padding: 12px 14px; font-size: 14px; }
            QLineEdit:focus { border: 2px solid #39c8bb; }
            QLineEdit:read-only { color: #a5b6c9; background: #14283f; }
            QPushButton#primaryAction { color: #062327; background: #54d8c7; border: none;
                                         border-radius: 10px; font-size: 14px; font-weight: 750;
                                         padding: 13px; }
            QPushButton#primaryAction:hover { background: #7de9dc; }
            QPushButton#primaryAction:disabled { background: #477e80; color: #c4dbd9; }
            QPushButton#secondaryAction { color: #d0dfed; background: transparent;
                                           border: 1px solid #39516a; border-radius: 9px; padding: 11px; }
            QPushButton#secondaryAction:hover { background: #1a314b; }
            QCheckBox { color: #b7c9db; font-size: 12px; spacing: 8px; }
            QCheckBox::indicator { width: 15px; height: 15px; }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(34, 28, 34, 24)
        outer.setSpacing(0)
        eyebrow = QLabel("ITHUTESIGN  /  LOANHUB")
        eyebrow.setObjectName("eyebrow")
        outer.addWidget(eyebrow)
        outer.addSpacing(12)
        title = QLabel("Welcome back")
        title.setObjectName("headline")
        outer.addWidget(title)
        outer.addSpacing(6)
        subtitle = QLabel("Sign in with your existing LoanHub staff account.")
        subtitle.setObjectName("subheading")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)
        outer.addSpacing(24)

        card = QFrame()
        card.setObjectName("formCard")
        form = QVBoxLayout(card)
        form.setContentsMargins(22, 22, 22, 22)
        form.setSpacing(8)

        def field_label(value):
            label = QLabel(value)
            label.setObjectName("fieldLabel")
            return label

        form.addWidget(field_label("Phone number"))
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("Enter your LoanHub phone number")
        self.phone.setClearButtonEnabled(True)
        self.phone.setMinimumHeight(46)
        form.addWidget(self.phone)
        form.addSpacing(12)
        form.addWidget(field_label("Password"))
        password_row = QHBoxLayout()
        password_row.setSpacing(8)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Enter your password")
        self.password.setMinimumHeight(46)
        self.password.returnPressed.connect(self.login)
        password_row.addWidget(self.password, 1)
        self.show_password = QCheckBox("Show")
        self.show_password.toggled.connect(
            lambda checked: self.password.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password))
        password_row.addWidget(self.show_password)
        form.addLayout(password_row)
        form.addSpacing(14)

        self.submit = QPushButton("Sign in to LoanHub")
        self.submit.setObjectName("primaryAction")
        self.submit.setMinimumHeight(47)
        self.submit.clicked.connect(self.login)
        form.addWidget(self.submit)
        outer.addWidget(card)
        outer.addSpacing(16)

        self.status = QLabel("Secure connection to LoanHub")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        outer.addSpacing(10)
        self.origin = QLineEdit("https://api.loanhub.co.ls")
        self.origin.setReadOnly(True)
        self.origin.setVisible(False)
        hint = QLabel("Your credentials are checked by LoanHub. They are not saved on this computer.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        outer.addWidget(hint)
        outer.addStretch(1)
        self.cancel = QPushButton("Cancel and return to workspace")
        self.cancel.setObjectName("secondaryAction")
        self.cancel.clicked.connect(self.reject)
        outer.addWidget(self.cancel)
        self.phone.setFocus()

    def login(self):
        phone = self.phone.text().strip()
        password = self.password.text()  # Password is never trimmed.
        if not phone or not password:
            self.status.setText("Enter your LoanHub phone number and password.")
            return
        self.submit.setEnabled(False)
        try:
            payload = {"phone": phone, "password": password}
            response = LoanHubLoginTransport(self.origin.text()).post("/api/v1/auth/login", payload)
            # Do not display raw server response or tokens in UI/logs.
            if any(k in response for k in ("mfa_required", "requires_mfa", "otp_required")):
                self.status.setText("This LoanHub account requires additional verification. Use LoanHub to complete it.")
                return
            token = response.get("access_token")
            if not isinstance(token, str) or not token.strip():
                self.status.setText("LoanHub did not return a supported access token. Login not completed.")
                return
            transport = LoanHubLoginTransport(self.origin.text())
            verified = transport.get_authenticated("/api/v1/auth/me", token)
            user = verified.get("user") if isinstance(verified.get("user"), dict) else verified
            if not isinstance(user, dict) or not (user.get("id") or user.get("user_id")):
                self.status.setText("LoanHub session identity could not be verified.")
                return
            if user.get("is_active") is False or user.get("active") is False:
                self.status.setText("LoanHub user account is inactive.")
                return
            if user.get("must_change_password") is True or user.get("requires_password_change") is True:
                self.status.setText("Change your password in LoanHub before using IthuteSign.")
                return
            self.access_token = token
            self.verified_user = user
            self.response = None
            self.password.clear()
            self.accept()
        except Exception as exc:
            self.status.setText(str(exc))
        finally:
            self.submit.setEnabled(True)
