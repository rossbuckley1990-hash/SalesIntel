"""Accounts, unified discovery and the Today queue for SalesIntel 2.0.

Identity rules, deliberately conservative:
- the same Companies House number links records as the same organisation (confirmed);
- the same name after removing legal suffixes links them, shown as unconfirmed;
- similar names are only suggested and never merged until a person confirms.
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.intelligence.renewal_radar import families
from app.models.crm import Account, AccountLink, Activity, Contact, DealRecord, Draft, FunnelEvent, Preference, Site, Task
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.models.prospect import Prospect
from app.models.tenancy import LeadState
from app.services.prospect_research import view as prospect_view
from app.tenancy import hosted

LEGAL = re.compile(r"\b(limited|ltd|plc|llp|lp|cic|incorporated|inc|the)\b")
# Keys are the Renewal Radar family names. Adjacent work (extinguishers, risk assessments, passive fire, smoke control) is its own
# service, never counted as fire alarms, so a fire-alarm installer is not told a fire-risk-assessment tender "sells what you sell".
FAMILY_SERVICE = {"fire_alarm": "fire_alarm", "cctv": "cctv", "access": "access_control", "access_control": "access_control", "intruder": "intruder",
                  "emergency_lighting": "emergency_lighting", "sprinkler": "sprinkler", "sprinklers": "sprinkler", "suppression": "sprinkler",
                  "extinguisher": "extinguishers", "extinguishers": "extinguishers", "passive_fire": "passive_fire", "smoke_control": "smoke_control",
                  "fire_risk_assessment": "fire_risk_assessment", "door_entry": "access_control"}
SERVICE_WORDS = {"fire alarm": "fire_alarm", "fire detection": "fire_alarm", "cctv": "cctv", "camera": "cctv", "access control": "access_control",
                 "door entry": "access_control", "intruder": "intruder", "burglar": "intruder", "emergency lighting": "emergency_lighting",
                 "sprinkler": "sprinkler", "suppression": "sprinkler", "monitoring": "monitoring"}
NATIONS = {"england": "England", "scotland": "Scotland", "wales": "Wales", "northern ireland": "Northern Ireland"}
REGIONS = ["yorkshire", "north west", "north east", "midlands", "east midlands", "west midlands", "london", "south east", "south west",
           "east of england", "east anglia", "humber"]


def now() -> datetime:
    return datetime.now(UTC)


UK = ZoneInfo("Europe/London")


def uk_today() -> date:
    """The salesperson's calendar day. Follow-ups are UK dates, so 00:30 BST is already tomorrow."""
    return now().astimezone(UK).date()


