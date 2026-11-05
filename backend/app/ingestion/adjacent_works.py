"""Adjacent works: building projects that will need fire and security systems nobody has advertised yet.

Source: Contracts Finder (Crown copyright, Open Government Licence v3.0), through the existing
search connector and its request budget. A new building, extension, refurbishment or fit-out is
an indirect signal: the systems are usually bought later, as a specialist package by the main
contractor or as maintenance once the building is occupied. Neither is certain, and the
classifier is deliberately conservative: notices that already name fire or security work are
left to the procurement collectors, and design-only, infrastructure-only or non-works notices
are dropped.

Observations are append-only. A changed notice becomes a new observation; nothing is rewritten.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import hashlib
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion import market_contracts_search as cf
from app.intelligence.renewal_radar import _buyer_key
from app.intelligence.signal_inference import observation
from app.models.market_inference import MarketObservation

SOURCE = 'Contracts Finder'
LICENCE = 'Contains public sector information licensed under the Open Government Licence v3.0.'
KEYWORDS = ['"new build"', '"construction of"', '"extension to"', 'refurbishment', '"fit out"', 'redevelopment']
MIN_VALUE = 250_000

WORKS = [('new_build', re.compile(r'\bnew[\s-]?build\b|\bconstruction of\b|\bnew (?:primary |secondary |special )?(?:school|hospital|building|centre|campus|facility|unit|block|depot|station|wing|homes?|library|hub)\b', re.I)),
         ('extension', re.compile(r'\bextension (?:to|of)\b|\bnew (?:wing|extension)\b', re.I)),
         ('refurbishment', re.compile(r'\brefurbish\w*|\bremodel\w*|\bredevelopment\b|\bconversion of\b|\bregeneration\b', re.I)),
         ('fit_out', re.compile(r'\bfit[\s-]?out\b|\bcat(?:egory)?[\s-]?[ab]\b', re.I))]
DIRECT = re.compile(r'\bfire\b|\bcctv\b|\bsecurity\b|\baccess control\b|\bintruder\b|\bsprinkler', re.I)  # already a fire/security procurement
NOT_WORKS = re.compile(r'\b(?:sales agent|consultan\w*|surveyor|surveys?|quantity survey\w*|legal|valuation|insurance|feasibility|design team|design (?:and|&) project management|'
                       r'project manage\w*|pm and design|architect\w*|riba [0-4]\b|cleaning|catering|grounds maintenance|roads?|sewers?|drainage|groundworks|'
                       r'landscap\w*|demolition only|highway\w*|pavement|footpath|footbridge|bridge|dam|reservoir|canal|flood|coastal|railway|rail|cycle\w*|'
                       r'play ?parks?|playground|play equipment|recreation ground|bus services?|kitchen|bathrooms?|voids?|responsive repairs|repairs (?:and|&) maintenance|'
                       r'painting|sealants?|lighting, sound|rigging|geotechnical|manager|change management|support services|maintenance services|'
                       r'software|licen[cs]e|recruitment|training|information notice|grant structure|'
                       r'3g|pitch(?:es)?|athletics|track|toilets?|roof\w*|external (?:refurbish\w*|maintenance|works|repairs)|windows?|heating|boilers?|'
                       r'demolition|ball courts?|games area|muga|provision of [\w\s]{0,40}services?)\b', re.I)
BUILDING_NOUN = re.compile(r'\b(?:school|academy|college|university|campus|nursery|hospital|clinic|health (?:centre|hub)|surgery|ward|unit|homes?|flats|apartments|'
                           r'housing|residences?|halls? of residence|office|depot|warehouse|library|museum|leisure (?:centre|facility)|community (?:centre|hub)|hub|'
                           r'centre|building|block|town hall|police station|fire station|prison|hmp|court|care home|extra care|barracks|market|food court)\b', re.I)
OVERSEAS = re.compile(r'\b(?:embassy|high commission|residence of the|hma\b|consulate)\b|\bforeign,? commonwealth', re.I)
BUILDING = [('healthcare', re.compile(r'\bhospital|\bhealth|\bclinic|\bmental health|\bsurgery|\bnhs\b|\bmedical', re.I)),
            ('education', re.compile(r'\bschool|\bcollege|\bacademy|\buniversity|\bcampus|\bnursery', re.I)),
            ('residential', re.compile(r'\bhousing|\bhomes?\b|\bflats?\b|\bapartments?|\bextra care|\bsupported living|\bresidential|\bdwellings?', re.I)),
            ('commercial', re.compile(r'\boffice|\bdepot|\bwarehouse|\bindustrial|\blogistics|\bstudio', re.I)),
            ('public_venue', re.compile(r'\blibrary|\bleisure|\bmuseum|\bmarket|\btheatre|\bcommunity (?:centre|hub)|\bsports', re.I))]
CONSORTIA = re.compile(r'\b(?:prosper|lhc|ypo|espo|fusion21|pagabo|scape|efficiency east midlands|construction hub|construction framework|procurement hub|'
                       r'crown commercial|framework alliance|consortium|purchasing (?:organisation|consortium)|procurement (?:partnership|services))\b', re.I)
STAGE_WORDS = re.compile(r'\b(?:tender|tenders|award|awarded|contract|contracts|notice|invitation|itt|pqq|pin|call[\s-]?off|lot \d+|framework|of|the|and|for|to|at|a)\b', re.I)


def project_key(buyer: str, title: str) -> str:
    """The same project's tender, award and amendment share a key, so they count once as evidence."""
    core = ' '.join(sorted(set(re.findall(r'[a-z0-9]{3,}', STAGE_WORDS.sub(' ', title.lower())))))[:120]
    return hashlib.sha256(f'{_buyer_key(buyer)}|{core}'.encode()).hexdigest()[:24]


