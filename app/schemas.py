import re
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

# The voice agent may send a date of birth in several shapes depending on how
# the caller says it and how the LLM formats it (e.g. "01/05/1990",
# "1990-01-05", "January 5, 1990"). Pydantic's default date parser only
# accepts ISO format, which silently rejected everything else — this list
# covers the formats we've seen in practice, tried in order.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%m/%d/%y",
    "%B %d, %Y",
    "%B %d %Y",
    "%b %d, %Y",
    "%b %d %Y",
    "%d %B %Y",
    "%d %b %Y",
)


def parse_flexible_date(v):
    """Accepts a date object as-is; parses strings against several known
    formats. Raises ValueError (caught by Pydantic and surfaced as a normal
    422) if nothing matches."""
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        s = v.strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        raise ValueError(
            f"date_of_birth {v!r} is not a recognized date format "
            f"(expected e.g. YYYY-MM-DD or MM/DD/YYYY)"
        )
    raise ValueError("date_of_birth must be a date string")

NAME_RE = re.compile(r"^[A-Za-z'\-\s]{1,50}$")
VALID_SEX = {"Male", "Female", "Other", "Decline to Answer"}
VALID_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


def normalize_phone(v: str) -> str:
    digits = re.sub(r"\D", "", v or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("phone_number must be a valid 10-digit U.S. phone number")
    return digits


class PatientBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    date_of_birth: date
    sex: str
    phone_number: str
    email: Optional[EmailStr] = None

    address_line_1: str = Field(..., min_length=1, max_length=255)
    address_line_2: Optional[str] = None
    city: str = Field(..., min_length=1, max_length=100)
    state: str
    zip_code: str

    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = "English"

    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v):
        if not NAME_RE.match(v):
            raise ValueError("names must be 1-50 alphabetic characters (hyphens/apostrophes allowed)")
        return v.strip()

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_dob(cls, v):
        return parse_flexible_date(v)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v):
        if v > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return v

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v):
        if v not in VALID_SEX:
            raise ValueError(f"sex must be one of {sorted(VALID_SEX)}")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        return normalize_phone(v)

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v):
        if v in (None, ""):
            return v
        return normalize_phone(v)

    @field_validator("state")
    @classmethod
    def validate_state(cls, v):
        v = v.strip().upper()
        if v not in VALID_STATES:
            raise ValueError("state must be a valid 2-letter U.S. state abbreviation")
        return v

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v):
        if not ZIP_RE.match(v.strip()):
            raise ValueError("zip_code must be 5 digits or ZIP+4 format")
        return v.strip()


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    """All fields optional to support partial updates (PUT with partial body)."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v):
        if v is None:
            return v
        if not NAME_RE.match(v):
            raise ValueError("names must be 1-50 alphabetic characters (hyphens/apostrophes allowed)")
        return v.strip()

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_dob(cls, v):
        if v is None:
            return v
        return parse_flexible_date(v)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v):
        if v is not None and v > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return v

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v):
        if v is not None and v not in VALID_SEX:
            raise ValueError(f"sex must be one of {sorted(VALID_SEX)}")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return v
        return normalize_phone(v)

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v):
        if v in (None, ""):
            return v
        return normalize_phone(v)

    @field_validator("state")
    @classmethod
    def validate_state(cls, v):
        if v is None:
            return v
        v = v.strip().upper()
        if v not in VALID_STATES:
            raise ValueError("state must be a valid 2-letter U.S. state abbreviation")
        return v

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v):
        if v is None:
            return v
        if not ZIP_RE.match(v.strip()):
            raise ValueError("zip_code must be 5 digits or ZIP+4 format")
        return v.strip()


class PatientOut(PatientBase):
    patient_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Envelope(BaseModel):
    data: Optional[object] = None
    error: Optional[str] = None
