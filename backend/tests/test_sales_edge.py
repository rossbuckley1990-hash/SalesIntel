"""The sales edge: what a notice states, and what the published record says about the field. Fictional records only.

- A notice's value, dates, scoring, term, lots and portal are read as published; placeholder values are not values.
- An award notice says how many bids there were and how they were scored.
- A tender brief names the published holder, sets this tender against the last award, and answers from the record
  only what the record states.
- An early notice asks about route and timing, and the next move is to read it.
- A procurement let in lots never names another lot's supplier as the holder.
- Nothing here predicts a winner, a chance or a price for this contract.
- A row in Discover carries what its own notice states, and never another notice's facts.
- A salesperson can order the list by published value, by the next published date or by newest; a framework ceiling is never
  ranked as a contract value, and the default order does not change.
- Today lists the tenders closing soonest and the largest contracts reaching a published end.
- A supplier's footprint counts published contracts only, and states no typical size from too few values.
- A public record before any tender (a regulator's finding, a fire authority's notice, an early notice, a press report) is
  briefed as that record: never as a contract, with no end date, renewal pattern or supplier implied, and with the questions
  that decide whether it is a way in. Its row says what the record is and keeps its place in the list; Today lists the
  best evidenced first."""
from __future__ import annotations

import copy
import json
import re
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models.market_contract import MarketContract
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.models.atlas import AtlasContractor
from app.services import atlas, atlas_fixtures, brief, field, living_fixtures, notice, signals
from app.services import si_core as core
from app.services import si_engage as engage

TODAY = date.today()


def d(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'edge.db'}")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def market(db):
    """The fictional tender, its notice, the buyer's previous award and the fictional contract atlas."""
    keys = living_fixtures.load(db, TODAY)
    atlas_fixtures.load(db, TODAY)
    db.commit()
    atlas.ensure_built(db)
    db.commit()
    return db, keys


def gap(b: dict, key: str) -> dict:
    return next(g for g in b['gaps'] if g['gap'] == key)


def test_a_tender_notice_is_read_as_published():
    f = notice.facts(living_fixtures.ashby_notice(TODAY), source_url=living_fixtures.ASHBY_URL, source='contracts_finder')
    assert f['stage'] == 'tender' and f['reference'] == 'AVC-2026-014'
    assert f['value']['label'] == '£480k' and f['value']['kind'] == 'estimate' and 'excluding VAT' in f['value']['basis']
    assert [(x['key'], x['date']) for x in f['deadlines']] == [('enquiries', d(12)), ('submission', d(21)), ('award', d(63))]
    assert f['deadlines'][1]['time'] == '12:00'
    assert f['criteria']['summary'] == 'Quality 60% / Price 40%' and f['criteria']['same_for_all_lots']
    assert f['term']['label'] == '3 years, plus up to 2 years of extensions'
    assert [lot['value_label'] for lot in f['lots']] == ['£300k', '£180k']
    assert f['portal'] == living_fixtures.ASHBY_PORTAL
    assert len(f['requirements']) == 2 and 'BAFE SP203-1' in f['requirements'][0]
    assert f['buyer']['region'] == 'Yorkshire and the Humber' and f['buyer']['website'] == 'https://www.ashbyvale.example'
    assert [x['label'] for x in f['documents']] == ['Tender documents', 'Specification']
    row = notice.headline(f, TODAY)
    assert row['value'] == '£480k' and row['deadline'] == {'key': 'submission', 'label': 'Tenders due', 'date': d(21), 'days': 21}
    assert row['place'] == 'Ashby Vale, Yorkshire and the Humber' and row['lots'] == 2


def test_an_award_notice_says_how_it_was_bought():
    f = notice.facts(living_fixtures.ashby_award(TODAY))
    assert f['stage'] == 'award'
    assert f['value']['label'] == '£412k' and f['value']['kind'] == 'award'
    assert f['bids']['label'] == '4 bids received' and f['bids']['bid_range']['label'] == 'Valid bids ranged from £371k to £498k'
    assert f['criteria']['summary'] == 'Quality 40% / Price 60%'
    assert [s['name'] for s in f['suppliers']] == [living_fixtures.ASHBY_HOLDER]
    assert 'portal' not in f and 'deadlines' not in f  # an award notice has no deadline to act on


def test_an_early_notice_gives_the_engagement_date_and_when_the_tender_is_expected():
    raw = {'ocid': 'ocds-fixture-early', 'tag': ['planning'], 'buyer': {'name': 'Example Vale NHS Trust'},
           'planning': {'milestones': [{'type': 'engagement', 'dueDate': f'{d(14)}T00:00:00Z', 'description': 'Supplier day at the trust headquarters.'}]},
           'tender': {'title': 'Security systems maintenance', 'status': 'planned', 'communication': {'futureNoticeDate': f'{d(90)}T00:00:00Z'},
                      'value': {'amount': 900000, 'currency': 'GBP'}}}
    f = notice.facts(raw)
    assert f['stage'] == 'planning'
    assert [(x['key'], x['date']) for x in f['deadlines']] == [('engagement', d(14)), ('notice_expected', d(90))]
    assert notice.headline(f, TODAY)['deadline']['key'] == 'engagement'


def test_a_placeholder_value_is_not_a_value_and_an_empty_notice_states_nothing():
    raw = copy.deepcopy(living_fixtures.ashby_notice(TODAY))
    raw['tender']['value'] = {'amount': 1, 'currency': 'GBP'}
    raw['tender']['lots'] = []
    assert 'value' not in notice.facts(raw)
    empty = notice.facts({})
    assert not {'value', 'deadlines', 'criteria', 'term', 'portal'} & set(empty) and notice.headline(empty, TODAY) == {}


def test_weights_that_do_not_add_up_are_not_summarised():
    raw = copy.deepcopy(living_fixtures.ashby_notice(TODAY))
    for lot in raw['tender']['lots']:
        lot['awardCriteria']['criteria'][0]['numbers'][0]['number'] = 20
    assert not (notice.facts(raw)['criteria'] or {}).get('summary')


