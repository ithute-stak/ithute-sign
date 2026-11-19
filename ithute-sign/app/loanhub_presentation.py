"""Presentation helpers for authenticated LoanHub employees.

The LoanHub AuthUserRead schema stores names under user.person.
Never display the login phone number as the person's name.
"""


def employee_display_name(user):
    if not isinstance(user, dict):
        return "LoanHub employee"
    person = user.get("person")
    if isinstance(person, dict):
        parts = [person.get("first_name"), person.get("middle_name"),
                 person.get("last_name")]
        name = " ".join(part.strip() for part in parts
                        if isinstance(part, str) and part.strip())
        if name:
            return name
    for key in ("full_name", "name"):
        value = user.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "LoanHub employee"
