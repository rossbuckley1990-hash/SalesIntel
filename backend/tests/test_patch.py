"""The patch brief: five leads for one rep's patch, on fictional records.

- A rep is a name, a patch, disciplines, sectors and target accounts, kept with the workspace's preferences. No schema change.
- The five are chosen by a fixed rule that is shown: target accounts, then two or more independent records, then the deadlines
  closing soonest, then the largest contracts reaching a published end. Never by a score, and Discover keeps its own order.
- Each lead carries its evidence chain, oldest first: every dated record opens its source and is labelled Published; SalesIntel's
  reading is labelled Inferred. A tender needs no reading.
- A lead the rep has judged leaves the five; another rep still sees it.
- With no rep yet the brief covers the whole record, so there is something to read before anything is set up.
- The same five are available as plain text for the owner to send, with no machine dates."""
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base, get_db
from app.main import create_app
from app.services import atlas, atlas_fixtures, living_fixtures, patch
from app.services import si_core as core
from test_sales_edge import add, ceiling, published

TODAY = date.today()
ISO = re.compile(r'\d{4}-\d\d-\d\d')
YORKSHIRE = 'Yorkshire and the Humber'


@pytest.fixture
def local(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'patch.db'}", connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    db = Session(engine)
    keys = living_fixtures.load(db, TODAY)
    atlas_fixtures.load(db, TODAY)
    db.commit()
    atlas.ensure_built(db)
    keys['ending'] = add(db, 'ending', 'Alder Housing', 200, value=published(900000))
    keys['small'] = add(db, 'small', 'Birch Housing', 100, value=published(120000))
    keys['frame'] = add(db, 'frame', 'Cedar Consortium', 150, value=ceiling(40000000))   # a ceiling is not a contract value
    keys['later'] = add(db, 'later', 'Dale Housing', 500, value=published(5000000))      # beyond twelve months
    db.commit()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db, keys
    db.close()
    engine.dispose()


def chosen(v: dict) -> list[tuple[str, str]]:
    return [(c['chosen'], c['key']) for c in v['leads']]


def test_with_no_rep_the_brief_covers_the_whole_record_by_the_stated_rule(local):
    client, db, keys = local
    order = [x['key'] for x in core.discover(db, limit=500)['items']]
    v = client.get('/api/si/patch').json()
    assert v['rep'] == {'name': '', 'regions': [], 'services': [], 'sectors': [], 'targets': []} and v['reps'] == [] and v['active'] == ''
    # two independent records first (both rest on two sources, so the newer record leads), then the deadline closing soonest, then the largest
    # published contract ending within a year
    assert chosen(v) == [('two_records', keys['signal']), ('two_records', keys['fernhill']), ('closing', keys['tender']), ('ending', keys['ending']), ('ending', keys['small'])]
    assert v['counts'] == {'in_patch': 7, 'held': 7, 'target': 0, 'two_records': 2, 'closing': 1, 'ending': 2} and v['calls'] == []
    assert keys['frame'] not in [c['key'] for c in v['leads']] and keys['later'] not in [c['key'] for c in v['leads']]
    assert len(v['rule']) == 6 and [c['chosen_because'] for c in v['leads']][:3] == ['Two or more independent records', 'Two or more independent records', 'A published deadline still ahead']
    assert [x['key'] for x in core.discover(db, limit=500)['items']] == order  # reading the brief moves nothing in Discover
    assert not re.search(r'\d+(\.\d+)?\s?%|probab|likelihood|score', str(v['leads']).lower().replace('no score', ''))


