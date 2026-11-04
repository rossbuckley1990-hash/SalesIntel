"""A deliberately narrow, local RightClick X client for public research.

Only an exact, operator-reviewed source operation may be executed. Capability
descriptions, receipts and API results remain untrusted data. A successful call
or a receipt does not establish accuracy, source coverage or buying intent.
"""
from __future__ import annotations

import ipaddress
import json
import re
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.config import Settings, get_settings

PROVIDER = "openapi:planning-data-gov-uk-api"
CAPABILITY = PROVIDER + ":search-entities-entity-extension-get"
OFFICIAL_ORIGIN = "https://www.planning.data.gov.uk"
OFFICIAL_CONTRACT = OFFICIAL_ORIGIN + "/openapi.json"
OFFICIAL_OPERATION = OFFICIAL_ORIGIN + "/entity.{extension}"
MAX_RESPONSE = 524_288
MAX_RESULTS = 10
# Only these coarse public topics may leave the application for directory
# discovery. Never forward a brief, company, person, postcode or model output
# unless it is an exact member of this fixed set.
DISCOVERY_TOPICS = frozenset({
    "fire safety", "building", "procurement", "planning", "security systems",
    "facilities maintenance", "healthcare facilities", "social housing",
    "education estates", "hotel facilities", "retail estates", "industrial facilities",
    "logistics facilities", "property development", "construction", "business growth",
    "energy efficiency", "environmental health", "business registrations", "licensing",
    "transport", "employment", "financial distress", "public safety",
})
DEDICATED_RUNTIME_NAME = "misi-public-discovery"

# Static keyword rules are a privacy boundary, not an attempt to classify the
# brief completely. Place service topics first and select at most two before
# adding a sector or business signal when one is present.
_SERVICE_RULES = (
    ("fire safety", r"\b(?:fire|sprinklers?|extinguishers?)\b"),
    ("security systems", r"\b(?:security|cctv|intruder|surveillance|access control)\b"),
    ("facilities maintenance", r"\b(?:maintenance|facilities|facility|servicing|ppm)\b"),
    ("energy efficiency", r"\b(?:energy|decarbonisation|decarbonization|efficiency)\b"),
    ("environmental health", r"\b(?:environmental health|food hygiene)\b"),
    ("public safety", r"\b(?:public safety|emergency services)\b"),
)
_CONTEXT_RULES = (
    ("healthcare facilities", r"\b(?:healthcare|hospitals?|nhs|clinics?|care homes?|medical)\b"),
    ("social housing", r"\b(?:social housing|housing associations?|council housing)\b"),
    ("education estates", r"\b(?:schools?|education|universit(?:y|ies)|colleges?|campus)\b"),
    ("hotel facilities", r"\b(?:hotels?|hospitality)\b"),
    ("retail estates", r"\b(?:retail|shops?|shopping cent(?:re|er)s?|supermarkets?)\b"),
    ("industrial facilities", r"\b(?:industrial|factor(?:y|ies)|manufacturing)\b"),
    ("logistics facilities", r"\b(?:logistics|warehouses?|distribution cent(?:re|er)s?)\b"),
    ("property development", r"\b(?:property development|developers?)\b"),
    ("construction", r"\b(?:construction|building works?)\b"),
    ("business growth", r"\b(?:expansion|business growth|new sites?)\b"),
    ("financial distress", r"\b(?:insolvenc(?:y|ies)|administration|financial distress)\b"),
    ("business registrations", r"\b(?:companies house|company registrations?|business registrations?)\b"),
    ("licensing", r"\b(?:licensing|licences?|licenses?)\b"),
    ("transport", r"\b(?:transport|railways?|traffic|airports?)\b"),
    ("employment", r"\b(?:employment|recruitment|vacancies|jobs?)\b"),
    ("procurement", r"\b(?:procurement|tenders?|contracts?)\b"),
    ("planning", r"\b(?:planning|planning applications?)\b"),
    ("building", r"\b(?:buildings?|premises|estates?|properties|property)\b"),
)


def topics_from_brief(brief: str) -> list[str]:
    """Return only broad, static directory topics; never the user's text."""
    if not isinstance(brief, str):
        return []
    text = brief.casefold()[:20_000]
    service = [topic for topic, pattern in _SERVICE_RULES if re.search(pattern, text)]
    context = [topic for topic, pattern in _CONTEXT_RULES if re.search(pattern, text)]
    return (service[:2] + context[:3])[:3]


class RightClickError(RuntimeError):
    """The runtime is unavailable, untrusted, or rejected an operation."""


