"""A small, entirely fictional fire and security market for Contract Atlas tests, browser tests and screenshots.

Every organisation, company number, address and web page here is invented. The cases each test an identity or contract
rule: one company under two spellings of its legal name, a parent and its subsidiary kept apart, one name published with
two company numbers, a lookalike name, a framework appointment, an extension window, a successor notice and the
workspace's own contract. Dates are relative to the load date, so the statuses stay meaningful.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_contract import MarketContract
from app.models.market_graph import MarketRelationship
from app.models.market_network import MarketAward, MarketEntity, SourceRevision

PREFIX = 'atlas-fixture:'
KESTREL = ('Kestrel Fire Services Ltd', '09876543')
KESTREL_PARENT = ('Kestrel Fire Holdings Ltd', '09876500')
BRIGHTWATER_A = ('Brightwater Security Ltd', '11122233')
BRIGHTWATER_B = ('Brightwater Security Ltd', '44455566')


def _contracts(today: date) -> list[dict]:
    d = lambda days: (today + timedelta(days=days)).isoformat()  # noqa: E731
    return [
        {'key': 'fenwick', 'buyer': 'Fenwick Housing Trust', 'postcode': 'HG1 2AB', 'nation': 'England', 'supplier': 'Kestrel Fire Services Ltd', 'number': KESTREL[1],
         'title': 'Fire alarm and emergency lighting maintenance', 'fit': 'core',
         'description': 'Planned preventative maintenance, testing and reactive repairs of fire alarm and emergency lighting systems across 46 sheltered housing schemes.',
         'start': d(-1160), 'end': d(300), 'published': d(-1190), 'value': {'published_total': 240000.0, 'estimated_annualised': 60000.0, 'type': 'estimated_annualised',
         'basis': 'Published award value divided by the published term of 4.0 years.'}},
        {'key': 'calder', 'buyer': 'Calder Valley Council', 'postcode': 'HX1 1UJ', 'nation': 'England', 'supplier': 'Kestrel Fire Services Limited', 'number': None,
         'title': 'Supply and installation of CCTV at council depots', 'fit': 'core',
         'description': 'Supply and installation of new CCTV cameras and recording equipment at three depots.',
         'start': d(-700), 'end': d(-60), 'published': d(-730), 'value': {'published_total': 85000.0, 'type': 'published_total', 'basis': 'As published.'}},
        {'key': 'pennine-framework', 'buyer': 'Pennine Procurement Partnership', 'postcode': 'LS1 4AP', 'nation': 'England', 'supplier': 'Kestrel Fire Services Ltd',
         'number': KESTREL[1], 'title': 'Fire Safety Systems Framework', 'fit': 'framework',
         'description': 'A framework agreement for fire safety systems maintenance for member housing associations. Call-offs are awarded separately.',
         'start': d(-300), 'end': d(1100), 'published': d(-330), 'value': {'framework_ceiling': 5000000.0, 'type': 'framework_ceiling', 'basis': 'Maximum value of the framework.'}},
        {'key': 'whitby', 'buyer': 'Whitby Harbour Authority', 'postcode': 'YO21 3PU', 'nation': 'England', 'supplier': 'Kestrel Fire Holdings Ltd', 'number': KESTREL_PARENT[1],
         'title': 'Sprinkler system servicing', 'fit': 'core', 'description': 'Annual servicing and inspection of wet sprinkler systems at the harbour buildings.',
         'start': d(-200), 'end': d(1000), 'published': d(-230), 'value': None},
        {'key': 'tees', 'buyer': 'Tees Valley College', 'postcode': 'TS1 3BA', 'nation': 'England', 'supplier': 'Brightwater Security Ltd', 'number': BRIGHTWATER_A[1],
         'title': 'Intruder alarm maintenance and monitoring', 'fit': 'core',
         'description': 'Maintenance of intruder alarm systems and alarm monitoring across two campuses.',
         'start': d(-900), 'end': d(150), 'published': d(-930), 'value': {'published_total': 64000.0, 'type': 'published_total', 'basis': 'As published.'}},
        {'key': 'durham', 'buyer': 'Durham Coast Trust', 'postcode': 'DH1 3HP', 'nation': 'England', 'supplier': 'Brightwater Security Ltd', 'number': BRIGHTWATER_B[1],
         'title': 'Access control maintenance', 'fit': 'core', 'description': 'Servicing and repair of access control and door entry systems.',
         'start': d(-100), 'end': d(800), 'published': d(-120), 'value': None},
        {'key': 'durham-holdings', 'buyer': 'Durham Coast Trust', 'postcode': 'DH1 3HP', 'nation': 'England', 'supplier': 'Brightwater Security Holdings Ltd', 'number': None,
         'title': 'CCTV maintenance', 'fit': 'core', 'description': 'Maintenance of CCTV systems.', 'start': d(-400), 'end': None, 'published': d(-420), 'value': None},
        {'key': 'ryedale', 'buyer': 'Ryedale Schools Trust', 'postcode': 'YO17 7HH', 'nation': 'England', 'supplier': 'Moorland Fire & Security Ltd', 'number': None,
         'title': 'Fire alarm servicing', 'fit': 'core', 'description': 'Servicing and testing of fire alarm systems in five schools.',
         'start': d(-500), 'end': d(-200), 'published': d(-520), 'value': None,
         'replacement': {'title': 'Fire alarm servicing 2026 to 2029', 'published': d(-150), 'url': 'https://www.contractsfinder.service.gov.uk/Notice/atlas-fixture-ryedale-2026'}},
        {'key': 'craven', 'buyer': 'Craven Homes', 'postcode': 'BD23 1UD', 'nation': 'England', 'supplier': 'Moorland Fire and Security Limited', 'number': None,
         'title': 'Fire alarm and emergency lighting maintenance', 'fit': 'core', 'description': 'Maintenance of fire alarm and emergency lighting systems in 12 blocks.',
         'start': d(-1035), 'end': d(60), 'latest_end': d(425), 'latest_end_basis': 'A published option to extend by 12 months', 'published': d(-1060), 'value': None},
        {'key': 'own', 'buyer': 'Leeds Example Trust', 'postcode': 'LS2 9JT', 'nation': 'England', 'supplier': 'Mitie Fire & Security Ltd', 'number': None,
         'title': 'Fire alarm maintenance', 'fit': 'core', 'description': 'Maintenance of fire alarm systems.', 'start': d(-600), 'end': d(200), 'published': d(-630), 'value': None},
    ]


def load(db: Session, today: date | None = None) -> dict:
    """Insert the fictional market once. Returns what it holds."""
    today = today or date.today()
    if db.scalar(select(MarketContract.id).where(MarketContract.canonical_key.like(f'{PREFIX}%'))):
        return {'loaded': False}
    moment = datetime.now(UTC)
    entities: dict[str, MarketEntity] = {}

    def entity(name: str, number: str) -> MarketEntity:
        if number not in entities:
            entities[number] = MarketEntity(name=name.upper(), identifier_scheme='GB-COH', identifier_value=number, identity_status='published_company_number',
                                            first_seen=moment, last_seen=moment)
            db.add(entities[number])
            db.flush()
        return entities[number]

    for i, c in enumerate(_contracts(today)):
        key = c['key']
        url = f'https://www.contractsfinder.service.gov.uk/Notice/atlas-fixture-{key}'
        supplier_party = {'id': f'GB-COH-{c["number"]}' if c['number'] else f'GB-CFS-fixture-{i}', 'name': c['supplier']}
        raw = {'ocid': f'ocds-fixture-{key}', 'id': f'fixture-{key}', 'date': f"{c['published']}T09:00:00Z",
               'buyer': {'id': f'GB-CFS-buyer-{i}', 'name': c['buyer']},
               'parties': [{'name': c['buyer'], 'roles': ['buyer'], 'address': {'postalCode': c['postcode'], 'countryName': 'UK'}},
                           {**supplier_party, 'roles': ['supplier'], 'identifier': {'scheme': 'GB-COH', 'id': c['number']} if c['number'] else {}}],
               'tender': {'title': c['title'], 'description': c['description']},
               'awards': [{'id': f'award-{key}', 'status': 'active', 'date': f"{c['published']}T09:00:00Z", 'suppliers': [supplier_party],
                           'value': {'amount': (c['value'] or {}).get('published_total') or (c['value'] or {}).get('framework_ceiling'), 'currency': 'GBP'} if c['value'] else None,
                           'contractPeriod': {'startDate': f"{c['start']}T00:00:00Z", **({'endDate': f"{c['end']}T23:59:59Z"} if c['end'] else {})}}]}
        revision = SourceRevision(source_key='contracts_finder', record_key=f'atlas-fixture-{key}', ocid=raw['ocid'], source_url=url,
                                  content_hash=hashlib.sha256(key.encode()).hexdigest(), raw=raw, published_at=datetime.fromisoformat(f"{c['published']}T09:00:00"),
                                  retrieved_at=moment, last_seen=moment, superseded_at=None)
        db.add(revision)
        db.flush()
        supplier_entity = entity(c['supplier'], c['number']) if c['number'] else None
        db.add(MarketAward(source_revision_id=revision.id, supplier_id=supplier_entity.id if supplier_entity else None, award_id=f'award-{key}',
                           title=c['title'], buyer=c['buyer'], supplier=c['supplier'], status='active', award_date=c['published'],
                           amount=str((c['value'] or {}).get('published_total') or ''), currency='GBP', classification='unknown'))
        facts = {'suppliers': [c['supplier']], 'company_numbers': [], 'supplier_entity_ids': [], 'identity_status': 'name_only', 'description': c['description'],
                 'value': c['value'] or {'type': 'unknown', 'basis': 'No value is published.'}, 'start_date': c['start'], 'published_end_date': c['end'],
                 'estimated_end_date': None, 'end_basis': 'award_contract_period' if c['end'] else 'none', 'latest_end': c.get('latest_end'),
                 'latest_end_basis': c.get('latest_end_basis'), 'extension_note': None, 'replacement': c.get('replacement'), 'contradictions': [], 'checks': [],
                 'framework_stage': 'framework_agreement' if c['fit'] == 'framework' else None, 'published': c['published'], 'source_urls': [url],
                 'evidence': [{'source_revision_id': revision.id, 'source_url': url, 'source_key': 'contracts_finder', 'record_key': f'atlas-fixture-{key}',
                               'source': 'Contracts Finder', 'published_at': f"{c['published']}T09:00:00", 'ocid': raw['ocid'],
                               'fields': ['buyer.name', 'tender.title', 'awards.suppliers', 'awards.contractPeriod.endDate']}]}
        status = 'framework_agreement' if c['fit'] == 'framework' else ('term_unknown' if not c['end'] else ('historical' if c['end'] < today.isoformat() else 'in_term_published'))
        db.add(MarketContract(canonical_key=f'{PREFIX}{key}', ocid=raw['ocid'], buyer=c['buyer'], supplier=c['supplier'], title=c['title'], fit=c['fit'],
                              nation=c['nation'], lifecycle_status=status, category=None, end_date=c['end'], end_estimated=False, facts=facts,
                              first_seen=moment, last_evaluated=moment, last_verified=moment))
    # A reviewed registry filing: the holding company controls the trading company. They stay separate contractors.
    child, parent = entity(*KESTREL), entity(*KESTREL_PARENT)
    filing = SourceRevision(source_key='companies_house_reviewed', record_key='atlas-fixture-psc-09876543', ocid=None,
                            source_url='https://find-and-update.company-information.service.gov.uk/company/09876543/persons-with-significant-control',
                            content_hash=hashlib.sha256(b'psc').hexdigest(), raw={'kind': 'psc', 'fixture': True}, published_at=moment, retrieved_at=moment,
                            last_seen=moment, superseded_at=None)
    db.add(filing)
    db.flush()
    db.add(MarketRelationship(subject_entity_id=child.id, object_entity_id=parent.id, source_revision_id=filing.id, relation_type='SIGNIFICANT_CONTROL_BY',
                              effective_from=None, effective_to=None, observed_at=moment, assertion_status='reviewed_cached_registry_filing',
                              evidence_excerpt='Kestrel Fire Holdings Ltd has more than 75% of shares in Kestrel Fire Services Ltd.'))
    db.flush()
    return {'loaded': True, 'contracts': len(_contracts(today))}
