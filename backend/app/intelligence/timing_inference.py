"""Infer when an organisation is likely to buy, from clues that are not the purchase itself.

The method mirrors inferring a traffic light's timing from the traffic around it: no
single observation shows the hidden state, but each indirect clue implies a window, and
windows from independent clues that overlap in time narrow down the phase.

Every clue becomes an explicit window with its rule and basis. Rules are industry rules
of thumb (system service lives, typical contract terms, budget cycles), not standards,
and the result is a phase with reasons, never a probability.

The phase is about recurring maintenance. Replacing systems is a separate, later sale: a
replacement date still years away is shown as context and never holds contact back, and a
refurbishment says nothing about the age of the systems. A vacancy is not an appointment,
and an acquisition is not a site opening: each is kept as what it is, a reason to ask.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Any

# Typical service life before replacement is usually considered, in years (rule of thumb).
LIFESPANS: dict[str, tuple[int, int, str]] = {
    "fire_alarm": (10, 15, "fire alarm panels are commonly replaced after 10 to 15 years as parts and support end"),
    "cctv": (6, 10, "CCTV estates are commonly refreshed after 6 to 10 years, often moving from analogue to IP"),
    "access_control": (8, 12, "access control is commonly upgraded after 8 to 12 years as readers and software age"),
    "intruder": (10, 15, "intruder alarm panels are commonly replaced after 10 to 15 years"),
    "emergency_lighting": (8, 12, "emergency lighting fittings are commonly replaced after 8 to 12 years"),
    "sprinkler": (20, 30, "sprinkler control equipment is commonly overhauled after 20 to 30 years"),
    "general": (8, 15, "fire and security systems are commonly reviewed for replacement after 8 to 15 years"),
}
CONTRACT_TERM_YEARS = (3, 5)  # private maintenance contracts commonly run three to five years
LOCK_IN_MONTHS = 12           # a supplier appointed in the last year is rarely replaced

KINDS: dict[str, str] = {
    "system_installed": "System installed",
    "building_completed": "Building opened",
    "refurbishment": "Refurbishment or fit-out",
    "supplier_appointed": "Supplier appointed",
    "contract_end_stated": "Contract end stated",
    "financial_year_end": "Financial year end",
    "regulatory_deadline": "Regulatory deadline",
    "leadership_change": "New decision maker",
    "site_opening": "New site opening",
    "incident": "Incident",
    "incumbent_distress": "Incumbent in difficulty",
    "role_vacancy": "Role advertised",
    "acquisition": "Acquisition",
    "contractor_appointed": "Building contractor appointed",
}
# Kinds that are reasons to ask but set no window: what they imply for maintenance is not published.
NOTES: dict[str, str] = {
    "role_vacancy": "a vacancy is not an appointment, so no new-leader window starts. Ask who covers the role now and whether it has been filled",
    "acquisition": "a change of owner is a reason to ask whether inherited maintenance contracts will be kept or consolidated. It is not a site opening, so no pre-opening window applies",
    "refurbishment": "a refurbishment does not show how old the systems are or when their maintenance is reviewed. Ask who maintains them now and when that arrangement is next reviewed",
    "contractor_appointed": "a contractor appointed to build or fit out a site is not its fire and security maintenance supplier, so it does not hold contact back. Ask who installs those systems under the build and who will maintain them after handover",
}
REPLACEMENT = {"system_installed", "building_completed"}  # what replacement windows rest on; a separate sale from maintenance
_VACANCY = re.compile(r"\b(vacanc|advertis|recruit|hiring|job (?:listing|advert|posting)|listing on|is seeking|seeks? an?\b|looking for an?\b)", re.I)
_APPOINTED = re.compile(r"\b(appointed|appoints|appointment of|joined|joins|promoted|has started|starts as|named as|takes up|took up)\b", re.I)
_DOUBT = re.compile(r"[^.]*\b(whether|not known|unknown|unclear|not confirmed|no confirmed|not yet)\b[^.]*\.?", re.I)
_ACQUIRED = re.compile(r"\b(acquir|acquisition|bought|buys\b|purchas|takeover|taken over|takes over)", re.I)
# A change of owner filed as a supplier; narrower than _ACQUIRED, since suppliers are often appointed through a purchasing exercise.
_TAKEOVER = re.compile(r"\b(acquir|acquisition|takeover|taken over|takes over|merger|merged with)", re.I)
# A contractor building or fitting out a site, as opposed to a supplier who maintains its systems.
_BUILDS = re.compile(r"\b(construction|constructing|builders?\b|build\b|building contractor|main contractor|principal contractor|design[- ]and[- ]build|"
                     r"fit[- ]?out contractor|groundworks?|developers?\b|developments\b|M&E contractor|mechanical and electrical)", re.I)
_MAINTAINS = re.compile(r"\b(maintain|maintains|maintained|maintenance|servicing|service (?:contract|provider|agreement)|facilities management|"
                        r"facilities services|FM (?:provider|contract|supplier)|hard FM|soft FM|monitoring|alarm receiving|guarding)\b", re.I)
# Events that can force a change even inside a recently signed contract.
OVERRIDES_LOCK = {"incident", "incumbent_distress", "regulatory_deadline", "contract_end_stated"}


@dataclass(frozen=True)
class Parsed:
    day: date
    precision: str  # day, month or year


def parse_when(value: Any) -> Parsed | None:
    """Accept YYYY, YYYY-MM or YYYY-MM-DD; a year alone is placed mid-year."""
    if isinstance(value, date):
        return Parsed(value, "day")
    text = str(value or "").strip()
    match = re.match(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", text)
    if not match or not 1950 <= int(match[1]) <= 2100:
        return None
    year, month, day = int(match[1]), match[2], match[3]
    try:
        if month and day:
            return Parsed(date(year, int(month), int(day)), "day")
        if month:
            return Parsed(date(year, int(month), 15), "month")
    except ValueError:
        return None
    return Parsed(date(year, 7, 1), "year")


def add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(day.day, 28))


def add_years(day: date, years: float) -> date:
    return add_months(day, round(years * 12))


def _strength(basis: str, precision: str) -> str:
    if basis != "stated":
        return "weak"
    return "strong" if precision in ("day", "month") else "moderate"


def reclassify(clue: dict) -> dict:
    """What a clue is, from what it says. Research sometimes files a vacancy as a new leader, a takeover as a site
    opening, or a takeover or a building contractor as a new fire and security supplier; the words it stored say otherwise. Sentences
    that only raise a doubt ("whether anyone has been appointed") never count as an appointment."""
    kind, text = clue.get("kind"), str(clue.get("detail") or "")
    if kind == "leadership_change" and _VACANCY.search(text) and not _APPOINTED.search(_DOUBT.sub(" ", text)):
        return {**clue, "kind": "role_vacancy", "filed_as": kind}
    if kind == "site_opening" and _ACQUIRED.search(text):
        return {**clue, "kind": "acquisition", "filed_as": kind}
    if kind == "supplier_appointed" and not _MAINTAINS.search(text):
        if _TAKEOVER.search(text):
            return {**clue, "kind": "acquisition", "filed_as": kind}
        if _BUILDS.search(text):
            return {**clue, "kind": "contractor_appointed", "filed_as": kind}
    return clue


def clue_window(clue: dict, today: date) -> dict | None:
    """Turn one clue into a window, the rule behind it, and whether it opens or holds closed."""
    kind = clue.get("kind")
    when = parse_when(clue.get("date"))
    if kind not in KINDS or kind in NOTES or when is None:
        return None
    day, basis = when.day, "stated" if clue.get("basis") == "stated" else "inferred"
    family = clue.get("system_family") if clue.get("system_family") in LIFESPANS else "general"
    polarity, start, end, rule = 1, day, day, ""
    if kind in REPLACEMENT:
        low, high, why = LIFESPANS[family]
        start, end, rule = add_years(day, low), add_years(day, high), f"{why}; installed or completed around {day.year}"
    elif kind == "supplier_appointed":
        start, end = add_years(day, CONTRACT_TERM_YEARS[0] - 0.5), add_years(day, CONTRACT_TERM_YEARS[1])
        rule = "maintenance contracts commonly run three to five years, so re-procurement is usually prepared from about two and a half years in"
        if add_months(day, LOCK_IN_MONTHS) > today:
            return {**_base(clue, kind, basis, when), "polarity": -1, "start": day, "end": add_months(day, LOCK_IN_MONTHS),
                    "rule": "a supplier appointed within the last year is rarely replaced before the first year ends"}
    elif kind == "contract_end_stated":
        start, end, rule = add_months(day, -9), day, "re-procurement is normally run in the nine months before a stated contract end"
    elif kind == "financial_year_end":
        year_end = date(today.year, day.month, min(day.day, 28))
        while add_months(year_end, -2) < today:
            year_end = date(year_end.year + 1, year_end.month, year_end.day)
        start, end, rule = add_months(year_end, -6), add_months(year_end, -2), f"budgets for the year ending {year_end:%B %Y} are usually set two to six months before it"
    elif kind == "regulatory_deadline":
        start, end, rule = add_months(day, -12), day, "organisations usually act in the year before a compliance deadline"
    elif kind == "leadership_change":
        start, end, rule = add_months(day, 1), add_months(day, 9), "new estates, facilities or security leaders commonly review suppliers in their first nine months"
    elif kind == "site_opening":
        start, end, rule = add_months(day, -12), add_months(day, -3), "fire and security for a new site is usually procured three to twelve months before it opens"
    elif kind == "incident":
        start, end, rule = day, add_months(day, 4), "incidents often prompt a review of systems and providers within about four months"
    elif kind == "incumbent_distress":
        start, end, rule = day, add_months(day, 6), "customers of a supplier in difficulty often seek alternatives within about six months"
    return {**_base(clue, kind, basis, when), "polarity": polarity, "start": start, "end": end, "rule": rule}


def _base(clue: dict, kind: str, basis: str, when: Parsed) -> dict:
    return {"kind": kind, "label": KINDS[kind], "detail": str(clue.get("detail") or "")[:300], "basis": basis,
            "strength": _strength(basis, when.precision), "observed": when.day, "precision": when.precision,
            "source_url": clue.get("source_url") or "", "system_family": clue.get("system_family") or ""}


def _status(window: dict, today: date) -> str:
    return "active" if window["start"] <= today <= window["end"] else "upcoming" if window["start"] > today else "past"


def convergence(windows: list[dict], today: date, horizon_months: int = 24) -> dict | None:
    """Where do the most independent kinds of clue overlap, from today to the horizon?"""
    horizon = add_months(today, horizon_months)
    positive = [w for w in windows if w["polarity"] > 0 and w["end"] >= today and w["start"] <= horizon]
    points = sorted({max(w["start"], today) for w in positive})
    best = None
    for point in points:
        live = [w for w in positive if w["start"] <= point <= w["end"]]
        kinds = sorted({w["kind"] for w in live})
        if len(kinds) >= 2 and (best is None or len(kinds) > len(best["kinds"])):
            end = min(w["end"] for w in live)
            best = {"start": point, "end": end, "kinds": kinds, "labels": [KINDS[k] for k in kinds]}
    return best


def infer_timing(clues: list[dict], today: date) -> dict:
    """Fuse clue windows into a phase for maintenance: engage now, prepare, not yet, or unknown."""
    clues = [reclassify(c) for c in clues if isinstance(c, dict)]
    windows = [w for w in (clue_window(c, today) for c in clues) if w]
    for w in windows:
        w["status"] = _status(w, today)
        # A deadline that applies to everyone says nothing specific about this organisation
        # unless a source ties it to them, so an inferred one is context, not evidence. A
        # replacement date still ahead is a separate, later sale: context, never a reason to wait.
        w["context_only"] = (w["kind"] == "regulatory_deadline" and w["basis"] != "stated") or (w["kind"] in REPLACEMENT and w["status"] == "upcoming")
    notes = [{**_base(c, c["kind"], "stated" if c.get("basis") == "stated" else "inferred", when), "rule": NOTES[c["kind"]]}
             for c in clues if c.get("kind") in NOTES and (when := parse_when(c.get("date")))]
    evidence = [w for w in windows if not w["context_only"]]
    positive = [w for w in evidence if w["polarity"] > 0 and w["status"] != "past"]
    active = [w for w in positive if w["status"] == "active"]
    upcoming = sorted((w for w in positive if w["status"] == "upcoming"), key=lambda w: w["start"])
    locks = [w for w in evidence if w["polarity"] < 0 and w["status"] == "active"]
    overriding = [w for w in active if w["kind"] in OVERRIDES_LOCK]
    together = convergence(evidence, today)
    context = [w for w in windows if w["context_only"] and w["status"] != "past"]
    reasons: list[str] = []
    if not evidence:
        phase = "unknown"
        if not notes and not context:
            reasons = ["No dated clue specific to this organisation was found, so timing cannot be inferred yet."]
    elif locks and not overriding:
        phase = "not_yet"
        reasons.append(f"A supplier was appointed recently; expect little appetite to change before {locks[0]['end']:%B %Y}.")
    elif [w for w in active if w["strength"] != "weak"] or (together and together["start"] <= today):
        phase = "engage_now"
    elif active:
        phase = "prepare"
        reasons.append("Only weak, inferred clues are active now; confirm before investing heavily.")
    elif upcoming and upcoming[0]["start"] <= add_months(today, 12):
        phase = "prepare"
    elif upcoming:
        phase = "not_yet"
    else:
        phase = "unknown"
        reasons.append("The clues found point to windows that have already passed.")
    for w in sorted(active, key=lambda w: ("strong", "moderate", "weak").index(w["strength"])):
        reasons.append(f"{w['label']}: {w['rule']}. Window open until {w['end']:%B %Y}.")
    for w in upcoming[:3]:
        reasons.append(f"{w['label']}: {w['rule']}. Window opens {w['start']:%B %Y}.")
    said = set()
    for n in sorted(notes, key=lambda n: n["observed"], reverse=True):  # one line for each kind of note, however many clues say it
        if n["kind"] not in said and len(said) < 2:
            said.add(n["kind"])
            reasons.append(f"{n['label']}: {n['rule']}.")
    for w in [w for w in context if w["kind"] in REPLACEMENT][:1]:
        reasons.append(f"Replacement, a separate sale: {w['rule']}. That window opens {w['start']:%B %Y}; it does not set when maintenance is reviewed.")
    if not evidence and (notes or context):  # the specific reason to ask comes first; this only says what is missing
        reasons.append("When their maintenance is next reviewed is not published.")
    for w in [w for w in context if w["kind"] not in REPLACEMENT][:1]:
        reasons.append(f"Context: {w['detail'] or w['label']} ({w['end']:%B %Y}). It applies widely, so confirm it affects them before relying on it.")
    if together:
        reasons.insert(0, f"{len(together['kinds'])} independent clues converge from {together['start']:%B %Y} to {together['end']:%B %Y}: {', '.join(together['labels'])}.")
    window = None
    if together:
        window = {"start": together["start"], "end": together["end"]}
    elif active:
        window = {"start": today, "end": max(w["end"] for w in active)}
    elif upcoming:
        window = {"start": upcoming[0]["start"], "end": upcoming[0]["end"]}
    light = {"engage_now": "green", "prepare": "amber", "not_yet": "red", "unknown": "grey"}[phase]
    label = {"engage_now": "Engage now", "prepare": "Prepare", "not_yet": "Not yet", "unknown": "Timing unknown"}[phase]
    return {"phase": phase, "light": light, "label": label, "window": window, "convergence": together,
            "blocked_until": locks[0]["end"] if locks and not overriding else None, "reasons": reasons[:6],
            "clues": sorted(windows, key=lambda w: w["start"]), "notes": sorted(notes, key=lambda n: n["observed"]), "as_of": today,
            "method": "Inferred from indirect, dated clues using industry rules of thumb. A phase, not a probability."}