def planning_identifier(q: str) -> str:
    value = q.strip().upper()
    if not (re.fullmatch(r"[0-9]{1,20}", value) or re.fullmatch(r"[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2}", value)):
        raise ValueError("Use a specific UPRN or UK postcode for planning research.")
    return value


def _topically_relevant(topic: str, title: str, description: str) -> bool:
    """Conservative local screening; directory text remains unverified.

    This is a lexical relevance gate, not classification of an actual public
    data source, its ownership, licensing, coverage, or fitness for use.
    """
    words = set(re.findall(r"[a-z0-9]+", (title + " " + description).casefold()))
    if topic == "fire safety":
        fire_terms = {"fire", "firefighting", "firefighter", "firefighters"}
        context_terms = {"safety", "protection", "alarm", "alarms", "suppression", "extinguisher", "extinguishers", "inspection", "inspections", "rescue", "prevention", "detection"}
        return bool(words & fire_terms and words & context_terms)
    if topic == "building":
        return bool(words & {"building", "buildings", "construction", "property", "properties", "premises", "estate", "estates", "facilities", "housing"})
    if topic == "procurement":
        return bool(words & {"procurement", "tender", "tenders", "tendering", "purchasing"} or
                    (words & {"contract", "contracts"} and words & {"public", "government", "procurement", "tender"}))
    if topic == "planning":
        return bool(words & {"planning", "zoning"} and
                    words & {"land", "property", "building", "buildings", "council", "development", "housing", "spatial", "geographic"})
    # Each group is an independent lexical constraint. Directory entries are
    # still unreviewed suggestions, not approved data sources.
    terms = {
        "security systems": ({"security", "cctv", "surveillance", "intruder"}, {"security", "cctv", "alarm", "alarms", "systems", "surveillance"}),
        "facilities maintenance": ({"facility", "facilities", "building", "buildings", "estate", "estates"}, {"maintenance", "servicing", "management"}),
        "healthcare facilities": ({"healthcare", "hospital", "hospitals", "nhs", "clinic", "clinics"},),
        "social housing": ({"housing", "homes"}, {"social", "council", "affordable"}),
        "education estates": ({"education", "school", "schools", "university", "universities", "college", "colleges"},),
        "hotel facilities": ({"hotel", "hotels", "hospitality"},),
        "retail estates": ({"retail", "shopping", "supermarket", "supermarkets"},),
        "industrial facilities": ({"industrial", "manufacturing", "factory", "factories"},),
        "logistics facilities": ({"logistics", "warehouse", "warehouses", "distribution"},),
        "property development": ({"property", "properties", "building", "buildings"}, {"development", "developers", "construction"}),
        "construction": ({"construction", "building", "buildings"},),
        "business growth": ({"business", "businesses", "company", "companies"}, {"growth", "expansion", "development"}),
        "energy efficiency": ({"energy"}, {"efficiency", "performance", "consumption"}),
        "environmental health": ({"environmental", "environment"}, {"health", "hygiene", "pollution"}),
        "business registrations": ({"business", "company", "companies"}, {"registration", "registrations", "register", "registry"}),
        "licensing": ({"licensing", "licence", "licences", "license", "licenses"},),
        "transport": ({"transport", "rail", "railway", "traffic", "airport", "airports"},),
        "employment": ({"employment", "jobs", "recruitment", "vacancies", "workforce"},),
        "financial distress": ({"insolvency", "insolvent", "bankruptcy", "liquidation"},),
        "public safety": ({"public"}, {"safety", "emergency"}),
    }.get(topic)
    return bool(terms and all(words & group for group in terms))


def _local_mcp_endpoint(value: str | None) -> str:
    if not value:
        raise RightClickError("Source discovery is not configured.")
    try:
        parts = urlsplit(value.strip())
        if (parts.scheme != "http" or parts.username or parts.password or parts.query or parts.fragment
                or parts.path.rstrip("/") != "/mcp" or not parts.hostname):
            raise ValueError
        host = parts.hostname.lower()
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError
        if not parts.port or parts.port < 1:
            raise ValueError
        return value.strip().rstrip("/")
    except ValueError as exc:
        raise RightClickError("Source discovery must use a configured local HTTP MCP endpoint.") from exc


class RightClickClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.endpoint = _local_mcp_endpoint(self.settings.rightclick_x_url)

    def _call(self, name: str, args: dict[str, Any]) -> Any:
        # Never allow an API or model caller to choose an arbitrary runtime tool.
        if name not in {"context_runtime", "context_graph", "context_explain", "context_run", "context_research"}:
            raise RightClickError("That discovery operation is not permitted.")
        if name == "context_research" and (set(args) != {"topic", "limit", "learn"} or
                args.get("topic") not in DISCOVERY_TOPICS or args.get("limit") != 5 or args.get("learn") != 0):
            raise RightClickError("Only bounded directory discovery is permitted.")
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                   "MCP-Protocol-Version": "2025-06-18"}
        if self.settings.rightclick_x_token:
            headers["Authorization"] = "Bearer " + self.settings.rightclick_x_token
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}
        try:
            with httpx.Client(timeout=httpx.Timeout(12, connect=2), follow_redirects=False, trust_env=False) as client:
                with client.stream("POST", self.endpoint, headers=headers, json=request) as response:
                    response.raise_for_status()
                    if "application/json" not in response.headers.get("content-type", "").lower():
                        raise RightClickError("Source discovery returned an unsupported response type.")
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_RESPONSE:
                            raise RightClickError("Source discovery returned a response exceeding the safety limit.")
                        chunks.append(chunk)
            envelope = json.loads(b"".join(chunks))
            if not isinstance(envelope, dict) or envelope.get("error") or envelope.get("id") != 1:
                raise RightClickError("Source discovery rejected the request.")
            result = envelope.get("result")
            if not isinstance(result, dict) or result.get("isError"):
                raise RightClickError("Source discovery could not complete the request.")
            if "structuredContent" in result:
                return result["structuredContent"]
            text = "".join(c.get("text", "") for c in result.get("content", []) if isinstance(c, dict) and c.get("type") == "text")
            return json.loads(text)
        except (httpx.HTTPError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RightClickError("Source discovery is unavailable or returned an invalid response.") from exc

    def status(self) -> dict[str, Any]:
        info = self._call("context_runtime", {})
        if not isinstance(info, dict) or info.get("product") != "RightClick X":
            raise RightClickError("The endpoint did not identify itself as the supported runtime.")
        graph = info.get("graph") if isinstance(info.get("graph"), dict) else {}
        return {"available": True, "configured": True, "version": str(info.get("version") or "")[:80],
                "capabilities": graph.get("capabilities") if isinstance(graph.get("capabilities"), int) else None,
                "message": "Connected. Capability discovery is not proof of source coverage or accuracy."}

    def search(self, query: str = "planning") -> dict[str, Any]:
        if len(query) > 200:
            raise RightClickError("The discovery query is too long.")
        # Do not expose the caller's question or sensitive account names to the
        # runtime graph. Search the reviewed public operation only.
        raw = self._call("context_graph", {"op": "search", "query": "planning", "limit": 30})
        rows = raw.get("result", []) if isinstance(raw, dict) else raw
        if not isinstance(rows, list):
            raise RightClickError("Source discovery returned an invalid capability list.")
        items = [{"id": CAPABILITY, "title": "Search Planning Data England entities",
                  "provider": PROVIDER, "source": OFFICIAL_CONTRACT}
                 for item in rows if isinstance(item, dict) and item.get("id") == CAPABILITY and item.get("provider") == PROVIDER]
        return {"items": items[:1], "message": "Only the reviewed public-source operation is shown. Discovery is not permission to run arbitrary capabilities or evidence of coverage."}

    def candidates(self, topic: str) -> dict[str, Any]:
        if topic not in DISCOVERY_TOPICS:
            raise RightClickError("Select one of the supported public discovery topics.")
        runtime = self._call("context_runtime", {})
        # Name is a misconfiguration check, not an authentication or isolation
        # guarantee. The dedicated runtime must be started without environment
        # catalogs and with its operator-controlled egress policy.
        if not isinstance(runtime, dict) or runtime.get("product") != "RightClick X" or runtime.get("name") != DEDICATED_RUNTIME_NAME:
            raise RightClickError("Directory discovery requires MiSi's dedicated isolated runtime.")
        result = self._call("context_research", {"topic": topic, "limit": 5, "learn": 0})
        if not isinstance(result, dict) or not isinstance(result.get("directories"), list):
            raise RightClickError("Source discovery returned an invalid response.")
        directories, candidates = [], []
        for directory in result["directories"][:2]:
            if not isinstance(directory, dict) or directory.get("id") not in {"apis.guru", "mcp-registry"}:
                continue
            directory_id = directory["id"]
            directories.append({"id": directory_id, "reachable": directory.get("reachable") is True})
            entries = directory.get("candidates", [])
            if not isinstance(entries, list):
                continue
            for item in entries[:5]:
                if not isinstance(item, dict) or item.get("directory") != directory_id:
                    continue
                kind = item.get("kind")
                if kind not in {"openapi", "mcp", "graphql"}:
                    continue
                def clean(value: Any, length: int) -> str:
                    if not isinstance(value, str):
                        return ""
                    return " ".join("".join(c if c.isprintable() else " " for c in value).split())[:length]
                title = clean(item.get("title"), 160)
                description = clean(item.get("description"), 300)
                if title and _topically_relevant(topic, title, description):
                    candidates.append({"title": title, "description": description,
                                       "directory": directory_id, "kind": kind})
        return {"topic": topic, "candidates": candidates[:10], "directories": directories,
                "message": "Unreviewed directory candidates only, filtered by conservative keywords. MiSi has not accessed, learned, approved or verified these sources; relevance, public access, licences and UK coverage are unknown. Empty results are not a comprehensive search."}

    def _approved_contract(self, capability: str) -> dict[str, Any]:
        if capability != CAPABILITY:
            raise RightClickError("Only the approved Planning Data read operation can be used.")
        detail = self._call("context_explain", {"id": CAPABILITY, "detail": "run"})
        if not isinstance(detail, dict):
            raise RightClickError("Source discovery returned an invalid capability contract.")
        cap = detail.get("capability")
        execution = detail.get("execution")
        if not isinstance(cap, dict) or not isinstance(execution, dict):
            raise RightClickError("The capability contract is incomplete.")
        invoke = cap.get("invoke") if isinstance(cap.get("invoke"), dict) else {}
        origins = execution.get("origins")
        risks = execution.get("consequentialRisks")
        if (cap.get("id") != CAPABILITY or cap.get("provider") != PROVIDER or cap.get("risk") != "read"
                or invoke.get("kind") != "http" or invoke.get("method") != "GET" or invoke.get("url") != OFFICIAL_OPERATION
                or execution.get("allowed") is not True or execution.get("declaredRisk") != "read"
                or not isinstance(origins, list) or set(origins) != {OFFICIAL_ORIGIN}
                or not isinstance(risks, list) or set(risks) != {"read"}):
            raise RightClickError("The capability changed or is outside the approved public read policy.")
        return detail

    def explain(self, capability: str) -> dict[str, Any]:
        detail = self._approved_contract(capability)
        cap = detail["capability"]
        inputs = [{"name": str(item.get("name", ""))[:100], "type": str(item.get("type", ""))[:100],
                   "required": bool(item.get("required"))} for item in cap.get("inputs", [])[:40] if isinstance(item, dict)]
        return {"id": CAPABILITY, "title": "Search Planning Data England entities", "provider": PROVIDER,
                "risk": "read", "method": "GET", "origin": OFFICIAL_ORIGIN, "inputs": inputs,
                "limitations": ["England only; dataset coverage varies and missing results do not mean no activity.",
                                "An API contract and a returned record do not establish a service need or buying intent.",
                                "The runtime and source descriptions are untrusted; verify source content and identity."],
                "message": "Approved for bounded read-only use; the actual contract is checked before execution."}

    def planning_query(self, q: str, dataset: str = "planning-application", limit: int = 10) -> dict[str, Any]:
        # Only a UPRN or UK postcode may be sent to this exact source; user text,
        # arbitrary URLs, fields, geometry and dates cannot cross this boundary.
        try:
            value = planning_identifier(q)
        except (TypeError, ValueError) as exc:
            raise RightClickError("Use a specific UPRN or UK postcode for planning research.") from exc
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_RESULTS:
            raise RightClickError("Planning searches are limited to ten records.")
        if dataset not in {"planning-application", "brownfield-land", "conservation-area"}:
            raise RightClickError("The requested planning dataset is not approved.")
        self._approved_contract(CAPABILITY)
        result = self._call("context_run", {"id": CAPABILITY, "args": {"extension": "json", "q": value,
            "dataset": dataset, "limit": str(limit), "offset": "0", "exclude_field": "geometry"}, "view": {"full": True}})
        if (not isinstance(result, dict) or result.get("status") != "completed" or result.get("capability") != CAPABILITY
                or result.get("provider") != PROVIDER or result.get("responseStatus") != 200):
            raise RightClickError("The approved source did not return a complete result.")
        output = result.get("output")
        if not isinstance(output, dict) or not isinstance(output.get("entities"), list) or len(output["entities"]) > limit:
            raise RightClickError("The planning source returned an unexpected result.")
        return {"source": OFFICIAL_ORIGIN, "source_contract": OFFICIAL_CONTRACT,
                "dataset": dataset, "query": value, "entities": output["entities"],
                "receipt": result.get("receipt"), "verification": "unverified",
                "limitations": ["Planning Data covers England; local authority sharing is incomplete.",
                                "Empty results do not establish that no planning activity exists.",
                                "Returned records are unverified and do not establish a service need or buying intent."]}
