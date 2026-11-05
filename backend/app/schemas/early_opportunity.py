from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from app.schemas.common import MisiSchema


class EarlyOpportunityRequest(MisiSchema):
    query: str = Field(min_length=8, max_length=600)


class EarlyOpportunityFinding(MisiSchema):
    organisation: str = Field(min_length=1, max_length=180)
    signal: str = Field(min_length=1, max_length=400)
    signal_date: str = Field(max_length=80)
    signal_source_url: str = Field(min_length=1, max_length=2048)
    inferred_need: str = Field(min_length=1, max_length=400)
    fit_and_timing: str = Field(min_length=1, max_length=400)
    uncertainties: str = Field(min_length=1, max_length=400)
    contact_name: str = Field(max_length=180)
    contact_role: str = Field(min_length=1, max_length=180)
    contact_source_url: str = Field(max_length=2048)
    engagement_opener: str = Field(min_length=1, max_length=400)
    discovery_question: str = Field(min_length=1, max_length=300)
    next_action: str = Field(min_length=1, max_length=300)

    @field_validator("signal_source_url", "contact_source_url")
    @classmethod
    def urls_must_be_public_web_links(cls, value: str) -> str:
        if value:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Source URLs must be HTTP or HTTPS links.")
        return value

    @model_validator(mode="after")
    def named_contact_needs_source(self) -> "EarlyOpportunityFinding":
        if self.contact_name and not self.contact_source_url:
            raise ValueError("A named contact must have a source URL.")
        return self


class EarlyOpportunityResult(MisiSchema):
    query: str = Field(min_length=1, max_length=600)
    summary: str = Field(min_length=1, max_length=600)
    findings: list[EarlyOpportunityFinding] = Field(max_length=3)
    limitations: list[str] = Field(max_length=6)
