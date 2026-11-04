"""Manually supplied observations. Grouping by an ID does not verify identity."""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.config import get_settings
from app.intelligence.openai_client import InvalidOpenAIJSONError, MissingOpenAIKeyError, OpenAIRequestError
from app.intelligence.side_channel import candidate_sites, known_site, public_web_url, source_key, synthesise_hypotheses
from app.models.evidence_observation import EvidenceObservation
from app.schemas.side_channel import AIHypothesisRequest, AIHypothesisResponse, CandidateResult
from app.schemas.evidence_observation import (
    AccountPage, AccountSummary, EvidenceDossier, EvidenceImportRequest,
    EvidenceImportResult, EvidenceObservationRead, EvidencePage,
)

router = APIRouter(prefix="/api/evidence-observations", tags=["evidence observations"])


def _fingerprint(observation) -> str:
    # Do not include retrieval time or display names: re-fetching the same claim
    # should not add evidence. Different statements from the same source survive.
    fields = observation.model_dump(mode="json", include={
        "organisation_id", "site", "category", "observed_statement", "source_reference",
        "source_url", "published_at", "observed_at",
    })
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@router.post("/import", response_model=EvidenceImportResult)
def import_evidence(request: EvidenceImportRequest, db: Session = Depends(get_db)) -> EvidenceImportResult:
    observations = {}
    for observation in request.observations:
        observations.setdefault(_fingerprint(observation), observation)
    fingerprints = list(observations)
    existing: set[str] = set()
    try:
        # Bounded queries avoid SQLite parameter limits and avoid an N+1 lookup.
        for start in range(0, len(fingerprints), 500):
            existing.update(db.scalars(select(EvidenceObservation.fingerprint).where(
                EvidenceObservation.fingerprint.in_(fingerprints[start:start + 500])
            )).all())
        new_records = [EvidenceObservation(fingerprint=fingerprint, **observation.model_dump())
                       for fingerprint, observation in observations.items() if fingerprint not in existing]
        db.add_all(new_records)
        db.commit()
    except IntegrityError as exc:
        # A concurrent import may have won the unique-key race. Roll back the
        # whole batch and let the caller retry; never commit a partial batch.
        db.rollback()
        original = exc.orig
        if (getattr(original, "sqlstate", None) == "23505" or
                "UNIQUE constraint failed: evidence_observations.fingerprint" in str(original)):
            raise HTTPException(status_code=409, detail="Evidence import conflicted with another write; retry the whole batch.") from exc
        raise
    except Exception:
        db.rollback()
        raise
    return EvidenceImportResult(imported=len(new_records), duplicates=len(request.observations) - len(new_records))


def _page(db: Session, organisation_id: str | None, limit: int, offset: int):
    filters = [] if organisation_id is None else [EvidenceObservation.organisation_id == organisation_id]
    total = db.scalar(select(func.count()).select_from(EvidenceObservation).where(*filters)) or 0
    items = db.scalars(select(EvidenceObservation).where(*filters).order_by(EvidenceObservation.id.desc()).offset(offset).limit(limit)).all()
    return items, total


@router.get("", response_model=EvidencePage)
def list_evidence(organisation_id: str | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)) -> EvidencePage:
    items, total = _page(db, organisation_id, limit, offset)
    return EvidencePage(items=[EvidenceObservationRead.model_validate(item) for item in items], total=total)


@router.get("/accounts", response_model=AccountPage)
def list_accounts(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)) -> AccountPage:
    total = db.scalar(select(func.count(func.distinct(EvidenceObservation.organisation_id)))) or 0
    rows = db.execute(select(EvidenceObservation.organisation_id, func.min(EvidenceObservation.organisation_name), func.count()).group_by(EvidenceObservation.organisation_id).order_by(EvidenceObservation.organisation_id).offset(offset).limit(limit)).all()
    return AccountPage(items=[AccountSummary(organisation_id=org, organisation_name=name, observation_count=count) for org, name, count in rows], total=total)