def test_a_tender_brief_shows_what_the_notice_states_and_answers_from_it(market):
    db, keys = market
    b = brief.build(db, keys['tender'])
    assert b['notice']['value']['label'] == '£480k' and b['notice']['portal'] == living_fixtures.ASHBY_PORTAL
    assert [(x['key'], x['days']) for x in b['notice']['deadlines']] == [('enquiries', 12), ('submission', 21), ('award', 63)]
    assert b['organisation']['location'] == 'Ashby Vale, Yorkshire and the Humber'
    scoring = gap(b, 'evaluation_criteria')
    assert scoring['status'] == 'resolved' and scoring['answered_from'] == 'notice' and 'Quality 60% / Price 40%' in scoring['answer']
    eligibility = gap(b, 'eligibility')
    assert eligibility['status'] == 'partial' and 'BAFE SP203-1' in eligibility['answer'] and 'may add more' in eligibility['answer']
    assert b['gaps'][0]['gap'] == 'eligibility'  # what the notice cannot settle stays the first question
    assert b['next']['action'] == 'open_notice' and b['next']['params'] == {'url': living_fixtures.ASHBY_PORTAL}
    assert 'in 21 days' in b['next']['why']
    assert 'qualify' in [a['action'] for a in b['alternatives']]


def test_a_tender_brief_names_the_published_holder_and_sets_this_tender_against_the_last_award(market):
    db, keys = market
    b = brief.build(db, keys['tender'])
    seen = b['field']
    assert seen['available'] and seen['incumbent']['state'] == 'in_term' and seen['incumbent']['names'] == [living_fixtures.ASHBY_HOLDER]
    assert 'holds a published contract' in seen['incumbent']['text'] and 'does not confirm who delivers the work today' in seen['incumbent']['caveat']
    assert seen['incumbent']['last_time'] == {'bids': '4 bids received', 'bid_range': 'Valid bids ranged from £371k to £498k', 'scoring': 'Quality 40% / Price 60%',
                                              'procedure': 'Open competition'}
    compared = {c['label']: c['text'] for c in seen['compared']}
    assert compared['Scoring'] == 'Price counted for 60% of the score last time and counts for 40% now: quality carries more weight than it did.'
    assert compared['Size'] == 'This notice works out at about £160k a year. The last published award worked out at about £137k a year.'
    assert compared['Competition'].startswith('4 bids received last time')
    assert [w['label'] for w in seen['ways']] == ['How it was bought last time']  # the contract being replaced is not "an earlier opening"
    incumbent = gap(b, 'incumbent')
    assert incumbent['status'] == 'resolved' and incumbent['answered_from'] == 'records' and living_fixtures.ASHBY_HOLDER in incumbent['answer']
    winners = seen['winners']
    assert winners['items'][0]['name'] == living_fixtures.ASHBY_HOLDER and winners['items'][0]['this_buyer']
    assert winners['caveat'] == 'A record of published awards. It does not say who will bid.'
    assert any(w['yours'] for w in winners['items'])  # your own company is marked, never ranked as a rival
    text = json.dumps(b)
    assert 'current supplier is' not in text.lower() and 'incumbent is' not in text.lower()
    assert not re.search(r'(chance|probability|likelihood) of winning|\d+% (chance|likely)', text.lower())


def test_one_database_is_never_served_another_databases_notice(tmp_path):
    answers = []
    for name, raw in (('a', living_fixtures.ashby_notice(TODAY)), ('b', living_fixtures.ashby_award(TODAY))):
        engine = create_engine(f"sqlite:///{tmp_path / name}.db")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            revision = living_fixtures._revision(session, f'fixture-{name}', 'https://example.test/notice', raw, datetime.now(UTC))
            session.commit()
            answers.append((revision.id, notice.for_revision(session, revision.id)['stage']))
        engine.dispose()
    assert answers == [(1, 'tender'), (1, 'award')]


def test_without_the_atlas_the_field_says_so_and_the_question_stays_open(db):
    keys = living_fixtures.load(db, TODAY)
    db.commit()
    b = brief.build(db, keys['tender'])
    assert b['field'] == {'available': False, 'coverage': field.COVERAGE}
    assert gap(b, 'incumbent')['status'] == 'open' and not gap(b, 'incumbent').get('answered_from')
    assert gap(b, 'evaluation_criteria')['answered_from'] == 'notice'  # the notice still answers what it states


def test_no_published_contract_is_never_reported_as_no_supplier(market):
    db, _ = market
    seen = field.view(db, customer='Nowhere Borough Council', title='Fire alarm maintenance', nation='England', today=TODAY)
    assert seen['incumbent']['state'] == 'none'
    assert seen['incumbent']['text'] == 'No published contract for similar work with this buyer in the records collected.'
    assert 'may simply be unlisted' in seen['incumbent']['caveat'] and 'not proof that nobody holds the work' in seen['coverage']


def test_a_contract_ending_names_its_own_holder_only_when_let_in_lots(market):
    db, _ = market
    first = db.scalar(select(MarketContract).where(MarketContract.canonical_key == 'atlas-fixture:fenwick'))
    facts = copy.deepcopy(first.facts)
    facts['suppliers'] = ['Second Lot Systems Ltd']
    db.add(MarketContract(canonical_key='atlas-fixture:fenwick-lot-2', ocid=first.ocid, buyer=first.buyer, supplier='Second Lot Systems Ltd', title='Emergency lighting maintenance',
                          fit=first.fit, nation=first.nation, lifecycle_status=first.lifecycle_status, category=first.category, end_date=first.end_date,
                          end_estimated=False, facts=facts, first_seen=first.first_seen, last_evaluated=datetime.now(UTC), last_verified=first.last_verified))
    db.commit()
    atlas.ensure_built(db)
    db.commit()
    both = field.view(db, customer=first.buyer, title=first.title, nation='England', ocids={first.ocid}, contract_ending=True, today=TODAY)
    assert len(both['holder']['suppliers']) == 2  # the procurement alone cannot tell the lots apart
    by_id = field.view(db, customer=first.buyer, title=first.title, nation='England', ocids={first.ocid}, contract_id=first.id, contract_ending=True, today=TODAY)
    assert [s['name'].lower() for s in by_id['holder']['suppliers']] == ['kestrel fire services ltd']
    by_name = field.view(db, customer=first.buyer, title=first.title, nation='England', ocids={first.ocid}, supplier='Second Lot Systems Ltd', contract_ending=True,
                         today=TODAY)
    assert [s['name'] for s in by_name['holder']['suppliers']] == ['Second Lot Systems Ltd']
    assert [c['suppliers'][0]['name'].lower() for c in by_name['buyer']['items'] if c['similar']][:1] == ['kestrel fire services ltd']


