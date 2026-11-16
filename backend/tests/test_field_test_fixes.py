"""Defects found in the sales field test of 16 November 2026, each reproduced on fictional records.

- Maintenance is not replacement: a refurbishment never implies system age, and a replacement date still ahead never holds
  contact back. An old system already in its replacement window is still a reason to talk.
- A vacancy is not an appointment, and an acquisition is not a site opening.
- An early notice's expected date is not a bid deadline; a research milestone still to come is not a report.
- A research timing reading is never shown as published knowledge.
- A note is internal preparation: it never makes an account contacted or engaged.
- A draft's warnings follow its recipient and sender.
- Research results that rest on no source are named, and are not offered on the patch brief.
- One phone number is one route, however it is written."""
from __future__ import annotations

import copy
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base, get_db
from app.intelligence.timing_inference import infer_timing, reclassify
from app.main import create_app
from app.models.crm import Account, Activity, Contact, Preference
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.models.prospect import Prospect
from app.services import atlas, atlas_fixtures, brief, living_fixtures, navigator, patch
from app.services import si_core as core
from app.services import si_engage as engage
from app.services.research_handlers import sourced_summary

TODAY = date(2026, 11, 16)
LIVE_TODAY = date.today()


def d(days: int) -> str:
    return (LIVE_TODAY + timedelta(days=days)).isoformat()


@pytest.fixture
def local(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'field.db'}", connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    db = Session(engine)
    keys = living_fixtures.load(db, LIVE_TODAY)
    atlas_fixtures.load(db, LIVE_TODAY)
    db.commit()
    atlas.ensure_built(db)
    db.commit()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db, keys
    db.close()
    engine.dispose()


