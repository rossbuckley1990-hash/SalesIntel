"""Contract Atlas: who holds fire and security work, for whom, until when, on what evidence.

Adversarial by design, on an entirely fictional market (app/services/atlas_fixtures.py):
- identity: two spellings of one legal name join; a parent and its subsidiary never merge; one name published with two
  company numbers is left as a conflict; a lookalike "Holdings" name stays apart;
- contracts: a framework appointment is not a contract and its ceiling is not revenue; installation is not maintenance; a
  passed end date is "status not established", never "ended"; a similar newer notice is not a confirmed replacement;
- private research keeps only what the retrieved pages say, never a value or an end date, and an old case study is history;
- researched relationships belong to the workspace that paid for them, and research needs an approved budget."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base, get_db
from app.main import create_app
from app.models.atlas import AtlasContractor, AtlasIdentityConflict, AtlasRelationship
from app.services import atlas, atlas_fixtures, atlas_research, jobs
from app.services.ai_costs import Meter
from app.services.research_replay import replay_post
from tenancy_support import hosted  # noqa: F401
from test_shadow_radar import workspace

TODAY = date.today()
REASON_PARTS = {'facts', 'mechanism', 'alternatives', 'disconfirming', 'missing', 'action', 'next_step'}


@pytest.fixture
def market(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'atlas.db'}", connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    db = Session(engine)
    atlas_fixtures.load(db, TODAY)
    db.commit()
    stats = atlas.ensure_built(db)
    db.commit()
    yield db, engine, stats
    db.close()
    engine.dispose()


def contractor(db, key: str) -> AtlasContractor:
    return db.scalar(select(AtlasContractor).where(AtlasContractor.key == key))


def by_title(record: dict, title: str) -> dict:
    return next(c for c in record['contracts'] if c['title'] == title)


# ------------------------------------------------------------------ identity

def test_identity_joins_one_legal_name_and_keeps_parents_lookalikes_and_conflicts_apart(market):
    db, _, stats = market
    assert stats['rebuilt'] and stats['conflicts'] == 1
    kestrel = atlas.contractor_record(db, contractor(db, 'coh:09876543').id, today=TODAY)
    # "Kestrel Fire Services Ltd" (numbered) and "Kestrel Fire Services Limited" (no number) are the identical legal name.
    assert {c['title'] for c in kestrel['contracts']} == {'Fire alarm and emergency lighting maintenance', 'Supply and installation of CCTV at council depots',
                                                          'Fire Safety Systems Framework'}
    assert by_title(kestrel, 'Supply and installation of CCTV at council depots')['match']['basis'] == 'identical_legal_name'
    # The holding company is a separate contractor: the group link is shown, but no contract moves between them.
    assert kestrel['identity']['group']['parent_name'] == 'KESTREL FIRE HOLDINGS LTD'
    parent = atlas.contractor_record(db, contractor(db, 'coh:09876500').id, today=TODAY)
    assert [c['title'] for c in parent['contracts']] == ['Sprinkler system servicing']
    # One name, two published company numbers: two contractors and a conflict for a person, never a merge.
    conflict = db.scalar(select(AtlasIdentityConflict))
    assert conflict.company_numbers == ['11122233', '44455566'] and conflict.status == 'unresolved'
    assert contractor(db, 'coh:11122233') and contractor(db, 'coh:44455566')
    assert atlas.contractor_record(db, contractor(db, 'coh:11122233').id, today=TODAY)['identity']['conflicts']
    # A lookalike name is not the same company.
    holdings = contractor(db, 'name:brightwater security holdings ltd')
    assert holdings and holdings.identity_basis == 'name_only'
    # Without a number, "&" and "and", "Ltd" and "Limited" are formatting: one name-only contractor.
    moorland = contractor(db, 'name:moorland fire and security ltd')
    assert moorland.contract_count == 2 and moorland.company_number is None


def test_a_rebuild_keeps_contractor_ids(market):
    db, _, _ = market
    before = {c.key: c.id for c in db.scalars(select(AtlasContractor))}
    atlas.rebuild(db)
    db.commit()
    assert {c.key: c.id for c in db.scalars(select(AtlasContractor))} == before  # researched relationships stay linked
    assert atlas.ensure_built(db) == {'rebuilt': False}  # nothing changed in the Market Network


# ------------------------------------------------------------------ what each contract shows

def test_contracts_keep_framework_scope_value_and_date_distinctions(market):
    db, _, _ = market
    kestrel = atlas.contractor_record(db, contractor(db, 'coh:09876543').id, today=TODAY)
    framework = by_title(kestrel, 'Fire Safety Systems Framework')
    assert framework['status']['code'] == 'framework' and framework['route']['code'] == 'framework_appointment'
    assert framework['value']['kind'] == 'framework_ceiling' and 'not this supplier' in framework['value']['basis']
    assert not framework['reasons']  # an appointment to a framework is not a contract to win
    housing = by_title(kestrel, 'Fire alarm and emergency lighting maintenance')
    assert housing['status']['code'] == 'end_approaching' and housing['scope']['code'] == 'maintenance'
    assert housing['region'] == 'Yorkshire and the Humber' and housing['value']['annual_estimate'] == 60000.0
    cctv = by_title(kestrel, 'Supply and installation of CCTV at council depots')
    assert cctv['scope']['code'] == 'installation'
    assert cctv['status']['code'] == 'end_passed_unknown' and 'not established' in cctv['status']['label']
    assert not any(w in json.dumps(cctv['status']).lower() for w in ('terminated', 'expired', 'is ended'))
    moorland = atlas.contractor_record(db, contractor(db, 'name:moorland fire and security ltd').id, today=TODAY)
    assert by_title(moorland, 'Fire alarm servicing')['status']['code'] == 'replacement_identified'
    assert 'not a confirmed replacement' in by_title(moorland, 'Fire alarm servicing')['status']['detail']
    assert by_title(moorland, 'Fire alarm and emergency lighting maintenance')['status']['code'] == 'extension_possible'
    holdings = atlas.contractor_record(db, contractor(db, 'name:brightwater security holdings ltd').id, today=TODAY)
    assert holdings['contracts'][0]['status']['code'] == 'term_not_published'
    events = [e['basis'] for e in housing['timeline']]
    assert 'publication date' in events and 'contract event' in events and 'retrieval' in events  # dates are kept apart


def test_reasons_explain_themselves_and_never_estimate_a_probability(market):
    db, _, _ = market
    prefs = {'services': ['fire_alarm'], 'territory': ['England'], 'company_name': 'Mitie Fire & Security'}
    kestrel = atlas.contractor_record(db, contractor(db, 'coh:09876543').id, prefs=prefs, today=TODAY)
    assert [c['title'] for c in kestrel['worth_investigating']] == ['Fire alarm and emergency lighting maintenance']  # CCTV is not in the profile
    for c in kestrel['contracts']:
        for r in c['reasons']:
            assert REASON_PARTS <= set(r) and r['facts'] and r['alternatives'] and r['missing']
    text = json.dumps(kestrel).lower()
    assert 'probability' not in text and 'likelihood' not in text and 'confidence' not in text
    ours = db.scalar(select(AtlasContractor).where(AtlasContractor.display_name == 'Mitie Fire & Security Ltd'))
    own = atlas.contractor_record(db, ours.id, prefs=prefs, today=TODAY)
    assert own['yours'] and own['worth_investigating'] == []  # your own contracts are not opportunities to win


def test_search_by_name_region_service_and_window(market):
    db, _, _ = market
    found = atlas.search(db, 'kestrel', today=TODAY)
    assert {c['name'] for c in found['contractors']} == {'KESTREL FIRE SERVICES LTD', 'KESTREL FIRE HOLDINGS LTD'}
    yorkshire = atlas.search(db, '', region='Yorkshire and the Humber', ending_months=18, today=TODAY)
    # The whole market, your own contracts included (Leeds Example Trust); only reasons to investigate leave them out.
    assert {c['name'] for c in yorkshire['customers']} == {'Fenwick Housing Trust', 'Craven Homes', 'Leeds Example Trust'}
    alarms = atlas.search(db, '', discipline='intruder', today=TODAY)
    assert [c['name'] for c in alarms['customers']] == ['Tees Valley College']


def test_a_customer_shows_published_reported_and_unknown_suppliers_separately(market):
    db, _, _ = market
    assert atlas.customer_record(db, 'fenwick housing trust', today=TODAY)['incumbent']['state'] == 'published'
    calder = atlas.customer_record(db, 'calder valley council', today=TODAY)
    assert calder['incumbent'] == {'state': 'unknown', 'label': 'Current supplier not publicly established'}  # the only contract's end has passed
    assert atlas.customer_record(db, 'northmoor care group', today=TODAY)['incumbent']['state'] == 'unknown'


def test_a_framework_with_several_suppliers_lists_each_supplier_once(tmp_path):
    # A framework names several suppliers on one notice. The customer's record lists one row per supplier, and each row has
    # its own party_id: lists keyed by the contract alone repeat a key, and the browser may then drop or duplicate rows.
    from app.models.market_contract import MarketContract
    engine = create_engine(f"sqlite:///{tmp_path / 'atlas.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        atlas_fixtures.load(db, TODAY)
        framework = db.scalar(select(MarketContract).where(MarketContract.title == 'Fire Safety Systems Framework'))
        framework.facts = {**framework.facts, 'suppliers': ['Kestrel Fire Services Ltd', 'Moorland Fire & Security Ltd']}
        db.commit()
        atlas.ensure_built(db)
        db.commit()
        rows = [c for c in atlas.customer_record(db, 'pennine procurement partnership', today=TODAY)['contracts'] if c['key'] == f'mc:{framework.id}']
        assert sorted(r['supplier'].lower() for r in rows) == ['kestrel fire services ltd', 'moorland fire & security ltd']
        assert len({r['party_id'] for r in rows}) == 2
    engine.dispose()


# ------------------------------------------------------------------ private relationships from public pages

def test_private_research_keeps_only_what_the_pages_say(market):
    db, _, _ = market
    meter = Meter(replay_post, 'claude-sonnet-5-5', 'replay', simulated=True)
    kestrel = contractor(db, 'coh:09876543')
    result = atlas_research.run(db, 'contractor', 'Kestrel Fire Services Ltd', meter, contractor_id=kestrel.id)
    db.commit()
    rows = {r.customer_name: r for r in db.scalars(select(AtlasRelationship))}
    northmoor = rows['Northmoor Care Group']
    assert northmoor.status == 'reported' and northmoor.quote_verified and northmoor.currency == 'stated_ongoing'
    assert northmoor.services == ['fire_alarm', 'emergency_lighting'] and northmoor.published_on == '2025-03'
    brightline = rows['Brightline Retail']
    assert brightline.kind == 'subcontract' and brightline.intermediary == 'Castleford FM Services' and brightline.status == 'reported'
    assert rows['Harbour Point Hotels'].currency == 'historical'  # a 2019 case study is a past job, not a current contract
    pennine = rows['Pennine Leisure']
    assert pennine.status == 'reported' and not pennine.quote_verified  # the paraphrase is not on the page
    assert pennine.duration_stated == '' and pennine.currency == 'not_stated'  # "five-year agreement" is not on the page either
    assert rows['Fenwick Housing Trust'].status == 'unsupported'  # the page never names this customer
    assert rows['Moorgate Logistics'].status == 'unsupported' and not rows['Moorgate Logistics'].checks['source_retrieved']
    assert result['reported'] == 4 and result['unsupported'] == 2 and result['historical'] == 1
    view = atlas.contractor_record(db, kestrel.id, today=TODAY)
    shown = {r['customer'] for r in view['relationships']}
    assert shown == {'Northmoor Care Group', 'Brightline Retail', 'Harbour Point Hotels', 'Pennine Leisure'} and view['unsupported_relationships'] == 2
    for r in view['relationships']:
        assert not {'value', 'amount', 'end', 'end_date'} & set(r) and 'not established' in r['caveat'] or r['currency'] == 'historical'
    assert atlas.customer_record(db, 'northmoor care group', today=TODAY)['incumbent']['state'] == 'reported'
    assert [c['name'] for c in atlas.search(db, 'northmoor', today=TODAY)['customers']] == ['Northmoor Care Group']  # findable once researched
    # A person's decision survives a new run, and a new run adds no duplicates.
    northmoor.status = 'confirmed'
    db.commit()
    atlas_research.run(db, 'contractor', 'Kestrel Fire Services Ltd', meter, contractor_id=kestrel.id)
    db.commit()
    assert len(db.scalars(select(AtlasRelationship)).all()) == 6
    assert db.get(AtlasRelationship, northmoor.id).status == 'confirmed'


def test_researching_a_customer_finds_its_reported_supplier(market):
    db, _, _ = market
    meter = Meter(replay_post, 'claude-sonnet-5-5', 'replay', simulated=True)
    result = atlas_research.run(db, 'customer', 'Northmoor Care Group', meter)
    db.commit()
    assert result['reported'] == 1
    row = db.scalar(select(AtlasRelationship))
    assert row.contractor_id == contractor(db, 'coh:09876543').id  # matched to the published contractor by its exact name


# ------------------------------------------------------------------ the API, accounts and workspaces

@pytest.fixture
def local(market):
    db, engine, _ = market
    session = Session(engine)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app), session
    session.close()


def test_the_api_answers_by_contractor_customer_and_account(local):
    client, session = local
    found = client.get('/api/si/atlas/search', params={'q': 'brightwater'}).json()
    assert len(found['contractors']) == 3 and found['options']['regions']
    record = client.get(f"/api/si/atlas/contractors/{found['contractors'][0]['id']}").json()
    assert record['coverage']['private'].startswith('Published case studies and announcements not researched')
    assert client.get('/api/si/atlas/customers/Fenwick Housing Trust').json()['incumbent']['state'] == 'published'
    assert client.get('/api/si/atlas/contractors/99999').status_code == 404
    # Investigating a competitor-held contract creates the account, linked to the contract and its evidence.
    contract = next(c for c in atlas.contractor_record(session, session.scalar(select(AtlasContractor).where(AtlasContractor.key == 'coh:09876543')).id,
                                                       today=TODAY)['contracts'] if c['status']['code'] == 'end_approaching')
    linked = client.post(f"/api/si/discover/{contract['key']}/account", json={}).json()
    assert linked['created']
    account = client.get(f"/api/si/accounts/{linked['account_id']}").json()
    assert account['name'] == 'Fenwick Housing Trust'
    source = next(s for s in account['sources'] if s['key'] == contract['key'])
    assert source['supplier'] == 'KESTREL FIRE SERVICES LTD' and source['evidence'] and source['category_label'] == 'Competitor-held contract'
    assert client.get(f"/api/si/atlas/account/{linked['account_id']}").json()['incumbent']['state'] == 'published'
    assert client.post('/api/si/atlas/research', json={'direction': 'contractor', 'subject': 'Kestrel'}).status_code == 403  # no provider configured here


def test_research_needs_a_budget_and_its_findings_stay_in_the_workspace(hosted, monkeypatch):
    h = hosted
    with h.system() as db:
        atlas_fixtures.load(db, TODAY)
        db.commit()
    from app.services import spend
    monkeypatch.setattr(spend, 'live_provider', lambda: True)  # as if a real, paid provider were configured
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')
    bob, _ = workspace(h, 'bob', 'Beta Security Ltd')
    found = alice.get('/api/si/atlas/search', params={'q': 'kestrel fire services'}).json()
    kestrel = next(c for c in found['contractors'] if c['company_number'] == '09876543')
    body = {'direction': 'contractor', 'subject': 'Kestrel Fire Services Ltd', 'contractor_id': kestrel['id']}
    refused = alice.post('/api/si/atlas/research', json=body)
    assert refused.status_code == 409 and 'Nothing was started or charged' in refused.json()['detail']
    assert alice.post('/api/si/research-budget', json={'amount_cents': 300, 'note': 'Atlas test'}).status_code == 200
    started = alice.post('/api/si/atlas/research', json=body)
    assert started.status_code == 200, started.text
    jobs.drain(h.engine)
    mine = alice.get(f"/api/si/atlas/contractors/{kestrel['id']}").json()
    assert len(mine['relationships']) == 4 and mine['research']['status'] == 'succeeded' and mine['research']['cost_cents'] > 0
    theirs = bob.get(f"/api/si/atlas/contractors/{kestrel['id']}").json()
    assert theirs['relationships'] == [] and theirs['research'] is None  # which competitor Alpha researched is Alpha's business
    assert len(theirs['contracts']) == len(mine['contracts']) == 3  # published contracts are shared public facts
    assert bob.get('/api/si/atlas/customers/Northmoor Care Group').json()['incumbent']['state'] == 'unknown'
    assert alice.get('/api/si/atlas/customers/Northmoor Care Group').json()['incumbent']['state'] == 'reported'