def test_an_early_notice_asks_about_route_and_timing_and_the_next_move_is_to_read_it(db):
    now = datetime.now(UTC)
    raw = {'ocid': 'ocds-fixture-early', 'id': 'early-1', 'date': f'{d(-5)}T09:00:00Z', 'tag': ['planning'], 'buyer': {'name': 'Example Vale NHS Trust'},
           'tender': {'title': 'Intruder alarm and CCTV maintenance', 'status': 'planned', 'procurementMethod': 'open',
                      'communication': {'futureNoticeDate': f'{d(90)}T00:00:00Z'}}}
    revision = living_fixtures._revision(db, 'fixture-early', 'https://www.find-tender.service.gov.uk/Notice/fixture-early', raw, now)
    result = living_fixtures.tender_result(TODAY)
    result.update(category='official_early_signal', category_label='Early notice', customer='Example Vale NHS Trust', title='Intruder alarm and CCTV maintenance', timing=d(90),
                  timing_basis='Expected tender date in the published notice')
    result['evidence'] = [{'source_revision_id': revision.id, 'source_url': revision.source_url, 'source': 'Find a Tender', 'record_key': 'fixture-early',
                           'ocid': 'ocds-fixture-early', 'published_at': d(-5)}]
    row = MarketOpportunity(dedup_key='fixture:early', first_seen=now, last_evaluated=now)
    db.add(row)
    db.flush()
    version = MarketOpportunityRevision(opportunity_id=row.id, fingerprint='fixture-early', result=result, created_at=now)
    db.add(version)
    db.flush()
    row.current_revision_id = version.id
    db.commit()
    b = brief.build(db, f'mo:{row.id}')
    assert [g['gap'] for g in b['gaps']] == ['incumbent', 'find_role', 'route']  # the notice answers route and timing, so the open questions lead
    route = gap(b, 'route')
    assert route['status'] == 'resolved' and route['answered_from'] == 'notice' and 'expects to publish the tender notice around' in route['answer'] and 'open competition' in route['answer']
    assert b['next']['action'] == 'open_notice' and b['next']['label'] == 'Read the early notice'
    assert 'published an early notice' in b['reveal']['headline'] or 'published an early notice' in json.dumps(b['reveal'])
    assert b['kind'] == 'public_tender' and b['kind_label'] == 'Early notice, before the tender'  # nothing to bid for yet, and the brief says so


def test_what_the_record_now_states_is_no_longer_listed_as_unknown(market):
    """The tender's stored unknowns predate reading the notice: scoring is now stated, and accreditation is narrowed."""
    db, keys = market
    b = brief.build(db, keys['tender'])
    assert 'Evaluation weightings' not in b['unknowns']
    assert b['unknowns'] == ['Any conditions beyond those stated in the notice.']
    # Narrowing is exact: a stored sentence that is not one of the recognised points is left as it was written.
    kept = ['Whether the original supplier currently delivers the service, and whether a competitive process is planned.', 'Current supplier.', 'Contract value.']
    assert brief._still_unknown(kept, {}, None) == kept
    assert brief._still_unknown(kept, {'value': {'label': '£1m'}}, {'incumbent': {'state': 'in_term'}}) == [kept[0], 'Whether the published holder still delivers the work today.']
    assert brief._still_unknown(['Current supplier.'], {}, {'incumbent': {'state': 'past'}}) == ['Current supplier.']


# ---- Discover rows, the salesperson's order, Today's clock and a supplier's footprint ----

NO_VALUE = {'type': 'unknown', 'published_total': None, 'estimated_annualised': None, 'framework_ceiling': None, 'basis': 'No value is published.', 'scope_note': ''}


def published(total: float, years: float = 3.0) -> dict:
    return {**NO_VALUE, 'type': 'estimated_annualised', 'published_total': total, 'estimated_annualised': round(total / years),
            'basis': f'Published award value divided by the published term of {years} years.'}


def ceiling(amount: float) -> dict:
    return {**NO_VALUE, 'type': 'framework_ceiling', 'framework_ceiling': amount, 'basis': 'Published framework ceiling.'}


def add(db, key: str, customer: str, days: int, *, value: dict | None = None, category: str = 'pre_tender', seen: str = '2024-03-01', evidence: list | None = None) -> str:
    """One more fictional published record, in the shape the collectors store."""
    now = datetime.now(UTC)
    row = MarketOpportunity(dedup_key=f'edge-fixture:{key}', first_seen=now, last_evaluated=now)
    db.add(row)
    db.flush()
    result = {'kind': 'possible_renewal_window', 'category': category, 'customer': customer, 'title': f'Fire alarm maintenance ({key})', 'supplier': 'Sample Fire Services Ltd',
              'timing': d(days), 'timing_basis': 'published award contract period', 'nation': 'England', 'fit': 'core', 'value': value or NO_VALUE,
              'priority': {'tier': 1, 'reasons': ['Core fit']}, 'counter_evidence': [], 'unknowns': [], 'brief': {'missing_information': []},
              'evidence': evidence if evidence is not None else [{'source_revision_id': 0, 'source_url': f'https://example.invalid/notice/{key}', 'source': 'Contracts Finder',
                                                                'record_key': f'edge-fixture-{key}', 'published_at': seen}]}
    version = MarketOpportunityRevision(opportunity_id=row.id, fingerprint='edge-fixture', result=result, created_at=now)
    db.add(version)
    db.flush()
    row.current_revision_id = version.id
    db.flush()
    return f'mo:{row.id}'


def rows(db, **kw) -> dict:
    return {x['key']: x for x in core.discover(db, limit=500, **kw)['items']}


