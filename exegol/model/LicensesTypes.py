from enum import Enum
from typing import Optional
from typing_extensions import NotRequired, TypedDict


# Types
class LicenseType(Enum):
    Community = 0
    Professional = 1
    Enterprise = 2


# Form data
class EnrollmentForm(TypedDict):
    machine_id: str
    machine_name: str
    machine_os: str
    license_id: str
    revoke_previous_machine: NotRequired[bool]


# Response data
class LicensesEnumeration(TypedDict):
    type: str
    valid_until: str
    organization: str
    enrolled_on: str
    last_seen: str


class TokenRotate(TypedDict):
    next_token: str


class LicenseSession(TypedDict):
    session: Optional[str]


class LicenseEnrollment(TypedDict):
    next_token: str
    session: str


class SessionData(TypedDict):
    machine_id: str
    license: str
    license_id: str
    license_owner: str
    username: str
    expiration_date: str
