"""Convert bounded public-source results into cautious research context."""
from datetime import UTC, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from typing import Any

from app.config import Settings
from app.intelligence.rightclick_x import RightClickClient, RightClickError, OFFICIAL_ORIGIN, DISCOVERY_TOPICS
from app.schemas.universal_research import ResearchObservation, UniversalResearchRequest


def _clean(value: Any, maximum: int) -> str:
    return " ".join(str(value or "").split())[:maximum]


def discover_source_candidates(topics: list[str], settings: Settings) -> dict | None:
    """Consult directories using fixed generic topics, never the user brief.

    The output contains unreviewed descriptions only. It is not an evidence
    source, an approval to execute a candidate, or an exhaustive search.
    """
    if not settings.rightclick_x_url:
        return None
    selected = list(dict.fromkeys(item for item in topics if isinstance(item, str) and item in DISCOVERY_TOPICS))[:3]
    base: dict[str, Any] = {"status": "discovered", "message": "Public source candidates are unreviewed suggestions, not evidence or approved sources. Directory coverage is incomplete.",
        "capabilities": [], "query": None, "topics": selected, "candidates": [], "directories": [], "failed_topics": []}
    if not selected:
        base["message"] = "No suitable generic source-discovery topic was identified; web research continued."
        return base
    try:
        client = RightClickClient(settings)
        client.status()
    except RightClickError:
        base.update(status="unavailable", message="Public source discovery is unavailable; web research continued.", failed_topics=selected)
        return base
    def discover(topic: str):
        return topic, client.candidates(topic)
    with ThreadPoolExecutor(max_workers=min(3, len(selected))) as pool:
        futures = {pool.submit(discover, topic): topic for topic in selected}
        results = {}
        for future in as_completed(futures):
            topic = futures[future]
            try:
                _, results[topic] = future.result()
            except (RightClickError, ValueError, TypeError):
                base["failed_topics"].append(topic)
        seen = set()
        for topic in selected:
            data = results.get(topic, {})
            for item in data.get("candidates", [])[:5]:
                key = (_clean(item.get("title"), 160).casefold(), item.get("directory"))
                if not key[0] or key in seen:
                    continue
                seen.add(key)
                if len(base["candidates"]) < 10:
                    base["candidates"].append({"title": _clean(item.get("title"), 160),
                        "description": _clean(item.get("description"), 300),
                        "directory": _clean(item.get("directory"), 50), "kind": _clean(item.get("kind"), 20)})
            for directory in data.get("directories", [])[:2]:
                if directory not in base["directories"]:
                    base["directories"].append(directory)
    if len(base["failed_topics"]) == len(selected):
        base.update(status="unavailable", message="Public source discovery could not complete; web research continued.")
    elif base["failed_topics"]:
        base["message"] += " Some directory searches failed."
    return base


def collect_rightclick_context(request: UniversalResearchRequest, settings: Settings) -> tuple[dict, list[ResearchObservation]]:
    """Explore the approved capability and optionally run one explicit public lookup.

    Provider records are untrusted, cannot prove the owner or current need, and
    never become independent corroboration on their own.
    """
    result = {"status": "unavailable", "message": "Public source discovery is unavailable; web research continues.",
              "capabilities": [], "query": None}
    try:
        client = RightClickClient(settings)
        client.status()
        found = client.search("planning")
        result["capabilities"] = found["items"][:1]
        if not result["capabilities"]:
            result.update(status="no_approved_capability", message="The approved Planning Data capability is not available in the connected runtime; web research continues.")
            return result, []
        result.update(status="discovered", message="The approved Planning Data England capability was discovered. Enter a UPRN or postcode to run a bounded source lookup; a capability is not evidence of demand.")
        if not request.rightclick_identifier.strip():
            return result, []
        data = client.planning_query(request.rightclick_identifier, request.rightclick_dataset, limit=5)
        records = []
        observations = []
        retrieved = datetime.now(UTC).isoformat()
        for item in data["entities"]:
            if not isinstance(item, dict):
                continue
            entity = str(item.get("entity", ""))
            if not entity.isascii() or not entity.isdigit() or len(entity) > 18 or item.get("dataset") != request.rightclick_dataset:
                continue
            title = _clean(item.get("name"), 255) or f"Planning record {entity}"
            when = _clean(item.get("start-date") or item.get("entry-date"), 10)
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", when):
                when = ""
            source_url = f"{OFFICIAL_ORIGIN}/entity/{entity}"
            description = f"Returned by the {request.rightclick_dataset} dataset for the supplied identifier. Check the record's geography, date and relevance."
            records.append({"entity_id": entity, "title": title, "source_url": source_url,
                            "description": description, "date": when})
            observations.append(ResearchObservation(id=f"RC{len(observations)+1}", source_url=source_url,
                source_title=f"Planning Data England: {title}"[:255], published_date=when,
                fact=f"Planning Data England returned {title} (dataset {request.rightclick_dataset}) for the supplied identifier {request.rightclick_identifier.strip()}. This is unverified geographic context, not proof of property identity, ownership, maintenance need or buying intent.",
                origin="public_api", source_reference=f"Planning Data entity {entity}", retrieved_at=retrieved))
        receipt = data.get("receipt")
        receipt_hash = receipt.get("hash") if isinstance(receipt, dict) else None
        if not isinstance(receipt_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", receipt_hash):
            receipt_hash = None
        result.update(status="searched", message="MiSi searched the approved public source. Records are unverified context, not proof of a sales opportunity. Coverage is incomplete; no result does not mean no activity.",
            query={"identifier": request.rightclick_identifier.strip().upper(), "dataset": request.rightclick_dataset,
                   "records": records, "receipt": receipt_hash})
        return result, observations
    except RightClickError:
        result["message"] = "The approved public-source lookup could not complete. Check the connection and identifier; web research continues."
        return result, []
