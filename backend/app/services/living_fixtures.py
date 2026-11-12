"""Fictional records for the Living Opportunity: tests, browser tests and screenshots. Every organisation, person, page
and number here is invented.

- Fernhill Parcels: a parcel company's depot programme (some depots opened, others planned), a main contractor already
  appointed for one site, a named head of property, and a switchboard route. The same shape as a real multi-site
  logistics expansion, so the reveal can be judged on it.
- Ashby Vale Council: a live published tender for fire alarm and emergency lighting maintenance, with the notice itself
  (value, deadlines, scoring, term, lots, portal) and the council's previous award for the same work, so the brief can
  show what the notice states and what the published record says about the field.
- Fenwick Housing Trust: a public signal before any tender. A regulator's finding and, later, the trust's own early notice:
  two records from two independent sources. The trust is also a buyer in the fictional Contract Atlas market, so the brief
  can set the signal beside the published holder of its fire contract without connecting the two.

The publishers named (Contracts Finder, Find a Tender, the Regulator of Social Housing) are real services. Every record
attributed to them here is invented, and the invented records point at example addresses.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_contract import MarketContract
from app.models.market_network import SourceRevision
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.models.prospect import Prospect

FERNHILL = 'Fernhill Parcels Ltd'
NEWS = 'https://news.example/fernhill'
ASHBY = 'Ashby Vale Council'
ASHBY_URL = 'https://www.contractsfinder.service.gov.uk/Notice/living-fixture-ashby'
ASHBY_PORTAL = 'https://procurement.ashbyvale.example/tenders/AVC-2026-014'
ASHBY_HOLDER = 'Tarnside Fire Systems Ltd'
ASHBY_AWARD_URL = 'https://www.contractsfinder.service.gov.uk/Notice/living-fixture-ashby-award'
FENWICK = 'Fenwick Housing Trust'
FENWICK_FINDING_URL = 'https://regulator.example/judgements/fenwick-housing-trust'
FENWICK_EARLY_URL = 'https://procurement.example/notices/fenwick-early-engagement'
FENWICK_EARLY_TITLE = 'Fire alarm replacement and remedial works programme'
SIGNAL_CAUTION = 'An inference from public records, not a finding about any company. Do not repeat it to a customer as fact.'
_ASHBY_PARTY = {'id': 'GB-CFS-ashby', 'name': ASHBY, 'roles': ['buyer'], 'address': {'locality': 'Ashby Vale', 'postalCode': 'LS1 9ZZ', 'countryName': 'United Kingdom'},
                'details': {'url': 'https://www.ashbyvale.example', 'classifications': [{'scheme': 'UK_CA_TYPE', 'id': 'publicAuthoritySubCentralGovernment',
                                                                                         'description': 'Local authority'}]}}


def _split(quality: int, social: int, price: int) -> dict:
    return {'criteria': [{'type': 'quality', 'name': 'Service delivery and technical approach', 'numbers': [{'number': quality, 'weight': 'percentageExact'}]},
                         {'type': 'quality', 'name': 'Social value', 'numbers': [{'number': social, 'weight': 'percentageExact'}]},
                         {'type': 'price', 'name': 'Price', 'numbers': [{'number': price, 'weight': 'percentageExact'}]}]}


def ashby_notice(today: date) -> dict:
    """The tender notice as a buyer publishes it: what it is worth, when it is due, how it is scored, where to submit."""
    d = lambda days: (today + timedelta(days=days)).isoformat()  # noqa: E731
    renewal = {'hasRenewal': True, 'renewal': {'description': 'Two optional extensions of 12 months each, at the council\'s discretion.'}}
    return {'ocid': 'ocds-fixture-ashby-2026', 'id': 'living-fixture-ashby', 'date': f'{d(-9)}T09:00:00Z', 'tag': ['tender'], 'buyer': {'id': 'GB-CFS-ashby', 'name': ASHBY},
            'parties': [_ASHBY_PARTY],
            'tender': {'id': 'AVC-2026-014', 'title': 'Fire alarm and emergency lighting maintenance across council buildings', 'status': 'active',
                       'description': 'Planned maintenance, testing and reactive repairs of fire alarm and emergency lighting systems in 38 council buildings, '
                                      'including offices, depots, libraries and four leisure centres.',
                       'value': {'amount': 480000, 'amountGross': 576000, 'currency': 'GBP'}, 'procurementMethod': 'open', 'procurementMethodDetails': 'Open procedure',
                       'mainProcurementCategory': 'services', 'aboveThreshold': True, 'suitability': {'sme': True},
                       'enquiryPeriod': {'endDate': f'{d(12)}T17:00:00Z'}, 'tenderPeriod': {'endDate': f'{d(21)}T12:00:00Z'}, 'awardPeriod': {'endDate': f'{d(63)}T00:00:00Z'},
                       'contractPeriod': {'startDate': f'{d(120)}T00:00:00Z', 'endDate': f'{d(120 + 3 * 365)}T23:59:59Z', 'maxExtentDate': f'{d(120 + 5 * 365)}T23:59:59Z'},
                       'submissionMethodDetails': f'Tenders must be submitted through the council\'s portal: {ASHBY_PORTAL}',
                       'selectionCriteria': {'criteria': [
                           {'description': 'Third-party certification for the maintenance of fire detection and alarm systems (BAFE SP203-1 or equivalent).'},
                           {'description': 'Employer\'s liability insurance of £10m and public liability insurance of £5m.'}]},
                       'lots': [{'id': '1', 'title': 'Fire alarm and detection maintenance', 'value': {'amount': 300000, 'currency': 'GBP'}, 'awardCriteria': _split(50, 10, 40), **renewal},
                                {'id': '2', 'title': 'Emergency lighting testing and maintenance', 'value': {'amount': 180000, 'currency': 'GBP'}, 'awardCriteria': _split(50, 10, 40),
                                 **renewal}],
                       'documents': [{'documentType': 'biddingDocuments', 'title': 'Invitation to tender', 'url': f'{ASHBY_PORTAL}/itt.pdf', 'datePublished': f'{d(-9)}T09:00:00Z'},
                                     {'documentType': 'technicalSpecifications', 'title': 'Specification and asset list', 'url': f'{ASHBY_PORTAL}/specification.pdf',
                                      'datePublished': f'{d(-9)}T09:00:00Z'}],
                       'items': [{'id': '1', 'classification': {'scheme': 'CPV', 'id': '50413200', 'description': 'Repair and maintenance services of firefighting equipment'},
                                  'deliveryAddresses': [{'region': 'UKE'}]}]}}


def ashby_award(today: date) -> dict:
    """The council's previous award for the same work: who won it, for how much, against how many bids and on what scoring."""
    d = lambda days: (today + timedelta(days=days)).isoformat()  # noqa: E731
    return {'ocid': 'ocds-fixture-ashby-previous', 'id': 'living-fixture-ashby-award', 'date': f'{d(-990)}T09:00:00Z', 'tag': ['award'], 'buyer': {'id': 'GB-CFS-ashby', 'name': ASHBY},
            'parties': [_ASHBY_PARTY, {'id': 'GB-CFS-fixture-tarnside', 'name': ASHBY_HOLDER, 'roles': ['supplier'], 'details': {'scale': 'sme'}}],
            'tender': {'id': f'AVC-{(today - timedelta(days=990)).year}-007', 'title': 'Fire alarm and emergency lighting servicing', 'procurementMethod': 'open', 'procurementMethodDetails': 'Open procedure',
                       'description': 'Servicing, testing and repair of fire alarm and emergency lighting systems in council buildings.',
                       'lots': [{'id': '1', 'title': 'Fire alarm and emergency lighting servicing', 'awardCriteria': {'criteria': [
                           {'type': 'quality', 'name': 'Quality', 'numbers': [{'number': 40, 'weight': 'percentageExact'}]},
                           {'type': 'price', 'name': 'Price', 'numbers': [{'number': 60, 'weight': 'percentageExact'}]}]}}]},
            'bids': {'statistics': [{'id': '1', 'measure': 'bids', 'value': 4}, {'id': '2', 'measure': 'lowestValidBidValue', 'value': 371000},
                                    {'id': '3', 'measure': 'highestValidBidValue', 'value': 498000}]},
            'awards': [{'id': 'award-ashby-previous', 'status': 'active', 'date': f'{d(-990)}T09:00:00Z', 'suppliers': [{'id': 'GB-CFS-fixture-tarnside', 'name': ASHBY_HOLDER}],
                        'value': {'amount': 412000, 'currency': 'GBP'}, 'contractPeriod': {'startDate': f'{d(-975)}T00:00:00Z', 'endDate': f'{d(120)}T23:59:59Z'}}]}


