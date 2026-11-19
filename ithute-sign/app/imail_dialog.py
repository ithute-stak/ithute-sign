"""One-time iMail credentials for sending a locally signed contract."""
import os
import smtplib
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QLabel,
    QPushButton, QMessageBox, QHBoxLayout, QCheckBox, QComboBox,
)
from imail_delivery import send_signed_pdf, validate_recipient


class IMailDeliveryDialog(QDialog):
    def __init__(self, pdf_path, parent=None):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.setWindowTitle("Email signed contract - Batlokoa iMail")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        heading = QLabel("Send signed contract via iMail")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(heading)
        layout.addWidget(QLabel("From: documents@batlokoa.co.ls"))
        form = QFormLayout()
        self.recipient = QLineEdit()
        self.recipient.setPlaceholderText("client@example.com")
        form.addRow("Client email", self.recipient)
        self.reference = QLineEdit()
        self.reference.setMaxLength(100)
        form.addRow("Contract reference", self.reference)
        self.host = QLineEdit(os.environ.get("ITHUTESIGN_IMAIL_SMTP_HOST", ""))
        self.host.setPlaceholderText("SMTP host from iMail administrator")
        form.addRow("iMail SMTP server", self.host)
        self.security = QComboBox()
        self.security.addItem("SSL/TLS (port 465)", ("ssl", 465))
        self.security.addItem("STARTTLS (port 587)", ("starttls", 587))
        form.addRow("Encryption", self.security)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Mailbox password or app password")
        form.addRow("iMail password", self.password)
        layout.addLayout(form)
        self.confirm = QCheckBox("I have verified the client's email address and permission to send this contract.")
        self.confirm.setWordWrap(True) if hasattr(self.confirm, "setWordWrap") else None
        layout.addWidget(self.confirm)
        actions = QHBoxLayout()
        self.send_button = QPushButton("Send signed PDF")
        self.send_button.clicked.connect(self.submit)
        actions.addWidget(self.send_button)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        layout.addLayout(actions)

    def submit(self):
        try:
            if not self.confirm.isChecked():
                raise ValueError("Confirm the recipient and permission before sending")
            recipient = validate_recipient(self.recipient.text())
            self.send_button.setEnabled(False)
            security, port = self.security.currentData()
            send_signed_pdf(
                self.host.text(), port, security,
                "documents@batlokoa.co.ls", self.password.text(),
                recipient, self.pdf_path, self.reference.text()
            )
            self.password.clear()
            QMessageBox.information(
                self, "iMail", "The iMail SMTP server accepted the message for "
                + recipient + ". This does not guarantee inbox delivery."
            )
            self.accept()
        except (ValueError, OSError, smtplib.SMTPException) as exc:
            self.password.clear()
            QMessageBox.warning(self, "iMail sending failed",
                                "Email was not confirmed as submitted. Check SMTP settings and "
                                "delivery logs before retrying.\n" + str(exc))
        finally:
            self.send_button.setEnabled(True)
