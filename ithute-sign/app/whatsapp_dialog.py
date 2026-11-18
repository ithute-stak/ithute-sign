"""IthuteSign WhatsApp contract delivery dialog."""
import os
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QCheckBox)
from whatsapp_delivery import submit_signed_contract, normalise_whatsapp_number, fetch_delivery_status


class WhatsAppDeliveryDialog(QDialog):
    def __init__(self, token, company, pdf_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Send signed contract via WhatsApp")
        self.setMinimumWidth(470)
        self.token = token
        self.company = company
        self.pdf_path = str(pdf_path)
        self.delivery_id = None
        layout = QVBoxLayout(self)
        layout.setSpacing(13)
        title = QLabel("Send signed contract")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)
        if company:
            layout.addWidget(QLabel("Company: " + str(company["name"])))
        else:
            note = QLabel(
                "Offline-signed document. Signing does not require LoanHub. "
                "Automatic WhatsApp delivery is not yet available for standalone "
                "documents until independent service authentication is configured."
            )
            note.setWordWrap(True)
            layout.addWidget(note)
        layout.addWidget(QLabel("Document: " + Path(pdf_path).name))
        layout.addWidget(QLabel("Client WhatsApp number"))
        self.number = QLineEdit()
        self.number.setPlaceholderText("+266 5xxxxxxx")
        layout.addWidget(self.number)
        layout.addWidget(QLabel("Contract reference"))
        self.reference = QLineEdit()
        self.reference.setMaxLength(100)
        layout.addWidget(self.reference)
        self.consent = QCheckBox("I confirmed the recipient and their consent to receive this contract.")
        layout.addWidget(self.consent)
        actions = QHBoxLayout()
        self.send = QPushButton("Send via WhatsApp")
        self.send.clicked.connect(self.submit)
        if not token or not company:
            self.send.setEnabled(False)
            self.send.setToolTip("Standalone delivery requires a separate authenticated business account")
        actions.addWidget(self.send)
        self.check = QPushButton("Check delivery status")
        self.check.setEnabled(False)
        self.check.clicked.connect(self.check_status)
        actions.addWidget(self.check)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        layout.addLayout(actions)

    def submit(self):
        try:
            number = normalise_whatsapp_number(self.number.text())
            reference = self.reference.text().strip()
            if not reference:
                raise ValueError("Enter the contract reference")
            if not self.consent.isChecked():
                raise ValueError("Confirm the recipient and messaging consent")
            origin = os.environ.get("ITHUTESIGN_DELIVERY_URL", "")
            if not origin:
                raise ValueError("WhatsApp delivery service is not configured")
            self.send.setEnabled(False)
            result = submit_signed_contract(origin, self.token, self.company["id"],
                                            number, self.pdf_path, reference)
            self.delivery_id = str(result["delivery_id"])
            self.check.setEnabled(True)
            self.send.setEnabled(False)
            QMessageBox.information(self, "WhatsApp",
                "Accepted for processing. This does not confirm delivery.\\n"
                "Delivery ID: " + self.delivery_id)
        except (ValueError, ConnectionError) as exc:
            QMessageBox.warning(self, "WhatsApp", str(exc))
        finally:
            if self.delivery_id is None:
                self.send.setEnabled(True)

    def check_status(self):
        if not self.delivery_id:
            return
        try:
            origin = os.environ.get("ITHUTESIGN_DELIVERY_URL", "")
            status = fetch_delivery_status(origin, self.token, self.delivery_id)
            QMessageBox.information(self, "WhatsApp delivery", "Current status: " + status)
        except (ValueError, ConnectionError) as exc:
            QMessageBox.warning(self, "WhatsApp delivery", str(exc))