def fernhill_data(today: date) -> dict:
    d = lambda days: (today + timedelta(days=days)).isoformat()  # noqa: E731
    month = lambda days: (today + timedelta(days=days)).isoformat()[:7]  # noqa: E731
    return {
        'website': 'https://www.fernhill-parcels.example', 'sector': 'Parcel delivery and logistics', 'location': 'Wakefield, Leicester, Bristol and Swindon',
        'company_number': '', 'size': '', 'headline': 'Fernhill Parcels is part-way through a six-depot automation programme.',
        'summary': 'A national parcel carrier building six automated depots.',
        'signals': [
            {'type': 'investment', 'title': '£240m programme for six new automated parcel depots', 'detail': 'Six automated depots are planned over three years.',
             'date': month(-420), 'basis': 'stated', 'direction': 'supports', 'source_url': f'{NEWS}-programme'},
            {'type': 'new_site', 'title': 'Wakefield depot opened', 'detail': 'The first automated depot opened in Wakefield.', 'date': d(-240), 'basis': 'stated',
             'direction': 'supports', 'source_url': f'{NEWS}-wakefield'},
            {'type': 'new_site', 'title': 'Leicester depot opened', 'detail': 'A second depot opened in Leicester.', 'date': d(-60), 'basis': 'stated',
             'direction': 'supports', 'source_url': f'{NEWS}-leicester'},
            {'type': 'new_site', 'title': 'Bristol depot under construction', 'detail': 'Construction is under way at Avonmouth.', 'date': d(-150), 'basis': 'stated',
             'direction': 'supports', 'source_url': f'{NEWS}-bristol'},
            {'type': 'planning_application', 'title': 'Swindon depot approved', 'detail': 'Planning permission was granted for a depot in Swindon.', 'date': d(-90),
             'basis': 'stated', 'direction': 'supports', 'source_url': 'https://planning.example/swindon/fernhill'},
            {'type': 'contract_change', 'title': 'Halden Construction appointed main contractor for the Bristol depot',
             'detail': 'The main contractor may let the specialist packages itself.', 'date': d(-200), 'basis': 'stated', 'direction': 'against',
             'source_url': f'{NEWS}-halden'},
            {'type': 'expansion', 'title': 'Two further depots still to be announced', 'detail': '', 'date': '', 'basis': 'inferred', 'direction': 'supports', 'source_url': ''}],
        'timing_clues': [
            {'kind': 'site_opening', 'date': d(45), 'detail': 'Bristol depot due to open', 'basis': 'stated', 'system_family': '', 'source_url': f'{NEWS}-bristol'},
            {'kind': 'site_opening', 'date': month(320), 'detail': 'Swindon depot due to open', 'basis': 'stated', 'system_family': '', 'source_url': 'https://planning.example/swindon/fernhill'}],
        'incumbent': {'name': '', 'detail': '', 'basis': 'unknown', 'source_url': ''}, 'competitors': [],
        'people': [{'name': 'Priya Shah', 'role': 'Head of Property', 'influence': 'decision_maker', 'why': 'Leads the depot programme',
                    'source_url': f'{NEWS}-programme', 'quote': 'said Priya Shah, Head of Property at Fernhill Parcels'}],
        'contact_routes': [{'kind': 'switchboard', 'value': '0113 496 0000', 'label': 'Switchboard', 'source_url': 'https://www.fernhill-parcels.example/contact',
                            'quote': 'Call us on 0113 496 0000'}],
        'approach': {'angle': '', 'opening_line': '', 'offer': '', 'questions': []}, 'services': ['fire_alarm', 'cctv', 'access_control', 'intruder'],
        'unknowns': ['Which supplier maintains the opened depots', 'Whether the Bristol packages are already let']}


