"""Build a bounded, source-attributed map from an existing research dossier.

This is a projection of the dossier's own links, not entity resolution or a
knowledge graph of verified real-world relationships. No additional data is
fetched, and no identity, site ownership, supplier or buying intent is inferred.
"""
from hashlib import sha256
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit, urlunsplit


MAX_REFERENCES = 50


def _text(value: Any, limit: int = 1200) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _identifier(value: Any) -> str:
    """Do not truncate identifiers: two long IDs can share the same prefix."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return value if 0 < len(value) <= 120 else ""


def _public_link(value: Any) -> str | None:
    """Validate a display link without fetching it or collapsing distinct URLs."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > 2048:
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return None
        hostname = parts.hostname.lower().rstrip(".")
        if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
            return None
        try:
            if not ip_address(hostname).is_global:
                return None
        except ValueError:
            pass  # A public hostname is not resolved or fetched here.
        # Accessing the port also rejects malformed ports. Fragments do not
        # identify a different document; query strings are retained in full.
        _ = parts.port
        return urlunsplit((parts.scheme.lower(), parts.netloc, parts.path or "/", parts.query, ""))
    except ValueError:
        return None


def build_evidence_graph(lead_id: int, opportunity: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Expose only explicit dossier references and clearly label their limits."""
    opportunity = opportunity if isinstance(opportunity, dict) else {}
    observations = observations if isinstance(observations, list) else []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    seen_node_ids: set[str] = set()

    def add_node(node: dict[str, Any]) -> None:
        if node["id"] not in seen_node_ids:
            seen_node_ids.add(node["id"])
            nodes.append(node)

    def edge(source: str, target: str, relation: str, label: str, observation_id: str | None = None) -> None:
        edges.append({"source": source, "target": target, "relation": relation, "label": label,
                      "observation_id": observation_id, "verification": "unverified"})

    headline = _text(opportunity.get("headline"), 300) or "Research hypothesis"
    add_node({"id": "hypothesis", "type": "hypothesis", "label": headline,
              "description": _text(opportunity.get("thesis")), "verification": "unverified",
              "suggested_approach": _text(opportunity.get("engagement")),
              "next_verification": _text(opportunity.get("verification_action"))})
    for key, node_type, relation, label in (
        ("organisation", "organisation", "proposed_organisation", "Proposed organisation for this hypothesis"),
        ("location", "location", "location_context", "Location context for this hypothesis"),
        ("contact_role", "stakeholder_role", "suggested_role", "Suggested role to verify"),
    ):
        value = _text(opportunity.get(key), 300)
        if value:
            add_node({"id": node_type, "type": node_type, "label": value, "verification": "unverified"})
            edge("hypothesis", node_type, relation, label)

    # Duplicate ids are ambiguous: do not guess which record was referenced.
    by_id: dict[str, list[dict[str, Any]]] = {}
    for observation in observations[:500]:
        if not isinstance(observation, dict):
            continue
        oid = _identifier(observation.get("id"))
        if oid:
            by_id.setdefault(oid, []).append(observation)

    source_nodes: dict[str, str] = {}
    linked_roles: set[tuple[str, str]] = set()
    selected: set[str] = set()
    for key, relation, label in (
        ("supporting_observation_ids", "supports_hypothesis", "Cited as supporting context"),
        ("counter_observation_ids", "counter_context", "Cited as alternative or counter-context"),
        ("contact_observation_ids", "contact_context", "Cited as context for the suggested contact"),
    ):
        references = opportunity.get(key)
        if not isinstance(references, list):
            continue
        for raw_id in references[:MAX_REFERENCES]:
            oid = _identifier(raw_id)
            if not oid:
                missing.append({"id": _text(raw_id, 120), "relation": relation, "reason": "invalid"})
                continue
            if (relation, oid) in linked_roles:
                continue
            linked_roles.add((relation, oid))
            matches = by_id.get(oid, [])
            if len(matches) != 1:
                missing.append({"id": oid, "relation": relation, "reason": "ambiguous" if matches else "missing"})
                continue
            if oid not in selected and len(selected) >= MAX_REFERENCES:
                missing.append({"id": oid, "relation": relation, "reason": "limit"})
                continue
            selected.add(oid)
            obs = matches[0]
            obs_node = "observation:" + oid
            origin = _text(obs.get("origin"), 50) or "web_search"
            if origin == "rightclick_x":
                origin = "public_api"
            add_node({"id": obs_node, "type": "observation", "label": _text(obs.get("fact")),
                      "observation_id": oid, "source_title": _text(obs.get("source_title"), 255),
                      "published_date": _text(obs.get("published_date"), 50),
                      "retrieved_at": _text(obs.get("retrieved_at"), 50),
                      "origin": origin, "verification": "unverified"})
            edge(obs_node, "hypothesis", relation, label, oid)
            url = _public_link(obs.get("source_url"))
            if url:
                source_node = source_nodes.get(url)
                if source_node is None:
                    source_node = "source:" + sha256(url.encode("utf-8")).hexdigest()
                    source_nodes[url] = source_node
                    add_node({"id": source_node, "type": "source", "label": _text(obs.get("source_title"), 255) or "Public source",
                              "url": url, "verification": "unverified"})
                if not any(e["source"] == source_node and e["target"] == obs_node for e in edges):
                    edge(source_node, obs_node, "attributed_to", "Observation attributed to this source", oid)

    unknowns = opportunity.get("unknowns")
    return {"lead_id": lead_id, "nodes": nodes, "edges": edges, "missing_references": missing,
            "unknowns": [_text(v) for v in unknowns[:30] if _text(v)] if isinstance(unknowns, list) else [],
            "limitations": [
                "This map displays explicit references in one saved research result, not a verified graph of real-world relationships.",
                "Source claims, dates, identity, site relevance and source independence require review; links do not establish buying intent or supplier performance.",
                "Organisation, location and stakeholder role are proposed context for the hypothesis, not proof of ownership, decision-making authority or a verified contact.",
                "Only cited observations are shown. Missing, ambiguous or out-of-range references are not treated as evidence.",
            ]}
