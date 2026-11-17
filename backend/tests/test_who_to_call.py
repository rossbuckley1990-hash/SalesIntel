"""Who to call: the right role for what is happening, the best person a source names, and the best way in. Never a guessed address.

- SalesIntel's site reader reads only the organisation's own website, only pages robots.txt allows, under an honest name. A site
  that asks automated readers to stop is not read; there is no way round that. Every detail kept is on a page it fetched, word for
  word, with the words around it and the day it was read.
- A route reaches a person only when the words around it name them. The card says how each route was found and, when no route
  reaches the right person, the next best way in. People the team marked "do not contact" are left out wherever they are named.
- During a live procurement the notice's own contact point is the way in.

Every organisation, person, address and number here is fictional (".example" domains, Ofcom drama numbers).
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import httpx

from app.models.crm import Contact
from app.models.prospect import Prospect
from app.models.research_chat import ResearchChat
from app.services import research_chat as rc
from app.services import site_reader as sr
from app.services import who_to_call as wtc
from tenancy_support import hosted  # noqa: F401
from test_acquisition import workspace
from test_patch import local  # noqa: F401
from test_research_chat import NEWS, PEOPLE, _card, _state, start

TODAY = date(2026, 11, 17)
SITE = 'https://www.example-cold-store.example'
HOME = ('<html><head><title>Example Cold Store</title></head><body><nav><a href="/contact-us">Contact us</a> <a href="/about/our-team">Our team</a> '
        '<a href="https://elsewhere.example/partner">Our partner</a></nav><p>Fresh food logistics.</p>'
        '<script>var hidden = "spam@example-cold-store.example";</script></body></html>')
CONTACT = ('<html><head><title>Contact us</title></head><body><p>Head office: 01632 960 123</p><p>Fax: 01632 960 999</p>'
           '<p>General enquiries: info@example-cold-store.example</p><p>Data protection: privacy@example-cold-store.example</p>'
           '<p>Website by hello@web-agency.example</p><p><a href="mailto:facilities@example-cold-store.example?subject=Hello">Email our facilities team</a></p></body></html>')
TEAM = ('<html><head><title>Our team</title></head><body><h2>Jane Smith</h2><p>Facilities Manager, Jane Smith, looks after our three sites. '
        'Reach Jane on jane.smith@example-cold-store.example or +44 (0)1632 960 123.</p></body></html>')
JANE = {'name': 'Jane Smith', 'role': 'Facilities Manager', 'source_url': PEOPLE, 'quote': 'Jane Smith, Facilities Manager', 'influence': 'operational', 'why': ''}
ALEX = {'name': 'Alex Other', 'role': 'Chief Executive', 'source_url': PEOPLE, 'quote': 'Alex Other, Chief Executive', 'influence': 'decision', 'why': ''}
ASK = 'who looks after fire safety and the maintenance of their fire and security systems'


class Site:
    """A fictional website: pages by path, a robots.txt, and every request it was sent."""

    def __init__(self, pages=None, robots='User-agent: *\nAllow: /\n', headers=None):
        self.pages = {'/': HOME, '/contact-us': CONTACT, '/about/our-team': TEAM} if pages is None else pages
        self.robots, self.headers, self.requests = robots, headers or {}, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text=self.robots) if isinstance(self.robots, str) else httpx.Response(self.robots or 404)
        found = self.pages.get(request.url.path)
        if found is None:
            return httpx.Response(404)
        status, body, extra = found if isinstance(found, tuple) else (200, found, {})
        return httpx.Response(status, headers={'content-type': 'text/html; charset=utf-8', **self.headers, **extra}, text=body)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self), headers={'User-Agent': sr.USER_AGENT})


def read(site: Site, names=('Jane Smith', 'Alex Other')) -> dict:
    return sr.read(SITE, list(names), TODAY, client=site.client())


def test_the_reader_keeps_only_what_the_organisations_own_pages_show_word_for_word():
    site = Site()
    found = read(site)
    assert found['stopped'] == '' and found['read_on'] == '2026-11-17'
    assert [p['url'] for p in found['pages']] == [f'{SITE}/', f'{SITE}/contact-us', f'{SITE}/about/our-team']  # contact pages first; never the partner's site
    # Kept: a phone number, a general address, a department and a named person. Not kept: the fax, data protection, the web agency,
    # an address only in a script, and the same number written another way.
    assert [r['value'] for r in found['routes']] == ['info@example-cold-store.example', '01632 960 123', 'facilities@example-cold-store.example',
                                                     'jane.smith@example-cold-store.example']
    for r in found['routes']:
        assert r['value'] in r['quote'] or r['quote'] == 'Email our facilities team'  # an address only in a link keeps the link's own words
        assert r['source_url'].startswith(SITE) and r['read_on'] == '2026-11-17'
    jane = found['routes'][-1]
    assert jane['name'] == 'Jane Smith' and 'Facilities Manager, Jane Smith, looks after our three sites' in jane['quote']
    assert [r['name'] for r in found['routes'][:3]] == ['', '', '']  # a name is attached only when the words around the detail name the person
    assert {r.url.host for r in site.requests} == {'www.example-cold-store.example'}
    assert all(r.headers['user-agent'].startswith('SalesIntelContactReader/1.0') and 'cookie' not in r.headers for r in site.requests)
    assert sr.digits('+44 (0)1632 960 123') == sr.digits('01632 960 123') == '01632960123'


def test_robots_txt_and_any_request_to_stop_are_obeyed():
    barred = Site(robots='User-agent: *\nDisallow: /about/\n')
    found = read(barred)
    assert [p['url'] for p in found['pages']] == [f'{SITE}/', f'{SITE}/contact-us'] and found['not_allowed'] == [f'{SITE}/about/our-team']
    assert '/about/our-team' not in [r.url.path for r in barred.requests]
    only_us = Site(robots='User-agent: SalesIntelContactReader\nDisallow: /\n')
    assert read(only_us)['pages'] == [] and [r.url.path for r in only_us.requests] == ['/robots.txt']
    for site, said in [(Site(robots=403), 'asked automated readers to stop (HTTP 403)'),
                       (Site(robots=503), 'asked automated readers to stop (HTTP 503)'),
                       (Site(pages={'/': '<html><head><title>Just a moment...</title></head><body>Checking</body></html>'}), 'showed a check for automated readers'),
                       (Site(pages={'/': HOME, '/contact-us': (429, 'Slow down', {})}), 'asked automated readers to stop (HTTP 429)'),
                       (Site(headers={'cf-mitigated': 'challenge'}), 'asked automated readers to stop')]:
        stopped = read(site)
        assert said in stopped['stopped'] and stopped['routes'] == [], said
    assert read(Site(robots=500))['stopped'].endswith('could not say which pages may be read (HTTP 500), so it was not read.')
    # Live, 17 November 2026: a site built by scripts has no words to read. It says so, rather than "no contact details published".
    shell = '<html><head><title></title></head><body><div id="root"></div><script src="/app.js"></script></body></html>'
    assert read(Site(pages={'/': shell, '/contact': shell}))['stopped'] == (
        'www.example-cold-store.example builds its pages with scripts, which SalesIntel’s reader does not run, so it found no words to read. '
        'Open the site yourself, or ask the research chat to read it.')
    # A redirect off the site is not followed; with no first page, the usual contact pages are tried instead.
    moved = Site(pages={'/': (301, '', {'location': 'https://elsewhere.example/'}), '/contact': CONTACT})
    found = read(moved)
    assert [p['url'] for p in found['pages']] == [f'{SITE}/contact'] and 'elsewhere.example' not in {r.url.host for r in moved.requests}


def test_only_a_website_is_read():
    assert sr.root('example-cold-store.example') == ('https://example-cold-store.example/', 'example-cold-store.example')
    assert sr.root('https://www.example-cold-store.example/en') == ('https://www.example-cold-store.example/en', 'example-cold-store.example')
    assert [sr.root(x) for x in ('', 'mailto:a@b.example', 'localhost', 'http://127.0.0.1', 'ftp://files.example')] == [None] * 5
    assert sr.read('not a website', [], TODAY)['stopped'] == 'No website address to read.'
    assert sr.own('uk.example-cold-store.example', 'example-cold-store.example') and not sr.own('example-cold-store.example.evil.example', 'example-cold-store.example')


def record(**over) -> dict:
    base = {'name': 'Example Cold Store Ltd', 'sector': 'Food logistics and cold storage', 'signals': [{'type': 'new_site', 'source_url': NEWS}],
            'timing_clues': [{'kind': 'site_opening', 'date': '2027-05'}], 'people': [ALEX, JANE], 'contact_routes': []}
    return {**base, **over}


def test_the_right_person_by_name_and_a_route_that_names_them():
    call = wtc.view(record(site_read=read(Site())), [], TODAY)
    assert call['play'] == 'new_site' and call['roles'] == ['Estates or property director', 'Site or general manager of the depot',
                                                            'Head of facilities or facilities manager']
    assert call['person']['name'] == 'Jane Smith' and call['person']['fits'] and call['grade'] == 'direct' and call['direct']
    assert call['line'] == 'Email Jane Smith, Facilities Manager, at jane.smith@example-cold-store.example.'
    assert call['route']['how'] == 'On example-cold-store.example, the organisation’s own website, read by SalesIntel on 17 November 2026' and call['route']['confirmed']
    assert call['cautions'] == ['Their address is personal data: say where you found it and offer an easy way to opt out in the first email.']
    assert [p['name'] for p in call['also']] == ['Alex Other'] and len(call['more']) == 3
    assert call['site'] == {'website': SITE, 'read_on': '2026-11-17', 'stopped': '', 'pages': 3, 'found': 4}


def test_when_no_route_names_them_the_card_gives_the_next_best_way_in():
    switchboard = [{'kind': 'switchboard', 'value': '01632 960 123', 'label': 'Head office', 'source_url': NEWS, 'quote': 'Head office: 01632 960 123'}]
    call = wtc.view(record(contact_routes=switchboard), [], TODAY)
    assert call['line'] == 'Call 01632 960 123 and ask for Jane Smith, Facilities Manager.' and call['grade_label'] == 'Main line'
    assert call['route']['how'] == 'Stated on news.example, found by research' and not call['route']['confirmed'] and call['reachable'] and not call['direct']
    assert call['cautions'] == ['Before a cold call, check the number against the CTPS and TPS do-not-call registers.']
    # Only the chief executive is named: they are the most senior person named, not the buyer.
    senior = wtc.view(record(people=[ALEX], contact_routes=switchboard), [], TODAY)
    assert senior['line'] == f'Call 01632 960 123 and ask {ASK}. The most senior person named is Alex Other, Chief Executive.'
    assert senior['person']['fits'] is False and not senior['reachable']
    nobody = wtc.view(record(people=[]), [], TODAY)
    assert nobody['line'] == 'No named person or way in is on record yet. Look for the estates or property director.' and nobody['grade'] == 'none'
    general = wtc.view(record(people=[], contact_routes=[{'kind': 'email', 'value': 'info@example-cold-store.example', 'source_url': NEWS, 'quote': ''}]), [], TODAY)
    assert general['line'] == 'Email info@example-cold-store.example and ask for the estates or property director.'


def test_the_sector_and_what_is_happening_decide_the_roles():
    care = wtc.view(record(sector='Care homes', signals=[{'type': 'acquisition'}], timing_clues=[],
                           people=[ALEX, {'name': 'Morgan Day', 'role': 'Registered Manager', 'source_url': PEOPLE}]), [], TODAY)
    assert care['play'] == 'supplier_review' and care['roles'] == ['Head of facilities or facilities manager', 'Registered manager of the home',
                                                                    'Contract manager for the current service']
    assert care['person']['name'] == 'Morgan Day' and care['line'] == 'Morgan Day, Registered Manager, is named, but no way to reach them is on record yet.'
    inn = wtc.view(record(sector='Hospitality (B&B / inn)', signals=[{'type': 'fire_incident'}], timing_clues=[],
                          people=[{'name': 'Pat Example', 'role': 'Owner', 'source_url': PEOPLE}],
                          contact_routes=[{'kind': 'phone', 'value': '01632 960 456', 'source_url': NEWS, 'quote': 'Bookings: 01632 960 456'}]), [], TODAY)
    assert inn['play'] == 'risk' and inn['roles'][:2] == ['Fire safety or health and safety lead', 'General manager of the hotel or site']
    assert inn['line'] == 'Call 01632 960 456 and ask for Pat Example, Owner.'  # at a business its owner runs, the owner decides
    # A right person who can be reached directly beats a better-placed one who cannot.
    estates = {'name': 'Lee Estates', 'role': 'Estates Director', 'source_url': PEOPLE}
    both = wtc.view(record(people=[estates, JANE], site_read=read(Site())), [], TODAY)
    assert both['person']['name'] == 'Jane Smith' and both['grade'] == 'direct'
    assert wtc.view(record(people=[estates, JANE]), [], TODAY)['person']['name'] == 'Lee Estates'


def test_saved_contacts_count_and_do_not_contact_is_obeyed_wherever_the_person_is_named():
    sam = Contact(name='Sam Lee', role='Head of Estates', email='sam.lee@example-cold-store.example', quality='public_source', basis='published',
                  source_url=NEWS, source_quote='Sam Lee, Head of Estates, on sam.lee@example-cold-store.example', status='unverified', route_kind='email', flags=[])
    call = wtc.view(record(), [sam], TODAY)
    assert call['person'] == {'name': 'Sam Lee', 'role': 'Head of Estates', 'source_url': NEWS, 'from': 'saved', 'fits': True, 'host': 'news.example'}
    assert call['line'] == 'Email Sam Lee, Head of Estates, at sam.lee@example-cold-store.example.' and call['route']['how'] == 'Saved by your team: publicly sourced'
    opted_out = Contact(name='Jane Smith', email='jane.smith@example-cold-store.example', status='do_not_contact', route_kind='email', flags=[])
    call = wtc.view(record(site_read=read(Site())), [opted_out], TODAY)
    assert call['person']['name'] == 'Alex Other' and 'jane.smith@example-cold-store.example' not in str(call) and 'Jane Smith' not in str(call)


def test_during_a_live_procurement_the_notice_is_the_way_in():
    call = wtc.during_procurement(wtc.view({}, [], TODAY, play='public_tender'))
    assert call['grade_label'] == 'The notice’s own route' and call['route'] is None and not call['reachable']
    assert call['line'] == ('Use the contact point and clarification process the notice gives. During a live procurement, an approach outside it can count '
                            'against a bid.')


def test_a_chat_card_reads_the_website_once_a_day_and_keeps_what_it_found_when_saved(hosted, monkeypatch):
    h = hosted
    c, org = workspace(h, 'ana', 'Alpha Fire Ltd')
    chat_id = start(c)['id']
    site = Site()
    monkeypatch.setattr(sr, 'TRANSPORT', httpx.MockTransport(site))
    assert 'Give the organisation\'s own website whenever you know it' in rc.system_prompt('Alpha Fire Ltd')
    db, state = _state(h, org, chat_id)
    told = state.offer(_card(website=SITE, people=[JANE]))
    assert told['who_to_call'] == 'Email Jane Smith, Facilities Manager, at jane.smith@example-cold-store.example.'
    assert told['website_read'].startswith(f'Read 3 page(s) of {SITE}: info@example-cold-store.example, 01632 960 123')
    asked = len(site.requests)
    state.offer(_card(website=SITE, people=[JANE]))
    assert len(site.requests) == asked  # read once a day is enough
    card = rc.card_view(state.cards[0], TODAY)
    assert card['call']['grade'] == 'direct' and card['call']['site']['found'] == 4
    chat = db.get(ResearchChat, chat_id)
    chat.cards = state.cards
    saved = rc.save_card(db, chat, 1)
    db.commit()
    prospect = db.get(Prospect, saved['prospect_id'])
    assert prospect.data['site_read']['routes'][-1]['name'] == 'Jane Smith'
    db.close()
    lead = next(x for x in c.get('/api/si/discover', params={'status': 'all'}).json()['items'] if x['key'] == f"pr:{saved['prospect_id']}")
    assert lead['brief']['who']['call']['line'] == 'Email Jane Smith, Facilities Manager, at jane.smith@example-cold-store.example.'
    # No website: nothing is read, and the model is told so.
    assert state.offer(_card(name='Example Other Ltd'))['website_read'] == 'No website was given, so SalesIntel did not read one.'


def test_a_saved_lead_s_website_is_read_on_request(hosted, monkeypatch):
    h = hosted
    c, org = workspace(h, 'ana', 'Alpha Fire Ltd')
    monkeypatch.setattr(sr, 'TRANSPORT', httpx.MockTransport(Site()))
    db = h.as_workspace(org)
    now = datetime.now(UTC)
    row = Prospect(dedup_key='example cold store', name='Example Cold Store Ltd', status='new', data=record(website=''), created_at=now, updated_at=now)
    db.add(row)
    db.commit()
    pid = row.id
    db.close()
    assert c.post(f'/api/si/prospects/{pid}/read-site', json={}).status_code == 422  # no website on record and none given
    assert c.post(f'/api/si/prospects/{pid}/read-site', json={'website': 'not a website'}).status_code == 422
    assert c.post('/api/si/prospects/999999/read-site', json={'website': SITE}).status_code == 404
    got = c.post(f'/api/si/prospects/{pid}/read-site', json={'website': 'www.example-cold-store.example'})
    assert got.status_code == 200, got.text
    lead = got.json()
    assert lead['key'] == f'pr:{pid}' and lead['brief']['who']['call']['direct'] is True and lead['brief']['who']['call']['site']['found'] == 4
    db = h.as_workspace(org)
    assert db.get(Prospect, pid).data['website'] == 'www.example-cold-store.example'
    db.close()


def test_the_brief_that_is_sent_says_who_to_call_for_each_lead(local):
    client, _db, _keys = local
    client.put('/api/si/patch/reps', json={'name': 'Sam North', 'regions': ['Yorkshire and the Humber'], 'services': [], 'sectors': [], 'targets': ['Fenwick Housing Trust']})
    body = client.get('/api/si/patch/text').text
    assert body.count('   Who to call: ') == 2
    assert ('   Who to call: Use the contact point and clarification process the notice gives. During a live procurement, an approach outside it '
            'can count against a bid.') in body
    assert 'Contact details are only those a public source or the organisation’s own website gives, never guessed.' in body
    leads = client.get('/api/si/patch').json()['leads']
    assert all(lead['call']['line'] for lead in leads)
