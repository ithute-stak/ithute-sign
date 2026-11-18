"""Offline LoanHub per-field consent dialog; no signature is applied by opening it."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QPushButton, QFrame, QScrollArea)


class SignatureAuthorizationDialog(QDialog):
    def __init__(self, employee_name, options, parent=None):
        """options: [(role, eligible, reason)] for pending employee fields."""
        super().__init__(parent)
        self.setWindowTitle("IthuteSign | Authorize contract signatures")
        self.setMinimumWidth(560)
        self.setMinimumHeight(460)
        self.selected_roles = set()
        self.checks = {}\n        self.selection_labels = {}
        self.setStyleSheet("""
            QDialog { background: #102137; color: #eaf3f8; }
            QLabel#heading { font-size: 22px; font-weight: 800; color: white; }
            QLabel#subtitle { color: #a7bed1; font-size: 12px; }
            QFrame#card { background: #ffffff; border-radius: 10px; }
            QFrame#card QLabel { color: #18344c; }
            QFrame#card QCheckBox { color: #18344c; font-size: 14px; font-weight: 600; }
            QFrame#card QCheckBox:disabled { color: #84919d; }
            QFrame#card QCheckBox::indicator {
                width: 23px; height: 23px; border: 2px solid #5b7286;
                border-radius: 5px; background: white;
            }
            QFrame#card QCheckBox::indicator:checked {
                background: #087e82; border: 2px solid #087e82;
            }
            QFrame#card QCheckBox::indicator:disabled {
                background: #e4e9ee; border: 2px solid #b4bec8;
            }
            QFrame#card QCheckBox:focus { color: #087e82; }
            QPushButton#approve { background: #087e82; color: white;
                border-radius: 8px; padding: 11px; font-weight: 700; }
            QPushButton#approve:disabled { background: #647580; }
            QPushButton#cancel { background: #253c53; color: white;
                border-radius: 8px; padding: 11px; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 22)
        root.setSpacing(13)
        heading = QLabel("Authorize stored signatures")
        heading.setObjectName("heading")
        root.addWidget(heading)
        subtitle = QLabel("Offline LoanHub contract • Signed-in employee: " + employee_name)
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)
        explanation = QLabel("Choose exactly which pending fields may use your enrolled signature. "
            "Unchecked fields will require a fresh signature from their actual signer.")
        explanation.setObjectName("subtitle")
        explanation.setWordWrap(True)
        root.addWidget(explanation)
        card = QFrame()
        card.setObjectName("card")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(20, 20, 20, 18)
        inner.setSpacing(14)
        for role, eligible, reason in options:
            check = QCheckBox(role)
            check.setEnabled(eligible)
            check.setChecked(False)
            self.checks[role] = check
            check.setMinimumHeight(38)
            inner.addWidget(check)
            selection = QLabel("Not selected" if eligible else "Unavailable for this employee")
            selection.setStyleSheet("color: #64748b; font-size: 11px; margin-left: 32px;")
            inner.addWidget(selection)
            self.selection_labels[role] = selection
            check.toggled.connect(
                lambda checked, label=selection: label.setText(
                    "✓ Selected — use my stored signature" if checked else "Not selected"))
            note = QLabel(reason)
            note.setWordWrap(True)
            note.setStyleSheet("color: #667a8b; font-size: 11px; margin-left: 23px;")
            inner.addWidget(note)
        root.addWidget(card)
        self.attest = QCheckBox("I confirm my signing authority and witness attestation")\n        self.attest.setMinimumHeight(32)
        root.addWidget(self.attest)
        attestation_details = QLabel(
            "I am authorized for every selected role and personally witnessed "
            "any signing event I am attesting to.")
        attestation_details.setObjectName("subtitle")
        attestation_details.setWordWrap(True)
        root.addWidget(attestation_details)
        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("cancel")
        cancel.clicked.connect(self.reject)
        self.approve = QPushButton("Continue with selected signatures")
        self.approve.setObjectName("approve")
        self.approve.clicked.connect(self.accept_selection)
        buttons.addWidget(cancel)
        buttons.addWidget(self.approve)
        root.addLayout(buttons)
        for check in self.checks.values():
            check.toggled.connect(self.update_button)
        self.attest.toggled.connect(self.update_button)
        self.update_button()

    def update_button(self):
        self.approve.setEnabled(self.attest.isChecked() and
            any(check.isChecked() for check in self.checks.values()))

    def accept_selection(self):
        if not self.approve.isEnabled():
            return
        self.selected_roles = {
            role for role, check in self.checks.items()
            if check.isEnabled() and check.isChecked()
        }
        self.accept()
