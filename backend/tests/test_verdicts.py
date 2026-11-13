"""A rep's one-tap verdict on a lead, on fictional records.

- Three verdicts: "Didn't know, worth a call", "Knew already", "Wrong". Each is stored with the evidence that was shown.
- The latest verdict for a lead and a rep counts; the history stays; a verdict can be taken back.
- "Wrong" dismisses the lead and taking it back restores it. No verdict changes the order of the list.
- The measure is a count ("2 of 3"), in total, by kind of lead and by rep.
- A verdict follows the lead, whether it is given from the list or from its account."""
from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base, get_db
from app.main import create_app
from app.models.shadow import LeadFeedback
from app.services import atlas, atlas_fixtures, living_fixtures, verdicts
from app.services import si_core as core

TODAY = date.today()


@pytest.fixture
def local(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'verdicts.db'}", connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    db = Session(engine)
    keys = living_fixtures.load(db, TODAY)
    atlas_fixtures.load(db, TODAY)
    db.commit()
    atlas.ensure_built(db)
    db.commit()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db, keys
    db.close()
    engine.dispose()


def order(db) -> list[str]:
    return [x['key'] for x in core.discover(db, limit=500, status='all')['items']]


def test_a_verdict_is_stored_with_the_evidence_that_was_shown(local):
    client, db, keys = local
    before = client.get(f"/api/si/brief/{keys['signal']}").json()
    assert before['judgeable'] is True and before['verdict'] is None
    done = client.post(f"/api/si/brief/{keys['signal']}/verdict", json={'verdict': 'worth_a_call'})
    assert done.status_code == 200 and done.json()['verdict']['value'] == 'worth_a_call' and done.json()['verdict']['label'] == "Didn't know, worth a call"
    row = db.scalar(select(LeadFeedback).where(LeadFeedback.lead_key == keys['signal']))
    shown = json.loads(row.note)
    assert (row.decision, row.sensor, row.reason) == ('worth_a_call', 'public_signal', '')
    assert shown['headline'] == before['reveal']['headline'] and shown['why'] == before['reveal']['why'] and shown['next'] == before['next']['label']
    assert shown['organisation'] == living_fixtures.FENWICK and shown['kind_label'] == 'Public record, before any tender'
    # every dated record that was on screen, with its link and whether it was published
    assert {e['url'] for e in shown['evidence'] if e['url']} == {living_fixtures.FENWICK_EARLY_URL, living_fixtures.FENWICK_FINDING_URL,
                                                                 'https://www.contractsfinder.service.gov.uk/Notice/atlas-fixture-fenwick'}  # and the buyer's award notice
    assert [(e['title'], e['basis']) for e in shown['evidence'] if e['effect'] == 'supports'] == [('Official market engagement', 'published'),
                                                                                                 ('Regulator finding on fire safety compliance', 'published')]
    assert client.get(f"/api/si/brief/{keys['signal']}").json()['verdict']['value'] == 'worth_a_call'


def test_the_latest_verdict_counts_and_the_history_stays(local):
    client, db, keys = local
    for verdict in ('knew_already', 'worth_a_call'):
        assert client.post(f"/api/si/brief/{keys['tender']}/verdict", json={'verdict': verdict}).status_code == 200
    assert verdicts.current(db, keys['tender'])['value'] == 'worth_a_call'
    assert [r.decision for r in db.scalars(select(LeadFeedback).order_by(LeadFeedback.id))] == ['knew_already', 'worth_a_call']
    total = client.get('/api/si/brief/verdicts').json()
    assert (total['judged'], total['worth_a_call'], total['knew_already'], total['wrong']) == (1, 1, 0, 0)  # one lead, judged once
    # taken back: unjudged again, with every tap still on record
    assert client.post(f"/api/si/brief/{keys['tender']}/verdict", json={'verdict': 'cleared'}).json()['verdict'] is None
    assert client.get('/api/si/brief/verdicts').json()['judged'] == 0 and db.query(LeadFeedback).count() == 3
    assert client.post(f"/api/si/brief/{keys['tender']}/verdict", json={'verdict': 'brilliant'}).status_code == 422