def tender_result(today: date) -> dict:
    deadline = (today + timedelta(days=21)).isoformat()
    url = ASHBY_URL
    return {'kind': 'published_procurement', 'category': 'live_procurement', 'category_label': 'Live tender', 'customer': ASHBY,
            'title': 'Fire alarm and emergency lighting maintenance across council buildings', 'supplier': '', 'timing': deadline, 'timing_basis': 'published deadline',
            'nation': 'England', 'fit': 'core', 'value': {'type': 'unknown', 'basis': 'No value is published.'}, 'unknowns': [], 'counter_evidence': [],
            'link': {'confidence': 'exact', 'records': 1, 'sources': ['Contracts Finder']},
            'brief': {'why_it_matters': 'A live tender for services the profile sells.', 'missing_information': ['Mandatory accreditations', 'Evaluation weightings'],
                      'contract_lifecycle': '', 'procurement_route': 'Open procedure'},
            'evidence': [{'source_revision_id': 0, 'source_url': url, 'source': 'Contracts Finder', 'record_key': 'living-fixture-ashby', 'ocid': 'ocds-fixture-ashby-2026',
                          'published_at': (today - timedelta(days=9)).isoformat()}],
            'next_actions': ['Review the tender documents'], 'next_action': 'Review the tender documents', 'priority': {'tier': 1, 'reasons': ['Live tender']}}