def name_key(name: str) -> str:
    text = (name or "").lower().replace("&", " and ")
    text = LEGAL.sub(" ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()[:255]


def display_name(name: str) -> str:
    """Registers often publish buyers in capitals; show them as people write them."""
    if name != name.upper():
        return name.strip()
    words = name.lower().split()
    keep = {"nhs", "uk", "plc", "llp", "hmrc", "dvla", "cic"}
    return " ".join(w.upper() if w in keep else w.capitalize() for w in words)


ORIGIN = {"shadow_hypothesis": ("sh", "shadow"), "market_opportunity": ("mo", "public"), "prospect": ("pr", "private")}


def origin_of(db: Session, account_id: int) -> tuple[str | None, str]:
    """The discovery record an account came from (its first link), or manual when it was added by hand."""
    link = db.scalar(select(AccountLink).where(AccountLink.account_id == account_id).order_by(AccountLink.id))
    if link is None:
        return None, "manual"
    prefix, kind = ORIGIN.get(link.entity_type, (link.entity_type[:12], "manual"))
    return f"{prefix}:{link.entity_id}", kind


def track(db: Session, event: str, *, account_id: int | None = None, deal_id: int | None = None, ref: str | None = None,
          origin: str | None = None, amount: float | None = None, amount_basis: str | None = None) -> None:
    """Record one step of the acquisition journey. The origin is fixed now, so attribution never shifts afterwards."""
    source_type = None
    if origin:
        source_type = next((kind for prefix, kind in ORIGIN.values() if origin.startswith(prefix + ":")), "manual")
    elif account_id is not None:
        origin, source_type = origin_of(db, account_id)
    db.add(FunnelEvent(event=event[:48], day=now().date(), at=now(), account_id=account_id, deal_id=deal_id, ref=(ref or None) and ref[:48],
                       origin=origin, source_type=source_type, amount=amount, amount_basis=amount_basis))


# ---------------------------------------------------------------- source records

def _mo(db: Session, entity_id: int) -> tuple[MarketOpportunity, dict] | None:
    item = db.get(MarketOpportunity, entity_id)
    version = db.get(MarketOpportunityRevision, item.current_revision_id) if item and item.current_revision_id else None
    return (item, version.result) if version else None


def source_identity(db: Session, entity_type: str, entity_id: int) -> dict | None:
    if entity_type == "market_opportunity":
        found = _mo(db, entity_id)
        if not found:
            return None
        return {"name": found[1].get("customer") or "", "company_number": None, "kind": "public_body", "region": found[1].get("nation"), "sector": "Public sector"}
    if entity_type == "prospect":
        row = db.get(Prospect, entity_id)
        if not row:
            return None
        number = str(row.data.get("company_number") or "").strip().upper() or None
        return {"name": row.name, "company_number": number if number and re.fullmatch(r"[0-9A-Z]{8}", number) else None, "kind": "private",
                "region": row.data.get("location"), "sector": row.data.get("sector"), "website": row.data.get("website")}
    if entity_type == "shadow_hypothesis":
        from app.services import shadow
        found = shadow.current(db, entity_id)
        if not found:
            return None
        a = found[1]
        public = bool(re.search(r"\b(council|nhs|trust|borough|college|university|academy|school|police|fire|department|office|agency|authority|housing)\b", a["entity_name"], re.I))
        return {"name": a["entity_name"], "company_number": a.get("company_number"), "kind": "public_body" if public else "unknown", "region": None,
                "sector": "Public sector" if public else None}
    return None


def resolve_account(db: Session, name: str, company_number: str | None) -> tuple[Account | None, str]:
    if company_number:
        found = db.scalar(select(Account).where(Account.company_number == company_number))
        if found:
            return found, "company_number"
    key = name_key(name)
    if key:
        candidates = db.scalars(select(Account).where(Account.key == key)).all()
        # A different registered number means a different organisation, whatever the name.
        candidates = [a for a in candidates if not (company_number and a.company_number and a.company_number != company_number)]
        if candidates:
            return candidates[0], "same_name"
    return None, ""


def link_source(db: Session, entity_type: str, entity_id: int, account_id: int | None = None) -> tuple[Account, AccountLink, bool]:
    """Attach a research record to its account, creating the account only when none matches."""
    existing = db.scalar(select(AccountLink).where(AccountLink.entity_type == entity_type, AccountLink.entity_id == entity_id))
    if existing:
        return db.get(Account, existing.account_id), existing, False
    identity = source_identity(db, entity_type, entity_id)
    if identity is None:
        raise LookupError("Record not found")
    moment, created = now(), False
    if account_id is not None:
        account = db.get(Account, account_id)
        if account is None:
            raise LookupError("Account not found")
        basis, confirmed = "user_confirmed", True
    else:
        account, basis = resolve_account(db, identity["name"], identity.get("company_number"))
        confirmed = basis == "company_number"
        if account is None:
            account = Account(name=display_name(identity["name"])[:255], key=name_key(identity["name"]), kind=identity["kind"],
                              company_number=identity.get("company_number"), website=identity.get("website"), sector=identity.get("sector"),
                              region=(identity.get("region") or "")[:160] or None, status="prospect", watched=False, notes="",
                              created_at=moment, updated_at=moment)
            db.add(account)
            db.flush()
            basis, confirmed, created = "created_from", True, True
            prefix = ORIGIN.get(entity_type, (entity_type[:12], "manual"))[0]
            track(db, "account_created", account_id=account.id, origin=f"{prefix}:{entity_id}")
    if identity.get("company_number") and not account.company_number and basis != "same_name":
        account.company_number = identity["company_number"]
    link = AccountLink(account_id=account.id, entity_type=entity_type, entity_id=entity_id, name_seen=identity["name"][:255],
                       basis=basis, confirmed=confirmed, created_at=moment)
    db.add(link)
    account.updated_at = moment
    if entity_type == "prospect":
        import_prospect_contacts(db, account, db.get(Prospect, entity_id))
    db.flush()
    return account, link, created


def import_prospect_contacts(db: Session, account: Account, prospect: Prospect) -> int:
    """Copy only the people and routes research kept, with their sources. Nothing is added."""
    moment, added = now(), 0
    known = {(c.name or "", c.email or "", c.phone or "") for c in db.scalars(select(Contact).where(Contact.account_id == account.id))}
    for person in prospect.data.get("people") or []:
        key = (person.get("name") or "", "", "")
        if key in known:
            continue
        db.add(Contact(account_id=account.id, name=person.get("name"), role=person.get("role") or "", basis="published", source_url=person.get("source_url"),
                       source_quote=person.get("quote"), influence=person.get("influence") or "", status="unverified", label="", created_at=moment, updated_at=moment))
        known.add(key)
        added += 1
    for route in prospect.data.get("contact_routes") or []:
        email = route["value"] if route.get("kind") == "email" else None
        phone = route["value"] if route.get("kind") in ("phone", "switchboard") else None
        if not (email or phone) or ("", email or "", phone or "") in known:
            continue
        db.add(Contact(account_id=account.id, name=None, role="", email=email, phone=phone, label=route.get("label") or route.get("kind") or "", basis="published",
                       source_url=route.get("source_url"), source_quote=route.get("quote"), status="unverified", influence="", created_at=moment, updated_at=moment))
        known.add(("", email or "", phone or ""))
        added += 1
    return added


GENERIC = {"group", "housing", "association", "services", "service", "uk", "trust", "council", "city", "county", "borough", "district", "metropolitan",
           "nhs", "foundation", "university", "college", "school", "and", "of", "company", "holdings", "international", "property", "properties",
           "care", "homes", "logistics", "estates", "management", "partnership", "for", "national", "royal", "new", "health", "community"}


def _distinctive(key: str) -> set[str]:
    return {t for t in key.split() if t not in GENERIC and len(t) > 2}


def suggestions(db: Session, account: Account) -> list[dict]:
    """Records that might be the same organisation, offered for confirmation, never merged."""
    mine = _distinctive(account.key)
    if not mine:
        return []
    linked = {(x.entity_type, x.entity_id) for x in db.scalars(select(AccountLink))}
    out = []
    for row in db.scalars(select(Prospect).where(Prospect.status != "dismissed")):
        if ("prospect", row.id) not in linked and mine & _distinctive(name_key(row.name)):
            out.append({"source": f"pr:{row.id}", "name": row.name, "why": "Shares a distinctive name. Confirm it is the same organisation before linking."})
    for item in discover_items(db, include_private=False, limit=None):
        if item["account_id"] is None and mine & _distinctive(name_key(item["organisation"])):
            out.append({"source": item["key"], "name": item["organisation"], "why": "Public notice with a similar buyer name. Confirm before linking."})
    return out[:8]


# ---------------------------------------------------------------- discover

def _services_from_title(title: str) -> list[str]:
    return sorted({FAMILY_SERVICE[f] for f in families(title) if f in FAMILY_SERVICE})


def _days(day: str | None, today: date) -> int | None:
    try:
        return (date.fromisoformat(str(day)[:10]) - today).days if day else None
    except ValueError:
        return None


def _why_public(s: dict) -> str:
    cat, timing, supplier = s.get("category"), s.get("timing"), s.get("supplier")
    when = date.fromisoformat(timing[:10]).strftime("%-d %B %Y") if timing else None
    if cat == "live_procurement":
        return f"Tender open now{f', deadline {when}' if when else ''}."
    if cat == "official_early_signal":
        return f"The buyer published an early notice{f'; tender expected {when}' if when else ''}."
    if cat == "contract_defence":
        return f"Group-held contract ending{f' {when}' if when else ''}: protect it before re-tender."
    if cat == "pre_tender":
        return f"Published contract{f' with {supplier}' if supplier else ''} ends {when or 'soon'}; the buyer is likely to plan its replacement before then."
    if cat == "verify_first":
        return f"Published term {'ended' if timing and _days(timing, uk_today()) is not None and _days(timing, uk_today()) < 0 else 'ends'} {when or 'on an unpublished date'}; current arrangement not confirmed."
    return (s.get("brief") or {}).get("why_it_matters") or "Public signal worth checking."


def discover_items(db: Session, *, include_private: bool = True, include_public: bool = True, limit: int | None = 200, include_shadow: bool = True) -> list[dict]:
    today = uk_today()
    links = {(x.entity_type, x.entity_id): x for x in db.scalars(select(AccountLink))}
    items: list[dict] = []
    prefs = preferences(db)
    statuses = {a.id: a.status for a in db.scalars(select(Account))}
    routes = dict(db.execute(select(Contact.account_id, func.count()).where(Contact.status != "do_not_contact", Contact.route_kind.not_in(["", "none"]))
                             .group_by(Contact.account_id)).all())
    if include_public:
        # This workspace's own review of each shared notice; another company's review is never seen.
        reviewed = {r.entity_id: r.status for r in db.scalars(select(LeadState).where(LeadState.entity_type == "market_opportunity"))}
        rows = db.execute(select(MarketOpportunity, MarketOpportunityRevision).join(MarketOpportunityRevision, MarketOpportunity.current_revision_id == MarketOpportunityRevision.id)
                          .where(MarketOpportunity.state == "suggested")).all()
        for item, version in rows:
            s = version.result
            link = links.get(("market_opportunity", item.id))
            days = _days(s.get("timing"), today)
            urgent = s.get("category") in ("contract_defence", "live_procurement") or (days is not None and 0 <= days <= 120)
            items.append({
                "key": f"mo:{item.id}", "type": "public", "source_label": "Public procurement", "organisation": display_name(s.get("customer") or ""),
                "title": s.get("title") or "", "why_now": _why_public(s), "category": s.get("category"), "category_label": s.get("category_label"),
                "basis": "inferred" if s.get("category") == "inferred_signal" else "published", "timing": s.get("timing"), "days": days, "sector": s.get("sector"),
                "timing_label": s.get("timing_basis") or "", "nation": s.get("nation"), "tier": (s.get("priority") or {}).get("tier"),
                "services": _services_from_title(s.get("title") or ""), "supplier": s.get("supplier"), "value": s.get("value"),
                "status": reviewed.get(item.id) or ("new" if hosted() else {"unreviewed": "new", "investigate": "investigating", "defer": "watching", "dismiss": "dismissed"}.get(item.review_state, "new")),
                "account_id": link.account_id if link else None, "link_basis": link.basis if link else None,
                "rank": (0 if urgent and (s.get("priority") or {}).get("tier") == 1 else 1 if urgent else 2, days if days is not None and days >= 0 else 9999),
            })
            it = items[-1]
            it["kind"] = _kind(it, statuses.get(it["account_id"]))
            known = [{"text": f"{e.get('source')} notice {e.get('record_key')}", "source_url": e.get("source_url"), "date": (e.get("published_at") or "")[:10], "basis": "published"}
                     for e in s.get("evidence") or []]
            if s.get("supplier"):
                known.append({"text": f"Supplier named on the published record: {s['supplier']} (reported, not necessarily today's incumbent)", "source_url": None, "date": "", "basis": "published"})
            if s.get("timing"):
                known.append({"text": f"{s.get('timing_basis') or 'Timing'}: {s['timing']}", "source_url": None, "date": "", "basis": "published"})
            it["brief"] = _brief(it, it["kind"], prefs, s.get("sector") or "", known, (s.get("brief") or {}).get("missing_information") or [],
                                 routes.get(it["account_id"], 0), 0)
            it["kind_label"] = KIND_LABEL[it["kind"]]
    if include_private:
        for row in db.scalars(select(Prospect)):
            v = prospect_view(row, today)
            link = links.get(("prospect", row.id))
            phase = v["timing"]["phase"]
            items.append({
                "key": f"pr:{row.id}", "type": "private", "source_label": "Private research", "organisation": row.name, "title": v.get("headline") or "",
                "why_now": (v["timing"]["reasons"] or [v.get("headline") or ""])[0], "category": "private_" + phase, "category_label": v["timing"]["label"],
                "basis": "published" if any(s.get("basis") == "stated" for s in v.get("signals") or []) else "inferred",
                "timing": (v["timing"].get("window") or {}).get("start"), "days": None, "timing_label": v["timing"]["label"], "light": v["timing"]["light"],
                "nation": None, "region": v.get("location"), "tier": None, "services": v.get("services") or [], "supplier": (v.get("incumbent") or {}).get("name") or None,
                "sector": v.get("sector"), "signal_types": [x.get("type") for x in v.get("signals") or [] if x.get("source_url")],
                "value": None, "status": {"new": "new", "watching": "watching", "pipeline": "investigating", "dismissed": "dismissed"}.get(row.status, "new"),
                "account_id": link.account_id if link else None, "link_basis": link.basis if link else None,
                "people": len(v.get("people") or []), "contact_routes": len(v.get("contact_routes") or []),
                # Inferred timing never outranks a published deadline in the same bucket.
                "rank": (1 if phase == "engage_now" else 2 if phase == "prepare" else 3, 9999),
            })
            it = items[-1]
            it["kind"] = _kind(it, statuses.get(it["account_id"]))
            known = [{"text": sig.get("title") or "", "source_url": sig.get("source_url") or None, "date": sig.get("date") or "", "basis": sig.get("basis") or "inferred"}
                     for sig in v.get("signals") or []]
            known += [{"text": f"{c.get('detail') or c.get('kind')}", "source_url": c.get("source_url") or None, "date": c.get("date") or "", "basis": c.get("basis") or "inferred"}
                      for c in v.get("timing_clues") or [] if c.get("source_url")]
            stated = next((sig for sig in v.get("signals") or [] if sig.get("basis") == "stated" and sig.get("source_url")), None)
            it["brief"] = _brief(it, it["kind"], prefs, v.get("sector") or "", known, v.get("unknowns") or [], routes.get(it["account_id"], 0), len(v.get("people") or []),
                                 why_now=(v.get("headline") or stated.get("title")) if stated else None, inferred_timing=it["why_now"] if stated else "")
            it["kind_label"] = KIND_LABEL[it["kind"]]
    if include_shadow:
        items += _shadow_items(db, links, statuses, routes, prefs, today)
    # Published deadlines first, then by how much of the recorded fit matches; never by an invented score.
    items.sort(key=lambda x: (x["status"] == "dismissed", x["kind"] == "unverified_candidate", x["rank"], -len(x["brief"]["fit"]["matched"]), x["organisation"]))
    return items if limit is None else items[:limit]


KIND_LABEL = {"published_procurement": "Published procurement opportunity", "contract_ending": "Existing contract approaching a reported end date",
              "private_signal": "Private organisation with an observable signal", "customer_expansion": "Existing customer: expansion opportunity",
              "unverified_candidate": "Unverified research candidate", "shadow_signal": "Unadvertised: inferred from indirect public signals"}
WHO = {"shadow": ["Estates, property or facilities manager", "Main contractor supply chain", "Procurement or category manager"], "public": ["Procurement or category manager", "Estates, property or facilities manager", "Fire safety or health and safety manager"],
       "private": ["Estates, property or facilities manager", "Operations or managing director", "Fire safety or health and safety manager"]}


def _kind(item: dict, status: str | None) -> str:
    if status == "customer":
        return "customer_expansion"
    if item["type"] == "public":
        return {"live_procurement": "published_procurement", "official_early_signal": "published_procurement", "inferred_signal": "unverified_candidate"}.get(item["category"], "contract_ending")
    return "private_signal" if item["basis"] == "published" else "unverified_candidate"


def _fit(item: dict, prefs: dict, sector: str) -> dict:
    """Transparent fit against what this workspace sells and covers. No score is invented."""
    matched, gaps, unknown = [], [], []
    ours = set(prefs["services"])
    if not ours:
        unknown.append("Your services are not set")
    elif set(item["services"]) & ours:
        matched.append("Sells what you sell: " + ", ".join(sorted(set(item["services"]) & ours)).replace("_", " "))
    elif item["services"]:
        gaps.append("Services outside what you sell")
    else:
        unknown.append("Services not stated")
    place = f"{item.get('nation') or ''} {item.get('region') or ''}".lower()
    # Free-text places ("Selby, North Yorkshire") rarely name a nation: an English region means England, another named
    # nation means outside; anything else is not confirmed, never "outside".
    if not item.get("nation") and any(r in place for r in REGIONS):
        place += " england"
    territory = [t for t in prefs["territory"] if t.lower() in place]
    named_nation = any(n in place for n in NATIONS)
    (matched.append(f"In your territory: {territory[0]}") if territory else gaps.append("Outside your recorded territory") if prefs["territory"] and named_nation
     else unknown.append(("Location not confirmed against your territory" if place.strip() else "Location not stated") if prefs["territory"] else "Your territory is not set"))
    if prefs["sectors"]:
        hit = [s for s in prefs["sectors"] if s.lower() in (sector or "").lower() or s.lower() in item["title"].lower()]
        matched.append(f"Target sector: {hit[0]}") if hit else unknown.append("Sector not matched to your targets")
    value = (item.get("value") or {}).get("published_total") if isinstance(item.get("value"), dict) else None
    low, high = prefs.get("deal_size_min"), prefs.get("deal_size_max")
    if value and (low or high):
        inside = (not low or value >= float(low)) and (not high or value <= float(high))
        (matched if inside else gaps).append(f"Published value £{value:,.0f} {'within' if inside else 'outside'} your preferred deal size")
    elif low or high:
        unknown.append("Value not published")
    return {"matched": matched, "gaps": gaps, "unknown": unknown}


def _brief(item: dict, kind: str, prefs: dict, sector: str, known: list[dict], unknowns: list[str], routes: int, people: int,
           why_now: str | None = None, inferred_timing: str = "") -> dict:
    fit = _fit(item, prefs, sector)
    if kind == "contract_ending":
        unknowns = ["Whether the buyer will re-tender, extend or bring it in house: a contract ending is not a confirmed tender.", *unknowns]
    if kind in ("private_signal", "unverified_candidate"):
        unknowns = [*unknowns, "Any confirmed requirement: the signal is a reason to investigate, not proof of buying intent."]
    if kind == "unverified_candidate":
        unknowns = ["The signal is inferred or unsourced. Verify it before acting.", *unknowns]
    if item["account_id"] is None:
        nxt = "Open the account and find the right people." if kind != "unverified_candidate" else "Verify the signal before opening an account."
    elif not routes:
        nxt = "Find the right people at this organisation."
    elif kind == "published_procurement":
        nxt = "Read the notice and respond through the buyer's portal and rules."
    else:
        nxt = "Prepare an introduction to the best-ranked contact."
    return {"why_customer": fit["matched"] or ["No recorded fit yet: set your services, territory and sectors."], "fit": fit,
            "why_now": why_now or item["why_now"], "why_now_basis": "Published" if item["basis"] == "published" else "Inferred",
            "inferred_timing": inferred_timing,
            "known": known[:6], "unknown": list(dict.fromkeys(unknowns))[:6],
            "who": {"roles": WHO[item["type"]], "routes_saved": routes, "people_in_research": people,
                    "summary": (f"{routes} saved contact route(s)" if routes else "No contact routes saved yet")}, "next": nxt}


def shadow_why(a: dict) -> str:
    anchor = next((e for e in a["timeline"] if e["role"] == "anchor"), None)
    if not anchor:
        return a["hypothesis"]
    return f"{anchor['statement']} {a['hypothesis']}"


def _shadow_items(db: Session, links: dict, statuses: dict, routes: dict, prefs: dict, today: date) -> list[dict]:
    from app.services import shadow
    reviewed = {r.entity_id: r.status for r in db.scalars(select(LeadState).where(LeadState.entity_type == "shadow_hypothesis"))}
    order = {"corroborated": 0, "indicated": 1, "surfaced": 2, "challenged": 3}
    # One row per piece of evidence: competing readings of the same project are shown together, not as duplicates.
    groups: dict[str, list] = {}
    for row, a in shadow.active(db):
        groups.setdefault(a["key"].split("|", 1)[1], []).append((row, a))
    primaries = []
    for members in groups.values():
        members.sort(key=lambda m: (order.get(m[1]["state"], 3), m[1]["sensor"] != "adjacent_package"))
        primaries.append((members[0], [m for m in members[1:]]))
    out = []
    for (row, a), rivals in primaries:
        link = links.get(("shadow_hypothesis", row.id))
        start = date.fromisoformat(a["window"][0])
        item = {"key": f"sh:{row.id}", "type": "shadow", "source_label": "Shadow Radar", "organisation": display_name(a["entity_name"]),
                "title": f"{a['sensor_name']}: {a.get('site') or a['hypothesis']}", "why_now": shadow_why(a), "category": a["sensor"], "category_label": a["sensor_name"],
                "basis": "inferred", "timing": a["window"][0], "days": (start - today).days, "timing_label": "Possible investigation window opens",
                "nation": None, "region": None, "tier": None, "services": a["services"], "supplier": a.get("main_contractor"), "value": None,
                "status": reviewed.get(row.id, "new"), "account_id": link.account_id if link else None, "link_basis": link.basis if link else None,
                "rank": (1 + order.get(a["state"], 3), max((start - today).days, 0)),
                "shadow": {**a, "competing": [{"key": f"sh:{r.id}", "sensor_name": x["sensor_name"], "hypothesis": x["hypothesis"], "first_action": x["first_action"],
                                               "state_label": x["state_label"], "window": x["window"]} for r, x in rivals]}}
        item["kind"] = "customer_expansion" if statuses.get(item["account_id"]) == "customer" else "shadow_signal"
        known = [{"text": f"{e['label']}: {e['statement']}", "source_url": e["source_url"], "date": e["published"], "basis": e["basis"]}
                 for e in a["timeline"] if e["role"] in ("anchor", "supports", "advertised")]
        unknown = list(a["unknown"]) + [f"Alternative: {x['explanation']}" for x in a["alternatives"]]
        item["brief"] = _brief(item, item["kind"], prefs, "", known, unknown, routes.get(item["account_id"], 0), 0, why_now=shadow_why(a))
        if item["account_id"] is None:
            item["brief"]["next"] = a["first_action"]
        item["kind_label"] = KIND_LABEL[item["kind"]]
        out.append(item)
    return out


def interpret(q: str) -> dict:
    text = (q or "").lower()
    nations = [v for k, v in NATIONS.items() if k in text]
    services = sorted({v for k, v in SERVICE_WORDS.items() if k in text})
    regions = [r for r in REGIONS if r in text]
    stop = {"find", "with", "and", "the", "in", "of", "for", "that", "evidence", "suggesting", "potential", "opportunities", "opportunity", "maintenance",
            "groups", "group", "companies", "multi", "site", "sites", "estates", "estate", "a", "to", "near", "around", "show", "me", "all", "contracts", "contract"}
    words = re.findall(r"[a-z0-9]+", text)
    consumed = " ".join(list(NATIONS) + list(SERVICE_WORDS) + regions).split()
    keywords = [w for w in words if w not in stop and w not in consumed and len(w) > 2]
    return {"nations": nations, "services": services, "regions": regions, "keywords": keywords}


def discover(db: Session, *, q: str = "", source: str = "all", nation: str = "", service: str = "", status: str = "active", category: str = "",
             limit: int = 50, offset: int = 0) -> dict:
    meaning = interpret(q)
    items = discover_items(db, include_public=source in ("all", "public"), include_private=source in ("all", "private"), limit=None,
                           include_shadow=source in ("all", "public", "shadow"))
    nations = [nation] if nation else meaning["nations"]
    services = [service] if service else meaning["services"]
    def keep(x: dict) -> bool:
        if status == "active" and x["status"] == "dismissed":
            return False
        if status not in ("active", "all") and x["status"] != status:
            return False
        if category and x["category"] != category:
            return False
        if nations and x["type"] == "public" and x.get("nation") not in nations:
            return False
        if nations and x["type"] == "private" and not any(n.lower() in str(x.get("region") or "").lower() for n in nations):
            return False  # research is located by free text, so match the nation there
        if services and not set(services) & set(x["services"]):
            return False
        hay = " ".join(str(x.get(k) or "") for k in ("organisation", "title", "why_now", "supplier", "region")).lower()
        return all(k in hay for k in meaning["keywords"])
    found = [x for x in items if keep(x)]
    gaps = []
    if meaning["regions"]:
        gaps.append(f"Public notices are located by nation, not region, so '{', '.join(meaning['regions'])}' is matched only where it appears in the text.")
    if nations and source != "public":
        gaps.append("Private research has no nation field, so it is matched on its location text.")
    if q and source != "public":
        gaps.append("Private matches come only from prospect research already run. Use “Research the web” to look further; it uses API credit.")
    if not found:
        gaps.append("No captured record matches. This does not mean no opportunity exists.")
    counts = {"public": sum(1 for x in found if x["type"] == "public"), "private": sum(1 for x in found if x["type"] == "private"),
              "shadow": sum(1 for x in found if x["type"] == "shadow")}
    return {"items": found[offset:offset + limit], "total": len(found), "counts": counts, "interpreted": meaning, "gaps": gaps}


def set_status(db: Session, key: str, status: str) -> None:
    kind, _, raw = key.partition(":")
    entity_id = int(raw)
    if kind == "mo":
        item = db.get(MarketOpportunity, entity_id)
        if not item:
            raise LookupError("Record not found")
        state = db.scalar(select(LeadState).where(LeadState.entity_type == "market_opportunity", LeadState.entity_id == entity_id))
        if state is None:
            db.add(LeadState(entity_type="market_opportunity", entity_id=entity_id, status=status, updated_at=now(), updated_by=db.info.get("user_id")))
        else:
            state.status, state.updated_at, state.updated_by = status, now(), db.info.get("user_id")
        if not hosted():  # the single-user classic workspace reads the shared review state
            item.review_state = {"new": "unreviewed", "watching": "defer", "dismissed": "dismiss", "investigating": "investigate"}[status]
    elif kind == "sh":
        from app.models.shadow import ShadowHypothesis
        if db.get(ShadowHypothesis, entity_id) is None:
            raise LookupError("Record not found")
        state = db.scalar(select(LeadState).where(LeadState.entity_type == "shadow_hypothesis", LeadState.entity_id == entity_id))
        if state is None:
            db.add(LeadState(entity_type="shadow_hypothesis", entity_id=entity_id, status=status, updated_at=now(), updated_by=db.info.get("user_id")))
        else:
            state.status, state.updated_at, state.updated_by = status, now(), db.info.get("user_id")
    elif kind == "pr":
        row = db.get(Prospect, entity_id)
        if not row:
            raise LookupError("Record not found")
        if row.status != "pipeline" or status == "dismissed":
            row.status = {"new": "new", "watching": "watching", "dismissed": "dismissed", "investigating": "watching"}[status]
    else:
        raise LookupError("Unknown record type")
    track(db, f"lead_{status}", ref=key)


def parse_key(key: str) -> tuple[str, int]:
    kind, _, raw = key.partition(":")
    if kind not in ("mo", "pr", "sh") or not raw.isdigit():
        raise LookupError("Unknown record")
    return {"mo": "market_opportunity", "pr": "prospect", "sh": "shadow_hypothesis"}[kind], int(raw)


# ---------------------------------------------------------------- accounts

def linked_summary(db: Session, link: AccountLink) -> dict | None:
    if link.entity_type == "market_opportunity":
        found = _mo(db, link.entity_id)
        if not found:
            return None
        item, s = found
        return {"key": f"mo:{item.id}", "type": "public", "title": s.get("title"), "why_now": _why_public(s), "category_label": s.get("category_label"),
                "timing": s.get("timing"), "supplier": s.get("supplier"), "value": s.get("value"), "basis": "published",
                "evidence": [{"label": f"{e.get('source')} notice {e.get('record_key')}", "url": e.get("source_url"), "date": (e.get("published_at") or "")[:10]} for e in s.get("evidence") or []][:4],
                "missing": (s.get("brief") or {}).get("missing_information") or [], "link_basis": link.basis, "confirmed": link.confirmed, "name_seen": link.name_seen}
    if link.entity_type == "shadow_hypothesis":
        from app.services import shadow
        found = shadow.current(db, link.entity_id)
        if not found:
            return None
        a = found[1]
        return {"key": f"sh:{link.entity_id}", "type": "shadow", "title": f"{a['sensor_name']}: {a.get('site') or a['entity_name']}", "why_now": shadow_why(a),
                "category_label": a["state_label"], "timing": a["window"][0], "supplier": a.get("main_contractor"), "value": None, "basis": "inferred",
                "evidence": [{"label": e["label"], "url": e["source_url"], "date": e["published"], "basis": e["basis"]} for e in a["timeline"] if e["role"] in ("anchor", "supports")][:6],
                "missing": a["unknown"], "hypothesis": a["hypothesis"], "alternatives": a["alternatives"], "link_basis": link.basis, "confirmed": link.confirmed,
                "name_seen": link.name_seen}
    if link.entity_type == "prospect":
        row = db.get(Prospect, link.entity_id)
        if not row:
            return None
        v = prospect_view(row)
        return {"key": f"pr:{row.id}", "type": "private", "title": v.get("headline"), "why_now": (v["timing"]["reasons"] or [""])[0], "category_label": v["timing"]["label"],
                "light": v["timing"]["light"], "timing": (v["timing"].get("window") or {}).get("start"), "supplier": (v.get("incumbent") or {}).get("name") or None,
                "value": None, "basis": "published" if any(s.get("basis") == "stated" for s in v.get("signals") or []) else "inferred",
                "evidence": [{"label": s.get("title"), "url": s.get("source_url"), "date": s.get("date"), "basis": s.get("basis")} for s in (v.get("signals") or []) if s.get("source_url")][:6],
                "missing": v.get("unknowns") or [], "approach": v.get("approach"), "link_basis": link.basis, "confirmed": link.confirmed, "name_seen": link.name_seen}
    return None


def account_view(db: Session, account_id: int) -> dict:
    account = db.get(Account, account_id)
    if account is None:
        raise LookupError("Account not found")
    links = db.scalars(select(AccountLink).where(AccountLink.account_id == account_id).order_by(AccountLink.id)).all()
    sources = [x for x in (linked_summary(db, link) for link in links) if x]
    contacts = db.scalars(select(Contact).where(Contact.account_id == account_id).order_by(Contact.id)).all()
    sites = db.scalars(select(Site).where(Site.account_id == account_id).order_by(Site.id)).all()
    activities = db.scalars(select(Activity).where(Activity.account_id == account_id).order_by(Activity.occurred_at.desc(), Activity.id.desc())).all()
    tasks = db.scalars(select(Task).where(Task.account_id == account_id).order_by(Task.status, Task.due_on)).all()
    drafts = db.scalars(select(Draft).where(Draft.account_id == account_id).order_by(Draft.id.desc())).all()
    deals = db.scalars(select(DealRecord).where(DealRecord.account_id == account_id).order_by(DealRecord.id.desc())).all()
    known, confirm = [], []
    for s in sources:
        known.append({"text": s["why_now"], "basis": s["basis"], "source": s["key"]})
        if s.get("supplier"):
            known.append({"text": f"Supplier named on {'the published record' if s['type'] == 'public' else 'research'}: {s['supplier']}. This is a reported relationship, not necessarily today's incumbent.", "basis": s["basis"], "source": s["key"]})
    usable = [c for c in contacts if c.status != "do_not_contact"]
    if not any(c.name for c in usable):
        confirm.append("Who the decision maker is (no named person yet)")
    if not any(c.status == "verified" for c in usable):
        confirm.append("A verified contact route")
    if not any(s.get("supplier") for s in sources):
        confirm.append("Who maintains their fire and security systems today")
    if not any((s.get("value") or {}).get("type") not in (None, "unknown") for s in sources if s.get("value")):
        confirm.append("Contract value (not published)")
    if not sites:
        confirm.append("Which sites are in scope")
    for s in sources:
        for m in s.get("missing") or []:
            if m not in confirm:
                confirm.append(m)
    open_tasks = [t for t in tasks if t.status == "open"]
    next_step = (f"{open_tasks[0].title} (due {open_tasks[0].due_on:%-d %b})" if open_tasks else
                 "Prepare an introduction" if not activities else "Schedule the next follow-up")
    return {
        "id": account.id, "name": account.name, "kind": account.kind, "company_number": account.company_number, "website": account.website, "sector": account.sector,
        "region": account.region, "status": account.status, "watched": account.watched, "notes": account.notes, "created_at": account.created_at.isoformat(),
        "updated_at": account.updated_at.isoformat(),
        "identities": [{"name_seen": l.name_seen, "entity_type": l.entity_type, "entity_id": l.entity_id, "basis": l.basis, "confirmed": l.confirmed} for l in links],
        "sources": sources, "known": known[:10], "to_confirm": confirm[:10], "next_step": next_step,
        "contacts": [contact_dict(c) for c in contacts], "sites": [{"id": s.id, "name": s.name, "address": s.address, "postcode": s.postcode, "uprn": s.uprn,
                    "basis": s.basis, "source_url": s.source_url, "systems": s.systems} for s in sites],
        "activities": [activity_dict(a) for a in activities], "tasks": [task_dict(t) for t in tasks], "drafts": [draft_dict(d) for d in drafts],
        "deals": [{"id": d.id, "title": d.title, "stage": d.stage, "opportunity_id": d.opportunity_id, "value_total": d.value_total, "value_basis": d.value_basis} for d in deals],
    }


def contact_dict(c: Contact) -> dict:
    return {"id": c.id, "name": c.name, "role": c.role, "email": c.email, "phone": c.phone, "label": c.label, "basis": c.basis, "source_url": c.source_url,
            "source_quote": c.source_quote, "status": c.status, "influence": c.influence, "quality": c.quality, "route_kind": c.route_kind,
            "role_category": c.role_category, "verification_method": c.verification_method, "verified_at": c.verified_at.isoformat() if c.verified_at else None,
            "source_date": c.source_date, "flags": c.flags, "use_restriction": c.use_restriction}


def activity_dict(a: Activity) -> dict:
    return {"id": a.id, "kind": a.kind, "direction": a.direction, "summary": a.summary, "outcome": a.outcome, "requirements": a.requirements, "objections": a.objections,
            "commitments": a.commitments, "occurred_at": a.occurred_at.isoformat(), "contact_id": a.contact_id, "deal_id": a.deal_id, "draft_id": a.draft_id}


def task_dict(t: Task) -> dict:
    return {"id": t.id, "title": t.title, "due_on": t.due_on.isoformat(), "status": t.status, "account_id": t.account_id, "deal_id": t.deal_id}


def draft_dict(d: Draft) -> dict:
    return {"id": d.id, "account_id": d.account_id, "contact_id": d.contact_id, "deal_id": d.deal_id, "channel": d.channel, "subject": d.subject, "body": d.body,
            "evidence": d.evidence, "gaps": d.gaps, "status": d.status, "updated_at": d.updated_at.isoformat()}


def accounts_list(db: Session, q: str = "") -> list[dict]:
    rows = db.scalars(select(Account).order_by(Account.updated_at.desc())).all()
    today = uk_today()
    out = []
    for a in rows:
        if q and q.lower() not in a.name.lower():
            continue
        due = db.scalar(select(func.min(Task.due_on)).where(Task.account_id == a.id, Task.status == "open"))
        last = db.scalar(select(func.max(Activity.occurred_at)).where(Activity.account_id == a.id))
        out.append({"id": a.id, "name": a.name, "kind": a.kind, "region": a.region, "sector": a.sector, "status": a.status, "watched": a.watched,
                    "sources": db.scalar(select(func.count()).select_from(AccountLink).where(AccountLink.account_id == a.id)),
                    "contacts": db.scalar(select(func.count()).select_from(Contact).where(Contact.account_id == a.id)),
                    "open_deals": db.scalar(select(func.count()).select_from(DealRecord).where(DealRecord.account_id == a.id, DealRecord.stage.not_in(["won", "lost"]))),
                    "next_due": due.isoformat() if due else None, "overdue": bool(due and due < today), "last_activity": last.isoformat() if last else None})
    return out


# ---------------------------------------------------------------- today

def today_queue(db: Session) -> dict:
    today = uk_today()
    names = {a.id: a.name for a in db.scalars(select(Account))}
    queue: list[dict] = []
    for t in db.scalars(select(Task).where(Task.status == "open", Task.due_on <= today).order_by(Task.due_on)):
        queue.append({"kind": "follow_up", "priority": 0 if t.due_on < today else 1, "title": t.title, "account": names.get(t.account_id), "account_id": t.account_id,
                      "deal_id": t.deal_id, "task_id": t.id, "due_on": t.due_on.isoformat(),
                      "why": f"Follow-up you scheduled {'is overdue since' if t.due_on < today else 'is due'} {t.due_on:%-d %B}."})
    for d in db.scalars(select(Draft).where(Draft.status.in_(["draft", "approved"])).order_by(Draft.updated_at)):
        queue.append({"kind": "draft", "priority": 2, "title": d.subject or "Draft introduction", "account": names.get(d.account_id), "account_id": d.account_id, "draft_id": d.id,
                      "why": "Approved and ready to send from your own email, then log it." if d.status == "approved" else "Draft saved but not yet reviewed."})
    stale = now() - timedelta(days=14)
    for deal in db.scalars(select(DealRecord).where(DealRecord.stage.not_in(["won", "lost"]))):
        last = db.scalar(select(func.max(Activity.occurred_at)).where(Activity.deal_id == deal.id))
        last = last if last is None or last.tzinfo else last.replace(tzinfo=UTC)
        has_task = db.scalar(select(func.count()).select_from(Task).where(Task.deal_id == deal.id, Task.status == "open"))
        if not has_task and (last is None or last < stale):
            queue.append({"kind": "deal", "priority": 3, "title": deal.title, "account": names.get(deal.account_id), "account_id": deal.account_id, "deal_id": deal.id,
                          "why": f"No recorded activity {'yet' if last is None else 'for over two weeks'} and no follow-up scheduled."})
    for a in db.scalars(select(Account).where(Account.watched.is_(True))):
        seen = a.watched_seen_at if a.watched_seen_at is None or a.watched_seen_at.tzinfo else a.watched_seen_at.replace(tzinfo=UTC)
        changed = []
        for link in db.scalars(select(AccountLink).where(AccountLink.account_id == a.id)):
            if link.entity_type == "market_opportunity" and (item := db.get(MarketOpportunity, link.entity_id)):
                at = item.last_evaluated if item.last_evaluated.tzinfo else item.last_evaluated.replace(tzinfo=UTC)
                if seen is None or at > seen:
                    changed.append("procurement record")
            elif link.entity_type == "prospect" and (row := db.get(Prospect, link.entity_id)):
                at = row.updated_at if row.updated_at.tzinfo else row.updated_at.replace(tzinfo=UTC)
                if seen is None or at > seen:
                    changed.append("research")
        if changed:
            queue.append({"kind": "intelligence", "priority": 4, "title": f"New intelligence on {a.name}", "account": a.name, "account_id": a.id,
                          "why": f"Updated {', '.join(sorted(set(changed)))} since you last looked."})
    queue.sort(key=lambda x: (x["priority"], x.get("due_on") or ""))
    upcoming = [task_dict(t) | {"account": names.get(t.account_id)} for t in db.scalars(select(Task).where(Task.status == "open", Task.due_on > today, Task.due_on <= today + timedelta(days=7)).order_by(Task.due_on))]
    fresh = [x for x in discover_items(db, limit=None) if x["status"] == "new" and x["account_id"] is None and x["rank"][0] <= 1 and x["basis"] == "published"][:6]
    return {"queue": queue, "upcoming": upcoming, "new_leads": fresh, "as_of": today.isoformat()}


def preferences(db: Session) -> dict:
    rows = {p.key: p.value for p in db.scalars(select(Preference))}
    return {"territory": rows.get("territory") or [], "services": rows.get("services") or [], "company_name": rows.get("company_name") or "", "sender_name": rows.get("sender_name") or "",
            "sectors": rows.get("sectors") or [], "deal_size_min": rows.get("deal_size_min"), "deal_size_max": rows.get("deal_size_max"), "capabilities": rows.get("capabilities") or []}


def set_preferences(db: Session, values: dict) -> dict:
    from app.services.si_engage import money
    for key in ("deal_size_min", "deal_size_max"):
        if values.get(key) not in (None, ""):
            values[key] = str(money(values[key], "Deal size"))
    if values.get("deal_size_min") and values.get("deal_size_max") and float(values["deal_size_min"]) > float(values["deal_size_max"]):
        raise ValueError("The smallest deal size is larger than the largest.")
    for key in ("territory", "services", "company_name", "sender_name", "sectors", "deal_size_min", "deal_size_max", "capabilities"):
        if key in values:
            row = db.scalar(select(Preference).where(Preference.key == key))  # scoped to the workspace
            if row is None:
                db.add(Preference(key=key, value=values[key]))
            else:
                row.value = values[key]
    db.flush()
    return preferences(db)