def test_each_lead_carries_its_chain_published_or_inferred_and_every_record_opens_its_source(local):
    client, _db, keys = local
    leads = {c['key']: c for c in client.get('/api/si/patch').json()['leads']}
    signal = leads[keys['signal']]
    assert [(l['date'], l['label'], l['url']) for l in signal['chain']] == [
        ((TODAY - timedelta(days=150)).isoformat(), 'Published', living_fixtures.FENWICK_FINDING_URL),
        ((TODAY - timedelta(days=12)).isoformat(), 'Published', living_fixtures.FENWICK_EARLY_URL), ('', 'Inferred', '')]
    assert signal['chain'][0]['text'] == f'The Regulator of Social Housing graded {living_fixtures.FENWICK} C3'  # the record's own sentence, oldest first
    assert signal['chain'][2]['text'] == 'That is a reason to make contact now, while the buyer can still talk to suppliers'
    assert signal['sources'] == 2 and signal['next'] == {'action': 'open_notice', 'label': 'Read the record at its source', 'url': living_fixtures.FENWICK_EARLY_URL}
    # a tender: the notice and its deadline, both published, and no reading added
    tender = leads[keys['tender']]
    assert [(l['label'], l['url']) for l in tender['chain']] == [('Published', living_fixtures.ASHBY_URL), ('Published', living_fixtures.ASHBY_URL)]
    assert tender['chain'][1]['text'].startswith('Tender deadline: ') and tender['worth'] == '£480k estimated in the notice' and tender['region'] == YORKSHIRE
    # a contract ending: the award, its published end (read from that notice, so it opens it), then the reading
    ending = leads[keys['ending']]
    assert [l['label'] for l in ending['chain']] == ['Published', 'Published', 'Inferred'] and ending['chain'][0]['url'] == ending['chain'][1]['url'] != ''
    # research on a company: where it began, the latest thing that happened, the next dated thing ahead; the timing is inferred
    fernhill = leads[keys['fernhill']]
    assert [l['label'] for l in fernhill['chain']] == ['Published', 'Published', 'Published', 'Inferred'] and all(l['url'] for l in fernhill['chain'][:3])
    assert fernhill['chain'][0]['text'].startswith('£240m programme') and fernhill['chain'][3]['text'].startswith('Fernhill Parcels Ltd is adding or changing sites')
    assert fernhill['chain'][3]['text'] != fernhill['why_now'].rstrip('.')  # the timing is said once, in "Why now"
    assert fernhill['against'] == 1  # one record points the other way, and the card says so
    for c in leads.values():
        assert all(l['url'] for l in c['chain'] if l['label'] == 'Published') and not any(l['url'] for l in c['chain'] if l['label'] == 'Inferred')
        assert [l['date'] for l in c['chain'] if l['date']] == sorted(l['date'] for l in c['chain'] if l['date'])
        assert not ISO.search(' '.join(l['text'] for l in c['chain']) + c['why_now'] + c['headline'])


def test_a_rep_sees_their_patch_and_named_targets_come_first_wherever_they_are(local):
    client, db, keys = local
    saved = client.put('/api/si/patch/reps', json={'name': '  Sam   North ', 'regions': [YORKSHIRE, 'Atlantis'], 'services': ['fire_alarm'], 'sectors': [],
                                                    'targets': ['Fenwick Housing Trust']})
    v = saved.json()
    assert saved.status_code == 200 and v['active'] == 'Sam North' and v['rep'] == {'name': 'Sam North', 'regions': [YORKSHIRE], 'services': ['fire_alarm'], 'sectors': [],
                                                                                 'targets': ['Fenwick Housing Trust']}
    # Fenwick has no stated region, but it is a named target; the tender is in the patch; the rest state no region, so they are left out
    assert chosen(v) == [('target', keys['signal']), ('closing', keys['tender'])] and v['counts']['in_patch'] == 2
    assert v['leads'][0]['chosen_because'] == 'A target account you named'
    assert [o for o in v['options']['regions'] if o['leads']] == [{'name': YORKSHIRE, 'leads': 1}]
    # a second rep, and switching between them
    client.put('/api/si/patch/reps', json={'name': 'Jo West', 'regions': ['South West'], 'services': [], 'sectors': ['Housing'], 'targets': []})
    assert client.get('/api/si/patch').json()['rep']['name'] == 'Jo West' and client.get('/api/si/patch').json()['leads'] == []
    assert chosen(client.get('/api/si/patch', params={'rep': 'Sam North'}).json()) == [('target', keys['signal']), ('closing', keys['tender'])]
    assert client.post('/api/si/patch/active', json={'name': 'Sam North'}).json()['active'] == 'Sam North'
    assert (client.get('/api/si/patch/reps').json()['active'], [r['name'] for r in client.get('/api/si/patch/reps').json()['reps']]) == ('Sam North', ['Sam North', 'Jo West'])
    assert client.post('/api/si/patch/active', json={'name': 'Nobody'}).status_code == 404
    assert [r['name'] for r in client.delete('/api/si/patch/reps/Jo West').json()['reps']] == ['Sam North']
    assert core.preferences(db)['territory'] == []  # the workspace's own settings, and so the order of Discover, are untouched
    assert client.put('/api/si/patch/reps', json={'name': ' ', 'regions': []}).status_code in (400, 422)


