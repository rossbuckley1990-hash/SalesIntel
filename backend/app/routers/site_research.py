"""Research one measured public-data signal using its source context."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.intelligence.openai_client import InvalidOpenAIJSONError, MissingOpenAIKeyError, OpenAIRequestError
from app.intelligence.site_research import research_site
from app.models.public_site_reference import PublicSiteReference

router = APIRouter(prefix="/api/virtual-sensors/false-alarms", tags=["virtual sensors"])


class ResearchRequest(BaseModel):
    property_type: str = Field(min_length=1, max_length=255)


@router.post("/{uprn}/research")
def research_false_alarm_site(uprn: str, request: ResearchRequest, db: Session = Depends(get_db)):
    from app.routers.virtual_sensor import get_site_detail, inspection_context

    detail = get_site_detail(db, uprn, request.property_type)
    references = db.scalars(select(PublicSiteReference).where(PublicSiteReference.uprn == uprn).limit(31)).all()
    source_refs = [{"uprn": item.uprn, "organisation_id": item.organisation_id,
                    "organisation_name": item.organisation_name, "site_name": item.site_name,
                    "postcode": item.postcode, "source_url": item.source_url,
                    "source_period": item.source_period} for item in references]
    if len(references) > 30:
        raise HTTPException(status_code=422, detail="Too many historical site matches; review the identifier before research.")
    # Send aggregate facts, not the full list of individual incident records.
    # Only public, attributed candidate records for this UPRN are supplied. The
    # inspection match is campus-level, not proof of the inspected block's UPRN.
    inspection = jsonable_encoder(inspection_context(uprn, db))
    inspection["matches"] = inspection["matches"][:10]
    context = {"site": jsonable_encoder({key: value for key, value in detail.items() if key != "incidents"}),
               "published_site_references": source_refs, "candidate_inspection_context": inspection}
    try:
        result = research_site(context)
    except MissingOpenAIKeyError as exc:
        raise HTTPException(status_code=503, detail="Public site research is not configured on the server.") from exc
    except OpenAIRequestError as exc:
        raise HTTPException(status_code=502, detail="The configured research provider could not complete site research.") from exc
    except InvalidOpenAIJSONError as exc:
        raise HTTPException(status_code=502, detail="The research provider returned invalid site research.") from exc
    return {"site": context["site"], "site_references": source_refs, "research": result.model_dump()}
