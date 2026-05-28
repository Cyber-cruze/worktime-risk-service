from enum import Enum


class UserRole(str, Enum):
    EMPLOYEE = "EMPLOYEE"
    PROJECT_MANAGER = "PROJECT_MANAGER"

# Приводит роль к внутреннему формату: employee / pm.
def normalize_role(role: str) -> str:

    if role is None:
        return "employee"

    r = str(role).strip().upper()

    if r in ("EMPLOYEE",):
        return "employee"
    if r in ("PROJECT_MANAGER", "PM"):
        return "pm"
    if r in ("BOTH",):
        return "both"

    # Если уже во внутреннем формате — пропускаем
    if r in ("EMPLOYEE", "PM", "BOTH"):
        return r.lower()

    # Fallback
    return "employee"


def is_pm_role(role: str) -> bool:
    # True если роль — Project Manager
    return normalize_role(role) == "pm"