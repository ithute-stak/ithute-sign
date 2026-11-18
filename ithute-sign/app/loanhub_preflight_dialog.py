"""Read-only preflight for offline LoanHub signature fields."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QFrame, QPushButton, QHBoxLayout


class LoanHubPreflightDialog(QDialog):
    def __init__(self, inspection, employee_name, has_signature, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IthuteSign | Inspect LoanHub contract")
        self.setMinimumWidth(600)
        self.setStyleSheet("""
            QDialog { background: #f5f8fc; color: #17324b; }
            QLabel { color: #17324b; }
            QLabel#title { font-size: 21px; font-weight: 800; }
            QLabel#note { color: #52677f; }
            QFrame { background: white; border: 1px solid #d3dfeb;
                     border-radius: 9px; }
            QPushButton { padding: 11px 18px; border-radius: 7px;
                          background: white; color: #17324b; }
            QPushButton#continue { background: #087e82; color: white;
                                   font-weight: 700; }
        """)
        body = QVBoxLayout(self)
        body.setContentsMargins(24, 24, 24, 24)
        heading = QLabel("Review contract signature status")
        heading.setObjectName("title")
        body.addWidget(heading)
        note = QLabel("Inspection only. No signatures are applied until you authorize "
                      "the relevant fields and approve the final PDF.")
        note.setObjectName("note")
        note.setWordWrap(True)
        body.addWidget(note)
        card = QFrame()
        rows = QVBoxLayout(card)
        pending = set(inspection["pending_roles"])
        roles = ("Borrower execution", "Lender execution",
                 "Borrower witness", "Lender witness")
        for role in roles:
            if role in pending:
                if role == "Borrower execution":
                    status = "Requires fresh borrower signature on STU-540"
                elif has_signature:
                    status = "Pending — employee signature may be offered if authorized"
                else:
                    status = "Pending — no enrolled employee signature available"
            else:
                status = "No pending field detected — preserve existing content"
            label = QLabel(role + "  |  " + status)
            label.setWordWrap(True)
            rows.addWidget(label)
        body.addWidget(card)
        note2 = QLabel("Signed labels elsewhere in the PDF are not independent proof "
                       "of handwritten execution. Employee: " + employee_name)
        note2.setObjectName("note")
        note2.setWordWrap(True)
        body.addWidget(note2)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        proceed = QPushButton("Continue to authorization")
        proceed.setObjectName("continue")
        proceed.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(proceed)
        body.addLayout(actions)