def load_private(db: Session, today: date | None = None) -> str:
    """The workspace's own research (Fernhill Parcels). Runs in the workspace's session."""
    today = today or date.today()
    now = datetime.now(UTC)
    found = db.scalar(select(Prospect).where(Prospect.dedup_key == 'fernhill parcels'))
    if found is None:
        found = Prospect(dedup_key='fernhill parcels', name=FERNHILL, status='new', data=fernhill_data(today), created_at=now - timedelta(days=3), updated_at=now - timedelta(days=3))
        db.add(found)
        db.flush()
    return f'pr:{found.id}'


def _revision(db: Session, record_key: str, url: str, raw: dict, moment: datetime) -> SourceRevision:
    row = SourceRevision(source_key='contracts_finder', record_key=record_key, ocid=raw['ocid'], source_url=url, content_hash=hashlib.sha256(record_key.encode()).hexdigest(),
                         raw=raw, published_at=datetime.fromisoformat(raw['date'][:19]), retrieved_at=moment, last_seen=moment, superseded_at=None)
    db.add(row)
    db.flush()
    return row


def _previous_award(db: Session, today: date, moment: datetime) -> None:
    """Ashby Vale's contract for the same work, in term until after the new tender closes."""
    d = lambda days: (today + timedelta(days=days)).isoformat()  # noqa: E731
    raw = ashby_award(today)
    revision = _revision(db, 'living-fixture-ashby-award', ASHBY_AWARD_URL, raw, moment)
    facts = {'suppliers': [ASHBY_HOLDER], 'company_numbers': [], 'supplier_entity_ids': [], 'identity_status': 'name_only', 'description': raw['tender']['description'],
             'value': {'published_total': 412000.0, 'estimated_annualised': 137300.0, 'type': 'estimated_annualised', 'basis': 'Published award value divided by the published term of 3.0 years.'},
             'start_date': d(-975), 'published_end_date': d(120), 'estimated_end_date': None, 'end_basis': 'award_contract_period', 'latest_end': None, 'latest_end_basis': None,
             'extension_note': None, 'replacement': None, 'contradictions': [], 'checks': [], 'framework_stage': None, 'published': d(-990), 'award_date': d(-990),
             'source_urls': [ASHBY_AWARD_URL],
             'evidence': [{'source_revision_id': revision.id, 'source_url': ASHBY_AWARD_URL, 'source_key': 'contracts_finder', 'record_key': 'living-fixture-ashby-award',
                           'source': 'Contracts Finder', 'published_at': f'{d(-990)}T09:00:00', 'ocid': raw['ocid'],
                           'fields': ['buyer.name', 'tender.title', 'awards.suppliers', 'awards.contractPeriod.endDate']}]}
    db.add(MarketContract(canonical_key='living-fixture:ashby-previous', ocid=raw['ocid'], buyer=ASHBY, supplier=ASHBY_HOLDER, title=raw['tender']['title'], fit='core', nation='England',
                          lifecycle_status='in_term_published', category=None, end_date=d(120), end_estimated=False, facts=facts, first_seen=moment, last_evaluated=moment,
                          last_verified=moment))
    db.flush()


