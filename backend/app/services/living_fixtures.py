"""Fictional records for the Living Opportunity: tests, browser tests and screenshots. Every organisation, person, page
and number here is invented.

- Fernhill Parcels: a parcel company's depot programme (some depots opened, others planned), a main contractor already
  appointed for one site, a named head of property, and a switchboard route. The same shape as a real multi-site
  logistics expansion, so the reveal can be judged on it.
- Ashby Vale Council: a live published tender for fire alarm and emergency lighting maintenance.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.models.prospect import Prospect

FERNHILL = 'Fernhill Parcels Ltd'
NEWS = 'https://news.example/fernhill'


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
    url = 'https://www.contractsfinder.service.gov.uk/Notice/living-fixture-ashby'
    return {'kind': 'published_procurement', 'category': 'live_procurement', 'category_label': 'Live tender', 'customer': 'Ashby Vale Council',
            'title': 'Fire alarm and emergency lighting maintenance across council buildings', 'supplier': '', 'timing': deadline, 'timing_basis': 'published deadline',
            'nation': 'England', 'fit': 'core', 'value': {'type': 'unknown', 'basis': 'No value is published.'}, 'unknowns': [], 'counter_evidence': [],
            'link': {'confidence': 'exact', 'records': 1, 'sources': ['Contracts Finder']},
            'brief': {'why_it_matters': 'A live tender for services the profile sells.', 'missing_information': ['Mandatory accreditations', 'Evaluation weightings'],
                      'contract_lifecycle': '', 'procurement_route': 'Open procedure'},
            'evidence': [{'source_revision_id': 0, 'source_url': url, 'source': 'Contracts Finder', 'record_key': 'living-fixture-ashby',
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


def load_public(db: Session, today: date | None = None) -> str:
    """The shared public record (the Ashby Vale tender). Hosted, this needs a system session: public tables are read-only to workspaces."""
    today = today or date.today()
    now = datetime.now(UTC)
    tender = db.scalar(select(MarketOpportunity).where(MarketOpportunity.dedup_key == 'living-fixture:ashby'))
    if tender is None:
        tender = MarketOpportunity(dedup_key='living-fixture:ashby', first_seen=now - timedelta(days=8), last_evaluated=now)
        db.add(tender)
        db.flush()
        version = MarketOpportunityRevision(opportunity_id=tender.id, fingerprint='living-fixture', result=tender_result(today), created_at=now)
        db.add(version)
        db.flush()
        tender.current_revision_id = version.id
        db.flush()
    return f'mo:{tender.id}'


def load(db: Session, today: date | None = None) -> dict:
    """Insert the fictional records once (local mode: one session holds both). Returns their keys."""
    return {'fernhill': load_private(db, today), 'tender': load_public(db, today)}
