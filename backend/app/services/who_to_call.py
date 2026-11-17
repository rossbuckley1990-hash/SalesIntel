"""Who to call about one lead: the right role for what is happening, the best person a source names, and the best way in.

Contact databases search for the role first, give the route second, and grade every route by how it was confirmed.
SalesIntel does the same, with one difference: it never builds or guesses an address. Every route comes from one of three
places: a public source states it (found by research), the organisation's own website shows it (read by SalesIntel's site
reader on a stated day), or the team saved it. Where no route reaches the right person, the card says so and gives the
next best way in. Anyone the team marked "do not contact" is left out, wherever else they are named.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlparse

from app.services.committee import ROLES, TEMPLATES, level as contact_level
from app.services.site_reader import digits

# What is happening decides who matters first: the buying-committee template for each kind of opportunity.
PLAY_OF = {
    'new_site': 'new_site', 'site_opening': 'new_site', 'building_completed': 'new_site', 'planning_application': 'new_site',
    'refurbishment': 'new_site', 'contractor_appointed': 'new_site', 'relocation': 'new_site',
    'security_incident': 'risk', 'fire_incident': 'risk', 'incident': 'risk', 'enforcement_action': 'risk', 'insurance_or_audit_pressure': 'risk',
    'regulatory_deadline': 'risk', 'ageing_systems': 'risk', 'system_installed': 'risk', 'stated_requirement': 'risk', 'customer_complaints': 'risk',
    'acquisition': 'supplier_review', 'leadership_change': 'supplier_review', 'outsourcing_or_restructure': 'supplier_review',
    'incumbent_poor_performance': 'supplier_review', 'incumbent_distress': 'supplier_review', 'contract_change': 'supplier_review',
    'cost_consolidation': 'supplier_review', 'competitor_activity': 'supplier_review',
    'contract_end_stated': 'renewal', 'supplier_appointed': 'renewal',
    'expansion': 'expansion', 'investment': 'expansion', 'hiring_fm_security': 'expansion', 'role_vacancy': 'expansion',
}
PRIORITY = ('new_site', 'risk', 'supplier_review', 'renewal', 'expansion', 'develop')
# Who answers for the premises day to day, where the sector has such a person. A rule of thumb, shown as such.
SECTOR = [
    (re.compile(r'care|nursing|hospice|supported living', re.I), 'Registered manager of the home',
     re.compile(r'registered manager|home manager|care home manager', re.I)),
    (re.compile(r'hotel|hospitality|\binn\b|b&b|leisure|resort', re.I), 'General manager of the hotel or site',
     re.compile(r'general manager|hotel manager|\bgm\b', re.I)),
    (re.compile(r'school|academy|college|universit|education', re.I), 'Business manager, bursar or estates manager',
     re.compile(r'business manager|bursar', re.I)),
    (re.compile(r'logistic|warehous|distribution|haulage|freight|parcel', re.I), 'Site or general manager of the depot',
     re.compile(r'site (?:general )?manager|general manager|depot manager|warehouse manager|site director', re.I)),
]
OWNER = re.compile(r'\bowner\b|proprietor|sole director', re.I)
SENIOR = re.compile(r'chief exec|\bceo\b|\bchair|founder|managing director|\bmd\b|president|\bdirector\b|\bpartner\b', re.I)
DEPARTMENT = re.compile(r'facilit|estate|propert|premises|maintenance|\bfm\b|safety|\bhs\b|hse|compliance|security|fire|procure|purchas|operations|\bops\b', re.I)
GENERAL = re.compile(r'^(?:info|enquir\w*|inquir\w*|hello|contact\w*|reception|office|admin|mail|general|bookings?|reservations?|sales|customer\w*|support|help|team)$', re.I)
GRADES = {
    'direct': ('Direct to them', 'The source gives this route with the person’s name.'),
    'department': ('Their department', 'A team address, not one person’s.'),
    'main_line': ('Main line', 'Ask for the person by name.'),
    'general': ('General address', 'Ask to be put in touch.'),
    'form': ('Enquiry form', 'Ask to be put in touch.'),
    'unattributed': ('Address not tied to a person', 'The source does not say whose address it is.'),
    'none': ('No way in yet', 'Nothing usable on record.'),
    'notice': ('The notice\u2019s own route', 'Questions go through the procurement\u2019s clarification process.'),
}
RANK = {'direct': 0, 'department': 1, 'main_line': 2, 'general': 3, 'form': 4, 'unattributed': 5, 'none': 9, 'notice': 9}
ASK = 'who looks after fire safety and the maintenance of their fire and security systems'


def _norm(text: Any) -> str:
    return re.sub(r'\s+', ' ', str(text or '')).strip().casefold()


def _host(url: str) -> str:
    return (urlparse(url or '').hostname or '').removeprefix('www.')


def _long(day: str) -> str:
    try:
        d = date.fromisoformat((day or '')[:10])
    except ValueError:
        return day or ''
    return f"{d.day} {d:%B %Y}"


def play_of(record: dict) -> str:
    """The kind of opportunity, from the stated signals and timing clues: a new site first, then a risk, then a change."""
    kinds = {PLAY_OF.get(s.get('type')) for s in record.get('signals') or [] if isinstance(s, dict)}
    kinds |= {PLAY_OF.get(c.get('kind')) for c in record.get('timing_clues') or [] if isinstance(c, dict)}
    return next((p for p in PRIORITY if p in kinds), 'develop')


def roles_for(record: dict, play: str | None = None) -> tuple[str, list[tuple[str, re.Pattern]]]:
    """The roles that matter for this lead, most important first: the template's lead role, the person on site, the rest."""
    play = play or play_of(record)
    roles = [(ROLES[k][0], re.compile(ROLES[k][2], re.I)) for k in TEMPLATES.get(play, TEMPLATES['develop']) if k != 'executive']
    sector = next(((label, pattern) for test, label, pattern in SECTOR if test.search(str(record.get('sector') or ''))), None)
    if sector:
        roles.insert(1, sector)
    return play, roles