def load_public(db: Session, today: date | None = None) -> str:
    """The shared public record (the Ashby Vale tender, its notice and the council's previous award). Hosted, this needs a
    system session: public tables are read-only to workspaces."""
    today = today or date.today()
    now = datetime.now(UTC)
    tender = db.scalar(select(MarketOpportunity).where(MarketOpportunity.dedup_key == 'living-fixture:ashby'))
    if tender is None:
        notice = _revision(db, 'living-fixture-ashby', ASHBY_URL, ashby_notice(today), now)
        _previous_award(db, today, now)
        tender = MarketOpportunity(dedup_key='living-fixture:ashby', first_seen=now - timedelta(days=8), last_evaluated=now)
        db.add(tender)
        db.flush()
        result = tender_result(today)
        result['evidence'][0]['source_revision_id'] = notice.id
        version = MarketOpportunityRevision(opportunity_id=tender.id, fingerprint='living-fixture', result=result, created_at=now)
        db.add(version)
        db.flush()
        tender.current_revision_id = version.id
        db.flush()
    return f'mo:{tender.id}'


def signal_result(today: date) -> dict:
    """A stored signal in the shape the collectors write: the records one by one, how independent they are, the explanations
    still open, and the caution that goes with every inference."""
    judged, early = (today - timedelta(days=150)).isoformat(), (today - timedelta(days=12)).isoformat()
    finding = (f'The Regulator of Social Housing graded {FENWICK} C3. It says: The trust could not evidence that actions arising from fire risk assessments in its sheltered '
               f'schemes were completed within its own timescales. Published {judged}.')
    engagement = f'{FENWICK} published an early notice: "{FENWICK_EARLY_TITLE}"'
    why = 'Customer level, not tied to one contract. SalesIntel holds 1 relevant published contract for this customer.'
    unknown = 'Whether the condition continues today.'
    reasons = ['Independent sources agree something is happening.',
               'Relevant, timely and supported by more than one source. This justifies investigation, not an assumption of a contract.']
    actions = ['Confirm the finding in the source and whether the customer has a remediation plan.', "Review the customer's published procurement plan."]

    def record(n: int, kind: str, label: str, day: str, group: str, reliability: str, url: str, statement: str) -> dict:
        return {'fingerprint': f'living-fixture-signal-{n}', 'signal_type': kind, 'label': label, 'occurred_on': day, 'source_group': group, 'reliability': reliability,
                'attribution': 'customer', 'capture': 'automatic', 'source_url': url, 'scope': 'customer', 'statement': statement}
    supporting = [record(1, 'regulator_compliance_finding', 'Regulator finding on fire safety compliance', judged, 'regulator', 'statutory_record', FENWICK_FINDING_URL, finding),
                  record(2, 'market_engagement', 'Official market engagement', early, 'procurement', 'official_notice', FENWICK_EARLY_URL, engagement)]
    return {'kind': 'inferred_signal', 'category': 'inferred_signal', 'category_label': 'Possible requirement before any tender', 'customer': FENWICK, 'title': finding[:160],
            'supplier': None, 'timing': None, 'timing_basis': 'none', 'nation': 'England', 'fit': 'inferred', 'sector': None,
            'value': {'published_total': None, 'framework_ceiling': None, 'type': 'unknown', 'basis': 'No contract value applies to this signal yet.'},
            'priority': {'tier': 1, 'reasons': reasons}, 'unknowns': [unknown], 'counter_evidence': [], 'link': {'confidence': 'possible', 'records': 2, 'sources': ['procurement', 'regulator']},
            'brief': {'why_it_matters': why, 'missing_information': [unknown], 'next_action': actions[0], 'contract_lifecycle': 'No contract linked', 'procurement_route': 'Not published'},
            'evidence': [{'source_revision_id': 0, 'source_url': x['source_url'], 'source_key': x['source_group'], 'record_key': x['signal_type'], 'source': x['label'],
                          'published_at': x['occurred_on'], 'ocid': None, 'fields': []} for x in supporting],
            'next_actions': actions, 'next_action': actions[0],
            'signal': {'label': 'Possible requirement before any tender', 'decision': 'pursue', 'decision_reasons': reasons, 'evidence_state': 'independently_corroborated',
                       'independent_sources': ['procurement', 'regulator'], 'supporting': supporting, 'contradicting': [], 'unknowns': [unknown], 'actions': actions,
                       'caution': SIGNAL_CAUTION, 'link': why,
                       'explanations': [
                           {'explanation': 'contractor_delivery', 'label': 'The current contractor may be under-delivering', 'status': 'not_established', 'against': [],
                            'test': 'Does the customer attribute the problem to this contractor under this contract?'},
                           {'explanation': 'ageing_assets', 'label': 'Ageing or obsolete systems', 'status': 'possible', 'against': [],
                            'test': 'Do published asset or backlog records show end-of-life equipment?'},
                           {'explanation': 'deferred_compliance', 'label': 'Compliance work has been deferred', 'status': 'supported', 'against': [],
                            'test': 'Does a regulator or audit place the backlog with the customer rather than a contractor?'}]}}


def load_signal(db: Session, today: date | None = None) -> str:
    """The shared public signal about Fenwick Housing Trust. Hosted, this needs a system session, like every public record."""
    today = today or date.today()
    now = datetime.now(UTC)
    row = db.scalar(select(MarketOpportunity).where(MarketOpportunity.dedup_key == 'living-fixture:fenwick-signal'))
    if row is None:
        row = MarketOpportunity(dedup_key='living-fixture:fenwick-signal', first_seen=now - timedelta(days=3), last_evaluated=now)
        db.add(row)
        db.flush()
        version = MarketOpportunityRevision(opportunity_id=row.id, fingerprint='living-fixture-signal', result=signal_result(today), created_at=now)
        db.add(version)
        db.flush()
        row.current_revision_id = version.id
        db.flush()
    return f'mo:{row.id}'


def load(db: Session, today: date | None = None) -> dict:
    """Insert the fictional records once (local mode: one session holds them all). Returns their keys."""
    return {'fernhill': load_private(db, today), 'tender': load_public(db, today), 'signal': load_signal(db, today)}
