"""Entity resolution for the Cross-entity 360 intelligence layer.

Buyers, opportunities, market signals and competitors are stored without
foreign keys linking them. The only shared key is free-text ``buyer_name``
(opportunities / market signals / buyer profiles) and ``sector`` (competitors).

This module turns that fragmented free-text into a connected, confidence-scored
graph through deterministic name normalisation and token-overlap matching.
It is deliberately rule-based and side-effect free so it is fully unit-testable
and never requires an OpenAI key.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.models import BuyerProfile, CompetitorProfile, MarketSignal, Opportunity

# Generic / legal suffixes that add no discriminative value when matching
# organisation names. Order matters slightly: longer tokens are stripped first.
_NAME_SUFFIX_TOKENS = {
    "ltd",
    "limited",
    "llp",
    "plc",
    "inc",
    "corp",
    "corporation",
    "company",
    "co",
    "group",
    "partnership",
    "partners",
    "trust",
    "authority",
    "council",
    "alliance",
    "services",
    "holdings",
    "uk",
    "the",
    "and",
    "of",
}

# "nhs" is treated as meaningful context but stripped as a noise token when it
# is the only token, so "NHS" / "The NHS" do not match every NHS buyer.
_NOISE_ONLY_TOKENS = {"nhs", "fm", "the"}

DEFAULT_FUZZY_THRESHOLD = 0.7


class _BuyerNamed(Protocol):
    buyer_name: str


@dataclass(frozen=True)
class ResolvedEntity:
    """A resolved link between the focal entity and a related entity.

    ``confidence`` is 1.0 for an exact normalised match and the token-overlap
    similarity for a fuzzy match. ``match_method`` records how the link was made
    so the synthesis can attribute evidence honestly.
    """

    entity: object
    confidence: float
    match_method: str


def normalise_entity_name(name: str) -> str:
    """Normalise an organisation name for matching.

    Lowercases, strips punctuation and generic legal/noise tokens, and collapses
    whitespace. The goal is that ``"NHS Leeds Trust"`` and ``"Leeds NHS"``
    normalise close enough to token-overlap as a strong (but not exact) match.
    """
    if not name:
        return ""
    text = name.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [token for token in text.split() if token]
    kept = [token for token in tokens if token not in _NAME_SUFFIX_TOKENS]
    if not kept:
        # All tokens were stripped (e.g. "The NHS Ltd") — fall back to the
        # meaningful tokens minus pure-noise ones so we never match on empty.
        kept = [token for token in tokens if token not in _NOISE_ONLY_TOKENS]
    return " ".join(kept)


def name_tokens(name: str) -> list[str]:
    """Return the discriminative tokens of a name (after normalisation)."""
    return normalise_entity_name(name).split()


def name_similarity(a: str, b: str) -> float:
    """Jaccard overlap of discriminative name tokens, on a 0-1 scale."""
    tokens_a = set(name_tokens(a))
    tokens_b = set(name_tokens(b))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return round(len(intersection) / len(union), 4)


def is_exact_name_match(a: str, b: str) -> bool:
    return normalise_entity_name(a) == normalise_entity_name(b) and bool(
        normalise_entity_name(a)
    )


def resolve_by_buyer_name(
    buyer_name: str,
    candidates: list[_BuyerNamed],
    *,
    threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> list[ResolvedEntity]:
    """Resolve opportunities or market signals to a buyer by ``buyer_name``.

    Exact normalised matches are returned first at confidence 1.0, then fuzzy
    matches above ``threshold`` in descending similarity order. Candidates that
    match only weakly are excluded so the 360 view never invents relationships.
    """
    resolved: list[ResolvedEntity] = []
    for candidate in candidates:
        candidate_name = getattr(candidate, "buyer_name", "") or ""
        if is_exact_name_match(buyer_name, candidate_name):
            resolved.append(ResolvedEntity(entity=candidate, confidence=1.0, match_method="exact"))
            continue
        similarity = name_similarity(buyer_name, candidate_name)
        if similarity >= threshold:
            resolved.append(
                ResolvedEntity(
                    entity=candidate,
                    confidence=similarity,
                    match_method="fuzzy",
                )
            )
    resolved.sort(key=lambda item: (item.match_method != "exact", -item.confidence))
    return resolved


def resolve_opportunities_for_buyer(
    buyer_name: str,
    opportunities: list[Opportunity],
    *,
    threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> list[ResolvedEntity]:
    return resolve_by_buyer_name(buyer_name, opportunities, threshold=threshold)


def resolve_signals_for_buyer(
    buyer_name: str,
    signals: list[MarketSignal],
    *,
    threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> list[ResolvedEntity]:
    return resolve_by_buyer_name(buyer_name, signals, threshold=threshold)


def sector_match_value(candidate_sector: str, target_sectors: list[str]) -> str | None:
    """Return the matched target sector if a candidate sector is in the list.

    Comparison is case-insensitive and ignores surrounding whitespace. Returns
    the canonical target sector string (preserving its casing) on match.
    """
    normalised_targets = {
        sector.strip().lower(): sector for sector in target_sectors if sector and sector.strip()
    }
    if not candidate_sector:
        return None
    key = candidate_sector.strip().lower()
    return normalised_targets.get(key)


def resolve_competitors_for_sector(
    sector: str,
    competitors: list[CompetitorProfile],
) -> list[ResolvedEntity]:
    """Resolve competitors that operate in the given sector.

    Linkage is by ``competitor.sectors`` membership since the schema has no
    buyer→competitor foreign key. ``match_method`` is "sector" and confidence
    reflects that this is an inferred, sector-level link rather than a named one.
    """
    resolved: list[ResolvedEntity] = []
    if not sector:
        return resolved
    for competitor in competitors:
        matched = sector_match_value(sector, competitor.sectors)
        if matched is not None:
            resolved.append(
                ResolvedEntity(
                    entity=competitor,
                    confidence=0.6,
                    match_method="sector",
                )
            )
    return resolved


def resolve_buyers_for_competitor(
    competitor: CompetitorProfile,
    buyers: list[BuyerProfile],
) -> list[ResolvedEntity]:
    """Resolve buyers whose sector intersects a competitor's sectors."""
    resolved: list[ResolvedEntity] = []
    for buyer in buyers:
        matched = sector_match_value(buyer.sector, competitor.sectors)
        if matched is not None:
            resolved.append(
                ResolvedEntity(
                    entity=buyer,
                    confidence=0.6,
                    match_method="sector",
                )
            )
    return resolved