def test_a_row_carries_what_its_own_notice_states(market):
    db, keys = market
    found = rows(db)
    tender = found[keys['tender']]
    assert tender['facts']['deadline'] == {'key': 'submission', 'label': 'Tenders due', 'date': d(21), 'days': 21}
    assert tender['worth'] == {'amount': 480000.0, 'kind': 'notice_estimate', 'label': '£480k estimated in the notice'}
    assert tender['facts'] == notice.headline(brief.build(db, keys['tender'])['notice'], TODAY)  # the row and the brief read the same notice
    private = found[keys['fernhill']]
    assert 'worth' not in private and 'facts' not in private  # a private signal has no notice, so it claims no figure


def test_a_row_never_borrows_another_notices_facts(market):
    """Evidence that does not name a stored notice's own record key (an inferred signal, a filing) reads no notice, even when
    its id happens to be a notice's id."""
    db, keys = market
    real = db.get(MarketOpportunity, int(keys['tender'].split(':')[1]))
    borrowed = db.get(MarketOpportunityRevision, real.current_revision_id).result['evidence'][0]['source_revision_id']
    key = add(db, 'inferred', 'Harrow Vale Estates', 200, category='inferred_signal',
              evidence=[{'source_revision_id': borrowed, 'source_url': 'https://example.invalid/filing', 'source': 'Companies House', 'record_key': 'new_site', 'published_at': '2026-05-01'}])
    row = rows(db)[key]
    assert row['facts'] == {} and row['worth'] is None
    assert brief.build(db, key)['notice'] is None


def test_the_value_order_never_ranks_a_ceiling_as_a_contract(market):
    db, keys = market
    small = add(db, 'small', 'Alder Housing', 300, value=published(90000))
    large = add(db, 'large', 'Birch Housing', 310, value=published(2400000))
    frame = add(db, 'frame', 'Cedar Consortium', 320, value=ceiling(50000000))
    none = add(db, 'none', 'Dale Housing', 330)
    default = [x['key'] for x in core.discover(db, limit=500)['items']]
    by_value = [x['key'] for x in core.discover(db, limit=500, sort='value')['items']]
    assert by_value.index(large) < by_value.index(keys['tender']) < by_value.index(small) < by_value.index(frame) < by_value.index(none)
    assert sorted(by_value) == sorted(default)  # the same rows, reordered: nothing is filtered out by the choice of order
    assert [x['key'] for x in core.discover(db, limit=500, sort='')['items']] == default
    assert rows(db)[frame]['worth']['label'] == '£50m framework ceiling'
    assert rows(db)[large]['worth']['label'] == '£2.4m published total, about £800k a year'


def test_the_date_orders_use_published_dates_only(market):
    db, keys = market
    near = add(db, 'near', 'Alder Housing', 40, seen='2022-01-10')
    far = add(db, 'far', 'Birch Housing', 400, seen='2026-06-01')
    past = add(db, 'past', 'Cedar Housing', -30, seen='2021-02-02')
    closing = [x['key'] for x in core.discover(db, limit=500, sort='closing')['items']]
    assert closing.index(keys['tender']) < closing.index(near) < closing.index(far) < closing.index(past)  # 21, 40, 400 days ahead; a date already past comes last
    newest = [x['key'] for x in core.discover(db, limit=500, sort='newest')['items']]
    assert newest.index(far) < newest.index(near) < newest.index(past)
    assert newest[-1] == keys['fernhill']  # no publication date: after every dated row


def test_today_lists_what_is_on_the_clock(market):
    db, keys = market
    big = add(db, 'big', 'Alder Housing', 200, value=published(900000))
    small = add(db, 'small', 'Birch Housing', 100, value=published(120000))
    add(db, 'later', 'Cedar Housing', 500, value=published(5000000))       # beyond twelve months
    add(db, 'frame', 'Dale Consortium', 150, value=ceiling(40000000))      # a ceiling is not a contract value
    add(db, 'unvalued', 'Elm Housing', 90)                                 # no published value
    add(db, 'check', 'Fen Housing', 120, value=published(700000), category='verify_first')
    today = core.today_queue(db)
    assert [r['key'] for r in today['closing']] == [keys['tender']] and today['closing_total'] == 1
    first = today['closing'][0]
    assert (first['days'], first['step'], first['worth']['label'], first['place']) == (21, 'Tenders due', '£480k estimated in the notice', 'Ashby Vale, Yorkshire and the Humber')
    assert [r['key'] for r in today['ending']] == [big, small] and today['ending_total'] == 2  # largest published total first
    assert today['ending'][0]['supplier'] == 'Sample Fire Services Ltd' and today['ending'][0]['step'] == 'Published end'
    core.set_status(db, big, 'dismissed')
    db.commit()
    assert [r['key'] for r in core.today_queue(db)['ending']] == [small]  # what the salesperson dismissed stays off the list


def test_a_footprint_counts_only_what_is_published(market):
    db, _ = market
    kestrel = db.scalar(select(AtlasContractor).where(AtlasContractor.display_name == 'KESTREL FIRE SERVICES LTD'))
    f = field.footprint(db, kestrel.id, today=TODAY)
    assert (f['contracts'], f['frameworks'], f['buyers']) == (2, 1, 2)
    assert f['exposure']['contracts'] == 1 and f['exposure']['label'].startswith('1 published contract reaches its published end by ')
    assert 'median' not in f['size'] and 'too few to state a typical size' in f['size']['basis']
    assert f['rivals'] == []  # one shared buyer is chance, not a pattern
    assert [r['code'] for r in f['routes']] and all(r['contracts'] for r in f['routes'])
    text = json.dumps(f).lower()
    assert not re.search(r'\d\s?%|probab|likely to|chance of|win rate', text)
    assert field.footprint(db, 10 ** 9, today=TODAY) is None


def test_lots_of_one_procurement_take_one_place_on_the_clock(market):
    db, _ = market
    first = add(db, 'lot-1', 'Alder Housing', 200, value=published(900000))
    add(db, 'lot-2', 'Alder Housing', 200, value=published(400000))
    add(db, 'lot-3', 'ALDER HOUSING ', 200, value=published(300000))
    other = add(db, 'other', 'Alder Housing', 260, value=published(200000))  # the same buyer on another date is another row
    today = core.today_queue(db)
    assert [(r['key'], r['same_day']) for r in today['ending']] == [(first, 2), (other, 0)] and today['ending_total'] == 2


