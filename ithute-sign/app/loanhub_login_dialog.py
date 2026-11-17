"""LoanHub login dialog for IthuteSign (no LoanHub backend modifications).

Login response is not treated as an authenticated session until the existing
LoanHub auth schema and company-membership handshake are verified.
"""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                               QPushButton, QLabel)
from loanhub_auth import LoanHubLoginTransport

class LoanHubLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IthuteSign | LoanHub login")
        self.setMinimumWidth(430)
        self.response = None
        self.access_token = None
        self.verified_user = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Sign in with your existing LoanHub account"))
        form = QFormLayout()
        self.origin = QLineEdit("https://api.loanhub.co.ls")
        self.origin.setReadOnly(True)
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("LoanHub account phone number")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        form.addRow("API server", self.origin)
        form.addRow("Phone", self.phone)
        form.addRow("Password", self.password)
        layout.addLayout(form)
        self.status = QLabel("Online login requires an internet connection.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.submit = QPushButton("Sign in to LoanHub")
        self.submit.clicked.connect(self.login)
        layout.addWidget(self.submit)
        self.cancel = QPushButton("Cancel")
        self.cancel.clicked.connect(self.reject)
        layout.addWidget(self.cancel)

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
