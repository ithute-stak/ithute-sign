"""Read-only, tenant-scoped LoanHub loans table."""
from urllib.parse import urlencode
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox)
from loanhub_auth import LoanHubLoginTransport

COLUMNS = ("Folio / loan", "Folio No.", "Principal", "Instalment",
           "Balance", "Next due", "Progress", "Status", "Contract", "Actions")


def money(value):
    try:
        return "LSL {:,.2f}".format(float(value))
    except (ValueError, TypeError):
        return "—"


class LoanHubLoansDialog(QDialog):
    def __init__(self, token, company, parent=None):
        super().__init__(parent)
        self.token = token
        self.company = company
        self.offset = 0
        self.setWindowTitle("IthuteSign — Loans & contracts")
        self.resize(1250, 720)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("Loans & contracts")
        title.setStyleSheet("font-size: 23px; font-weight: 750;")
        layout.addWidget(title)
        layout.addWidget(QLabel(str(company["name"]) + "  •  Read-only LoanHub records"))
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        self.status = QLabel("Loading loans…")
        actions.addWidget(self.status, 1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)
        more = QPushButton("Next 100")
        more.clicked.connect(self.next_page)
        actions.addWidget(more)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.refresh()

    def next_page(self):
        self.offset += 100
        self.refresh()

    def refresh(self):
        try:
            # The backend enforces the X-Company-ID tenant and branch role.
            rows = LoanHubLoginTransport("https://api.loanhub.co.ls").get_authenticated(
                "/api/v1/loans/?" + urlencode({"skip": self.offset, "limit": 100}),
                self.token, headers={"X-Company-ID": self.company["id"],
                                     "X-Active-Role": str(self.company.get("role") or "")})
            if not isinstance(rows, list):
                raise ValueError("LoanHub returned an unexpected loan list")
            self.table.setRowCount(len(rows))
            for index, loan in enumerate(rows):
                if not isinstance(loan, dict) or str(loan.get("company_id")) != self.company["id"]:
                    raise ValueError("Loan company scope mismatch")
                total = float(loan.get("total_repayable") or 0)
                paid = float(loan.get("amount_paid") or 0)
                progress = "{:.0f}%".format(max(0, min(100, paid / total * 100))) if total > 0 else "—"
                values = (
                    str(loan.get("loan_reference") or "—"),
                    str(loan.get("folio_number") or "—"),
                    money(loan.get("principal_amount")),
                    money(loan.get("installment_amount")),
                    money(loan.get("balance")),
                    str(loan.get("first_payment_due") or "—"),
                    progress,
                    str(loan.get("status") or "—"),
                    "Not checked",
                    "View (coming next)",
                )
                for column, value in enumerate(values):
                    self.table.setItem(index, column, QTableWidgetItem(value))
            self.status.setText("Showing {} loans (offset {})".format(len(rows), self.offset))
        except Exception:
            self.table.setRowCount(0)
            self.status.setText("Unable to load authorised LoanHub loans")
            QMessageBox.warning(self, "LoanHub", "Could not load the company's loans. Check your connection and access permissions.")