def test_one_record_is_found_by_its_key_whatever_the_list_shows(market):
    db, keys = market
    gone = add(db, 'gone', 'Alder Housing', 200, value=published(900000))
    core.set_status(db, gone, 'dismissed')
    db.commit()
    assert gone not in rows(db) and gone not in rows(db, q='nothing matches this')
    found = core.discover(db, key=gone, q='nothing matches this', status='new')
    assert [x['key'] for x in found['items']] == [gone] and found['total'] == 1
    assert found['items'][0]['status'] == 'dismissed' and found['items'][0]['worth']['label'].startswith('£900k')
    assert core.discover(db, key='mo:999999')['items'] == []
    assert core.discover(db, key=keys['fernhill'])['items'][0]['organisation'] == 'Fernhill Parcels Ltd'


def test_stored_sentences_reach_the_screen_in_plain_english(market):
    """Sentences stored by the collectors carry machine dates; a salesperson never sees one."""
    db, keys = market
    assert notice.readable('The published term ends 2027-02-14.') == 'The published term ends 14 February 2027.'
    assert notice.readable('fire suppression systems.. Title names both.') == 'fire suppression systems. Title names both.'
    assert notice.readable('Wait... then 2026-13-45') == 'Wait... then 2026-13-45' and notice.readable(None) == ''
    assert notice.clip('Maintenance of fire alarms across the estate', 30) == 'Maintenance of fire alarms…' and notice.clip('Short.', 30) == 'Short.'
    assert brief._event('2025-09-03', 'reported', 'A source', detail='Confirmed on 2025-09-03.')['detail'] == 'Confirmed on 3 September 2025.'
    assert brief.build(db, keys['tender'])['kind_label'] == 'Published tender'
    key = add(db, 'stored', 'Ridgeway Homes', 300)
    row = db.get(MarketOpportunity, int(key.split(':')[1]))
    version = db.get(MarketOpportunityRevision, row.current_revision_id)
    version.result = {**version.result, 'title': 'Fire alarm maintenance.', 'brief': {'why_it_matters': 'Title names the service. The published term ends 2027-02-14.', 'missing_information': []},
                      'counter_evidence': ['A similar newer notice exists: Fire alarms (2024-12-19). This is a title match, not a confirmed replacement.']}
    db.commit()
    b = brief.build(db, key)
    text = json.dumps({k: b[k] for k in ('reveal', 'evidence', 'unknowns')})
    assert '14 February 2027' in b['reveal']['happened']['detail'] and '(19 December 2024)' in text and 'maintenance..' not in text
    assert not re.search(r'2027-02-14|2024-12-19', text)
    assert not re.search(r'\d{4}-\d\d-\d\d', core.discover(db, key=key)['items'][0]['why_now'])


def test_a_contract_your_own_group_holds_is_briefed_as_one_to_keep(market):
    """Advice to "offer an alternative" is wrong when the published supplier is the user's own group."""
    db, _keys = market
    ours = brief.build(db, add(db, 'ours', 'Calder Trust', 300, category='contract_defence'))
    theirs = brief.build(db, add(db, 'theirs', 'Calder Trust', 320))
    assert ours['kind'] == 'contract_ending' and ours['kind_label'] == 'Your contract, nearing its end'
    assert ours['reveal']['headline'].startswith("Your group's contract (Sample Fire Services Ltd) ends ")
    assert 'defended' in ours['reveal']['why'] and 'offer an alternative' not in json.dumps(ours['reveal'])
    assert [g['gap'] for g in ours['gaps']] == [g['gap'] for g in theirs['gaps']]  # the same questions decide it; only the reason for asking differs
    assert theirs['kind_label'] == 'Published contract nearing its end' and 'offer an alternative' in theirs['reveal']['why']


# ---------------------------------------------------------------- public records, before any tender

ISO = re.compile(r'\d{4}-\d\d-\d\d')


def record(kind: str, group: str, reliability: str, day: str, statement: str, *, label: str = 'A public record', url: str = 'https://records.example/1') -> dict:
    return {'signal_type': kind, 'source_group': group, 'reliability': reliability, 'occurred_on': day, 'statement': statement, 'label': label, 'source_url': url,
            'attribution': 'customer', 'capture': 'automatic', 'scope': 'customer'}


def stored_signal(db, key: str, customer: str, records: list[dict], **signal) -> str:
    """A signal in the shape the collectors store, resting on the given records."""
    result = living_fixtures.signal_result(TODAY)
    result.update(customer=customer, title=records[0]['statement'][:160], nation='Not stated')
    result['signal'] = {**result['signal'], 'supporting': records, 'independent_sources': sorted({r['source_group'] for r in records}), **signal}
    result['evidence'] = [{'source_revision_id': 0, 'source_url': r['source_url'], 'source_key': r['source_group'], 'record_key': r['signal_type'], 'source': r['label'],
                           'published_at': r['occurred_on'], 'ocid': None, 'fields': []} for r in records]
    now = datetime.now(UTC)
    row = MarketOpportunity(dedup_key=f'edge-signal:{key}', first_seen=now, last_evaluated=now)
    db.add(row)
    db.flush()
    version = MarketOpportunityRevision(opportunity_id=row.id, fingerprint='edge-signal', result=result, created_at=now)
    db.add(version)
    db.flush()
    row.current_revision_id = version.id
    db.commit()
    return f'mo:{row.id}'


def test_the_first_sentence_of_a_stored_statement_is_its_headline():
    assert signals.lead_sentence('The Regulator of Social Housing graded Example Homes C3. It says: Actions were late.') == (
        'The Regulator of Social Housing graded Example Homes C3', 'It says: Actions were late.')
    # an abbreviation is not the end of a sentence
    assert signals.lead_sentence('A press report says the board of Example St. Mary Hospital found twelve breaches. No contractor is named.')[0].endswith('found twelve breaches')
    long = 'The board paper lists ' + 'a further overdue remedial action and ' * 8 + 'no date for completion'
    first, rest = signals.lead_sentence(long)
    assert first.endswith('…') and len(first) <= 181 and rest == long  # cut at a word and marked; the whole statement is kept as the rest
    assert signals.lead_sentence('') == ('', '') and signals.lead_sentence('Short and whole.') == ('Short and whole', '')
    assert signals.summary({'title': '', 'signal': {'supporting': []}}) is None  # nothing to show is never dressed up as a signal


