from pydantic import Field

from app.schemas.common import MisiSchema
from app.schemas.evidence_observation import EvidenceObservationRead


class CandidateHypothesis(MisiSchema):
    title: str
    explanation: str
    observation_ids: list[int]
    question: str


class CandidateSite(MisiSchema):
    site: str
    hypotheses: list[CandidateHypothesis]


class CandidateResult(MisiSchema):
    organisation_id: str
    total_observations: int
    analysed_observations: int
    sites: list[CandidateSite]
    observations: list[EvidenceObservationRead]
    limitations: list[str]


class AIHypothesis(MisiSchema):
    title: str = Field(min_length=1, max_length=180)
    explanation: str = Field(min_length=1, max_length=800)
    supporting_observation_ids: list[int] = Field(max_length=8)
    counter_observation_ids: list[int] = Field(max_length=8)
    unknowns: list[str] = Field(max_length=8)
    question: str = Field(min_length=1, max_length=300)


class AIHypothesisResult(MisiSchema):
    hypotheses: list[AIHypothesis] = Field(max_length=3)
    limitations: list[str] = Field(max_length=8)


class AIHypothesisRequest(MisiSchema):
    site: str = Field(min_length=1, max_length=255)
    observation_ids: list[int] = Field(min_length=2, max_length=100)


class AIHypothesisResponse(AIHypothesisResult):
    organisation_id: str
    site: str
    observations: list[EvidenceObservationRead]
