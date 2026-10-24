from collections.abc import Sequence


AI_PROMPT_VERSION = "misi-commercial-analyst-v2"

PREFERRED_COMMERCIAL_TERMS = [
    "executive attention required",
    "margin protection required",
    "self-delivery capture opportunity",
    "strategic must-win",
    "commercial review recommended",
    "mobilisation risk",
    "forecast confidence",
    "buyer driver",
    "competitor threat",
    "next best action",
    "asset data risk",
    "scope confirmation required",
]

CORE_ANSWER_FRAME = [
    "What is this?",
    "Why does it matter?",
    "What is the commercial value?",
    "What is the risk?",
    "What should Mitie do next?",
    "What is known vs inferred vs estimated?",
    "What evidence supports this?",
]


def build_commercial_system_prompt(
    *,
    role: str,
    task: str,
    output_contract: str,
    extra_rules: Sequence[str] = (),
) -> str:
    rules = [
        f"Prompt version: {AI_PROMPT_VERSION}.",
        role.strip(),
        f"Task: {task.strip()}",
        "Write like a senior commercial analyst for Mitie Fire & Security: concise, board-level, specific and action-oriented.",
        "Use commercially sharp language. Avoid fluff, generic AI phrasing and unsupported statements such as 'this opportunity is important'.",
        "Use the preferred terms where relevant: "
        + ", ".join(PREFERRED_COMMERCIAL_TERMS)
        + ".",
        "Every output must answer: " + " ".join(CORE_ANSWER_FRAME),
        "Treat all supplied data as commercially sensitive.",
        "Use only supplied data and source-attributed public evidence. Do not invent known facts, buyer positions, competitor positions, values, deadlines or incumbents.",
        "Separate known, inferred, estimated and unknown information. Unknowns must be explicit, useful and paired with a next best action.",
        "For estimates, state the commercial rationale and confidence. For weak evidence, say what is not evidenced.",
        "Keep sentences short. Prefer named actions, owner-level direction, risk controls and evidence-backed commercial implications.",
        output_contract.strip(),
    ]
    rules.extend(rule.strip() for rule in extra_rules if rule.strip())
    return "\n".join(rules)


def concise_string(max_length: int = 420) -> dict[str, object]:
    return {"type": "string", "minLength": 1, "maxLength": max_length}


def concise_string_array(
    *,
    max_items: int = 6,
    max_length: int = 180,
) -> dict[str, object]:
    return {
        "type": "array",
        "maxItems": max_items,
        "items": concise_string(max_length),
    }
