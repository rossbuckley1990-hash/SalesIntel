"""The directors of a small firm, from Companies House, for who to call (item 2 of the contacts plan, 17 November 2026).

Companies House answers from fictional companies here; nothing reaches the network. The officer records carry the
personal details the real register publishes, so the tests can show SalesIntel keeps none of them.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime

import httpx
import pytest

from app.models.crm import Contact
from app.models.prospect import Prospect
from app.models.research_chat import ResearchChat
from app.services import directors as d
from app.services import research_chat as rc
from app.services import who_to_call as wtc
from tenancy_support import hosted  # noqa: F401
from test_acquisition import workspace
from test_research_chat import _card, _state, start

TODAY = date(2026, 11, 17)
SECRET = {'date_of_birth': {'month': 4, 'year': 1971}, 'nationality': 'Martian', 'country_of_residence': 'Atlantis', 'occupation': 'Hotelier',
          'address': {'premises': '9', 'address_line_1': 'Private Road', 'locality': 'Hometown'}}


def officer(name, role='director', appointed='2010-01-04', resigned=None):
    return {'name': name, 'officer_role': role, 'appointed_on': appointed, **({'resigned_on': resigned} if resigned else {}), **SECRET}


def company(name, accounts='total-exemption-full', status='active', kind='ltd', officers=None, town='Harrogate'):
    return {'company_name': name, 'company_status': status, 'type': kind, 'accounts': accounts, 'town': town,
            'officers': [officer('MOOR, Jane Elizabeth')] if officers is None else officers}


class Register:
    """A fictional Companies House: profiles, officer lists and search, and every request it was sent."""

    def __init__(self, companies, status=200):
        self.companies, self.status, self.requests = companies, status, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status)
        parts = request.url.path.strip('/').split('/')
        if parts == ['search', 'companies']:
            q = request.url.params['q'].casefold()
            return httpx.Response(200, json={'items': [
                {'company_number': n, 'title': c['company_name'], 'company_status': c['company_status'], 'date_of_creation': '2004-02-01',
                 'address': {'premises': '9', 'address_line_1': 'Private Road', 'locality': c['town'], 'postal_code': 'HG1 1AA'},
                 'address_snippet': f"9 Private Road, {c['town']}, HG1 1AA"}
                for n, c in self.companies.items() if q.split()[0] in c['company_name'].casefold()]})
        found = self.companies.get(parts[1]) if parts[0] == 'company' else None
        if found is None:
            return httpx.Response(404)
        if len(parts) == 2:
            return httpx.Response(200, json={'company_number': parts[1], 'company_name': found['company_name'], 'company_status': found['company_status'],
                                             'type': found['type'], 'registered_office_address': SECRET['address'],
                                             'accounts': {'last_accounts': {'type': found['accounts']}}})
        return httpx.Response(200, json={'items': found['officers'], 'total_results': len(found['officers'])})


@pytest.fixture
def register(monkeypatch):
    def use(companies, status=200):
        reg = Register(companies, status)
        monkeypatch.setattr(d, 'TRANSPORT', httpx.MockTransport(reg))
        monkeypatch.setattr(d, '_key', lambda: 'test-key')
        return reg
    return use


def test_names_are_written_as_people_are_addressed_and_companies_are_matched_by_number_and_name():
    assert d.person_name('MOOR, Jane Elizabeth') == 'Jane Moor'
    assert d.person_name("O'NEILL-MCDONALD, Dr Siobhan, Ms") == "Siobhan O'Neill-McDonald"
    assert d.number(' 0504 9116 ') == '05049116' and d.number('SC123456') == 'SC123456' and d.number('5049116') == '' and d.number('Campeys') == ''
    assert d.same_company("DAISH'S HOLIDAYS LIMITED", "Daish's Holidays Ltd")
    assert d.same_company('HIND WELLINGBOROUGH LIMITED', 'Hind Wellingborough Limited (The Hind Hotel)')
    assert d.same_company('DHL SUPPLY CHAIN LIMITED', 'DHL Supply Chain UK')
    assert not d.same_company('ARORA HOLDINGS LIMITED', 'Arora Group')
    assert not d.same_company('MOORSIDE GARAGE LIMITED', 'Moorside Hotel Ltd')


def test_a_small_firm_s_directors_are_named_with_name_role_and_date_only(register):
    register({'01234567': company('MOORSIDE HOTEL LIMITED', officers=[
        officer('MOOR, Jane Elizabeth', appointed='2004-02-01'), officer('MOOR, Peter', appointed='2011-09-12'),
        officer('MOOR, Edward', resigned='2019-04-30'), officer('LEDGER SECRETARIES LIMITED', role='corporate-secretary'),
        officer('HOLDCO LIMITED', role='corporate-director'), officer('SHAW, Ann', role='secretary')])})
    got = d.read('01234567', 'Moorside Hotel Ltd', TODAY)
    assert got['shown'] and got['directors'] == [{'name': 'Jane Moor', 'role': 'Director', 'appointed_on': '2004-02-01'},
                                                 {'name': 'Peter Moor', 'role': 'Director', 'appointed_on': '2011-09-12'}]
    kept = json.dumps(got)
    for secret in ('1971', 'Martian', 'Atlantis', 'Hotelier', 'Private Road', 'Hometown', 'Elizabeth', 'Edward', 'LEDGER', 'HOLDCO', 'Shaw'):
        assert secret not in kept  # no date of birth, nationality, residence, occupation, address, middle name, or anyone else
    assert d.note(got) == ('Companies House, read by SalesIntel on 17 November 2026: MOORSIDE HOTEL LIMITED (01234567) files small-company accounts '
                           'and has 2 active directors.')
    assert got['source_url'] == 'https://find-and-update.company-information.service.gov.uk/company/01234567/officers'


@pytest.mark.parametrize('firm, why', [
    (company('MOORSIDE HOTEL LIMITED', accounts='full'), 'It files full accounts, so it is not a small firm: at a company this size, ask for the facilities '
                                                         'or site manager rather than a director.'),
    (company('MOORSIDE HOTEL LIMITED', accounts='audit-exemption-subsidiary'), 'It files subsidiary accounts'),
    (company('MOORSIDE HOTEL PLC', kind='plc'), 'It is a public limited company'),
    (company('MOORSIDE HOTEL LIMITED', status='dissolved'), 'Companies House lists it as dissolved, so its directors are not shown.'),
    (company('MOORSIDE HOTEL LIMITED', accounts='dormant'), 'It files dormant-company accounts'),
    (company('MOORSIDE HOTEL LIMITED', accounts=''), 'It has not yet filed accounts that show its size'),
    (company('MOORSIDE HOTEL LIMITED', officers=[officer(f'MOOR, Person{i}') for i in range(5)]), 'It has 5 active directors: with a board that size'),
])
def test_directors_are_not_named_where_a_director_rarely_buys_fire_and_security(register, firm, why):
    register({'01234567': firm})
    got = d.read('01234567', 'Moorside Hotel', TODAY)
    assert not got['shown'] and got['directors'] == [] and why in got['why'] and why in d.note(got)


def test_a_number_research_gives_must_belong_to_the_lead_but_one_the_rep_chooses_is_theirs(register):
    register({'01234567': company('MOORSIDE GARAGE LIMITED')})
    wrong = d.read('01234567', 'Moorside Hotel Ltd', TODAY)
    assert wrong['mismatch'] and not wrong['shown'] and wrong['directors'] == []
    assert 'That number belongs to a company of another name, so SalesIntel did not use it.' in d.note(wrong)
    chosen = d.read('01234567', 'Moorside Hotel Ltd', TODAY, chosen=True)
    assert chosen['shown'] and chosen['directors'][0] == {'name': 'Jane Moor', 'role': 'Sole director', 'appointed_on': '2010-01-04'}


def test_nothing_is_read_without_a_key_a_number_or_an_answer(register, monkeypatch):
    reg = register({})
    assert d.read('Moorside', 'Moorside Hotel', TODAY)['stopped'].startswith('That is not a Companies House company number')
    assert d.read('01234567', 'Moorside Hotel', TODAY) | {'read_on': ''} == {
        'company_number': '01234567', 'read_on': '', 'chosen': False, 'stopped': 'Companies House has no company with that number.', 'unavailable': False}
    reg = register({}, status=429)
    assert d.read('01234567', 'Moorside Hotel', TODAY)['stopped'] == 'Companies House is busy; try again in a few minutes.'
    monkeypatch.setattr(d, '_key', lambda: None)
    asked = len(reg.requests)
    assert d.read('01234567', 'Moorside Hotel', TODAY)['stopped'] == d.NOT_SET_UP and len(reg.requests) == asked
    with pytest.raises(d.LookupFailed, match='not set up'):
        d.search('Moorside')


def lead(**over):
    base = {'name': 'Moorside Hotel Ltd', 'sector': 'Hospitality (hotel)', 'signals': [{'type': 'refurbishment', 'source_url': 'https://news.example/moorside'}],
            'timing_clues': [], 'people': [], 'contact_routes': [{'kind': 'phone', 'value': '01423 960 000', 'source_url': 'https://www.moorside.example/contact'}]}
    return {**base, **over}


def test_a_sole_director_is_the_person_to_ask_for_and_the_route_still_comes_from_elsewhere(register):
    register({'01234567': company('MOORSIDE HOTEL LIMITED')})
    call = wtc.view(lead(register_read=d.read('01234567', 'Moorside Hotel Ltd', TODAY)), [], TODAY)
    assert call['line'] == 'Call 01423 960 000 and ask for Jane Moor, Sole director.'
    assert call['person']['from'] == 'register' and call['person']['fits'] and call['reachable'] and not call['direct']
    assert call['route']['how'] == 'Stated on moorside.example, found by research'  # Companies House gives no route
    assert call['register'] == {'company_number': '01234567', 'company_name': 'MOORSIDE HOTEL LIMITED', 'read_on': '2026-11-17', 'shown': True,
                                'mismatch': False, 'directors': 1, 'note': call['register']['note']}
    # With no route on record, the director is named and the card says there is no way in yet.
    alone = wtc.view(lead(contact_routes=[], register_read=d.read('01234567', 'Moorside Hotel Ltd', TODAY)), [], TODAY)
    assert alone['line'] == 'Jane Moor, Sole director, is named, but no way to reach them is on record yet.' and not alone['reachable']


def test_several_directors_research_names_and_do_not_contact(register):
    register({'01234567': company('MOORSIDE HOTEL LIMITED', officers=[officer('MOOR, Jane Elizabeth'), officer('MOOR, Peter James'), officer('HALE, Rita')])})
    read = d.read('01234567', 'Moorside Hotel Ltd', TODAY)
    gm = {'name': 'Sam Rowe', 'role': 'General Manager', 'source_url': 'https://www.moorside.example/team'}
    peter = {'name': 'Peter J. Moor', 'role': 'Owner', 'source_url': 'https://news.example/moorside'}
    call = wtc.view(lead(people=[gm, peter], register_read=read), [], TODAY)
    assert call['line'] == 'Call 01423 960 000 and ask for Peter J. Moor, Owner.'  # research's owner, not repeated from the register
    assert [a['name'] for a in call['also']] == ['Sam Rowe', 'Jane Moor', 'Rita Hale']
    # Directors of a firm with several are senior people, not owners: the card asks who looks after fire safety.
    plain = wtc.view(lead(register_read=read), [], TODAY)
    assert plain['line'].startswith('Call 01423 960 000 and ask who looks after fire safety') and 'Jane Moor, Director.' in plain['line']
    opted = Contact(name='Jane Moor', status='do_not_contact', flags=[])
    left = wtc.view(lead(register_read=read), [opted], TODAY)
    assert 'Jane Moor' not in json.dumps(left) and left['person']['name'] == 'Peter Moor'


def test_a_chat_card_with_a_company_number_reads_the_register_once_a_day(hosted, register):
    h = hosted
    c, org = workspace(h, 'ana', 'Alpha Fire Ltd')
    chat_id = start(c)['id']
    reg = register({'01234567': company('EXAMPLE COLD STORE LIMITED')})
    assert 'Give its Companies House company number when a page you read states it' in rc.system_prompt('Alpha Fire Ltd')
    db, state = _state(h, org, chat_id)
    told = state.offer(_card(company_number='0123 4567'))
    assert told['companies_house'].endswith('EXAMPLE COLD STORE LIMITED (01234567) files small-company accounts and has 1 active director.')
    assert told['who_to_call'] == 'Jane Moor, Sole director, is named, but no way to reach them is on record yet.'
    asked = len(reg.requests)
    state.offer(_card(company_number='01234567'))
    assert len(reg.requests) == asked  # read once a day is enough
    assert state.offer(_card(name='Example Other Ltd'))['companies_house'] == 'No company number was given, so SalesIntel did not read Companies House.'
    chat = db.get(ResearchChat, chat_id)
    chat.cards = state.cards
    saved = rc.save_card(db, chat, 1)
    db.commit()
    assert db.get(Prospect, saved['prospect_id']).data['register_read']['directors'][0]['name'] == 'Jane Moor'
    db.close()


def test_a_saved_lead_is_found_on_companies_house_by_the_rep_s_choice(hosted, register):
    h = hosted
    c, org = workspace(h, 'ana', 'Alpha Fire Ltd')
    reg = register({'01234567': company('MOORSIDE HOTEL LIMITED'), '07654321': company('MOORSIDE HOLIDAYS LIMITED', status='dissolved', town='Leeds')})
    db = h.as_workspace(org)
    now = datetime.now(UTC)
    row = Prospect(dedup_key='moorside hotel', name='Moorside Hotel Ltd', status='new', data=lead(company_number=''), created_at=now, updated_at=now)
    db.add(row)
    db.commit()
    pid = row.id
    db.close()
    url = f'/api/si/prospects/{pid}/read-register'
    assert c.post('/api/si/prospects/999999/read-register', json={}).status_code == 404
    # A name only lists companies, with the town of the registered office and no more of its address; nothing is kept.
    listed = c.post(url, json={'query': 'Moorside'})
    assert listed.status_code == 200, listed.text
    assert listed.json() == {'lead': None, 'candidates': [
        {'company_number': '01234567', 'name': 'MOORSIDE HOTEL LIMITED', 'status': 'active', 'town': 'Harrogate', 'created': '2004-02-01'},
        {'company_number': '07654321', 'name': 'MOORSIDE HOLIDAYS LIMITED', 'status': 'dissolved', 'town': 'Leeds', 'created': '2004-02-01'}]}
    db = h.as_workspace(org)
    assert 'register_read' not in db.get(Prospect, pid).data
    db.close()
    # The rep's choice is read and kept, with the number.
    chose = c.post(url, json={'company_number': '01234567'})
    assert chose.status_code == 200, chose.text
    call = chose.json()['lead']['brief']['who']['call']
    assert call['line'] == 'Call 01423 960 000 and ask for Jane Moor, Sole director.' and call['register']['shown']
    assert chose.json()['lead']['company_number'] == '01234567'
    brief = c.get(f'/api/si/brief/pr:{pid}')  # the lead page, loaded again, says the same
    assert brief.status_code == 200, brief.text
    assert brief.json()['call']['line'] == call['line'] and brief.json()['call']['register']['shown']
    # With a number on record, an empty request reads it again; a typed number is read directly.
    assert c.post(url, json={}).status_code == 200
    assert c.post(url, json={'query': '07654321'}).json()['lead']['brief']['who']['call']['register']['note'].endswith('so its directors are not shown.')
    assert c.post(url, json={'query': 'Nothing Like It'}).status_code == 422
    assert c.post(url, json={'company_number': '09999999'}).json()['detail'] == 'Companies House has no company with that number.'
    register({}, status=503)
    assert c.post(url, json={'query': 'Moorside'}).status_code == 503
    assert all(r.url.host == 'api.company-information.service.gov.uk' for r in reg.requests)