def test_a_public_signal_is_briefed_as_a_record_never_as_a_contract(market):
    db, keys = market
    b = brief.build(db, keys['signal'])
    r = b['reveal']
    assert b['kind'] == 'public_signal' and b['kind_label'] == 'Public record, before any tender' and b['organisation']['name'] == living_fixtures.FENWICK
    assert r['headline'] == f'{living_fixtures.FENWICK} published an early notice: "{living_fixtures.FENWICK_EARLY_TITLE}"'  # the newest record, as stored
    assert r['happened']['detail'] == '2 public records from 2 independent sources. The other is in the evidence below.'
    assert r['happened']['basis'] == 'published' and r['happened']['source'] == living_fixtures.FENWICK_EARLY_URL
    # not a contract: no notice facts, no renewal rule of thumb, no end date, no percentage
    assert b['notice'] is None and r['heuristic'] is None
    text = json.dumps(b)
    assert 'published end date' not in text and 'published contract:' not in text and 'similar work' not in text and not re.search(r'\d+(\.\d+)?\s?%', text)
    # the reading never goes further than the two records, and carries the stored caution
    assert 'Neither record says the two are connected' in r['why'] and r['why'].endswith(living_fixtures.SIGNAL_CAUTION)
    # every record is shown with its source, in plain dates
    supports = [e for e in b['evidence'] if e['effect'] == 'supports']
    assert [(e['title'], e['source']['label'], e['basis']) for e in supports] == [('Official market engagement', 'Procurement notice', 'published'),
                                                                                 ('Regulator finding on fire safety compliance', 'Regulator', 'published')]
    assert {e['source']['url'] for e in supports} == {living_fixtures.FENWICK_EARLY_URL, living_fixtures.FENWICK_FINDING_URL}
    assert supports[1]['detail'].endswith(f'Published {TODAY - timedelta(days=150):%-d %B %Y}.') and 'does not say how the organisation will put this right' in supports[1]['not_established']
    assert not any(ISO.search(' '.join((e['title'], e['detail'], e['establishes'], e['not_established']))) for e in b['evidence'])
    assert not ISO.search(json.dumps([r['headline'], r['happened']['detail'], r['why'], r['disprove'], b['unknowns'], [(g['question'], g['answer']) for g in b['gaps']]]))
    assert r['freshness']['latest_evidence'] == d(-12) and not r['freshness']['stale']
    # the questions that decide whether it is a way in, the decisive one first
    assert [(g['gap'], g['value']) for g in b['gaps']] == [('hypothesis_test', 'decisive'), ('route', 'timing'), ('incumbent', 'access'), ('find_role', 'access')]
    assert r['key_question']['question'].startswith('Is the problem in the record still open at Fenwick Housing Trust')
    assert gap(b, 'route')['question'] == 'When will the tender be published, and by which procedure or framework?'
    # a published holder is a lead on the answer, never the answer, and is never tied to the regulator's finding
    holder = gap(b, 'incumbent')
    assert holder['status'] == 'partial' and holder['answered_from'] == 'records' and 'KESTREL FIRE SERVICES LTD' in holder['answer']
    assert 'for fire or security work' in holder['answer'] and 'does not confirm who delivers the work today, or that this contract covers what the record describes' in holder['answer']
    assert b['field']['incumbent']['others'] == 0 and b['field']['winners'] is None and b['field']['prices'] is None  # no service is named, so no field of "similar" work
    # the first move is to read the record; the path starts there
    assert (b['next']['action'], b['next']['label'], b['next']['params']) == ('open_notice', 'Read the record at its source', {'url': living_fixtures.FENWICK_EARLY_URL})
    assert [j['label'] for j in b['journey']] == ['Read the record at its source', 'Confirm the problem is still open', 'Find who owns it', 'Engage', 'Qualify']
    assert b['unknowns'] == ['Whether the condition continues today.', 'Whether the systems are ageing or at the end of their life.', 'Whether a budget or a procurement is planned.']
    assert 'under-delivering' not in text  # a record about an organisation is never turned into a claim about a company
    # a buyer with nothing published says so once, and offers no empty record to open
    other = brief.build(db, stored_signal(db, 'unlisted', 'Example Moor Homes', [record('regulator_compliance_finding', 'regulator', 'statutory_record', '2026-02-10',
                                                                                    'A regulator found overdue fire safety actions at Example Moor Homes.')]))
    assert other['field']['incumbent']['text'] == 'No published fire or security contract with this buyer in the records collected.' and other['field']['buyer'] is None
    assert gap(other, 'incumbent')['status'] == 'open'