def test_disciplines_and_sectors_narrow_the_patch_without_guessing(local):
    client, _db, keys = local
    cctv = client.put('/api/si/patch/reps', json={'name': 'Cam', 'regions': [], 'services': ['cctv'], 'sectors': [], 'targets': []}).json()
    picked = [c['key'] for c in cctv['leads']]
    assert keys['fernhill'] in picked and keys['tender'] not in picked and keys['ending'] not in picked  # a notice that names other services is left out
    housing = client.put('/api/si/patch/reps', json={'name': 'Hal', 'regions': [], 'services': [], 'sectors': ['Housing'], 'targets': []}).json()
    # read from each organisation's own name; with fewer than five in the patch, the rest of the patch fills the brief (Dale Housing, ending later)
    assert [(c['chosen'], c['organisation']) for c in housing['leads']] == [('two_records', 'Fenwick Housing Trust'), ('ending', 'Alder Housing'), ('ending', 'Birch Housing'),
                                                                           ('next', 'Dale Housing')]
    assert patch.sector_of({'organisation': 'Ashby Vale Council'}) == 'Local government' and patch.sector_of({'organisation': 'Fernhill Parcels Ltd', 'sector': 'Parcel delivery and logistics'}) == 'Retail and logistics'
    assert patch.sector_of({'organisation': 'Zed Ltd'}) == ''  # nothing states one, so none is claimed


def test_a_judged_lead_leaves_the_five_for_that_rep_only(local):
    client, _db, keys = local
    client.put('/api/si/patch/reps', json={'name': 'Sam North', 'regions': [], 'services': [], 'sectors': [], 'targets': []})
    client.put('/api/si/patch/reps', json={'name': 'Jo West', 'regions': [], 'services': [], 'sectors': [], 'targets': []})
    before = [c['key'] for c in client.get('/api/si/patch', params={'rep': 'Sam North'}).json()['leads']]
    client.post(f"/api/si/brief/{keys['fernhill']}/verdict", json={'verdict': 'worth_a_call', 'rep': 'Sam North'})
    client.post(f"/api/si/brief/{keys['tender']}/verdict", json={'verdict': 'knew_already', 'rep': 'Sam North'})
    sam = client.get('/api/si/patch', params={'rep': 'Sam North'}).json()
    after = [c['key'] for c in sam['leads']]
    assert keys['fernhill'] not in after and keys['tender'] not in after and [k for k in before if k in after] == after[:3]  # the rest move up; the brief moves on
    assert sam['said']['headline'] == '1 of 2 judged leads: didn’t know, worth a call'
    # what Sam said was worth a call stays in reach, and the counts say how much of the patch is left to judge
    assert [(c['key'], c['organisation']) for c in sam['calls']] == [(keys['fernhill'], 'Fernhill Parcels Ltd')] and (sam['counts']['held'], sam['counts']['in_patch']) == (7, 5)
    jo = client.get('/api/si/patch', params={'rep': 'Jo West'}).json()
    assert [c['key'] for c in jo['leads']] == before and jo['said']['judged'] == 0  # another rep's brief is untouched
    client.post(f"/api/si/brief/{keys['signal']}/verdict", json={'verdict': 'wrong', 'rep': 'Sam North'})
    assert keys['signal'] not in [c['key'] for c in client.get('/api/si/patch', params={'rep': 'Jo West'}).json()['leads']]  # a lead that is wrong is hidden for everyone


def test_the_brief_as_text_is_ready_to_send_and_discover_can_show_the_whole_patch(local):
    client, _db, keys = local
    client.put('/api/si/patch/reps', json={'name': 'Sam North', 'regions': [YORKSHIRE], 'services': [], 'sectors': [], 'targets': ['Fenwick Housing Trust']})
    sent = client.get('/api/si/patch/text')
    body = sent.text
    assert sent.status_code == 200 and sent.headers['content-type'].startswith('text/plain')
    assert body.splitlines()[0] == f'SalesIntel patch brief for Sam North, {TODAY:%-d %B %Y}' and '2 leads from public records in Yorkshire and the Humber.' in body
    assert f'1. {living_fixtures.FENWICK}  [Public record, before any tender]' in body and '2. Ashby Vale Council  [Published tender]' in body
    assert f'[Published] {living_fixtures.FENWICK_FINDING_URL}' in body and '- So: That is a reason to make contact now' in body and '[Inferred]' in body
    assert 'A = Didn’t know, worth a call   B = Knew already   C = Wrong' in body and not ISO.search(body.replace(living_fixtures.FENWICK_FINDING_URL, ''))
    # everything in the patch, in Discover's own order
    region = client.get('/api/si/discover', params={'region': YORKSHIRE}).json()
    assert [x['key'] for x in region['items']] == [keys['tender']] and client.get('/api/si/discover', params={'region': 'Wales'}).json()['total'] == 0
