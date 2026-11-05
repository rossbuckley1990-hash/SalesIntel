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
from app.services.prospect_research import view as prospect_view

LEGAL = re.compile(r"\b(limited|ltd|plc|llp|lp|cic|incorporated|inc|the)\b")
FAMILY_SERVICE = {"fire_alarm": "fire_alarm", "cctv": "cctv", "access": "access_control", "access_control": "access_control", "intruder": "intruder",
                  "emergency_lighting": "emergency_lighting", "sprinkler": "sprinkler", "suppression": "sprinkler", "extinguisher": "fire_alarm",
                  "passive_fire": "fire_alarm", "door_entry": "access_control"}
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


def track(db: Session, event: str) -> None:
    db.add(FunnelEvent(event=event[:48], day=now().date()))


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
            track(db, "account_created")
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
           "care", "homes", "logistics", "estates", "management", "partnership", "for", "national", "royal", "new"}


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


def discover_items(db: Session, *, include_private: bool = True, include_public: bool = True, limit: int | None = 200) -> list[dict]:
    today = uk_today()
    links = {(x.entity_type, x.entity_id): x for x in db.scalars(select(AccountLink))}
    items: list[dict] = []
    if include_public:
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
                "basis": "inferred" if s.get("category") == "inferred_signal" else "published", "timing": s.get("timing"), "days": days,
                "timing_label": s.get("timing_basis") or "", "nation": s.get("nation"), "tier": (s.get("priority") or {}).get("tier"),
                "services": _services_from_title(s.get("title") or ""), "supplier": s.get("supplier"), "value": s.get("value"),
                "status": {"unreviewed": "new", "investigate": "investigating", "defer": "watching", "dismiss": "dismissed"}.get(item.review_state, "new"),
                "account_id": link.account_id if link else None, "link_basis": link.basis if link else None,
                "rank": (0 if urgent and (s.get("priority") or {}).get("tier") == 1 else 1 if urgent else 2, days if days is not None and days >= 0 else 9999),
            })
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
                "value": None, "status": {"new": "new", "watching": "watching", "pipeline": "investigating", "dismissed": "dismissed"}.get(row.status, "new"),
                "account_id": link.account_id if link else None, "link_basis": link.basis if link else None,
                "people": len(v.get("people") or []), "contact_routes": len(v.get("contact_routes") or []),
                # Inferred timing never outranks a published deadline in the same bucket.
                "rank": (1 if phase == "engage_now" else 2 if phase == "prepare" else 3, 9999),
            })
    items.sort(key=lambda x: (x["status"] == "dismissed", x["rank"], x["organisation"]))
    return items if limit is None else items[:limit]


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
    items = discover_items(db, include_public=source in ("all", "public"), include_private=source in ("all", "private"), limit=None)
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
    counts = {"public": sum(1 for x in found if x["type"] == "public"), "private": sum(1 for x in found if x["type"] == "private")}
    return {"items": found[offset:offset + limit], "total": len(found), "counts": counts, "interpreted": meaning, "gaps": gaps}


def set_status(db: Session, key: str, status: str) -> None:
    kind, _, raw = key.partition(":")
    entity_id = int(raw)
    if kind == "mo":
        item = db.get(MarketOpportunity, entity_id)
        if not item:
            raise LookupError("Record not found")
        item.review_state = {"new": "unreviewed", "watching": "defer", "dismissed": "dismiss", "investigating": "investigate"}[status]
    elif kind == "pr":
        row = db.get(Prospect, entity_id)
        if not row:
            raise LookupError("Record not found")
        if row.status != "pipeline" or status == "dismissed":
            row.status = {"new": "new", "watching": "watching", "dismissed": "dismissed", "investigating": "watching"}[status]
    else:
        raise LookupError("Unknown record type")
    track(db, f"lead_{status}")


def parse_key(key: str) -> tuple[str, int]:
    kind, _, raw = key.partition(":")
    if kind not in ("mo", "pr") or not raw.isdigit():
        raise LookupError("Unknown record")
    return ("market_opportunity" if kind == "mo" else "prospect"), int(raw)


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
            "source_quote": c.source_quote, "status": c.status, "influence": c.influence}


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
    return {"territory": rows.get("territory") or [], "services": rows.get("services") or [], "company_name": rows.get("company_name") or "", "sender_name": rows.get("sender_name") or ""}


def set_preferences(db: Session, values: dict) -> dict:
    for key in ("territory", "services", "company_name", "sender_name"):
        if key in values:
            row = db.get(Preference, key)
            if row is None:
                db.add(Preference(key=key, value=values[key]))
            else:
                row.value = values[key]
    db.flush()
    return preferences(db)
