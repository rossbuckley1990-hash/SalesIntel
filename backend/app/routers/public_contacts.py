"""On-demand research of public professional contact routes."""
from fastapi import APIRouter, HTTPException

from app.intelligence.openai_client import InvalidOpenAIJSONError, MissingOpenAIKeyError, OpenAIRequestError
from app.intelligence.public_contacts import research_public_contacts
from app.schemas.public_contacts import PublicContactRequest, PublicContactResult

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


@router.post("/public-contacts", response_model=PublicContactResult)
def public_contacts(request: PublicContactRequest) -> PublicContactResult:
    try:
        return research_public_contacts(request)
    except MissingOpenAIKeyError as exc:
        raise HTTPException(status_code=503, detail="Public contact research is not configured on the server.") from exc
    except (OpenAIRequestError, InvalidOpenAIJSONError) as exc:
        raise HTTPException(status_code=502, detail="Public contact research failed. Please try again.") from exc