def research(db, name: str, signals: list[dict], clues: list[dict]) -> Prospect:
    data = copy.deepcopy(living_fixtures.fernhill_data(LIVE_TODAY))
    data.update(signals=signals, timing_clues=clues, location='Example Town')
    row = Prospect(dedup_key=name.lower(), name=name, status='new', data=data, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add(row)
    db.commit()
    return row


# ---------------------------------------------------------------- timing

def test_a_refurbishment_never_holds_maintenance_contact_back():
    """Daish's: two refurbishments and a hotel bought were read as replacement lives, and the lead said "Not yet" until 2034."""
    clues = [{'kind': 'refurbishment', 'date': '2026-01', 'basis': 'stated', 'detail': 'Ten-hotel winter refurbishment programme.'},
             {'kind': 'refurbishment', 'date': '2026-09', 'basis': 'stated', 'system_family': 'fire_alarm', 'detail': 'Planning consent for phase two works.'},
             {'kind': 'site_opening', 'date': '2024-10', 'basis': 'stated', 'detail': 'Example Hotel acquired.'}]
    t = infer_timing(clues, TODAY)
    assert t['phase'] == 'unknown' and t['window'] is None and t['blocked_until'] is None
    # the specific reason to ask comes first: it is what a rep reads as "why now"
    assert t['reasons'][0].startswith('Refurbishment or fit-out: a refurbishment does not show how old the systems are') and 'Ask who maintains them now' in t['reasons'][0]
    assert t['reasons'][1].startswith('Acquisition: a change of owner is a reason to ask whether inherited maintenance contracts')
    assert t['reasons'][2] == 'When their maintenance is next reviewed is not published.'
    assert len(t['reasons']) == 3 and not any('2034' in r or 'replaced after' in r for r in t['reasons'])
    assert [n['kind'] for n in t['notes']] == ['acquisition', 'refurbishment', 'refurbishment'] and t['clues'] == []


def test_a_replacement_date_still_ahead_is_context_and_an_old_system_still_counts():
    """Aldi Bardon: a building completed in 2024 said "Not yet" until 2032. Replacing systems is a separate, later sale."""
    new = infer_timing([{'kind': 'building_completed', 'date': '2024', 'basis': 'stated'}], TODAY)
    assert new['phase'] == 'unknown' and new['blocked_until'] is None and new['window'] is None
    assert new['reasons'][0].startswith('Replacement, a separate sale:') and 'it does not set when maintenance is reviewed' in new['reasons'][0]
    old = infer_timing([{'kind': 'system_installed', 'date': '2013', 'basis': 'stated', 'system_family': 'fire_alarm'}], TODAY)
    assert old['phase'] == 'engage_now'  # an ageing system already in its window is a reason to talk now


def test_a_vacancy_is_not_an_appointment():
    dandara = {'kind': 'leadership_change', 'date': '2026', 'basis': 'stated',
               'detail': 'Head of Facilities vacancy advertised. Whether anyone has been appointed, and when they start, is not known.'}
    assert reclassify(dandara)['kind'] == 'role_vacancy'
    t = infer_timing([dandara], TODAY)
    assert t['phase'] == 'unknown' and t['window'] is None and not any('first nine months' in r for r in t['reasons'])
    assert t['reasons'][0] == ('Role advertised: a vacancy is not an appointment, so no new-leader window starts. Ask who covers the role now and whether it has '
                               'been filled.')
    promoted = {'kind': 'leadership_change', 'date': '2026-09-26', 'basis': 'stated', 'detail': 'Example Person promoted to Estates Director.'}
    filled = {'kind': 'leadership_change', 'date': '2026-09-26', 'basis': 'stated', 'detail': 'Example Person appointed to fill the vacancy.'}
    assert reclassify(promoted)['kind'] == reclassify(filled)['kind'] == 'leadership_change'
    assert infer_timing([promoted], TODAY)['phase'] == 'engage_now'  # an appointment still starts the new-leader window


def test_an_acquisition_is_not_a_site_opening():
    t = infer_timing([{'kind': 'site_opening', 'date': '2025', 'basis': 'stated', 'detail': 'Example Hotels bought the Example West hotel.'}], TODAY)
    assert t['phase'] == 'unknown' and t['clues'] == [] and [n['kind'] for n in t['notes']] == ['acquisition']
    assert not any(r.startswith('New site opening') for r in t['reasons'])
    opening = infer_timing([{'kind': 'site_opening', 'date': '2027-09-01', 'basis': 'stated', 'detail': 'New depot due to open.'}], TODAY)
    assert opening['phase'] == 'engage_now'  # a real opening keeps its rule


# ---------------------------------------------------------------- dates keep their meaning

def test_an_early_notices_expected_date_is_not_a_bid_deadline(local):
    _client, db, keys = local
    real = db.get(MarketOpportunity, int(keys['tender'].split(':')[1]))
    result = copy.deepcopy(db.get(MarketOpportunityRevision, real.current_revision_id).result)
    result.update(category='official_early_signal', category_label='Early notice', timing=d(15), timing_basis='published expected date')
    row = MarketOpportunity(dedup_key='field:early', first_seen=datetime.now(UTC), last_evaluated=datetime.now(UTC))
    db.add(row)
    db.flush()
    version = MarketOpportunityRevision(opportunity_id=row.id, fingerprint='field-early', result=result, created_at=datetime.now(UTC))
    db.add(version)
    db.flush()
    row.current_revision_id = version.id
    db.commit()
    early = next(e for e in brief.build(db, f'mo:{row.id}')['evidence'] if e['date'] == d(15))
    assert early['title'].startswith('Tender notice expected: ') and 'It is not a bid deadline' in early['establishes']
    assert 'deadline' not in early['title'].lower()
    live = next(e for e in brief.build(db, keys['tender'])['evidence'] if e['title'].startswith('Tender'))
    assert live['title'].startswith('Tender deadline: ')  # a live tender's date is its deadline


def test_a_research_milestone_still_to_come_is_an_expected_event(local):
    _client, db, _keys = local
    row = research(db, 'Example Cold Store Ltd',
                   [{'type': 'expansion', 'title': 'Fully operational by the end of next year', 'detail': '', 'date': d(400)[:7], 'basis': 'stated',
                     'direction': 'supports', 'source_url': 'https://news.example/cold-store'},
                    {'type': 'new_site', 'title': 'Warehouse opened', 'detail': '', 'date': d(-30), 'basis': 'stated', 'direction': 'supports',
                     'source_url': 'https://news.example/opened'}],
                   [{'kind': 'leadership_change', 'date': d(-20)[:7], 'basis': 'stated', 'detail': 'Head of Estates role advertised.', 'source_url': 'https://jobs.example/estates'}])
    events = {e['title']: e for e in brief.build(db, f'pr:{row.id}')['evidence']}
    assert events['Fully operational by the end of next year']['date_kind'] == 'event'  # still to come
    assert events['Warehouse opened']['date_kind'] == 'reported'
    assert 'Role advertised: Head of Estates role advertised.' in events and not any(t.startswith('New decision maker') for t in events)


# ---------------------------------------------------------------- what we know

def test_research_timing_is_never_shown_as_published_knowledge(local):
    _client, db, keys = local
    account, _link, _created = core.link_source(db, 'prospect', int(keys['fernhill'].split(':')[1]))
    db.commit()
    known = core.account_view(db, account.id)['known']
    reading = next(k for k in known if k['source'] == keys['fernhill'])
    assert reading['basis'] == 'inferred' and ('usually' in reading['text'] or 'commonly' in reading['text'] or 'Window' in reading['text'])


# ---------------------------------------------------------------- status

def test_a_note_never_makes_an_account_contacted_or_engaged(local):
    _client, db, keys = local
    account, _link, _created = core.link_source(db, 'prospect', int(keys['fernhill'].split(':')[1]))
    db.commit()
    engage.log_activity(db, account.id, {'kind': 'note', 'direction': 'internal', 'summary': 'Research notes. No customer contact yet.'})
    db.commit()
    assert db.get(Account, account.id).status == 'prospect' and core.account_view(db, account.id)['status'] == 'prospect'
    engage.log_activity(db, account.id, {'kind': 'call', 'direction': 'outbound', 'summary': 'Called the switchboard; no answer.', 'outcome': 'no_answer'})
    db.commit()
    assert core.account_view(db, account.id)['status'] == 'contacted'
    engage.log_activity(db, account.id, {'kind': 'call', 'direction': 'outbound', 'summary': 'Spoke to the estates team.', 'outcome': 'connected'})
    db.commit()
    assert core.account_view(db, account.id)['status'] == 'engaged' and db.get(Account, account.id).status == 'engaged'
    assert {r['id']: r['status'] for r in core.accounts_list(db)}[account.id] == 'engaged'


def test_a_status_a_note_once_set_wrongly_corrects_itself_without_changing_stored_records(local):
    """Both field-test accounts read "Engaged" after notes that said nobody had been contacted."""
    _client, db, _keys = local
    a = Account(name='Example Care Group', key='example care group', kind='unknown', status='engaged', watched=False, notes='',
                created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    won = Account(name='Example Customer Ltd', key='example customer', kind='unknown', status='customer', watched=False, notes='',
                  created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add_all([a, won])
    db.flush()
    db.add(Activity(account_id=a.id, kind='note', direction='outbound', summary='Desk research only.', outcome='', requirements='', objections='', commitments='',
                    occurred_at=datetime.now(UTC), created_at=datetime.now(UTC)))
    db.commit()
    statuses = {r['id']: r['status'] for r in core.accounts_list(db)}
    assert statuses[a.id] == 'prospect' and core.account_view(db, a.id)['status'] == 'prospect'
    assert db.get(Account, a.id).status == 'engaged'  # nothing stored was rewritten
    assert statuses[won.id] == 'customer'  # set by a deal, kept


# ---------------------------------------------------------------- drafts

def test_a_drafts_warnings_follow_its_recipient_and_sender(local):
    _client, db, keys = local
    account, _link, _created = core.link_source(db, 'prospect', int(keys['fernhill'].split(':')[1]))
    db.commit()
    intro = engage.prepare_introduction(db, account.id)
    draft = engage.save_draft(db, account.id, {'subject': intro['subject'], 'body': intro['body'], 'gaps': intro['gaps'], 'evidence': intro['evidence']})
    db.commit()
    assert "No contact selected: add the recipient's name." in draft.gaps
    person = engage.add_contact(db, account.id, {'name': 'Example Person', 'role': 'Commercial Director'})
    db.commit()
    draft = engage.save_draft(db, account.id, {'contact_id': person.id}, draft_id=draft.id)
    assert "No contact selected: add the recipient's name." not in draft.gaps
    assert draft.gaps[0] == ('Example Person is selected, but no direct route to them is verified: reach them through the published switchboard or office first.')
    assert 'Add your name and company under Your details.' in draft.gaps
    db.add_all([Preference(key='company_name', value='Example Fire Ltd'), Preference(key='sender_name', value='Sam North')])
    db.commit()
    draft = engage.save_draft(db, account.id, {'subject': 'Example'}, draft_id=draft.id)
    assert 'Add your name and company under Your details.' not in draft.gaps
    assert any('Current provider unknown' in g for g in draft.gaps)  # what was said about the evidence is kept
    # a draft saved before its recipient was chosen shows the warnings as they stand now, without being saved again
    stale = engage.save_draft(db, account.id, {'subject': 'Older', 'body': 'Dear [name],', 'gaps': ["No contact selected: add the recipient's name."]})
    stale.contact_id = person.id
    db.commit()
    shown = next(x for x in core.account_view(db, account.id)['drafts'] if x['id'] == stale.id)
    assert "No contact selected: add the recipient's name." not in shown['gaps'] and shown['gaps'][0].startswith('Example Person is selected')
    assert stale.gaps == ["No contact selected: add the recipient's name."]  # shown afresh; nothing stored was rewritten


# ---------------------------------------------------------------- sources

def test_research_that_rests_on_no_source_is_named_and_not_offered(local):
    client, db, keys = local
    bare = research(db, 'Example Hotels Ltd',
                    [{'type': 'hiring_fm_security', 'title': 'Group Head of Health and Safety vacancy', 'detail': '', 'date': d(-48)[:7], 'basis': 'inferred',
                      'direction': 'supports', 'source_url': ''}], [])
    summary = sourced_summary(db, [int(keys['fernhill'].split(':')[1]), bare.id])
    assert summary['message'] == ('2 organisations found: 1 with a published source; 1 needs checking first (Example Hotels Ltd). '
                                  'Signals are reasons to investigate, not confirmed requirements.')
    assert summary['needs_sources'] == [bare.id]
    assert sourced_summary(db, [int(keys['fernhill'].split(':')[1])])['message'].startswith('1 organisation found, each with a published source.')
    leads = [c['key'] for c in client.get('/api/si/patch').json()['leads']]
    assert f'pr:{bare.id}' not in leads and keys['fernhill'] in leads


def test_one_phone_number_is_one_route_however_it_is_written(local):
    _client, db, keys = local
    assert navigator.phone_key('+44 (0)1757 450000') == navigator.phone_key('0044 1757 450000') == navigator.phone_key('01757 450000') == '01757450000'
    assert navigator.phone_key('+44 1757 450000') == '01757450000' and navigator.phone_key('0800 324 7901') == '08003247901'
    account, _link, _created = core.link_source(db, 'prospect', int(keys['fernhill'].split(':')[1]))
    db.commit()
    first = navigator.Candidate(kind='switchboard', value='01757 450000', label='Main phone', source_url='https://directory.example/a', quote='Call 01757 450000')
    second = navigator.Candidate(kind='phone', value='+44 1757 450000', label='Main switchboard', source_url='https://www.example.co.uk/contact', quote='+44 1757 450000')
    navigator.save(db, account, [(first, 'good', [])], job_id=0, provider='test')
    result = navigator.save(db, account, [(second, 'good', [])], job_id=0, provider='test')
    db.commit()
    phones = [c for c in db.scalars(select(Contact).where(Contact.account_id == account.id, Contact.phone.is_not(None))) if navigator.phone_key(c.phone) == '01757450000']
    assert len(phones) == 1 and result['updated'] == 1 and result['added'] == 0
    # an opt-out keeps its own fingerprint: a number recorded either way is still matched as before
    assert navigator.digest('phone', '+44 1757 450000') != navigator.digest('phone', '01757 450000')


def test_the_date_a_tender_notice_is_expected_is_not_a_deadline_on_the_patch_brief():
    """Doncaster was chosen for the patch brief as "a published deadline still ahead"; its date was when the tender notice is expected."""
    expected = {'category': 'official_early_signal', 'days': 15, 'facts': {'deadline': {'key': 'notice_expected', 'label': 'Tender notice expected', 'days': 15}}}
    closes = {'category': 'official_early_signal', 'days': 15, 'facts': {'deadline': {'key': 'engagement', 'label': 'Market engagement closes', 'days': 14}}}
    due = {'category': 'live_procurement', 'days': 21, 'facts': {'deadline': {'key': 'submission', 'label': 'Tenders due', 'days': 21}}}
    assert patch._deadline(expected) is None and patch._deadline(closes) == 14 and patch._deadline(due) == 21

