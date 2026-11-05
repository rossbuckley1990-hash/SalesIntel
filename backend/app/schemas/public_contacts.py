"""Public contact leads require independent checking against their sources."""
from typing import Literal

from pydantic import Field

from app.schemas.common import MisiSchema


class PublicContactRequest(MisiSchema):
    organisation: str = Field(min_length=2, max_length=255)
    contact_name: str = Field(default="", max_length=180)
    contact_role: str = Field(default="", max_length=240)
    location: str = Field(default="", max_length=255)


class PublicContact(MisiSchema):
    name: str = Field(max_length=180)
    role: str = Field(max_length=240)
    kind: Literal["email", "phone"]
    value: str = Field(min_length=3, max_length=255)
    source_url: str = Field(min_length=1, max_length=2048)
    source_title: str = Field(min_length=1, max_length=255)
    source_date: str = Field(max_length=80)
    evidence_quote: str = Field(min_length=1, max_length=300)


class PublicContactResult(MisiSchema):
    organisation: str
    contacts: list[PublicContact]
    limitations: list[str]
