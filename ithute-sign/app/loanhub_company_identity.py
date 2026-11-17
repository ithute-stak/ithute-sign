"""Resolve a single company from LoanHub's verified authenticated user profile.

Never infer a company from phone numbers, names or previous sessions.
"""
from loanhub_company_dialog import active_memberships


def company_for_user(user):
    if not isinstance(user, dict):
        return None
    candidates = active_memberships(user)
    company = user.get("company")
    company_id = user.get("company_id") or user.get("company_uuid")
    if isinstance(company, dict):
        company_id = company.get("id") or company.get("uuid") or company_id
        company_name = company.get("name") or "Company"
        if company.get("is_active") is False or company.get("active") is False:
            return None
    else:
        company_name = "Company"
    if isinstance(company_id, str) and company_id.strip():
        candidates.append({"id": company_id, "name": str(company_name)})
    unique = {entry["id"]: entry for entry in candidates}
    # Ambiguous company binding must not silently pick a tenant.
    return next(iter(unique.values())) if len(unique) == 1 else None
