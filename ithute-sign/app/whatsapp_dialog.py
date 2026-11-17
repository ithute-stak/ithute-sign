"""IthuteSign WhatsApp contract delivery dialog."""
import os
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QCheckBox)
from whatsapp_delivery import submit_signed_contract, normalise_whatsapp_number


class WhatsAppDeliveryDialog(QDialog):
    def __init__(self, token, company, pdf_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Send signed contract via WhatsApp")
        self.setMinimumWidth(470)
        self.token = token
        self.company = company
        self.pdf_path = str(pdf_path)
        layout = QVBoxLayout(self)
        layout.setSpacing(13)
        title = QLabel("Send signed contract")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Company: " + str(company["name"])))
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
        self.consent.setWordWrap(True)
        layout.addWidget(self.consent)
        actions = QHBoxLayout()
        self.send = QPushButton("Send via WhatsApp")
        self.send.clicked.connect(self.submit)
        actions.addWidget(self.send)
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
            QMessageBox.information(self, "WhatsApp",
                "Submitted to WhatsApp. This does not yet confirm delivery.\\n"
                "Delivery ID: " + str(result["delivery_id"]))
            self.accept()
        except (ValueError, ConnectionError) as exc:
            QMessageBox.warning(self, "WhatsApp", str(exc))
        finally:
            self.send.setEnabled(True)