def test_what_a_signal_means_follows_the_kind_of_record_it_rests_on(db):
    finding = record('regulator_compliance_finding', 'regulator', 'statutory_record', '2026-04-15',
                     'The Regulator of Social Housing graded MARSHGATE DISTRICT COUNCIL C4. It says: Around 900 fire safety actions were overdue.')
    b = brief.build(db, stored_signal(db, 'finding', 'MARSHGATE DISTRICT COUNCIL', [finding]))
    assert b['organisation'] == {'name': 'Marshgate District Council', 'sector': '', 'location': '', 'website': None, 'company_number': None}  # a register's capitals, and no invented place
    assert b['reveal']['headline'] == 'The Regulator of Social Housing graded MARSHGATE DISTRICT COUNCIL C4'  # the stored sentence is shown as collected
    assert b['reveal']['happened']['detail'] == 'It says: Around 900 fire safety actions were overdue. One public record so far.'
    assert 'C4 is the lowest of that regulator’s four consumer grades' in b['reveal']['why'] and 'no tender, budget or change of contract is on record' in b['reveal']['why']
    assert [g['gap'] for g in b['gaps']] == ['hypothesis_test', 'route', 'incumbent', 'find_role']
    assert gap(b, 'route')['question'] == 'How does Marshgate District Council buy fire and security work: an existing contract, a framework, or its own tenders?'
    assert gap(b, 'incumbent')['status'] == 'open' and not any('early notice' in x for x in b['reveal']['disprove'])
    assert b['field']['available'] is False and 'incumbent' not in b['field']  # no contract record built here: said, not guessed around

    notices = [record('fire_enforcement_outcome', 'fire_service', 'statutory_record', day,
                      f'Northshire Fire and Rescue Service recorded "{what}" at EXAMPLE HOUSE on {day}. Responsibility is not published.', label='Fire authority inspection outcome')
               for day, what in (('2025-12-18', 'Enforcement Notice'), ('2026-03-02', 'Enforcement Notice Extended'))]
    b = brief.build(db, stored_signal(db, 'enforcement', 'Example House NHS Trust', notices))
    assert b['reveal']['headline'] == 'Northshire Fire and Rescue Service recorded "Enforcement Notice Extended" at EXAMPLE HOUSE on 2 March 2026'  # the newest record, in a plain date
    assert b['reveal']['happened']['detail'] == 'Responsibility is not published. 2 public records, all from one source. The other is in the evidence below.'
    assert 'formal fire safety action at a named site' in b['reveal']['why'] and b['reveal']['services'] == []  # no system is named, so none is claimed
    assert gap(b, 'site_operator')['question'] == 'Which organisation is responsible for fire safety at the premises named in the record?'
    assert [e['date'] for e in b['evidence'] if e['effect'] == 'supports'] == ['2026-03-02', '2025-12-18']

    press = record('customer_concern_published', 'local_press', 'opinion_press', '2026-04-02',
                   'A local news article, written as opinion, says board papers report 40 fire safety breaches at Example Infirmary. The board paper itself was not read.')
    b = brief.build(db, stored_signal(db, 'press', 'Example Infirmary NHS Trust', [press]))
    assert b['reveal']['happened']['basis'] == 'stated' and b['reveal']['happened']['detail'] == 'The board paper itself was not read. One press report so far.'
    assert b['reveal']['why'].startswith('This rests on a press report, not on an original document.')
    assert b['reveal']['disprove'][0] == 'The report may be wrong or out of date: the document behind it has not been read'
    assert [e['date_kind'] for e in b['evidence'] if e['effect'] == 'supports'] == ['reported']

    early = record('market_engagement', 'procurement', 'official_notice', d(-6), 'Example Vale Homes published an early notice: "Door entry and CCTV upgrade"')
    b = brief.build(db, stored_signal(db, 'early', 'Example Vale Homes', [early]))
    assert [(g['gap'], g['value']) for g in b['gaps']][0] == ('route', 'decisive')  # nothing is said to be wrong, so the first question is when and how it will be bought
    assert 'hypothesis_test' not in [g['gap'] for g in b['gaps']] and 'it can still talk to suppliers' in b['reveal']['why']
    assert b['reveal']['disprove'] == ['The early notice may be delayed, changed or dropped', 'The buyer may use a framework you are not on']


def test_a_record_that_points_the_other_way_is_shown_first_among_the_doubts(db):
    finding = record('regulator_compliance_finding', 'regulator', 'statutory_record', '2026-02-10', 'A regulator found overdue fire safety actions at Example Moor Homes.')
    against = {'statement': 'Example Moor Homes reported on 2026-06-01 that every overdue action was complete. No inspection has confirmed it.', 'occurred_on': '2026-06-01',
               'source_url': 'https://records.example/board-paper'}
    b = brief.build(db, stored_signal(db, 'against', 'Example Moor Homes', [finding], contradicting=[against]))
    weakens = [e for e in b['evidence'] if e['effect'] == 'weakens']
    assert [e['title'] for e in weakens] == ['Example Moor Homes reported on 1 June 2026 that every overdue action was complete'] and weakens[0]['source']['url'] == against['source_url']
    assert b['reveal']['disprove'][0] == 'Contrary evidence: Example Moor Homes reported on 1 June 2026 that every overdue action was complete'


def test_a_signal_row_says_what_the_record_is_and_keeps_its_place(market):
    db, keys = market
    order = [x['key'] for x in core.discover(db, limit=500)['items']]
    row = rows(db)[keys['signal']]
    assert order[-1] == keys['signal'] and row['kind'] == 'unverified_candidate' and row['rank'] == (2, 9999)  # where the list has always put it
    assert row['title'] == living_fixtures.signal_result(TODAY)['title']  # the stored title is untouched
    assert row['headline'] == f'{living_fixtures.FENWICK} published an early notice: "{living_fixtures.FENWICK_EARLY_TITLE}"'
    assert row['kind_label'] == 'Public record, before any tender'
    assert row['why_now'] == f'Early procurement notice, {TODAY - timedelta(days=12):%-d %B %Y}. 2 public records from 2 independent sources. A reason to ask, not a published requirement.'
    assert row['signal'] == {'date': d(-12), 'source': 'Procurement notice', 'source_url': living_fixtures.FENWICK_EARLY_URL, 'official': True, 'records': 2, 'sources': 2,
                             'corroborated': True, 'strength': '2 public records from 2 independent sources'}
    known = row['brief']['known']
    assert [k['text'] for k in known] == [row['headline'], f'The Regulator of Social Housing graded {living_fixtures.FENWICK} C3'] and all(k['source_url'] and k['basis'] == 'published' for k in known)
    assert not any('unsourced' in u for u in row['brief']['unknown']) and row['brief']['next'] == 'Read the record at its source before opening an account.'
    assert row['facts'] == {} and row['worth'] is None  # a signal is not a notice: it claims no value and no deadline
    assert 'headline' not in rows(db)[keys['tender']] and 'signal' not in rows(db)[keys['fernhill']]
    # found by what the newest record says, and by kind
    assert list(rows(db, q='remedial works programme')) == [keys['signal']]
    assert list(rows(db, category='inferred_signal')) == [keys['signal']] and keys['signal'] not in rows(db, category='live_procurement')


