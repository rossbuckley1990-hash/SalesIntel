from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.intelligence import (
    InvalidOpenAIJSONError,
    MissingOpenAIKeyError,
    OpenAIRequestError,
    analyse_opportunity_record_with_openai,
    analyse_opportunity_with_openai,
)
from app.intelligence.executive_summary import generate_executive_summary_with_openai
from app.intelligence.early_opportunities import research_early_opportunities
from app.intelligence.internet_research import research_internet_with_openai
from app.intelligence.opportunity_research import (
    autofill_opportunities_with_openai,
    build_chatgpt_assist_prompt,
    import_chatgpt_assist_result,
    research_opportunity_with_openai,
)
from app.models import Opportunity, OpportunityAIAnalysis
from app.schemas.early_opportunity import EarlyOpportunityRequest, EarlyOpportunityResult
from app.schemas import (
    AutofillOpportunitiesRequest,
    AutofillOpportunitiesResponse,
    ChatGPTAssistImportRequest,
    ChatGPTAssistPromptRequest,
    ChatGPTAssistPromptResponse,
    ExecutiveSummaryResult,
    InternetIntelligenceRequest,
    InternetIntelligenceResult,
    OpportunityAIAnalysisResult,
    OpportunityAnalysisRequest,
    OpportunityAnalysisResponse,
    ResearchOpportunityRequest,
    ResearchOpportunityResponse,
)

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


def _safe_openai_request_detail(exc: OpenAIRequestError, context: str) -> str:
    cause = exc.__cause__
    code = getattr(cause, "code", None)
    status_code = getattr(cause, "status_code", None)
    message = str(cause or exc).lower()

    if code == "insufficient_quota" or "insufficient_quota" in message:
        return (
            f"{context} failed because the backend OpenAI project has insufficient quota. "
            "Check OpenAI billing/credits for the project attached to OPENAI_API_KEY, then restart "
            "FastAPI and rerun the request. MiSi has not exposed prompts or secrets to the browser."
        )

    if status_code == 401 or code in {"invalid_api_key", "invalid_request_error"} and "api key" in message:
        return (
            f"{context} failed because the backend OpenAI key was rejected. "
            "Replace OPENAI_API_KEY with a valid project key, restart FastAPI, then retry. "
            "Never place the key in frontend code."
        )

    if status_code == 403 or code in {"permission_denied", "model_not_found"}:
        return (
            f"{context} failed because this backend key does not have access to the selected OPENAI_MODEL. "
            "Choose a model available to the key or update project access, restart FastAPI, then retry."
        )

    if status_code == 404 or "model" in message and "not found" in message:
        return (
            f"{context} failed because the selected OPENAI_MODEL was not found for this backend key. "
            "Use an available model name, restart FastAPI, then retry."
        )

    if status_code == 429:
        return (
            f"{context} failed because the backend OpenAI project is currently rate limited. "
            "Wait briefly or reduce request volume, then retry from MiSi."
        )

    return (
        f"{context} failed. Check OPENAI_API_KEY is valid, OPENAI_MODEL is available to this backend key, "
        "and outbound network access is working. MiSi has not exposed prompts or secrets to the browser."
    )


@router.post("/opportunity-analysis", response_model=OpportunityAnalysisResponse)
def analyse_opportunity(
    request: OpportunityAnalysisRequest,
) -> OpportunityAnalysisResponse:
    try:
        return analyse_opportunity_with_openai(request)
    except MissingOpenAIKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except OpenAIRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_safe_openai_request_detail(exc, "OpenAI analysis request"),
        ) from exc
    except InvalidOpenAIJSONError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned invalid structured JSON for this analysis request.",
        ) from exc


