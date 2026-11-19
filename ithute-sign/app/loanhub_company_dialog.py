"""Fail-closed company membership selection for authenticated LoanHub users.

Only explicit active memberships returned by the verified auth/me profile
are eligible. No arbitrary company ID entry and no inferred tenant access.
"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QListWidget,
                               QPushButton, QHBoxLayout)


def active_memberships(profile):
    if not isinstance(profile, dict):
        return []
    memberships = profile.get("memberships")
    if not isinstance(memberships, list):
        return []
    result = []
    seen = set()
    for membership in memberships:
        if not isinstance(membership, dict):
            continue
        company = membership.get("company")
        if not isinstance(company, dict):
            continue
        company_id = company.get("id") or company.get("uuid")
        if not isinstance(company_id, str) or not company_id.strip():
            continue
        if membership.get("is_active") is not True and membership.get("status") != "active":
            continue
        if company.get("is_active") is False or company.get("active") is False:
            continue
        if company_id in seen:
            continue
        seen.add(company_id)
        name = company.get("name") or "Company"
        result.append({"id": company_id, "name": str(name)})
    return result


class LoanHubCompanyDialog(QDialog):
    def __init__(self, memberships, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IthuteSign — Select LoanHub company")
        self.resize(480, 390)
        self.company = None
        layout = QVBoxLayout(self)
        title = QLabel("Choose your company")
        title.setStyleSheet("font-size: 23px; font-weight: 700;")
        layout.addWidget(title)
        explanation = QLabel("Only verified, active LoanHub company memberships are shown.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.items = QListWidget()
        self.companies = active_memberships({"memberships": memberships})
        for company in self.companies:
            self.items.addItem(company["name"])
        layout.addWidget(self.items)
        if not self.companies:
            note = QLabel("No verified active company memberships were returned by LoanHub. Access is blocked.")
            note.setWordWrap(True)
            layout.addWidget(note)
        actions = QHBoxLayout()
        self.confirm = QPushButton("Continue")
        self.confirm.setEnabled(False)
        self.items.currentRowChanged.connect(
            lambda index: self.confirm.setEnabled(0 <= index < len(self.companies)))
        self.confirm.clicked.connect(self.choose)
        actions.addWidget(self.confirm)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        layout.addLayout(actions)

    def choose(self):
        index = self.items.currentRow()
        if 0 <= index < len(self.companies):
            self.company = self.companies[index]
            self.accept()
