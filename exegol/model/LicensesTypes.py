from enum import Enum
from typing import Optional
from typing_extensions import NotRequired, TypedDict


# Types
class LicenseType(Enum):
    Community = 0
    Professional = 1
    Team = 2
    Enterprise = 3

# Features
class LicenseFeature(Enum):
    Offline = 0
    All = 1
    AllWrapper = 2
    Sentinel = 3

# Form data
class EnrollmentForm(TypedDict):
    machine_id: str
    machine_name: str
    machine_os: str
    license_id: str
    revoke_previous_machine: NotRequired[bool]
    activation_id: str

# Response data
class LicensesEnumeration(TypedDict):
    type: str
    features: NotRequired[Optional[list[str]]]
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
    offline_session: Optional[str]


class SessionDefaultData(TypedDict):
    license: str
    features: Optional[list[str]]
    license_id: str
    license_owner: str
    user_id: str
    username: str
    expiration_date: int
    exp: int
    iat: int

class SessionData(SessionDefaultData):
    machine_id: str

class SessionOfflineData(SessionDefaultData):
    activation_id: str