def _candidates(record: dict, contacts: list) -> list[dict]:
    """Named people: the team's saved contacts first, then people research names. Opted-out people are left out."""
    blocked = {_norm(c.name) for c in contacts if c.status == 'do_not_contact' and (c.name or '').strip()}
    out: list[dict] = []
    for c in contacts:
        if c.status != 'do_not_contact' and (c.name or '').strip():
            out.append({'name': c.name.strip(), 'role': (c.role or c.label or '').strip(), 'source_url': c.source_url or '', 'from': 'saved'})
    for p in record.get('people') or []:
        name = str((p or {}).get('name') or '').strip()
        if name and _norm(name) not in blocked and all(_norm(name) != _norm(o['name']) for o in out):
            out.append({'name': name, 'role': str(p.get('role') or '').strip(), 'source_url': p.get('source_url') or '', 'from': 'research'})
    return out


def _routes(record: dict, contacts: list, today: date) -> list[dict]:
    """Every way in on record, with how it was found. The site reader's own reading first, as it is confirmed on the page."""
    out: list[dict] = []
    site = record.get('site_read') or {}
    for r in site.get('routes') or []:
        out.append({'kind': r['kind'], 'value': r['value'], 'name': r.get('name') or '', 'quote': r.get('quote') or '', 'source_url': r.get('source_url') or '',
                    'how': f"On {_host(r.get('source_url'))}, the organisation’s own website, read by SalesIntel on {_long(r.get('read_on') or site.get('read_on'))}",
                    'confirmed': True})
    for r in record.get('contact_routes') or []:
        kind = 'phone' if r.get('kind') in ('phone', 'switchboard') else r.get('kind')
        out.append({'kind': kind, 'value': str(r.get('value') or '').strip(), 'name': '', 'quote': r.get('quote') or '', 'source_url': r.get('source_url') or '',
                    'how': f"Stated on {_host(r.get('source_url')) or 'a public source'}, found by research", 'confirmed': False})
    blocked = {_norm(c.email) for c in contacts if c.status == 'do_not_contact' and c.email} | \
              {digits(c.phone) for c in contacts if c.status == 'do_not_contact' and c.phone}
    for c in contacts:
        if c.status == 'do_not_contact':
            continue
        grade = contact_level(c, today)
        for kind, value in (('email', c.email), ('phone', c.phone)):
            if value:
                out.append({'kind': kind, 'value': value.strip(), 'name': (c.name or '').strip(), 'quote': c.source_quote or '', 'source_url': c.source_url or '',
                            'how': f"Saved by your team: {grade['label'].lower()}", 'confirmed': grade['level'] <= 3})
    kept, seen = [], set()
    for r in out:
        key = (r['kind'], _norm(r['value']) if r['kind'] != 'phone' else digits(r['value']))
        if r['value'] and key not in seen and key[1] not in blocked:
            seen.add(key)
            kept.append(r)
    return kept


def _grade(route: dict, person: dict | None) -> str:
    if person and (_norm(route['name']) == _norm(person['name']) or (len(person['name']) > 3 and _norm(person['name']) in _norm(route['quote']))):
        return 'direct'
    if route['kind'] == 'web_form':
        return 'form'
    if route['kind'] == 'email':
        local = route['value'].split('@')[0]
        if route['name']:  # another named person's own address
            return 'unattributed'
        return 'department' if DEPARTMENT.search(local.replace('.', ' ').replace('-', ' ')) else 'general' if GENERAL.match(local) else 'unattributed'
    return 'main_line'


def _fit(person: dict, roles: list[tuple[str, re.Pattern]]) -> int | None:
    """Where the person's role sits in the list of roles that matter (0 is the first), or None when it is not one of them."""
    if OWNER.search(person['role']):
        return 0  # at a business its owner runs, the owner decides
    return next((i for i, (_, pattern) in enumerate(roles) if pattern.search(person['role'])), None)