def beneficiary(buyer: str, title: str) -> tuple[str, bool]:
    """A purchasing consortium publishes for its members: name the member only as inferred, never merge them."""
    if not CONSORTIA.search(buyer):
        return buyer, False
    head = re.split(r'\s+[-–:|]\s+', title, maxsplit=1)[0].strip()
    if 3 <= len(head) <= 80 and head[0].isupper() and not WORKS[0][1].search(head) and not re.search(r'\d{3,}', head):
        return head, True
    return buyer, False


def classify(notice: dict[str, Any]) -> dict[str, Any] | None:
    """One Contracts Finder notice as a works observation, or None when it is not adjacent building work."""
    title, text = notice['title'], f"{notice['title']} {notice.get('description') or ''}"
    if DIRECT.search(title) or NOT_WORKS.search(title) or OVERSEAS.search(f"{notice['buyer']} {title}"):
        return None
    # Building work must be named in the title, or a building in the title with the works described.
    works = next((kind for kind, pattern in WORKS if pattern.search(title)), None)
    if works is None and BUILDING_NOUN.search(title):
        works = next((kind for kind, pattern in WORKS if pattern.search(text)), None)
    if works is None or not BUILDING_NOUN.search(text) or (notice.get('value') is not None and notice['value'] < MIN_VALUE):
        return None
    building = next((kind for kind, pattern in BUILDING if pattern.search(text)), 'unknown')
    awarded = bool(notice.get('suppliers')) and notice.get('type') in ('Contract', 'Awarded')
    who, inferred = beneficiary(notice['buyer'], notice['title'])
    published = date.fromisoformat(notice['published']) if notice.get('published') else None
    if published is None:
        return None
    started = date.fromisoformat(notice['start']) if notice.get('start') else published
    contractor = notice['suppliers'][0] if awarded else None
    value = f" valued at £{notice['value']:,.0f}" if notice.get('value') else ''
    statement = (f"{notice['buyer']} awarded \"{notice['title']}\"{value} to {contractor}." if awarded
                 else f"{notice['buyer']} published \"{notice['title']}\"{value}.")
    return observation('works_awarded' if awarded else 'works_planned', statement=statement, occurred=min(started, published) if awarded else published,
                       available=published, url=notice['url'], group='procurement', reliability='official_notice', buyer=who, supplier=contractor,
                       detail={'works_type': works, 'building_type': building, 'value': notice.get('value'), 'notice_type': notice.get('type'),
                               'title': notice['title'], 'publisher': notice['buyer'], 'beneficiary_inferred': inferred,
                               'postcode': notice.get('postcode') or None, 'region': notice.get('region') or None, 'end': notice.get('end') or None,
                               'source': SOURCE, 'licence': LICENCE, 'project': project_key(notice['buyer'], notice['title'])})


def store_append_only(db: Session, items: list[dict], now: datetime) -> dict:
    """Keep each observation exactly as first read. Seeing it again only records that it is still published."""
    if not items:
        return {'observed': 0, 'new': 0}
    known = {x.fingerprint: x for x in db.scalars(select(MarketObservation).where(MarketObservation.fingerprint.in_([i['fingerprint'] for i in items])))}
    new = 0
    for item in items:
        row = known.get(item['fingerprint'])
        if row is not None:
            row.last_seen = now
            continue
        origin = f"procurement:{item['detail'].get('project') or item['fingerprint'][:24]}"
        row = MarketObservation(**item, first_seen=now, last_seen=now, retrieved_at=now, origin_key=origin)
        db.add(row)
        known[item['fingerprint']] = row
        new += 1
    db.flush()
    return {'observed': len(items), 'new': new}


def load_capture(db: Session, path, *, now: datetime | None = None) -> dict:
    """Store observations from a saved capture of published notices, dated as when they were read."""
    import json
    capture = json.loads(open(path).read())
    retrieved = datetime.fromisoformat(capture['retrieved'])
    items = list({x['fingerprint']: x for x in (classify(n) for n in capture['notices']) if x}.values())
    return store_append_only(db, items, now or retrieved) | {'notices': len(capture['notices'])}


def collect(db: Session, *, days: int = 30, requests: int = 12, http=None, now: datetime | None = None, sleep=None, capture: list | None = None) -> dict:
    """A bounded read of recent works notices. Called by the radar worker; never by a browser request."""
    now = now or datetime.now(UTC)
    owned = http is None
    http = http or cf.client()
    budget = cf.Budget(requests_left=requests)
    found: list[dict] = []
    try:
        for keyword in KEYWORDS:
            rows = cf.collect(http, {'keyword': keyword, 'types': ['Contract', 'Pipeline', 'Opportunity', 'EarlyEngagement', 'Awarded']},
                              (now - timedelta(days=days)).date(), now.date(), budget, **({'sleep': sleep, 'pause': 0} if sleep else {}))
            if capture is not None:
                capture.extend(rows)  # the published notices as read, for a reproducible record
            found += [x for x in (classify(r) for r in rows) if x]
            if budget.exhausted:
                break
    finally:
        if owned:
            http.close()
    unique = list({x['fingerprint']: x for x in found}.values())
    stored = store_append_only(db, unique, now)
    return {**stored, 'requests': budget.requests_made, 'truncated': budget.truncated_hits, 'budget_exhausted': budget.exhausted}