@router.get("/accounts/{organisation_id}", response_model=EvidenceDossier)
def account_dossier(organisation_id: str, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)) -> EvidenceDossier:
    items, total = _page(db, organisation_id, limit, offset)
    if not total:
        raise HTTPException(status_code=404, detail="No observations for this supplied organisation identifier")
    name = db.scalar(select(func.min(EvidenceObservation.organisation_name)).where(EvidenceObservation.organisation_id == organisation_id))
    return EvidenceDossier(organisation_id=organisation_id, organisation_name=name, observations=[EvidenceObservationRead.model_validate(item) for item in items], total=total)


@router.get("/accounts/{organisation_id}/hypotheses", response_model=CandidateResult)
def account_hypotheses(organisation_id: str, db: Session = Depends(get_db)) -> CandidateResult:
    items, total = _page(db, organisation_id, 200, 0)
    if not total:
        raise HTTPException(status_code=404, detail="No observations for this supplied organisation identifier")
    observations = [item for item in items if known_site(item.site) and public_web_url(item.source_url)]
    limitations = [
        "Records, categories, site names and organisation identifiers are supplied and unverified; an HTTP link does not establish public access or support for a claim.",
        "Distinct URLs or source references do not establish independent reporting; check syndication, relevance, dates and counter-evidence.",
        "Candidate patterns are exploratory prompts, not calibrated predictions or evidence of supplier failure, a breach or buying intent.",
        "Only explicitly named sites with HTTP(S) sources are considered; unknown sites are not combined.",
    ]
    if total > len(items):
        limitations.append(f"Only the most recent {len(items)} of {total} observations were considered.")
    return CandidateResult(organisation_id=organisation_id, total_observations=total,
        analysed_observations=len(observations), sites=candidate_sites(observations),
        observations=[EvidenceObservationRead.model_validate(item) for item in observations], limitations=limitations)


@router.post("/accounts/{organisation_id}/ai-hypotheses", response_model=AIHypothesisResponse)
def account_ai_hypotheses(organisation_id: str, request: AIHypothesisRequest,
                          db: Session = Depends(get_db)) -> AIHypothesisResponse:
    if not known_site(request.site):
        raise HTTPException(status_code=422, detail="Select a specifically identified site.")
    # Strict scope: only explicitly selected IDs in the selected organisation and
    # exact site can leave MiSi. The request does not fetch or verify links.
    selected_ids = set(request.observation_ids)
    if len(selected_ids) != len(request.observation_ids):
        raise HTTPException(status_code=422, detail="Select each observation only once.")
    items = db.scalars(select(EvidenceObservation).where(
        EvidenceObservation.organisation_id == organisation_id, EvidenceObservation.site == request.site,
        EvidenceObservation.id.in_(selected_ids)
    ).order_by(EvidenceObservation.id.desc())).all()
    if len(items) != len(selected_ids):
        raise HTTPException(status_code=422, detail="Every selected observation must belong to the selected organisation and site.")
    observations = [item for item in items if public_web_url(item.source_url)]
    if len(observations) != len(items):
        raise HTTPException(status_code=422, detail="Every selected observation requires a public-looking HTTP(S) source URL.")
    if len({source_key(item.source_url) for item in observations}) < 2:
        raise HTTPException(status_code=422, detail="At least two distinct web source URLs are required for this site; source independence and public access must still be checked.")
    try:
        result = synthesise_hypotheses(organisation_id, request.site, observations, settings=get_settings())
    except MissingOpenAIKeyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OpenAIRequestError as exc:
        from app.routers.intelligence import _safe_openai_request_detail
        raise HTTPException(status_code=502, detail=_safe_openai_request_detail(exc, "OpenAI hypothesis synthesis")) from exc
    except InvalidOpenAIJSONError as exc:
        raise HTTPException(status_code=502, detail="OpenAI returned invalid or ungrounded hypothesis JSON.") from exc
    limitations = list(result.limitations)
    limitations.append("Only observations with HTTP(S) source URLs were sent; accessibility, accuracy, source independence and entity identity are not verified.")
    return AIHypothesisResponse(organisation_id=organisation_id, site=request.site,
        observations=[EvidenceObservationRead.model_validate(item) for item in observations],
        hypotheses=result.hypotheses, limitations=limitations)
