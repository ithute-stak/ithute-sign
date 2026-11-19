"""LoanHub company binding using the real AuthMembershipRead schema.

LoanHub /api/v1/auth/me returns memberships with flat company_id,
branch_id, is_primary and is_active fields. No company object is required.
"""
from __future__ import annotations
from uuid import UUID


def _uuid(value):
    try:
        return str(UUID(str(value))) if value is not None else None
    except (ValueError, TypeError, AttributeError):
        return None


def company_for_user(user):
    if not isinstance(user, dict) or user.get("is_active") is not True:
        return None
    memberships = user.get("memberships")
    if not isinstance(memberships, list):
        return None
    active = []
    for member in memberships:
        if not isinstance(member, dict) or member.get("is_active") is not True:
            continue
        company_id = _uuid(member.get("company_id"))
        if not company_id:
            continue
        branch_id = _uuid(member.get("branch_id"))
        active.append({
            "id": company_id,
            "name": "Company " + company_id[:8],
            "branch_id": branch_id,
            "role": member.get("role"),
            "is_primary": member.get("is_primary") is True,
        })
    if not active:
        return None
    primary = [member for member in active if member["is_primary"]]
    # If one primary membership exists, that is the user's default company.
    if len(primary) == 1:
        return primary[0]
    # Without a unique primary, use the company only if all active memberships
    # belong to the same tenant. Never guess across multiple companies.
    company_ids = {member["id"] for member in active}
    if len(company_ids) == 1:
        return active[0]
    return None
