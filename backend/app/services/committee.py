"""Who to speak to: contact confidence and the buying committee for an opportunity.

Contact confidence is stated, never implied. A routed address that was only inferred from a naming pattern is not
verified; a deliverability check would not prove a person holds a role; a role without a named person is shown as
exactly that. The committee follows the opportunity (a new site, a renewal, a tender), not one universal template.
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crm import Contact

LEVELS = {
    1: ("recently_reverified", "Recently re-verified", "Checked by your team in the last 90 days"),
    2: ("provider_verified", "Provider-verified", "Confirmed by a licensed data provider"),
    3: ("public_source", "Publicly sourced", "Published by the organisation or an official notice, with the quote kept"),
    4: ("unverified", "Unverified possible contact", "Not confirmed by any source yet"),
    5: ("role_only", "Role known, no named person", "A departmental route or switchboard, not a person"),
    6: ("none", "No verified contact route", "Nothing usable on record"),
}
FRESH_DAYS, STALE_DAYS = 90, 365


def _age(c: Contact, today: date) -> int | None:
    stamps = [c.verified_at.date() if c.verified_at else None]
    try:
        stamps.append(date.fromisoformat(c.source_date) if c.source_date else None)
    except ValueError:
        stamps.append(None)
    known = [s for s in stamps if s]
    return (today - max(known)).days if known else None


def level(c: Contact, today: date | None = None) -> dict:
    """The contact-confidence level of one saved contact, with its freshness and any restriction."""
    today = today or datetime.now(UTC).date()
    if c.status == 'do_not_contact':
        return {'level': 6, 'key': 'suppressed', 'label': 'Do not contact', 'detail': 'Opted out: never used for outreach', 'freshness': 'n/a', 'age_days': None, 'usable': False}
    age = _age(c, today)
    named = bool((c.name or '').strip())
    reverified = c.status == 'verified' and c.verified_at is not None and age is not None and age <= FRESH_DAYS
    if not named and (c.email or c.phone or c.route_kind not in ('', 'none')):
        n = 5
    elif reverified:
        n = 1
    elif c.quality == 'provider_verified':
        n = 2
    elif c.quality == 'public_source' or (c.basis == 'published' and c.source_url and c.source_quote):
        n = 3
    elif c.email or c.phone or named:
        n = 4
    else:
        n = 6
    key, label, detail = LEVELS[n]
    stale = 'stale' in (c.flags or []) or 'may_have_moved' in (c.flags or []) or (age is not None and age > STALE_DAYS)
    freshness = 'unknown' if age is None else 'stale' if stale else 'fresh' if age <= FRESH_DAYS else 'ageing'
    return {'level': n, 'key': key, 'label': label, 'detail': detail, 'freshness': freshness, 'age_days': age,
            'usable': n <= 5 and not stale, 'restriction': c.use_restriction or ''}


# Committee templates, by play. Each role: key, label, part, words that identify it in a contact's role.
PARTS = {'decision': 'Decision-maker', 'operational': 'Day-to-day owner', 'technical': 'Technical evaluator', 'budget': 'Budget holder',
         'procurement': 'Procurement', 'route': 'Route to market'}
ROLES = {
    'estates': ('Estates or property director', 'decision', r'estate|property|real estate'),
    'facilities': ('Head of facilities or facilities manager', 'operational', r'facilit|fm\b|premises|site manager|building'),
    'fire_safety': ('Fire safety or health and safety lead', 'technical', r'fire|health and safety|h&s|safety|compliance|security'),
    'procurement': ('Procurement or category manager', 'procurement', r'procure|purchas|category|commercial|buyer|tender'),
    'contract': ('Contract manager for the current service', 'operational', r'contract'),
    'finance': ('Finance director or budget holder', 'budget', r'financ|cfo|budget'),
    'contractor': ("Main contractor's package or supply-chain manager", 'route', r'supply chain|package|project manager|contractor'),
    'executive': ('Managing or operations director', 'decision', r'managing|operations director|chief exec|ceo|coo|director'),
}
TEMPLATES = {
    'new_site': ['estates', 'facilities', 'fire_safety', 'contractor', 'procurement'],
    'renewal': ['procurement', 'contract', 'facilities', 'finance'],
    'public_tender': ['procurement', 'contract', 'fire_safety'],
    'expansion': ['facilities', 'estates', 'procurement'],
    'supplier_review': ['facilities', 'contract', 'procurement', 'executive'],
    'develop': ['facilities', 'estates', 'procurement', 'finance'],
}


def committee(db: Session, account_id: int, play: str) -> dict:
    """The roles that matter for this kind of opportunity, who on record fills each, and the gaps."""
    contacts = db.scalars(select(Contact).where(Contact.account_id == account_id)).all()
    today = datetime.now(UTC).date()
    graded = [(c, level(c, today)) for c in contacts]
    template = TEMPLATES.get(play, TEMPLATES['new_site'])
    # Each person fills one role: the first in the template their own title matches, else their recorded category.
    # One Director of Estates is not also the procurement contact, so coverage is never overstated.
    CATEGORY = {'procurement': 'procurement', 'technical': 'fire_safety', 'security': 'fire_safety', 'executive': 'executive', 'commercial': 'procurement'}
    seat: dict[int, str] = {}
    for c, _ in graded:
        title = f"{c.role} {c.label}".lower()
        match = next((k for k in template if re.search(ROLES[k][2], title)), None) or next((k for k in template if CATEGORY.get(c.role_category) == k), None)
        if match:
            seat[c.id] = match
    used: set[int] = set()
    roles = []
    for key in template:
        label, part, pattern = ROLES[key]
        mine = [(c, lv) for c, lv in graded if seat.get(c.id) == key]
        mine.sort(key=lambda x: (x[1]['level'], x[1]['freshness'] == 'stale'))
        used.update(c.id for c, _ in mine)
        people = [{'id': c.id, 'name': c.name, 'role': c.role or c.label, 'email': c.email, 'phone': c.phone, 'source_url': c.source_url,
                   **lv} for c, lv in mine[:3]]
        named = [p for p in people if p['name'] and p['level'] <= 3 and p['freshness'] != 'stale']
        status = 'covered' if named else 'route_only' if any(p['usable'] for p in people) else 'gap'
        roles.append({'key': key, 'label': label, 'part': PARTS[part], 'status': status, 'people': people,
                      'gap': None if named else {'gap': 'find_role', 'subject': label}})
    others = [{'id': c.id, 'name': c.name, 'role': c.role or c.label, **lv} for c, lv in graded if c.id not in used]
    best = min((lv['level'] for _, lv in graded if lv['usable']), default=6)
    return {'play': play, 'roles': roles, 'others': others, 'best_level': best, 'best_label': LEVELS[best][1],
            'levels': [{'level': n, 'label': v[1], 'detail': v[2]} for n, v in LEVELS.items()]}