@router.post(
    "/analyse-opportunity/{opportunity_id}",
    response_model=OpportunityAIAnalysisResult,
)
def analyse_existing_opportunity(
    opportunity_id: int,
    db: Session = Depends(get_db),
) -> OpportunityAIAnalysisResult:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    settings = get_settings()
    try:
        result = analyse_opportunity_record_with_openai(opportunity, settings=settings)
    except MissingOpenAIKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except OpenAIRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_safe_openai_request_detail(exc, "OpenAI opportunity analysis request"),
        ) from exc
    except InvalidOpenAIJSONError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned invalid structured JSON for this opportunity analysis request.",
        ) from exc

    db.add(
        OpportunityAIAnalysis(
            opportunity_id=opportunity.id,
            model=settings.openai_model,
            **result.model_dump(),
        )
    )
    db.commit()
    return result


@router.post("/generate-executive-summary", response_model=ExecutiveSummaryResult)
def generate_executive_summary(
    db: Session = Depends(get_db),
) -> ExecutiveSummaryResult:
    settings = get_settings()
    try:
        return generate_executive_summary_with_openai(db, settings=settings)
    except MissingOpenAIKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except OpenAIRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_safe_openai_request_detail(exc, "OpenAI executive summary request"),
        ) from exc
    except InvalidOpenAIJSONError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned invalid structured JSON for this executive summary request.",
        ) from exc


@router.post("/internet-research", response_model=InternetIntelligenceResult)
def run_internet_research(
    request: InternetIntelligenceRequest,
) -> InternetIntelligenceResult:
    settings = get_settings()
    try:
        return research_internet_with_openai(request, settings=settings)
    except MissingOpenAIKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except OpenAIRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_safe_openai_request_detail(exc, "OpenAI internet intelligence request"),
        ) from exc
    except InvalidOpenAIJSONError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned invalid structured JSON for this internet intelligence request.",
        ) from exc


@router.post("/early-opportunities", response_model=EarlyOpportunityResult)
def run_early_opportunities(request: EarlyOpportunityRequest) -> EarlyOpportunityResult:
    try:
        return research_early_opportunities(request, settings=get_settings())
    except MissingOpenAIKeyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OpenAIRequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=_safe_openai_request_detail(exc, "Early opportunity research"),
        ) from exc
    except InvalidOpenAIJSONError as exc:
        raise HTTPException(
            status_code=502,
            detail="OpenAI returned invalid structured JSON for early opportunity research.",
        ) from exc


@router.post(
    "/chatgpt-assist/prompt",
    response_model=ChatGPTAssistPromptResponse,
)
def generate_chatgpt_assist_prompt(
    request: ChatGPTAssistPromptRequest,
) -> ChatGPTAssistPromptResponse:
    return build_chatgpt_assist_prompt(request)


@router.post(
    "/chatgpt-assist/import",
    response_model=ResearchOpportunityResponse,
)
def import_chatgpt_assist_opportunity(
    request: ChatGPTAssistImportRequest,
    db: Session = Depends(get_db),
) -> ResearchOpportunityResponse:
    try:
        return import_chatgpt_assist_result(request, db=db)
    except InvalidOpenAIJSONError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "Pasted ChatGPT output was not valid MiSi structured JSON. "
                "Ask ChatGPT to return JSON only, then paste the full object back into MiSi."
            ),
        ) from exc


@router.post("/research-opportunity", response_model=ResearchOpportunityResponse)
def research_opportunity(
    request: ResearchOpportunityRequest,
    db: Session = Depends(get_db),
) -> ResearchOpportunityResponse:
    settings = get_settings()
    try:
        return research_opportunity_with_openai(request, db=db, settings=settings)
    except MissingOpenAIKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except OpenAIRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_safe_openai_request_detail(
                exc,
                "OpenAI standing-start opportunity research",
            ),
        ) from exc
    except InvalidOpenAIJSONError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned invalid structured JSON for standing-start opportunity research.",
        ) from exc


@router.post("/autofill-opportunities", response_model=AutofillOpportunitiesResponse)
def autofill_opportunities(
    request: AutofillOpportunitiesRequest,
    db: Session = Depends(get_db),
) -> AutofillOpportunitiesResponse:
    settings = get_settings()
    try:
        return autofill_opportunities_with_openai(request, db=db, settings=settings)
    except MissingOpenAIKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