def _line(person: dict | None, route: dict | None, grade: str, roles: list[str]) -> str:
    who = (f"{person['name']}, {person['role']}" if person['role'] else person['name']) if person else ''
    mid = f"{who}," if person and person['role'] else who  # mid-sentence: "Jane Smith, Facilities Manager, at ..."
    value = route['value'] if route else ''
    if person and person['fits']:
        return {
            'direct': f"Email {mid} at {value}." if route and route['kind'] == 'email' else f"Call {mid} on {value}.",
            'department': f"Email {value} for the attention of {who}.",
            'main_line': f"Call {value} and ask for {who}.",
            'general': f"Email {value} and ask to be put in touch with {who}.",
            'unattributed': f"Email {value} and ask to be put in touch with {who}.",
            'form': f"Use their enquiry form and ask to be put in touch with {who}.",
            'none': f"{mid} is named, but no way to reach them is on record yet.",
        }[grade]
    first = f"the {roles[0][0].lower()}{roles[0][1:]}" if roles else 'the person responsible for the premises'
    senior = f" The most senior person named is {who}." if person else ''
    if grade == 'none':
        return (f"No one in an estates, facilities or safety role is named yet, and no way in is on record. {mid} is the most senior person named."
                if person else f"No named person or way in is on record yet. Look for {first}.")
    verb = 'Call' if route['kind'] == 'phone' else 'Email' if route['kind'] == 'email' else 'Use their enquiry form'
    target = f" {value}" if route['kind'] in ('phone', 'email') else ''
    return f"{verb}{target} and ask {ASK}.{senior}" if person else f"{verb}{target} and ask for {first}."


def view(record: dict, contacts: list | None = None, today: date | None = None, *, play: str | None = None) -> dict:
    """Who to call about one lead, and how: the person, the route, how the route was found, and what to say when it falls short."""
    today = today or date.today()
    contacts = list(contacts or [])
    play, roles = roles_for(record, play)
    people = _candidates(record, contacts)
    routes = _routes(record, contacts, today)
    for p in people:
        p['rank'] = _fit(p, roles)
        p['fits'] = p['rank'] is not None
    fitting = [p for p in people if p['fits']]

    def best_route(person: dict | None) -> tuple[dict | None, str]:
        graded = sorted(((r, _grade(r, person)) for r in routes), key=lambda x: (RANK[x[1]], not x[0]['confirmed']))
        return graded[0] if graded else (None, 'none')

    if fitting:  # a right person who can be reached directly beats a better-placed one who cannot
        person = min(fitting, key=lambda p: (best_route(p)[1] != 'direct', p['rank'], people.index(p)))
    else:
        person = next((p for p in people if SENIOR.search(p['role'])), None)
    route, grade = best_route(person)
    others = [{'kind': r['kind'], 'value': r['value'], 'how': r['how'], 'source_url': r['source_url'], 'grade': GRADES[_grade(r, person)][0]}
              for r in routes if r is not route][:3]
    label, detail = GRADES[grade]
    cautions = []
    if route and route['kind'] == 'email' and grade == 'direct':
        cautions.append('Their address is personal data: say where you found it and offer an easy way to opt out in the first email.')
    if route and route['kind'] == 'phone':
        cautions.append('Before a cold call, check the number against the CTPS and TPS do-not-call registers.')
    site = record.get('site_read') or None
    return {
        'play': play, 'roles': [r[0] for r in roles][:3],
        'person': {k: person[k] for k in ('name', 'role', 'source_url', 'from', 'fits')} | {'host': _host(person['source_url'])} if person else None,
        'route': {k: route[k] for k in ('kind', 'value', 'source_url', 'how', 'confirmed')} if route else None,
        'grade': grade, 'grade_label': label, 'grade_detail': detail,
        'line': _line(person, route, grade, [r[0] for r in roles]),
        'also': [{k: p[k] for k in ('name', 'role', 'source_url')} for p in people if p is not person][:3], 'more': others, 'cautions': cautions,
        'site': {k: site.get(k) for k in ('website', 'read_on', 'stopped')} | {'pages': len(site.get('pages') or []), 'found': len(site.get('routes') or [])} if site else None,
        'direct': bool(person and person['fits'] and grade == 'direct'), 'reachable': bool(person and person['fits'] and grade != 'none'),
    }


def during_procurement(call: dict) -> dict:
    """A published, live procurement: the notice's own contact point is the way in, and approaches outside it can count against a bid."""
    label, detail = GRADES['notice']
    return {**call, 'grade': 'notice', 'grade_label': label, 'grade_detail': detail, 'route': None, 'more': [], 'cautions': [], 'direct': False, 'reachable': False,
            'line': 'Use the contact point and clarification process the notice gives. During a live procurement, an approach outside it can count against a bid.'}
