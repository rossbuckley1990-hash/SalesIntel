from app.intelligence import executive_summary
from app.intelligence import internet_research
from app.intelligence import opportunity_analysis
from app.intelligence import opportunity_research
from app.intelligence import structured_analysis
from app.intelligence.prompt_contract import (
    AI_PROMPT_VERSION,
    CORE_ANSWER_FRAME,
    PREFERRED_COMMERCIAL_TERMS,
)


def test_all_ai_prompts_use_central_commercial_contract() -> None:
    prompts = [
        structured_analysis._system_prompt(),
        opportunity_analysis._system_prompt(),
        executive_summary._system_prompt(),
        internet_research._system_prompt(),
        opportunity_research._conversion_system_prompt(),
    ]

    for prompt in prompts:
        assert AI_PROMPT_VERSION in prompt
        assert "senior commercial analyst" in prompt
        assert "commercially sensitive" in prompt
        assert "Do not invent known facts" in prompt
        assert "known, inferred, estimated and unknown" in prompt
        assert "Return only" in prompt
        for question in CORE_ANSWER_FRAME:
            assert question in prompt
        for term in PREFERRED_COMMERCIAL_TERMS:
            assert term in prompt


def test_ai_json_schemas_constrain_executive_language_length() -> None:
    assert (
        structured_analysis.OPPORTUNITY_ANALYSIS_JSON_SCHEMA["properties"][
            "commercial_assessment"
        ]["maxLength"]
        == 420
    )
    assert (
        opportunity_analysis.OPPORTUNITY_AI_ANALYSIS_JSON_SCHEMA["properties"][
            "executive_summary"
        ]["maxLength"]
        == 420
    )
    assert (
        executive_summary.EXECUTIVE_SUMMARY_JSON_SCHEMA["properties"]["headline"][
            "maxLength"
        ]
        == 180
    )
    finding_properties = internet_research.INTERNET_INTELLIGENCE_JSON_SCHEMA[
        "properties"
    ]["findings"]["items"]["properties"]
    assert finding_properties["finding"]["maxLength"] == 260
    assert finding_properties["recommended_action"]["maxLength"] == 200
    field_properties = opportunity_research.RESEARCH_OPPORTUNITY_JSON_SCHEMA[
        "properties"
    ]["opportunity"]["properties"]["recommended_action"]["properties"]
    assert field_properties["value"]["maxLength"] == 260
    assert field_properties["rationale"]["maxLength"] == 260