def test_wrong_dismisses_the_lead_and_no_verdict_reorders_the_list(local):
    client, db, keys = local
    start = order(db)
    client.post(f"/api/si/brief/{keys['tender']}/verdict", json={'verdict': 'worth_a_call'})
    client.post(f"/api/si/brief/{keys['fernhill']}/verdict", json={'verdict': 'knew_already'})
    assert order(db) == start  # praise and "knew already" move nothing
    rows = {x['key']: x for x in core.discover(db, limit=500, status='all')['items']}
    assert rows[keys['tender']]['status'] == 'new' and rows[keys['fernhill']]['status'] == 'new'
    client.post(f"/api/si/brief/{keys['signal']}/verdict", json={'verdict': 'wrong'})
    assert keys['signal'] not in [x['key'] for x in core.discover(db, limit=500)['items']]  # hidden from the active list
    assert {x['key']: x['status'] for x in core.discover(db, limit=500, status='all')['items']}[keys['signal']] == 'dismissed'
    client.post(f"/api/si/brief/{keys['signal']}/verdict", json={'verdict': 'cleared'})
    assert order(db) == start and keys['signal'] in [x['key'] for x in core.discover(db, limit=500)['items']]  # taken back: restored, in its old place


def test_the_measure_is_a_count_by_kind_and_by_rep(local):
    client, db, keys = local
    client.post(f"/api/si/brief/{keys['signal']}/verdict", json={'verdict': 'worth_a_call', 'rep': 'Sam North'})
    client.post(f"/api/si/brief/{keys['tender']}/verdict", json={'verdict': 'knew_already', 'rep': 'Sam North'})
    client.post(f"/api/si/brief/{keys['fernhill']}/verdict", json={'verdict': 'worth_a_call', 'rep': 'Sam North'})
    client.post(f"/api/si/brief/{keys['tender']}/verdict", json={'verdict': 'worth_a_call', 'rep': 'Jo West'})  # the same lead, another rep
    total = client.get('/api/si/brief/verdicts').json()
    assert total['headline'] == '3 of 4 judged leads: didn’t know, worth a call' and '%' not in json.dumps(total)
    assert [(k['label'], k['judged'], k['worth_a_call']) for k in total['by_kind']] == [('Published tender', 2, 1), ('Private-sector signal', 1, 1),
                                                                                       ('Public record, before any tender', 1, 1)]
    assert [(r['rep'], r['judged'], r['worth_a_call'], r['knew_already']) for r in total['by_rep']] == [('Sam North', 3, 2, 1), ('Jo West', 1, 1, 0)]
    sam = client.get('/api/si/brief/verdicts', params={'rep': 'Sam North'}).json()
    assert sam['headline'] == '2 of 3 judged leads: didn’t know, worth a call' and len(sam['recent']) == 3
    # each rep sees their own verdict on a lead, and only their own
    assert client.get(f"/api/si/brief/{keys['tender']}", params={'rep': 'Sam North'}).json()['verdict']['value'] == 'knew_already'
    assert client.get(f"/api/si/brief/{keys['tender']}", params={'rep': 'Jo West'}).json()['verdict']['value'] == 'worth_a_call'
    assert client.get(f"/api/si/brief/{keys['tender']}").json()['verdict'] is None
    assert verdicts.judged(db, 'Sam North') == {keys['signal']: 'worth_a_call', keys['tender']: 'knew_already', keys['fernhill']: 'worth_a_call'}
    assert verdicts.summary(db, 'Nobody')['headline'] == ''  # nothing judged is never reported as a result


def test_a_verdict_follows_the_lead_from_its_account(local):
    client, db, keys = local
    account, _link, _created = core.link_source(db, 'market_opportunity', int(keys['signal'].split(':')[1]))
    db.commit()
    assert client.post(f'/api/si/brief/acct:{account.id}/verdict', json={'verdict': 'knew_already'}).json()['verdict']['value'] == 'knew_already'
    assert db.scalar(select(LeadFeedback.lead_key)) == keys['signal']
    assert client.get(f"/api/si/brief/{keys['signal']}").json()['verdict']['value'] == 'knew_already'
    assert client.get(f'/api/si/brief/acct:{account.id}').json()['judgeable'] is True
    # an account that did not come from a lead has nothing to judge
    made = client.post('/api/si/accounts', json={'name': 'Standalone Example Ltd'}).json()['account_id']
    own = client.get(f'/api/si/brief/acct:{made}').json()
    assert own['judgeable'] is False and own['verdict'] is None
    refused = client.post(f'/api/si/brief/acct:{made}/verdict', json={'verdict': 'wrong'})
    assert refused.status_code in (400, 422) and 'Only a lead can be judged' in refused.text


def test_shadow_radars_own_scorecard_is_not_disturbed(local):
    client, db, keys = local
    client.post(f"/api/si/brief/{keys['tender']}/verdict", json={'verdict': 'worth_a_call'})
    card = client.get('/api/si/radar/scorecard')
    assert card.status_code == 200 and 'public_tender' not in json.dumps(card.json())  # verdicts on other leads never appear as a "sensor"