def test_today_lists_public_signals_with_the_best_evidenced_first(market):
    db, keys = market
    newer = stored_signal(db, 'newer', 'Example Moor Homes', [record('regulator_compliance_finding', 'regulator', 'statutory_record', d(-2),
                                                                     'A regulator found overdue fire safety actions at Example Moor Homes.')])
    older = stored_signal(db, 'older', 'Example Fen Homes', [record('customer_concern_published', 'local_press', 'opinion_press', d(-40),
                                                                    'A press report says Example Fen Homes has overdue fire door repairs.')])
    today = core.today_queue(db)
    # two independent sources come before one newer record; then the newest
    assert [s['key'] for s in today['signals']] == [keys['signal'], newer, older] and today['signals_total'] == 3
    first = today['signals'][0]
    assert (first['organisation'], first['source'], first['date'], first['strength']) == (living_fixtures.FENWICK, 'Procurement notice', d(-12), '2 public records from 2 independent sources')
    assert today['signals'][2]['strength'] == 'One press report so far' and today['signals'][2]['official'] is False
    assert keys['signal'] not in [x['key'] for x in today['new_leads']]  # an inference is never listed among published leads
    core.set_status(db, newer, 'dismissed')
    db.commit()
    again = core.today_queue(db)
    assert [s['key'] for s in again['signals']] == [keys['signal'], older] and again['signals_total'] == 2  # what the salesperson dismissed stays off the list


def test_names_published_in_capitals_are_tidied_without_moving_a_row(market):
    assert core.display_name('EXAMPLE VALE AND DISTRICT COUNCIL') == 'Example Vale and District Council'
    assert core.display_name('STOKE-ON-EXAMPLE NHS TRUST') == 'Stoke-on-Example NHS Trust' and core.display_name('THE EXAMPLE TRUST OF SAMPLE') == 'The Example Trust of Sample'
    assert core.display_name('Example Homes Ltd') == 'Example Homes Ltd'  # a name already written for people is left alone
    db, _keys = market
    first = add(db, 'caps-a', 'EXAMPLE AND SAMPLE HOMES', 300)
    second = add(db, 'caps-b', 'EXAMPLE BOROUGH HOMES', 300)
    found = core.discover(db, limit=500)['items']
    order = [x['key'] for x in found]
    names = {x['key']: x['organisation'] for x in found}
    assert (names[first], names[second]) == ('Example and Sample Homes', 'Example Borough Homes')
    # The two tie on everything but the name. The tidier "and" would sort after "Borough"; the list keeps the order it has always had.
    assert order.index(first) < order.index(second) and not any('_order' in x for x in found)


def test_once_a_signal_is_saved_the_next_move_is_to_find_who_owns_the_problem(market):
    db, keys = market
    before = brief.build(db, keys['tender'])
    account, _link, _created = core.link_source(db, 'market_opportunity', int(keys['signal'].split(':')[1]))
    db.commit()
    b = brief.build(db, f'acct:{account.id}')
    assert account.name == living_fixtures.FENWICK and b['kind'] == 'public_signal'
    # Research is not configured in a test, and says so; the move that can be made is to find the people. The record stays within reach.
    assert b['next']['action'] == 'find_people' and [x['reason'] for x in b['next']['blocked']] == ['Web research is not configured here.']
    assert 'open_notice' in [a['action'] for a in b['alternatives']]
    assert [(j['label'], j['state']) for j in b['journey']][:2] == [('Read the record at its source', 'done'), ('Confirm the problem is still open', 'current')]
    assert b['story'][0]['text'] == 'Account opened from: Public record, before any tender'
    linked = core.account_view(db, account.id)['sources'][0]
    assert linked['title'].startswith(f'{living_fixtures.FENWICK} published an early notice') and linked['category_label'] == 'Public record, before any tender'
    assert [e['label'] for e in linked['evidence']] == ['Official market engagement', 'Regulator finding on fire safety compliance']
    # A tender is unchanged by any of this: its notice is still the first thing to read, and stays next to the bid decision.
    after = brief.build(db, keys['tender'])
    assert (after['next']['action'], [a['action'] for a in after['alternatives']]) == (before['next']['action'], [a['action'] for a in before['alternatives']]) == ('open_notice', ['qualify', 'research_gap', 'find_people'])


def test_an_introduction_from_a_signal_never_puts_the_finding_to_the_customer(market):
    db, keys = market
    account, _link, _created = core.link_source(db, 'market_opportunity', int(keys['signal'].split(':')[1]))
    db.commit()
    draft = engage.prepare_introduction(db, account.id)
    # The buyer's own early notice can be mentioned, because the buyer published it; the regulator's finding is left out, and the draft says so.
    assert f'I saw the early notice {living_fixtures.FENWICK} published, \u201c{living_fixtures.FENWICK_EARLY_TITLE}\u201d, and wanted to introduce us before any tender is issued.' in draft['body']
    assert not re.search(r'Regulator|graded|C3|fire risk assessments', draft['body']) and not ISO.search(draft['body'])
    assert [e['url'] for e in draft['evidence']] == [living_fixtures.FENWICK_EARLY_URL]
    assert any(g.startswith('The public record behind this lead is not mentioned') for g in draft['gaps'])
    assert 'We look after Fire alarm' in draft['body'] or 'We look after fire alarm' in draft['body']  # what the buyer's own notice names

    finding = record('regulator_compliance_finding', 'regulator', 'statutory_record', '2026-02-10', 'A regulator found overdue fire safety actions at Example Moor Homes.')
    other, _link, _created = core.link_source(db, 'market_opportunity', int(stored_signal(db, 'quiet', 'Example Moor Homes', [finding]).split(':')[1]))
    db.commit()
    quiet = engage.prepare_introduction(db, other.id)
    assert "I'm getting in touch about fire safety and security arrangements at Example Moor Homes." in quiet['body']
    assert 'overdue' not in quiet['body'] and 'regulator' not in quiet['body'].lower() and quiet['evidence'] == []
    assert any(g.startswith('The public record behind this lead is not mentioned') for g in quiet['gaps'])
    # A deal made from a signal is named for the work the buyer named, or for the account: never for a sentence about a record.
    deal = engage.create_deal(db, account.id, {'source_key': keys['signal'], 'qualification': {'requirement': 'Replace the fire alarm panels in six schemes'}})
    assert deal.title == living_fixtures.FENWICK_EARLY_TITLE
    plain = engage.create_deal(db, other.id, {'source_key': f'mo:{db.scalar(select(MarketOpportunity.id).where(MarketOpportunity.dedup_key == "edge-signal:quiet"))}',
                                             'qualification': {'requirement': 'Clear the overdue remedial actions'}})
    assert plain.title == 'Example Moor Homes fire and security'

