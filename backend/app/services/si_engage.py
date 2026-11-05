"""Engage and Deals: introductions, recorded interactions, follow-ups, and the path from a
qualified opportunity to a won contract and its handover.

SalesIntel never sends anything. A draft becomes an interaction only when the salesperson
confirms they sent it themselves. Unknown facts stay unknown: introductions use gaps, not
guesses, and quotes total only the quantities and rates a person has entered.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Opportunity
from app.models.crm import Account, AccountLink, Activity, Contact, DealRecord, Draft, Task
from app.services.si_core import account_view, link_source, linked_summary, now, parse_key, preferences, track

SERVICE_LABEL = {"fire_alarm": "fire alarm and detection", "cctv": "CCTV", "access_control": "access control", "intruder": "intruder alarm",
                 "emergency_lighting": "emergency lighting", "sprinkler": "sprinkler and suppression", "monitoring": "alarm monitoring"}
STAGES = ["qualify", "engage", "survey", "proposal", "bid_review", "negotiation", "approval", "won", "lost"]
LEGACY_STAGE = {"qualify": "Qualification", "engage": "Qualification", "survey": "Survey", "proposal": "Pricing", "bid_review": "Final review",
                "negotiation": "Negotiation", "approval": "Final review", "won": "Won", "lost": "Lost"}
WORK_TYPES = {"ppm": "Planned preventative maintenance", "reactive": "Reactive maintenance", "remedial": "Remedial works", "installation": "Installation project",
              "multi_site": "Multi-site maintenance agreement", "monitoring": "Monitoring"}
# What a quotation needs to know, by discipline. Each line is (field, question, unit for pricing).
SCOPE_FIELDS: dict[str, list[tuple[str, str, str]]] = {
    "fire_alarm": [("panels", "Fire alarm control panels", "panel"), ("devices", "Detectors, call points and sounders", "device"),
                   ("visits_per_year", "Service visits per year (BS 5839-1 expects at least two)", "visit"), ("panel_make", "Panel make and model", "")],
    "cctv": [("cameras", "Cameras", "camera"), ("recorders", "Recorders (NVR/DVR)", "recorder"), ("visits_per_year", "Service visits per year", "visit")],
    "access_control": [("doors", "Controlled doors", "door"), ("system", "System make and software", ""), ("visits_per_year", "Service visits per year", "visit")],
    "intruder": [("panels", "Intruder panels", "panel"), ("detectors", "Detectors", "detector"), ("signalling", "Signalling path (e.g. dual path)", "")],
    "emergency_lighting": [("fittings", "Emergency light fittings", "fitting"), ("visits_per_year", "Annual duration tests per year", "visit")],
    "sprinkler": [("installations", "Installations / valve sets", "installation"), ("pumps", "Pumps", "pump")],
    "monitoring": [("connections", "Monitored connections", "connection"), ("arc", "Alarm receiving centre requirement", "")],
}
COMMON_FIELDS = [("sites", "Number of sites in scope", "site"), ("access_hours", "Access hours and restrictions", ""), ("response_time", "Required reactive response time", ""),
                 ("term_years", "Contract term (years)", "")]
BASES = {"surveyed", "customer_stated", "estimate"}


# ---------------------------------------------------------------- contacts and sites

def add_contact(db: Session, account_id: int, data: dict) -> Contact:
    if not db.get(Account, account_id):
        raise LookupError("Account not found")
    if not (data.get("name") or data.get("role") or data.get("email") or data.get("phone")):
        raise ValueError("Give at least a name, role, email or phone.")
    moment = now()
    contact = Contact(account_id=account_id, name=(data.get("name") or None), role=data.get("role") or "", email=data.get("email") or None, phone=data.get("phone") or None,
                      label=data.get("label") or "", basis="user_entered", source_url=data.get("source_url") or None, source_quote=None,
                      status="verified" if data.get("verified") else "unverified", influence=data.get("influence") or "", created_at=moment, updated_at=moment)
    db.add(contact)
    db.flush()
    return contact


def update_contact(db: Session, contact_id: int, status: str) -> Contact:
    contact = db.get(Contact, contact_id)
    if not contact:
        raise LookupError("Contact not found")
    contact.status, contact.updated_at = status, now()
    return contact


# ---------------------------------------------------------------- introductions

def prepare_introduction(db: Session, account_id: int, *, contact_id: int | None = None, source_key: str | None = None) -> dict:
    """An introduction built only from recorded evidence, with gaps left visible as placeholders."""
    account = db.get(Account, account_id)
    if account is None:
        raise LookupError("Account not found")
    contact = db.get(Contact, contact_id) if contact_id else None
    if contact and contact.account_id != account_id:
        raise LookupError("Contact not found on this account")
    if contact and contact.status == "do_not_contact":
        raise PermissionError("This contact has asked not to be contacted.")
    links = db.scalars(select(AccountLink).where(AccountLink.account_id == account_id).order_by(AccountLink.id)).all()
    sources = [s for s in (linked_summary(db, l) for l in links) if s]
    source = next((s for s in sources if s["key"] == source_key), sources[0] if sources else None)
    prefs = preferences(db)
    company, sender = prefs["company_name"] or "[your company]", prefs["sender_name"] or "[your name]"
    gaps: list[str] = []
    if contact and contact.name:
        greeting = f"Dear {contact.name},"
    elif contact and contact.role:
        greeting = f"Dear {contact.role},"
        gaps.append("No named person: addressed to a role.")
    else:
        greeting = "Dear [name],"
        gaps.append("No contact selected: add the recipient's name.")
    if not prefs["company_name"]:
        gaps.append("Add your name and company under Your details.")
    services = []
    evidence = []
    if source is None:
        opening = f"I'm getting in touch about fire and security arrangements at {account.name}."
        gaps.append("No sourced reason recorded: add one before sending.")
    elif source["type"] == "public":
        evidence = [e for e in source.get("evidence") or [] if e.get("url")]
        title = source.get("title") or "fire and security"
        if source.get("category_label") and "Live" in str(source.get("category_label")):
            opening = f"I saw that {account.name} has published a tender for {title}."
        elif source.get("timing"):
            when = date.fromisoformat(source["timing"][:10]).strftime("%B %Y")
            opening = f"I noticed from the published notice that {account.name}'s contract for {title} runs to {when}."
        else:
            opening = f"I noticed {account.name}'s published notice for {title}."
        from app.services.si_core import _services_from_title
        services = _services_from_title(title)
    else:
        stated = [e for e in source.get("evidence") or [] if e.get("basis") == "stated" and e.get("url")]
        evidence = stated[:3]
        opening = f"I read that {stated[0]['label'][0].lower() + stated[0]['label'][1:]}." if stated else f"I've been following {account.name}'s plans."
        if not stated:
            gaps.append("Research found no stated signal: check the reason before sending.")
        services = []
    if not source or not source.get("supplier"):
        gaps.append("Current provider unknown: ask rather than assume.")
    offer = (f"We look after {', '.join(SERVICE_LABEL.get(s, s) for s in services)} for organisations with similar estates"
             if services else "We look after fire and security systems for organisations with similar estates")
    body = "\n\n".join([
        greeting, opening,
        f"{offer}, and it is often useful to talk before arrangements are reviewed rather than after. "
        "Would a short call in the next couple of weeks help, to understand how your current arrangements are working and what you would want from the next ones?",
        f"Kind regards,\n{sender}\n{company}",
    ])
    subject = f"{account.name}: fire and security arrangements"
    return {"subject": subject[:255], "body": body, "evidence": evidence, "gaps": gaps, "source_key": source["key"] if source else None, "contact_id": contact.id if contact else None}


def save_draft(db: Session, account_id: int, data: dict, draft_id: int | None = None) -> Draft:
    moment = now()
    if data.get("contact_id"):
        contact = db.get(Contact, data["contact_id"])
        if not contact or contact.account_id != account_id:
            raise LookupError("Contact not found on this account")
        if contact.status == "do_not_contact":
            raise PermissionError("This contact has asked not to be contacted.")
    if draft_id:
        draft = db.get(Draft, draft_id)
        if not draft or draft.account_id != account_id:
            raise LookupError("Draft not found")
        if draft.status == "logged":
            raise ValueError("This message was already logged as sent.")
        for key in ("subject", "body", "contact_id"):
            if key in data:
                setattr(draft, key, data[key])
        draft.status, draft.updated_at = "draft", moment
    else:
        draft = Draft(account_id=account_id, deal_id=data.get("deal_id"), contact_id=data.get("contact_id"), channel=data.get("channel") or "email",
                      subject=data.get("subject") or "", body=data["body"], evidence=data.get("evidence") or [], gaps=data.get("gaps") or [],
                      status="draft", created_at=moment, updated_at=moment)
        db.add(draft)
        track(db, "draft_saved")
    db.flush()
    return draft


def approve_draft(db: Session, draft_id: int) -> Draft:
    draft = db.get(Draft, draft_id)
    if not draft:
        raise LookupError("Draft not found")
    if "[name]" in draft.body or "[your" in draft.body:
        raise ValueError("Fill in the placeholders before approving.")
    draft.status, draft.approved_at, draft.updated_at = "approved", now(), now()
    return draft


def log_draft_sent(db: Session, draft_id: int, *, sent_externally: bool, follow_up: dict | None = None) -> tuple[Activity, Task | None]:
    """Record that the salesperson sent an approved draft from their own email."""
    draft = db.get(Draft, draft_id)
    if not draft:
        raise LookupError("Draft not found")
    if not sent_externally:
        raise ValueError("Confirm you sent it yourself. SalesIntel does not send email.")
    if draft.status != "approved":
        raise ValueError("Approve the draft before logging it as sent.")
    draft.status, draft.updated_at = "logged", now()
    return log_activity(db, draft.account_id, {"kind": "email", "direction": "outbound", "summary": f"Sent: {draft.subject}", "contact_id": draft.contact_id,
                                               "deal_id": draft.deal_id, "draft_id": draft.id}, follow_up)


# ---------------------------------------------------------------- activities and tasks

def log_activity(db: Session, account_id: int, data: dict, follow_up: dict | None = None) -> tuple[Activity, Task | None]:
    account = db.get(Account, account_id)
    if account is None:
        raise LookupError("Account not found")
    if data.get("kind") not in {"call", "email", "meeting", "site_visit", "note"}:
        raise ValueError("Choose call, email, meeting, site visit or note.")
    if not str(data.get("summary") or "").strip():
        raise ValueError("Say what happened.")
    if data.get("deal_id"):
        deal = db.get(DealRecord, data["deal_id"])
        if not deal or deal.account_id != account_id:
            raise LookupError("Deal not found on this account")
    if data.get("contact_id"):
        contact = db.get(Contact, data["contact_id"])
        if not contact or contact.account_id != account_id:
            raise LookupError("Contact not found on this account")
    moment = now()
    occurred = data.get("occurred_at")
    activity = Activity(account_id=account_id, deal_id=data.get("deal_id"), contact_id=data.get("contact_id"), draft_id=data.get("draft_id"), kind=data["kind"],
                        direction=data.get("direction") or "outbound", summary=data["summary"].strip(), outcome=data.get("outcome") or "",
                        requirements=data.get("requirements") or "", objections=data.get("objections") or "", commitments=data.get("commitments") or "",
                        occurred_at=datetime.fromisoformat(occurred) if occurred else moment, created_at=moment)
    db.add(activity)
    db.flush()
    track(db, "activity_logged")
    if data.get("outcome") == "meeting_booked":
        track(db, "meeting_booked")
    task = None
    if follow_up and follow_up.get("due_on"):
        task = add_task(db, account_id, {"title": follow_up.get("title") or f"Follow up with {account.name}", "due_on": follow_up["due_on"],
                                         "deal_id": data.get("deal_id"), "activity_id": activity.id})
    # Completing the step that prompted this interaction.
    for done in follow_up.get("complete_task_ids", []) if follow_up else []:
        complete_task(db, done)
    account.updated_at = moment
    if account.status == "prospect":
        account.status = "engaged"
    return activity, task


def add_task(db: Session, account_id: int, data: dict) -> Task:
    if not db.get(Account, account_id):
        raise LookupError("Account not found")
    due = data["due_on"] if isinstance(data["due_on"], date) else date.fromisoformat(str(data["due_on"]))
    task = Task(account_id=account_id, deal_id=data.get("deal_id"), activity_id=data.get("activity_id"), title=str(data["title"])[:255], due_on=due,
                status="open", created_at=now())
    db.add(task)
    db.flush()
    track(db, "follow_up_scheduled")
    return task


def complete_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise LookupError("Task not found")
    task.status, task.done_at = "done", now()
    return task


def reschedule_task(db: Session, task_id: int, due_on: str) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise LookupError("Task not found")
    task.due_on = date.fromisoformat(due_on)
    return task


# ---------------------------------------------------------------- deals

def create_deal(db: Session, account_id: int, data: dict) -> DealRecord:
    """Convert a qualified opportunity into a deal, freezing the evidence it came from."""
    account = db.get(Account, account_id)
    if account is None:
        raise LookupError("Account not found")
    qualification = data.get("qualification") or {}
    if not qualification.get("requirement"):
        raise ValueError("Record the customer's requirement before creating a deal.")
    source_key = data.get("source_key")
    origin: dict[str, Any] = {}
    opportunity_id = None
    value_total, value_annual, value_basis = None, None, "unknown"
    if source_key:
        entity_type, entity_id = parse_key(source_key)
        linked, _, _ = link_source(db, entity_type, entity_id)
        if linked.id != account_id:
            raise ValueError("That record belongs to a different account.")
        link = db.scalar(select(AccountLink).where(AccountLink.entity_type == entity_type, AccountLink.entity_id == entity_id))
        origin = linked_summary(db, link) or {}
        origin["captured_at"] = now().isoformat()
        if entity_type == "market_opportunity":
            from app.routers.market_opportunities import promote
            opportunity_id = promote(entity_id, db)["opportunity_id"]
            value = origin.get("value") or {}
            if value.get("type") == "published_total" and value.get("published_total"):
                value_total, value_basis = float(value["published_total"]), "published"
            elif value.get("type") == "estimated_annualised" and value.get("estimated_annualised"):
                value_annual, value_basis = float(value["estimated_annualised"]), "published_derived"
        else:
            from app.routers.prospects import promote
            opportunity_id = promote(entity_id, db)["opportunity_id"]
    existing = db.scalar(select(DealRecord).where(DealRecord.opportunity_id == opportunity_id)) if opportunity_id else None
    if existing:
        return existing
    title = (data.get("title") or origin.get("title") or f"{account.name} fire and security").strip()[:255]
    if opportunity_id is None:
        opp = Opportunity(name=title, buyer_name=account.name[:255], sector=(account.sector or "Unknown")[:120], region=(account.region or "United Kingdom")[:120],
                          source_type="SalesIntel", stage=LEGACY_STAGE["qualify"], owner="Unassigned", recommended_action=qualification.get("requirement", "")[:500])
        db.add(opp)
        db.flush()
        opportunity_id = opp.id
    if data.get("value_total") is not None:
        value_total, value_basis = float(data["value_total"]), "user_estimate"
    moment = now()
    deal = DealRecord(opportunity_id=opportunity_id, account_id=account_id, title=title, stage="qualify", origin_type=(parse_key(source_key)[0] if source_key else None),
                      origin_id=(parse_key(source_key)[1] if source_key else None), origin=origin, services=[s for s in data.get("services") or [] if s in SERVICE_LABEL],
                      work_type=data.get("work_type") if data.get("work_type") in WORK_TYPES else "", qualification=qualification,
                      value_annual=value_annual, value_total=value_total, value_basis=value_basis, next_step=data.get("next_step") or "", scope={}, quote={},
                      handover={}, outcome_reason="", created_at=moment, updated_at=moment)
    db.add(deal)
    db.flush()
    for act in db.scalars(select(Activity).where(Activity.account_id == account_id, Activity.deal_id.is_(None))):
        act.deal_id = deal.id  # the conversation that qualified it belongs to the deal
    account.status, account.updated_at = "opportunity", moment
    _sync_legacy(db, deal)
    track(db, "deal_created")
    return deal


def _sync_legacy(db: Session, deal: DealRecord) -> None:
    opp = db.get(Opportunity, deal.opportunity_id)
    if opp is not None:
        opp.stage = LEGACY_STAGE[deal.stage]
        if deal.value_total is not None and deal.value_basis in ("published", "user_estimate"):
            opp.estimated_total_contract_value = deal.value_total
        if deal.value_annual is not None:
            opp.estimated_annual_revenue = deal.value_annual


def scope_requirements(deal: DealRecord) -> list[dict]:
    fields = [("common", f, q, u) for f, q, u in COMMON_FIELDS]
    for service in deal.services:
        fields += [(service, f, q, u) for f, q, u in SCOPE_FIELDS.get(service, [])]
    out = []
    for service, field, question, unit in fields:
        entry = (deal.scope.get(service) or {}).get(field)
        out.append({"service": service, "field": field, "question": question, "unit": unit,
                    "value": entry.get("value") if entry else None, "basis": entry.get("basis") if entry else None})
    return out


def update_scope(db: Session, deal_id: int, entries: list[dict]) -> DealRecord:
    deal = db.get(DealRecord, deal_id)
    if not deal:
        raise LookupError("Deal not found")
    valid = {(s, f) for s, f, _, _ in [("common", f, q, u) for f, q, u in COMMON_FIELDS] + [(s, f, q, u) for s in deal.services for f, q, u in SCOPE_FIELDS.get(s, [])]}
    scope = {k: dict(v) for k, v in (deal.scope or {}).items()}
    for e in entries:
        key = (e.get("service"), e.get("field"))
        if key not in valid:
            raise ValueError(f"Unknown scope item {key[1]} for {key[0]}.")
        if e.get("value") in (None, ""):
            scope.get(key[0], {}).pop(key[1], None)
            continue
        if e.get("basis") not in BASES:
            raise ValueError("Say whether each value was surveyed, stated by the customer, or estimated.")
        scope.setdefault(key[0], {})[key[1]] = {"value": e["value"], "basis": e["basis"]}
    deal.scope, deal.updated_at = scope, now()
    return deal


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_quote(db: Session, deal_id: int, rates: dict | None = None) -> DealRecord:
    """A quotation draft: lines from the scope, priced only where a person gave a quantity and a rate."""
    deal = db.get(DealRecord, deal_id)
    if not deal:
        raise LookupError("Deal not found")
    rates = rates if rates is not None else (deal.quote or {}).get("rates", {})
    lines, missing = [], []
    for item in scope_requirements(deal):
        if item["service"] == "common":
            continue
        label = SERVICE_LABEL.get(item["service"], item["service"])
        if not item["unit"]:  # descriptive facts such as the panel make are needed, not priced
            if item["value"] is None:
                missing.append(f"{label}: {item['question']}")
            continue
        quantity = _number(item["value"])
        rate = _number(rates.get(f"{item['service']}.{item['field']}"))
        if quantity is None:
            missing.append(f"{label}: {item['question']}")
        if rate is None:
            missing.append(f"Rate per {item['unit']} for {label}")
        lines.append({"key": f"{item['service']}.{item['field']}", "description": f"{label.capitalize()}: {item['question'].lower()}",
                      "quantity": quantity, "quantity_basis": item["basis"], "unit": item["unit"], "rate": rate,
                      "total": round(quantity * rate, 2) if quantity is not None and rate is not None else None,
                      "warning": "Estimated quantity: confirm by survey." if item["basis"] == "estimate" else ""})
    if not deal.services:
        missing.append("Choose the services in scope")
    priced = [l["total"] for l in lines if l["total"] is not None]
    deal.quote = {"status": "draft", "lines": lines, "rates": rates, "missing": missing, "subtotal": round(sum(priced), 2) if priced and len(priced) == len(lines) else None,
                  "partial_total": round(sum(priced), 2) if priced else None, "built_at": now().isoformat(), "approved_by": None,
                  "terms_note": "Draft for internal review. Not an offer. Quantities and rates must be confirmed before issue."}
    deal.updated_at = now()
    track(db, "quote_drafted")
    return deal


def approve_quote(db: Session, deal_id: int, reviewer: str) -> DealRecord:
    deal = db.get(DealRecord, deal_id)
    if not deal or not deal.quote:
        raise LookupError("Build a quotation draft first.")
    if deal.quote.get("missing"):
        raise ValueError("Resolve the missing inputs before approval.")
    if any(l.get("quantity_basis") == "estimate" for l in deal.quote.get("lines", [])):
        raise ValueError("Confirm estimated quantities by survey or customer before approval.")
    if not reviewer.strip():
        raise ValueError("Name the person approving.")
    deal.quote = {**deal.quote, "status": "approved", "approved_by": reviewer.strip(), "approved_at": now().isoformat()}
    deal.updated_at = now()
    return deal


def move_stage(db: Session, deal_id: int, stage: str, reason: str = "") -> DealRecord:
    deal = db.get(DealRecord, deal_id)
    if not deal:
        raise LookupError("Deal not found")
    if stage not in STAGES:
        raise ValueError("Unknown stage.")
    if stage in ("won", "lost") and not reason.strip():
        raise ValueError("Record why it was won or lost.")
    if stage == "approval" and not deal.quote:
        raise ValueError("Build a quotation draft before commercial approval.")
    if stage == "won" and (deal.quote or {}).get("status") != "approved":
        raise ValueError("Approve the quotation before marking the deal won.")
    deal.stage, deal.updated_at = stage, now()
    if stage in ("won", "lost"):
        deal.outcome_reason = reason.strip()
        account = db.get(Account, deal.account_id)
        if account and stage == "won":
            account.status = "customer"
        if stage == "won":
            deal.handover = build_handover(db, deal)
    _sync_legacy(db, deal)
    track(db, f"deal_{stage}")
    return deal


def build_handover(db: Session, deal: DealRecord) -> dict:
    """Everything operations need, captured at the moment of winning."""
    view = account_view(db, deal.account_id)
    activities = [a for a in view["activities"] if a["deal_id"] == deal.id]
    return {"captured_at": now().isoformat(), "account": {k: view[k] for k in ("name", "company_number", "website", "region")},
            "contacts": [c for c in view["contacts"] if c["status"] != "do_not_contact"], "sites": view["sites"], "services": deal.services,
            "work_type": WORK_TYPES.get(deal.work_type, ""), "scope": scope_requirements(deal), "quote": deal.quote,
            "requirements": [a["requirements"] for a in activities if a["requirements"]], "commitments": [a["commitments"] for a in activities if a["commitments"]],
            "open_tasks": [t for t in view["tasks"] if t["status"] == "open"], "origin": deal.origin,
            "still_unconfirmed": view["to_confirm"]}


def deal_view(db: Session, deal_id: int) -> dict:
    deal = db.get(DealRecord, deal_id)
    if not deal:
        raise LookupError("Deal not found")
    account = db.get(Account, deal.account_id)
    activities = db.scalars(select(Activity).where(Activity.deal_id == deal.id).order_by(Activity.occurred_at.desc())).all()
    tasks = db.scalars(select(Task).where(Task.deal_id == deal.id).order_by(Task.due_on)).all()
    from app.services.si_core import activity_dict, task_dict
    return {"id": deal.id, "title": deal.title, "stage": deal.stage, "stages": STAGES, "account_id": deal.account_id, "account": account.name if account else "",
            "opportunity_id": deal.opportunity_id, "origin_type": deal.origin_type, "origin": deal.origin, "services": deal.services, "work_type": deal.work_type,
            "work_types": WORK_TYPES, "qualification": deal.qualification, "value_annual": deal.value_annual, "value_total": deal.value_total, "value_basis": deal.value_basis,
            "next_step": deal.next_step, "scope": scope_requirements(deal), "quote": deal.quote, "handover": deal.handover, "outcome_reason": deal.outcome_reason,
            "activities": [activity_dict(a) for a in activities], "tasks": [task_dict(t) for t in tasks], "service_labels": SERVICE_LABEL,
            "created_at": deal.created_at.isoformat(), "updated_at": deal.updated_at.isoformat()}


def deals_board(db: Session) -> dict:
    names = {a.id: a.name for a in db.scalars(select(Account))}
    rows = db.scalars(select(DealRecord).order_by(DealRecord.updated_at.desc())).all()
    items = [{"id": d.id, "title": d.title, "account": names.get(d.account_id), "account_id": d.account_id, "stage": d.stage, "services": d.services,
              "value_total": d.value_total, "value_annual": d.value_annual, "value_basis": d.value_basis, "next_step": d.next_step,
              "quote_status": (d.quote or {}).get("status"), "updated_at": d.updated_at.isoformat()} for d in rows]
    return {"stages": STAGES, "items": items}
