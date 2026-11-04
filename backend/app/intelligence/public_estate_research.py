"""Opt-in public premises context for a user-supplied postcode."""
from typing import Any

from app.intelligence.public_estates import FSA_RECORD, PublicEstateError, normalise_postcode, search_establishments
from app.schemas.universal_research import ResearchObservation, UniversalResearchRequest


def collect_estate_context(request: UniversalResearchRequest) -> tuple[dict, list[ResearchObservation]]:
    """Return source-attributed context; never treat a postcode as site identity."""
    result: dict[str, Any] = {"status": "unavailable", "message": "Public estate context is unavailable; web research continues.",
        "postcode": request.estate_postcode.strip(), "records": [], "retrieved_at": "", "limitations": []}
    if not request.estate_postcode.strip():
        result.update(status="missing_postcode", message="Enter a full postcode to search the public food establishment register.")
        return result, []
    try:
        postcode = normalise_postcode(request.estate_postcode)
        data = search_establishments(postcode, limit=5)
        records, observations = [], []
        retrieved = data.get("retrieved_at", "")
        for record in data.get("records", [])[:5]:
            if not isinstance(record, dict):
                continue
            identifier = str(record.get("id", ""))
            if not identifier.isascii() or not identifier.isdigit() or len(identifier) > 18 or record.get("postcode") != postcode:
                continue
            name = " ".join(str(record.get("name") or "").split())[:255]
            kind = " ".join(str(record.get("business_type") or "").split())[:120]
            if not name:
                continue
            source = FSA_RECORD + identifier
            records.append({"id": identifier, "name": name, "business_type": kind,
                "address": " ".join(str(record.get("address") or "").split())[:300],
                "postcode": postcode, "source_url": source})
            observations.append(ResearchObservation(id=f"FS{len(observations)+1}", source_url=source,
                source_title=f"Food Standards Agency: {name}"[:255], published_date="", retrieved_at=retrieved,
                fact=f"The public food establishment register lists {name}{f' as {kind}' if kind else ''} at postcode {postcode}. This is unverified public register context, not evidence of the exact premises, present occupier, fire or security conditions, maintenance need or purchasing intent.",
                origin="public_api", source_reference=f"Food establishment {identifier}"))
        result.update(status="searched", message="The public food establishment register was checked for the supplied postcode. These are context records, not identified sales requirements.",
            postcode=postcode, records=records, retrieved_at=retrieved, limitations=data.get("limitations", []),
            source=data.get("source"), scanned=data.get("scanned"), more_results_possible=data.get("more_results_possible", True))
        return result, observations
    except (PublicEstateError, ValueError):
        return result, []
