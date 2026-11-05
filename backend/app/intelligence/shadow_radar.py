"""Shadow Radar: reconstruct an unadvertised commercial state from the shadows it leaves in public records.

Observation -> entity resolution -> temporal correlation -> virtual sensor -> competing hypotheses
-> evidence challenge -> opportunity window -> lead.

Every rule is written down here and every output says what is published, what is inferred and
what is unknown. There are no probabilities: a state says how much independent evidence exists,
not how likely a purchase is. `evaluate` is a pure function of the observations available on an
`as_of` date, so the same code serves the live radar and a backtest that cannot see the future.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import json
import re
from typing import Any

from app.intelligence.signal_inference import council_key

RULE_VERSION = 'shadow-radar-v1'
CORRELATION_DAYS = 365
STATE_LABEL = {'indicated': 'One line of evidence', 'corroborated': 'Corroborated by independent sources', 'challenged': 'Contradicted by later evidence',
               'surfaced': 'Now advertised', 'closed': 'Window passed'}
TYPE_LABEL = {'works_awarded': 'Building contract awarded', 'works_planned': 'Building work planned or out to tender', 'estate_expansion': 'New or enlarged estate',
              'regulator_compliance_finding': 'Regulator finding on fire safety', 'fire_enforcement_outcome': 'Fire authority inspection outcome',
              'remedial_programme': 'Remedial work procured', 'issue_resolved': 'Published resolution', 'market_engagement': 'Fire or security work advertised',
              'contract_terminated': 'Contract terminated', 'tender_abandoned': 'Procurement abandoned', 'repeated_retender': 'Repeated retendering',
              'out_of_cycle_relet': 'Replacement before the published end', 'supplier_replaced': 'New supplier appointed', 'contract_modified': 'Contract extended or varied',
              'false_alarm_rise': 'Rise in fire service alarm attendances'}
DERIVED = {'false_alarm_rise', 'out_of_cycle_relet', 'repeated_retender'}  # computed by SalesIntel from records, not stated by a source
MODERNISE = re.compile(r'\b(?:upgrade|replacement|replace|analogue|digital|bms|building management|m\s?&\s?e|mechanical (?:and|&) electrical|rewir\w*|life[\s-]?cycle)\b', re.I)
SERVICES_BY_BUILDING = {'healthcare': ['fire_alarm', 'emergency_lighting', 'access_control', 'cctv'], 'education': ['fire_alarm', 'access_control', 'cctv', 'intruder'],
                        'residential': ['fire_alarm', 'emergency_lighting', 'access_control', 'cctv'], 'commercial': ['fire_alarm', 'cctv', 'access_control', 'intruder'],
                        'public_venue': ['fire_alarm', 'cctv', 'access_control', 'emergency_lighting'], 'unknown': ['fire_alarm', 'cctv', 'access_control']}


@dataclass(frozen=True)
class Sensor:
    key: str
    name: str
    hypothesis: str
    indicators: tuple[str, ...]
    relationships: str
    timing: str
    source_quality: str
    alternatives: tuple[tuple[str, str], ...]  # (rival explanation, what would tell them apart)
    disconfirming: tuple[str, ...]
    opportunity_type: str
    evidence_needed: tuple[str, ...]
    first_action: str
    plan: tuple[tuple[str, str], ...]  # (question, confirm|challenge) for the deep investigator
    status: str = 'active'  # active, or needs_source with the reason in `blocked`
    blocked: str = ''
    anchors: tuple[str, ...] = ()
    supports: tuple[str, ...] = ()
    counters: tuple[str, ...] = ()
    surfaces: tuple[str, ...] = ('market_engagement',)
    window: tuple[int, int] = (0, 365)


SENSORS: dict[str, Sensor] = {s.key: s for s in [
    Sensor('estate_mobilisation', 'New premises', 'A new or enlarged building will need fire and security systems installed and then maintained.',
           ('Building contract awarded or tendered', 'New estate published by the owner'),
           'The building work and the owner must be the same organisation; a purchasing consortium is never treated as the owner.',
           'Systems are usually specified within months of the main contract and maintained from handover, often 1 to 3 years later.',
           'Official procurement notices (high); the owner is stated, the systems are not.',
           (('Fire and security are inside the main contract (design and build)', 'Does the main contract specification list fire alarm, access control or CCTV?'),
            ('The project is paused or cancelled', 'Is the scheme still on programme?'),
            ('An existing estate maintenance contract will absorb the new building', 'Does the owner add new buildings to its current maintenance contract?')),
           ('A later notice shows the systems already let', 'The project is withdrawn'),
           'New installation, then planned maintenance', ('Scope of fire and security in the main contract', 'Handover date', 'Who maintains the owner\'s current estate'),
           "Ask the owner's estates team how fire and security for the new building will be bought and maintained after handover.",
           (('Is the project confirmed and on programme?', 'confirm'), ('Does the main contract already include fire and security systems?', 'challenge'),
            ('When is handover or practical completion?', 'confirm'), ('Who maintains the owner\'s existing fire and security systems?', 'confirm'),
            ('Has a specialist fire or security package already been let?', 'challenge')),
           anchors=('works_awarded', 'works_planned', 'estate_expansion'), supports=('works_awarded', 'works_planned', 'estate_expansion'), window=(90, 900)),
    Sensor('adjacent_package', 'Main contractor package', 'The appointed main contractor will buy a specialist fire and security package for this project.',
           ('Building contract awarded with the main contractor named',),
           'The award must name the contractor; the package is bought by that contractor, not the owner.',
           'Specialist packages are usually let within the first nine months of construction.',
           'Official award notices (high); package strategy is never published.',
           (('The contractor self-delivers mechanical and electrical work including fire', "Does the contractor have an in-house M&E division?"),
            ('The client nominated a specialist', 'Does the tender name a nominated or preferred fire and security supplier?'),
            ('The package is already let', 'Has the contractor announced its supply chain for this project?')),
           ('The contractor confirms the package is let', 'The specification names another supplier'),
           'Subcontract installation package', ("The contractor's supply-chain contact", 'Package programme', 'Specification for fire and security'),
           "Register with the main contractor's supply chain and ask when the fire and security package will be tendered.",
           (('Who is the main contractor and do they publish a supply-chain portal?', 'confirm'), ('Does the contractor deliver fire and security in-house?', 'challenge'),
            ('Has the specialist package been awarded?', 'challenge'), ('What is the construction programme?', 'confirm')),
           anchors=('works_awarded',), supports=('works_awarded', 'estate_expansion'), window=(0, 270)),
    Sensor('remediation', 'Fire safety remediation', 'Published fire safety failings will require remedial work, inspection or new systems.',
           ('Regulator finding on fire safety', 'Fire authority enforcement outcome', 'Remedial work procured'),
           'The finding must be about the organisation itself; a contractor is never presumed at fault.',
           'Remediation usually follows a finding within 12 months; regulators publish progress.',
           'Regulator and fire authority records (statutory, high); remedial procurement (official notice).',
           (('Work is done by an in-house team', 'Does the organisation have a direct labour organisation for fire safety work?'),
            ('An existing framework contractor will do it', 'Is there a current fire safety framework or term contract?'),
            ('The failings are not about fire systems (for example overdue risk assessments or fire doors)', 'Which remedial actions does the finding list?')),
           ('A later judgement records the issue as resolved', 'A remedial contract is already awarded'),
           'Remedial works and compliance services', ('The remedial action plan', 'Who holds the current fire safety contracts', 'Budget and timescale'),
           'Offer a compliance review aligned to the published finding, through the organisation\'s compliance or assets lead.',
           (('What remedial actions does the regulator or fire authority require?', 'confirm'), ('Has the organisation said it is resolved?', 'challenge'),
            ('Who holds the current fire safety maintenance contract?', 'confirm'), ('Is the remedial work already procured or in-house?', 'challenge')),
           anchors=('regulator_compliance_finding', 'fire_enforcement_outcome'), supports=('regulator_compliance_finding', 'fire_enforcement_outcome', 'remedial_programme', 'false_alarm_rise'),
           counters=('issue_resolved',), surfaces=('market_engagement', 'remedial_programme'), window=(0, 365)),
    Sensor('supplier_transition', 'Supplier transition', 'A disrupted contract creates a short window in which the buyer is open to a new supplier.',
           ('Contract terminated', 'Procurement abandoned', 'Repeated retendering', 'Replacement before the published end'),
           'The event must concern the buyer\'s own contract; a supplier is never presumed to have failed.',
           'Interim arrangements usually last 3 to 6 months before a new procurement.',
           'Official notices (high) and SalesIntel\'s own comparison of records (derived, medium).',
           (('Routine budget or timing change', 'Did the buyer publish a reason?'), ('Corporate change at the supplier', 'Was it a merger, rebrand or novation?')),
           ('A new supplier is already appointed', 'The buyer re-awards to the same supplier'),
           'Interim cover or the next procurement', ('Why the contract changed', 'Interim arrangements', 'Next procurement date'),
           "Ask the buyer how the service is covered now and when it will be procured again.",
           (('Why was the contract terminated, abandoned or re-let?', 'confirm'), ('Has a new supplier already been appointed?', 'challenge'),
            ('When will it be procured again?', 'confirm')),
           anchors=('contract_terminated', 'tender_abandoned', 'repeated_retender', 'out_of_cycle_relet'), supports=('contract_terminated', 'tender_abandoned', 'repeated_retender', 'out_of_cycle_relet', 'contract_modified'),
           counters=('supplier_replaced',), window=(0, 180)),
    Sensor('modernisation', 'Systems modernisation', 'Building services are being replaced or upgraded, and fire and security systems are often renewed with them.',
           ('Mechanical, electrical or building services replacement procured',),
           'The works must be to buildings the organisation owns or manages.',
           'Fire and security often follow or accompany services replacement within a year.',
           'Official notices (high); the fire and security scope is rarely stated.',
           (('Fire and security are inside the services contract', 'Does the specification include fire alarm or access control?'),
            ('Only plant is replaced (boilers, lifts)', 'Which systems are in scope?')),
           ('The specification excludes fire and security', 'A separate fire contract is current'),
           'Upgrade or replacement', ('Scope of the services replacement', 'Age of current fire and security systems'),
           "Ask the estates team whether fire alarm, emergency lighting or access control renewals are planned alongside the services work.",
           (('Which building services are being replaced?', 'confirm'), ('Are fire and security systems within that scope?', 'challenge'),
            ('How old are the current fire and security systems?', 'confirm')),
           anchors=('works_awarded', 'works_planned'), supports=('works_awarded', 'works_planned', 'remedial_programme'), window=(0, 365)),
    Sensor('consolidation', 'Portfolio consolidation', 'A merger or consolidation will rationalise suppliers across a larger estate.',
           ('Registered merger or transfer of engagements', 'Corporate control change'), 'Both organisations must be identified by registration number.',
           'Supplier rationalisation usually follows within 12 to 24 months.', 'Regulator registers and Companies House (statutory).',
           (('Each estate keeps its own contracts', 'Has the group announced supplier rationalisation?'),), ('No supplier change announced',),
           'Multi-site contract', ('Combined estate size', 'Current contracts in each part'), 'Ask the combined organisation how it will procure estate-wide services.',
           (('Is the merger complete?', 'confirm'),), status='needs_source',
           blocked='Needs the Companies House API (no key configured) and the Regulator of Social Housing register of mergers, which is not yet integrated.'),
    Sensor('funded_capital', 'Funded capital improvement', 'A funding award will pay for building improvements that include fire and security.',
           ('Published grant or capital allocation to a named organisation',), 'The recipient must be named in the funding record.',
           'Funded works are usually procured within the funding year.', 'Government funding releases (official).',
           (('The funding is for unrelated works', 'What does the allocation cover?'),), ('The scheme is withdrawn',), 'Capital project',
           ('Scope of funded works',), 'Ask the recipient whether fire and security upgrades are part of the funded scheme.',
           (('What does the award fund?', 'confirm'),), status='needs_source',
           blocked='Assessed: GOV.UK funding releases checked so far publish totals rather than named recipients and building scopes, so they cannot be resolved to organisations reliably.'),
    Sensor('leadership_change', 'New operational leader', 'A new estates, facilities or security leader often reviews suppliers in their first year.',
           ('Appointment of a relevant director or head',), 'The person, role and organisation must be stated by the organisation or Companies House.',
           'Supplier reviews usually start 3 to 12 months after appointment.', 'Company announcements and Companies House officers.',
           (('The appointment is a like-for-like replacement with no review', 'Has the new leader announced priorities?'),), ('No review planned',),
           'Supplier review', ('The new leader\'s priorities',), 'Introduce yourself to the new leader with a short, relevant point of view.',
           (('Who was appointed, to what role, and when?', 'confirm'),), status='needs_source',
           blocked='Needs Companies House officer data (no API key configured) or permitted announcement sources; found per account by the deep investigator instead.'),
]}


def _norm(text: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', (text or '').lower())).strip()


_STOP = {'the', 'and', 'for', 'of', 'to', 'at', 'in', 'on', 'works', 'work', 'contract', 'services', 'service', 'provision', 'maintenance', 'notice', 'early',
         'published', 'council', 'city', 'borough', 'county', 'district', 'nhs', 'trust', 'limited', 'ltd', 'new', 'construction', 'refurbishment', 'project', 'phase',
         'award', 'tender', 'fire', 'security', 'systems', 'system', 'cctv', 'alarm', 'access', 'control', 'lighting', 'emergency', 'door', 'doors', 'repairs'}


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r'[a-z]{4,}', (text or '').lower()) if w not in _STOP}


def same_project(anchor: dict, other: dict) -> bool:
    """Two notices concern the same project when they share distinctive place or building names, not just service words."""
    a = _tokens(f"{(anchor.get('detail') or {}).get('title') or ''} {anchor['statement']}") - _tokens(anchor.get('buyer') or '')
    b = _tokens(other['statement']) - _tokens(other.get('buyer') or '')
    return len(a & b) >= 2


def origin_of(o: dict) -> str:
    """One origin per underlying publication: repeated notices about one project, and republished copies, count once."""
    if o.get('origin_key'):
        return o['origin_key']
    return f"{o['source_group']}:" + hashlib.sha256(_norm(o['statement'])[:240].encode()).hexdigest()[:24]


def entity_of(o: dict) -> tuple[str, str]:
    name = o.get('buyer') or ''
    return council_key(name) if name else '', name


def _eligible(sensor: Sensor, o: dict) -> bool:
    d = o.get('detail') or {}
    if o['signal_type'] not in sensor.anchors:
        return False
    if sensor.key == 'estate_mobilisation' and o['signal_type'] != 'estate_expansion':
        return d.get('works_type') in ('new_build', 'extension', 'fit_out')
    if sensor.key == 'adjacent_package':
        return d.get('works_type') in ('new_build', 'extension', 'refurbishment', 'fit_out') and (d.get('value') is None or d['value'] >= 1_000_000)
    if sensor.key == 'modernisation':
        return bool(MODERNISE.search(f"{d.get('title') or ''} {o['statement']}")) and d.get('works_type') in ('refurbishment', 'fit_out', None)
    return True


def _entry(o: dict, role: str) -> dict:
    return {'role': role, 'type': o['signal_type'], 'label': TYPE_LABEL.get(o['signal_type'], o['signal_type'].replace('_', ' ')), 'statement': o['statement'],
            'event_date': str(o['occurred_on']), 'published': str(o['available_on']), 'first_seen': str(o['first_seen'])[:10] if o.get('first_seen') else None,
            'retrieved': str(o['retrieved_at'])[:10] if o.get('retrieved_at') else None, 'source_url': o['source_url'], 'source_group': o['source_group'],
            'basis': 'derived' if o['signal_type'] in DERIVED else 'published', 'origin': origin_of(o), 'id': o.get('id')}


def _publisher(o: dict) -> str:
    return council_key((o.get('detail') or {}).get('publisher') or o.get('buyer') or o['source_group'])


def evaluate(observations: list[dict], as_of: date, *, sensors: dict[str, Sensor] | None = None) -> list[dict]:
    """Every hypothesis the evidence available on `as_of` supports. Nothing published later is used."""
    usable = [o for o in observations if o['available_on'] <= as_of and not (o.get('retracted_on') and o['retracted_on'] <= as_of)]
    by_entity: dict[str, list[dict]] = {}
    for o in usable:
        key, _ = entity_of(o)
        if key:
            by_entity.setdefault(key, []).append(o)
    out = []
    for sensor in (sensors or SENSORS).values():
        if sensor.status != 'active':
            continue
        for key, items in by_entity.items():
            # The richest evidence anchors a lead (an award naming the contractor before a plan or a planning record);
            # anything already counted as support for a lead is not turned into a second lead about the same thing.
            priority = {'works_awarded': 0, 'works_planned': 1}
            anchors = sorted((o for o in items if _eligible(sensor, o)), key=lambda o: (priority.get(o['signal_type'], 2), o['available_on']))
            used: set[str] = set()
            for anchor in anchors:
                origin = origin_of(anchor)
                if origin in used:
                    continue  # the same project or publication is one line of evidence
                assessment = _assess(sensor, key, anchor, items, as_of)
                used |= {e['origin'] for e in assessment['timeline'] if e['role'] in ('anchor', 'supports')}
                out.append(assessment)
    return out


def _assess(sensor: Sensor, key: str, anchor: dict, items: list[dict], as_of: date) -> dict:
    start = anchor['available_on'] - timedelta(days=CORRELATION_DAYS)
    end = anchor['available_on'] + timedelta(days=CORRELATION_DAYS)
    nearby = [o for o in items if start <= o['available_on'] <= end and o is not anchor]
    supports = [o for o in nearby if o['signal_type'] in sensor.supports and origin_of(o) != origin_of(anchor)
                and (o['signal_type'] not in ('works_awarded', 'works_planned') or (o.get('detail') or {}).get('project') != (anchor.get('detail') or {}).get('project'))]
    counters = [o for o in items if o['signal_type'] in sensor.counters and o['available_on'] >= anchor['available_on']]
    adverts = [o for o in items if o['signal_type'] in sensor.surfaces and o['available_on'] >= anchor['available_on'] and origin_of(o) != origin_of(anchor)]
    # Organisation-wide needs (remediation) are answered by any later fire or security advert. Project needs only by an
    # advert about the same project or site; other adverts by the organisation are shown as related, not as this lead.
    surfaced = adverts if sensor.key in ('remediation', 'supplier_transition') else [o for o in adverts if same_project(anchor, o)]
    related = [o for o in adverts if o not in surfaced]
    # Independence: distinct publishers or source types. Two notices from one buyer are one voice.
    lines = {(anchor['source_group'], _publisher(anchor))} | {(o['source_group'], _publisher(o)) for o in supports}
    independent = len({group for group, _ in lines})  # a procurement notice and a regulator judgement are two voices; two notices are one
    d = anchor.get('detail') or {}
    happened = anchor['occurred_on'] if anchor['signal_type'] == 'works_awarded' else anchor['available_on']
    window = (happened + timedelta(days=sensor.window[0]), happened + timedelta(days=sensor.window[1]))
    if counters:
        state = 'challenged'
    elif surfaced:
        state = 'surfaced'
    elif window[1] < as_of:
        state = 'closed'
    elif independent >= 2:
        state = 'corroborated'
    else:
        state = 'indicated'
    timeline = sorted([_entry(anchor, 'anchor')] + [_entry(o, 'supports') for o in supports] + [_entry(o, 'challenges') for o in counters]
                      + [_entry(o, 'advertised') for o in surfaced] + [_entry(o, 'related') for o in related], key=lambda e: e['published'])
    evidence = [anchor] + supports
    first_seen = min((o['first_seen'] for o in evidence if o.get('first_seen')), default=None)
    first_advertised = min((o['available_on'] for o in surfaced), default=None)
    services = SERVICES_BY_BUILDING.get(d.get('building_type') or 'unknown', SERVICES_BY_BUILDING['unknown']) if anchor['signal_type'].startswith('works') \
        else (['fire_alarm', 'emergency_lighting', 'fire_risk_assessment'] if sensor.key == 'remediation' else ['fire_alarm', 'cctv', 'access_control'])
    entity_name = anchor.get('buyer') or key
    site = d.get('title') if anchor['signal_type'].startswith('works') else None
    verified = [f"{e['label']}: {e['statement']} ({e['published']})" for e in timeline if e['basis'] == 'published' and e['role'] in ('anchor', 'supports')]
    inferred = [sensor.hypothesis, f"Possible investigation window {window[0]:%b %Y} to {window[1]:%b %Y}, from a rule of thumb: {sensor.timing}"]
    if d.get('beneficiary_inferred'):
        inferred.insert(0, f"The owner is inferred from the notice title; it was published by {d.get('publisher')}, a purchasing consortium.")
    unknown = list(sensor.evidence_needed) + ([f"Whether {anchor.get('supplier')} delivers fire and security in-house"] if sensor.key == 'adjacent_package' and anchor.get('supplier') else [])
    return {'key': f"{sensor.key}|{key}|{origin_of(anchor)}", 'sensor': sensor.key, 'sensor_name': sensor.name, 'entity_key': key, 'entity_name': entity_name,
            'company_number': anchor.get('company_number'), 'site': site, 'postcode': d.get('postcode'), 'state': state, 'state_label': STATE_LABEL[state],
            'hypothesis': sensor.hypothesis, 'opportunity_type': sensor.opportunity_type, 'independent_sources': independent,
            'first_published_on': str(min(o['available_on'] for o in evidence)), 'first_seen': str(first_seen)[:10] if first_seen else None,
            'first_advertised_on': str(first_advertised) if first_advertised else None,
            'window': [str(window[0]), str(window[1])], 'services': services, 'timeline': timeline, 'verified': verified, 'inferred': inferred, 'unknown': unknown,
            'alternatives': [{'explanation': a, 'test': t} for a, t in sensor.alternatives], 'disconfirming': list(sensor.disconfirming),
            'first_action': sensor.first_action, 'main_contractor': anchor.get('supplier') if anchor['signal_type'] == 'works_awarded' else None,
            'value': d.get('value'), 'building_type': d.get('building_type'), 'works_type': d.get('works_type'), 'as_of': str(as_of), 'rule_version': RULE_VERSION}


def assessment_fingerprint(a: dict) -> str:
    stable = {k: v for k, v in a.items() if k not in ('as_of',)}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, default=str).encode()).hexdigest()


def registry() -> list[dict]:
    """The sensors as data, for the inspectable 'how this works' view and the report."""
    return [{'key': s.key, 'name': s.name, 'hypothesis': s.hypothesis, 'indicators': list(s.indicators), 'relationships': s.relationships, 'timing': s.timing,
             'source_quality': s.source_quality, 'alternatives': [{'explanation': a, 'test': t} for a, t in s.alternatives], 'disconfirming': list(s.disconfirming),
             'opportunity_type': s.opportunity_type, 'evidence_needed': list(s.evidence_needed), 'first_action': s.first_action, 'status': s.status,
             'blocked': s.blocked, 'window_days': list(s.window)} for s in SENSORS.values()]
