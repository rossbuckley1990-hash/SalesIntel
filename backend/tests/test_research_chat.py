"""Research chat: a rep asks in their own words; the model searches, reads and follows leads; SalesIntel's own tools check
what is known, what is published and the timing; and code checks every card before the rep sees it.

Runs the real application in hosted mode (signed tokens, workspaces) on SQLite and PostgreSQL. Research is replayed
offline (research_replay.replay_chat_post), including a page that tries to instruct the model and a personal email.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.models.research_chat import ResearchChat
from app.services import jobs, research_chat as rc, research_replay
from app.services import prospect_research as pr
from app.services.ai_costs import Meter, cost_cents
from app.services.anthropic_stream import Assembler, events
from app.services.opportunity_dossier import DossierUnavailable
from tenancy_support import hosted  # noqa: F401
from test_acquisition import add_notice, workspace

ASK = 'Logistics companies opening new warehouses in Yorkshire that have not gone to tender'
NEWS, PEOPLE, CONTACT = research_replay.PROSPECT_PAGES


def start(c, text=ASK):
    r = c.post('/api/si/research-chats', json={'text': text})
    assert r.status_code == 200, r.text
    return r.json()


def answered(h, c, chat_id):
    jobs.drain(h.engine)
    return c.get(f'/api/si/research-chats/{chat_id}').json()


def test_a_reply_researches_reads_checks_and_offers_only_checked_cards(hosted):
    h = hosted
    c, org = workspace(h, 'ana', 'Alpha Fire Ltd')
    first = start(c)
    assert first['title'] == ASK and first['turns'][0]['role'] == 'user' and first['running']['kind'] == 'research_chat'
    chat = answered(h, c, first['id'])
    assert chat['running'] is None and [t['role'] for t in chat['turns']] == ['user', 'assistant']
    reply = chat['turns'][1]
    # What it did, in words: searched, read a page, and used each of SalesIntel's tools.
    assert reply['steps'] == ['“I\'ll look for logistics operators with new sites that have not gone to tender.”',
                              'Searched: new distribution centre Yorkshire opening 2027', 'Checked what you already hold: Northgate Distribution Ltd, Calder Freight Services',
                              'Read: northgate-distribution.example/about/leadership', "Checked SalesIntel's records: Northgate Distribution Ltd",
                              'Worked out timing: Northgate Distribution Ltd', 'Prepared a card: Northgate Distribution Ltd', 'Prepared a card: Calder Freight Services']
    # The answer cites its sources by number.
    assert 'Wakefield, due to open in summer 2027.⟦1⟧' in reply['text'] and 'new sites.⟦2⟧' in reply['text']
    assert reply['sources'] == [{'n': 1, 'url': NEWS, 'title': research_replay.PAGES[NEWS]['title']}, {'n': 2, 'url': PEOPLE, 'title': research_replay.PAGES[PEOPLE]['title']}]
    # One card: Calder had no dated fact any page states, so it was not shown.
    assert [x['name'] for x in chat['cards']] == ['Northgate Distribution Ltd'] and reply['cards'] == [1]
    card = chat['cards'][0]
    assert card['standing'] == 'hidden' and card['standing_label'] == 'a hidden opportunity' and card['publishers'] == ['news.example', 'northgate-distribution.example']
    assert card['timing']['label'] == pr.timing_view(research_replay.PROSPECTS[0]['timing_clues'], date.today())['label']  # the app's rules, not the model's words
    assert card['records']['notices'] == [] and card['known']['known'] is False
    # The person is quoted from a page it read; the personal email planted by an injected page is removed.
    assert [p['name'] for p in card['people']] == ['Sam Patel']
    assert [r['value'] for r in card['contact_routes']] == ['0113 496 0000']
    assert 'md.northgate@gmail.com' not in str(chat)
    with h.as_workspace(org) as db:
        stored = db.get(ResearchChat, first['id'])
        results = [b for m in stored.messages if m['role'] == 'user' for b in m['content'] if b.get('type') == 'tool_result']
        offers = [b['content'] for b in results if 'accepted' in b['content']]
        assert '"accepted": false' in offers[1] and 'not shown' in offers[1]  # the model is told why, so it can say so
        assert '"contact_routes": 1' in offers[0]  # and what was removed
        assert stored.cost_cents == reply['cost_cents'] > 0
    # Another company sees none of it.
    bob, _ = workspace(h, 'bob', 'Beta Security Ltd')
    assert bob.get(f"/api/si/research-chats/{first['id']}").status_code == 404 and bob.get('/api/si/research-chats').json()['items'] == []
    assert c.get('/api/si/research-chats').json()['items'][0] == {'id': first['id'], 'title': ASK, 'updated_at': chat['updated_at'], 'cards': 1, 'saved': 0,
                                                                  'cost_cents': chat['cost_cents']}


def test_saving_a_card_puts_one_private_lead_in_discover(hosted):
    h = hosted
    c, _ = workspace(h, 'ana', 'Alpha Fire Ltd')
    chat = answered(h, c, start(c)['id'])
    saved = c.post(f"/api/si/research-chats/{chat['id']}/cards/1/save")
    assert saved.status_code == 200, saved.text
    key = saved.json()['lead_key']
    assert key.startswith('pr:') and saved.json()['card']['status'] == 'saved'
    lead = next(x for x in c.get('/api/si/discover', params={'source': 'private'}).json()['items'] if x['key'] == key)
    assert lead['organisation'] == 'Northgate Distribution Ltd'
    assert c.post(f"/api/si/research-chats/{chat['id']}/cards/1/save").json()['lead_key'] == key  # saving again keeps one record
    assert c.post(f"/api/si/research-chats/{chat['id']}/cards/9/save").status_code == 404
    # The next research knows the rep holds it.
    again = answered(h, c, start(c, 'More logistics sites in Yorkshire please')['id'])
    assert again['cards'][0]['known']['known'] is True and again['cards'][0]['known']['prospect']['name'] == 'Northgate Distribution Ltd'


def test_a_follow_up_sends_the_conversation_back_exactly_as_it_was(hosted, monkeypatch):
    h = hosted
    seen = []
    real = research_replay.replay_chat_post
    monkeypatch.setattr(research_replay, 'replay_chat_post', lambda payload, listener=None: (seen.append(payload), real(payload, listener))[1])
    c, org = workspace(h, 'ana', 'Alpha Fire Ltd')
    chat_id = start(c)['id']
    jobs.drain(h.engine)
    with h.as_workspace(org) as db:
        before = db.get(ResearchChat, chat_id).messages
    assert len(seen) == 4 and {str(p['tools']) for p in seen} == {str(seen[0]['tools'])} and {str(p['system']) for p in seen} == {str(seen[0]['system'])}
    assert seen[0]['cache_control'] == {'type': 'ephemeral'} and seen[0]['system'][0]['cache_control'] == {'type': 'ephemeral'}
    assert 'Alpha Fire Ltd' in seen[0]['system'][0]['text']  # the rep's own company, never a named third party
    r = c.post(f'/api/si/research-chats/{chat_id}/messages', json={'text': 'Who should I approach at Northgate?'})
    assert r.status_code == 200, r.text
    chat = answered(h, c, chat_id)
    assert seen[-1]['messages'][:len(before)] == before  # unchanged, block for block
    assert seen[-1]['messages'][len(before)]['content'][0]['text'].endswith('Who should I approach at Northgate?')
    assert [t['role'] for t in chat['turns']] == ['user', 'assistant', 'user', 'assistant']
    follow = chat['turns'][3]
    assert follow['text'].startswith('Sam Patel, Head of Property') and follow['sources'] == [{'n': 2, 'url': PEOPLE, 'title': research_replay.PAGES[PEOPLE]['title']}]  # numbers carry on


def test_one_reply_at_a_time_and_stopping_a_queued_reply(hosted):
    h = hosted
    c, _ = workspace(h, 'ana', 'Alpha Fire Ltd')
    chat_id = start(c)['id']
    busy = c.post(f'/api/si/research-chats/{chat_id}/messages', json={'text': 'And in Lancashire?'})
    assert busy.status_code == 409 and 'still being written' in busy.json()['detail']
    stopped = c.post(f'/api/si/research-chats/{chat_id}/stop').json()
    assert stopped['running'] is None and stopped['turns'][0]['job']['status'] == 'cancelled'
    assert c.post(f'/api/si/research-chats/{chat_id}/messages', json={'text': 'Try again please'}).status_code == 200
    assert [t['role'] for t in answered(h, c, chat_id)['turns']] == ['user', 'user', 'assistant']


def test_demo_mode_refuses_research_and_spends_nothing(hosted, monkeypatch):
    h = hosted
    c, _ = workspace(h, 'ana', 'Alpha Fire Ltd')
    monkeypatch.setenv('APP_ENV', 'demo')
    monkeypatch.setenv('RESEARCH_PROVIDER', 'anthropic')
    from app.config import get_settings
    get_settings.cache_clear()
    r = c.post('/api/si/research-chats', json={'text': ASK})
    assert r.status_code == 403 and 'switched off in demo mode' in r.json()['detail']
    get_settings.cache_clear()


# ---------------------------------------------------------------- the checks on a card, and the reply loop

def _state(h, org, chat_id):
    db = h.as_workspace(org)
    chat = db.get(ResearchChat, chat_id)
    state = rc.State(db, chat, date(2026, 11, 16), rc._live(None))
    state.sources = {NEWS: 'News', PEOPLE: 'People', CONTACT: 'Contact', 'https://other.example/a': 'Other'}
    return db, state


def _card(**over):
    base = {'name': 'Example Cold Store Ltd', 'headline': 'A new cold store opens in May 2027.', 'summary': 'A food logistics operator.', 'why_hidden': 'Two facts.',
            'signals': [{'type': 'new_site', 'title': 'Cold store announced', 'detail': 'Opening May 2027.', 'date': '2026-10-01', 'basis': 'stated', 'direction': 'supports',
                         'source_url': NEWS}],
            'timing_clues': [{'kind': 'site_opening', 'date': '2027-05', 'detail': 'Opening May 2027.', 'basis': 'stated', 'system_family': '', 'source_url': NEWS}]}
    return {**base, **over}


def test_a_card_is_hidden_only_with_dated_facts_from_two_independent_publishers(hosted):
    h = hosted
    c, org = workspace(h, 'ana', 'Alpha Fire Ltd')
    chat_id = start(c)['id']
    db, state = _state(h, org, chat_id)
    one = state.offer(_card())
    assert one['accepted'] and one['shown_as'] == 'one to check first' and one['independent_publishers'] == 1
    two = state.offer(_card(signals=[*_card()['signals'], {'type': 'hiring_fm_security', 'title': 'Site manager advertised', 'detail': 'For the new cold store.',
                                                             'date': '2026-10-20', 'basis': 'stated', 'direction': 'supports', 'source_url': 'https://other.example/a'}]))
    assert two['shown_as'] == 'a hidden opportunity' and two['card'] == one['card'] and len(state.cards) == 1  # the same organisation updates its card
    # A link the model never saw is removed, and a fact stated only by it no longer counts.
    unseen = state.offer(_card(name='Example Bakery Ltd', signals=[{**_card()['signals'][0], 'source_url': 'https://never-read.example/x'}], timing_clues=[]))
    assert unseen['accepted'] is False and unseen['removed']['links'] == 1
    # An undated fact is not a dated fact.
    undated = state.offer(_card(name='Example Mill Ltd', signals=[{**_card()['signals'][0], 'date': ''}], timing_clues=[]))
    assert undated['accepted'] is False
    # A tender already published for the organisation means the need is not hidden; a contract ending is reported, not a tender.
    with h.system() as system:
        add_notice(system, customer='EXAMPLE COLD STORE LIMITED', record_key='example-cold-store-1')
    assert state.offer(_card())['shown_as'] == 'one to check first'
    with h.system() as system:
        add_tender(system, 'Example Cold Store Ltd')
    published = state.offer(_card())
    assert published['shown_as'] == 'already published' and published['published_notice_found'] is True
    assert rc.search_records(db, 'Example Cold Store')['live_tenders_and_notices'][0]['category'] == 'live_procurement'
    db.close()


def add_tender(db, customer):
    from datetime import UTC, datetime
    from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
    from test_salesintel_journey import suggestion
    item = MarketOpportunity(dedup_key=f'tender:{customer}', first_seen=datetime.now(UTC), last_evaluated=datetime.now(UTC))
    db.add(item)
    db.flush()
    rev = MarketOpportunityRevision(opportunity_id=item.id, fingerprint='t', created_at=datetime.now(UTC),
                                    result={**suggestion(customer=customer), 'category': 'live_procurement', 'category_label': 'Live tender'})
    db.add(rev)
    db.flush()
    item.current_revision_id = rev.id
    db.commit()


def test_timing_comes_from_the_rules_and_a_stated_clue_needs_a_page_it_read():
    sources = {NEWS: 'News'}
    clue = {'kind': 'site_opening', 'date': '2027-05', 'detail': 'Opening May 2027.', 'basis': 'stated', 'system_family': '', 'source_url': NEWS}
    with_source = rc.assess_timing([clue], sources, date(2026, 11, 16), 'Example')
    without = rc.assess_timing([{**clue, 'source_url': 'https://never-read.example/x'}], sources, date(2026, 11, 16), 'Example')
    assert with_source['label'] == 'Engage now' and not __import__('re').search(r'\d\s?%', str(with_source))  # a phase, never a percentage
    assert without['label'] == 'Prepare' and 'Only weak, inferred clues' in without['reasons'][0]  # unsourced, so weak
    assert rc.assess_timing([{'kind': 'made_up', 'date': '2027-01'}], sources, date(2026, 11, 16))['label'] == 'Timing unknown'


def test_a_builder_is_not_a_new_supplier_and_a_card_shows_its_timing_as_of_today(hosted):
    """Live, 16 November 2026: the firm building a site was filed as its new supplier, so two 2027 openings said "Not yet"."""
    h = hosted
    c, org = workspace(h, 'ana', 'Alpha Fire Ltd')
    chat_id = start(c)['id']
    # The model is told what each kind of clue means, as one-off research is, and has a kind for a building contractor.
    prompt = rc.system_prompt('Alpha Fire Ltd')
    assert 'or for a building contractor.' in prompt and '- contractor_appointed: a contractor appointed to build, extend or fit out a site' in prompt
    assert 'contractor_appointed' in rc.CLUE_SCHEMA['properties']['kind']['enum']
    db, state = _state(h, org, chat_id)
    builder = {'kind': 'supplier_appointed', 'date': '2026-02', 'detail': 'Example Construction appointed; build began February 2026', 'basis': 'stated',
               'system_family': 'general', 'source_url': NEWS}
    assert state.offer(_card(timing_clues=[*_card()['timing_clues'], builder]))['timing'] == 'Engage now'
    # A card kept from before is shown with timing worked out today, by today's rules, as a saved lead is.
    old = {**state.cards[0], 'timing': {'phase': 'not_yet', 'label': 'Not yet', 'light': 'red', 'window': None,
                                        'reasons': ['A supplier was appointed recently; expect little appetite to change before February 2027.']}}
    shown = rc.card_view(old, date(2026, 11, 16))['timing']
    assert shown['label'] == 'Engage now' and shown['reasons'][1].startswith('Building contractor appointed: a contractor appointed to build')
    assert rc.card_view(old, date(2027, 6, 1))['timing']['label'] == 'Timing unknown'  # the opening window has passed by then
    db.get(ResearchChat, chat_id).cards = [old]
    db.commit()
    db.close()
    seen = c.get(f'/api/si/research-chats/{chat_id}').json()['cards'][0]['timing']
    assert seen['label'] == pr.timing_view(old['record']['timing_clues'], date.today())['label'] != 'Not yet'


class Script:
    """A provider that answers from a list, measured like the real one."""

    def __init__(self, answers, cents_each=0):
        self.answers, self.payloads, self.cents_each = list(answers), [], cents_each

    def __call__(self, payload, listener=None):
        self.payloads.append(__import__('copy').deepcopy(payload))  # as sent: the reply appends to the same list afterwards
        answer = self.answers.pop(0)
        return {**answer, 'usage': {'input_tokens': self.cents_each * 2500, 'output_tokens': 0}}  # 2,500 input tokens a cent on claude-opus-5-5


def _chat(h, c, org):
    """A chat with one message from the rep, whose queued reply is set aside so a test can run the reply itself."""
    chat = start(c)
    c.post(f"/api/si/research-chats/{chat['id']}/stop")
    return chat['id']


def test_a_paused_turn_continues_in_one_message_and_a_ceiling_stops_cleanly(hosted):
    h = hosted
    c, org = workspace(h, 'ana', 'Alpha Fire Ltd')
    chat_id = _chat(h, c, org)
    search = {'type': 'server_tool_use', 'id': 'srv_1', 'name': 'web_search', 'input': {'query': 'cold stores'}}
    script = Script([{'content': [{'type': 'text', 'text': 'Looking.'}, search], 'stop_reason': 'pause_turn'},
                     {'content': [{'type': 'web_search_tool_result', 'tool_use_id': 'srv_1', 'content': []}, {'type': 'text', 'text': 'Done.'}], 'stop_reason': 'end_turn'}])
    meter = Meter(script, 'claude-opus-5-5', 'test')
    with h.as_workspace(org) as db:
        result = rc.reply(db, chat_id, 0, meter, step=lambda s: None)
        db.commit()
        stored = db.get(ResearchChat, chat_id)
        assert result['status'] == 'succeeded' and [m['role'] for m in stored.messages] == ['user', 'assistant']
        assert [b['type'] for b in stored.messages[1]['content']] == ['text', 'server_tool_use', 'web_search_tool_result', 'text']
        assert stored.turns[-1]['text'] == 'Done.' and stored.turns[-1]['steps'] == ['“Looking.”', 'Searched: cold stores']  # notes along the way go with the work
    # The hard ceiling reached while paused: the unfinished step is left out, so the conversation can continue later.
    chat2 = _chat(h, c, org)
    paused = Script([{'content': [{'type': 'text', 'text': 'Looking.'}, search], 'stop_reason': 'pause_turn'}] * 2, cents_each=100)
    meter = Meter(paused, 'claude-opus-5-5', 'test', ceiling_cents=150)
    with h.as_workspace(org) as db:
        result = rc.reply(db, chat2, 0, meter, step=lambda s: None)
        db.commit()
        stored = db.get(ResearchChat, chat2)
        assert result['status'] == 'partial' and 'cost ceiling' in stored.turns[-1]['note'] and meter.cents == 200
        assert [m['role'] for m in stored.messages] == ['user']


def test_near_its_limit_a_reply_is_asked_to_answer_from_what_it_has(hosted):
    h = hosted
    c, org = workspace(h, 'ana', 'Alpha Fire Ltd')
    chat_id = _chat(h, c, org)
    ask = {'type': 'tool_use', 'id': 'toolu_1', 'name': 'check_known', 'input': {'names': ['Example Cold Store Ltd']}}
    script = Script([{'content': [{'type': 'text', 'text': 'Checking.'}, ask], 'stop_reason': 'tool_use'},
                     {'content': [{'type': 'text', 'text': 'Here is what I found so far.'}], 'stop_reason': 'end_turn'}], cents_each=100)
    with h.as_workspace(org) as db:
        result = rc.reply(db, chat_id, 0, Meter(script, 'claude-opus-5-5', 'test', ceiling_cents=150), step=lambda s: None)
        db.commit()
        stored = db.get(ResearchChat, chat_id)
        last = script.payloads[1]['messages'][-1]['content']
        assert [b['type'] for b in last] == ['tool_result', 'text'] and last[1]['text'] == rc.WRAP_UP
        assert result['status'] == 'partial' and stored.turns[-1]['text'] == 'Here is what I found so far.'
        assert 'spending limit, so it answered from what it had found' in stored.turns[-1]['note']


def test_stopping_mid_reply_keeps_what_was_done_and_the_next_message_follows_the_tool_answers(hosted):
    h = hosted
    c, org = workspace(h, 'ana', 'Alpha Fire Ltd')
    chat_id = _chat(h, c, org)
    ask = {'type': 'tool_use', 'id': 'toolu_1', 'name': 'check_known', 'input': {'names': ['Example Cold Store Ltd']}}
    script = Script([{'content': [{'type': 'text', 'text': 'Checking.'}, ask], 'stop_reason': 'tool_use'}])
    calls = []

    def step(stage):
        calls.append(stage)
        if len(calls) == 2:
            raise jobs.Cancelled('Cancelled')
    with h.as_workspace(org) as db:
        result = rc.reply(db, chat_id, 0, Meter(script, 'claude-opus-5-5', 'test'), step=step, cancelled=jobs.Cancelled)
        db.commit()
        stored = db.get(ResearchChat, chat_id)
        assert result['status'] == 'cancelled' and stored.turns[-1]['note'] == 'You stopped this reply.'
        assert [m['role'] for m in stored.messages] == ['user', 'assistant', 'user'] and stored.messages[-1]['content'][0]['type'] == 'tool_result'
        rc.add_message(stored, 'Carry on', 0)
        db.commit()
    following = Script([{'content': [{'type': 'text', 'text': 'Carrying on.'}], 'stop_reason': 'end_turn'}])
    with h.as_workspace(org) as db:
        rc.reply(db, chat_id, 2, Meter(following, 'claude-opus-5-5', 'test'), step=lambda s: None)
        sent = following.payloads[0]['messages']
        assert [m['role'] for m in sent] == ['user', 'assistant', 'user'] and [b['type'] for b in sent[-1]['content']] == ['tool_result', 'text']


# ---------------------------------------------------------------- streaming and cost

def test_a_stream_is_assembled_block_for_block():
    lines = []
    for event in [
        {'type': 'message_start', 'message': {'id': 'm', 'role': 'assistant', 'content': [], 'usage': {'input_tokens': 10, 'cache_read_input_tokens': 90}}},
        {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'thinking', 'thinking': '', 'signature': ''}},
        {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'thinking_delta', 'thinking': 'Plan.'}},
        {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'signature_delta', 'signature': 'sig'}},
        {'type': 'content_block_stop', 'index': 0},
        {'type': 'content_block_start', 'index': 1, 'content_block': {'type': 'server_tool_use', 'id': 's1', 'name': 'web_search', 'input': {}}},
        {'type': 'content_block_delta', 'index': 1, 'delta': {'type': 'input_json_delta', 'partial_json': '{"query": "cold'}},
        {'type': 'content_block_delta', 'index': 1, 'delta': {'type': 'input_json_delta', 'partial_json': ' stores"}'}},
        {'type': 'content_block_stop', 'index': 1},
        {'type': 'content_block_start', 'index': 2, 'content_block': {'type': 'web_search_tool_result', 'tool_use_id': 's1', 'content': [{'type': 'web_search_result', 'url': NEWS}]}},
        {'type': 'content_block_stop', 'index': 2},
        {'type': 'content_block_start', 'index': 3, 'content_block': {'type': 'text', 'text': ''}},
        {'type': 'content_block_delta', 'index': 3, 'delta': {'type': 'citations_delta', 'citation': {'type': 'web_search_result_location', 'url': NEWS}}},
        {'type': 'content_block_delta', 'index': 3, 'delta': {'type': 'text_delta', 'text': 'Opening '}},
        {'type': 'content_block_delta', 'index': 3, 'delta': {'type': 'text_delta', 'text': 'in May.'}},
        {'type': 'content_block_stop', 'index': 3},
        {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 40, 'server_tool_use': {'web_search_requests': 1}}},
        {'type': 'message_stop'},
    ]:
        lines += [f"event: {event['type']}", f'data: {__import__("json").dumps(event)}', '']
    heard = []
    a = Assembler(lambda kind, data: heard.append(kind))
    for name, data in events(lines):
        a.feed(data['type'], data)
    out = a.result()
    assert out['stop_reason'] == 'end_turn' and out['usage'] == {'input_tokens': 10, 'cache_read_input_tokens': 90, 'output_tokens': 40, 'server_tool_use': {'web_search_requests': 1}}
    assert out['content'] == [{'type': 'thinking', 'thinking': 'Plan.', 'signature': 'sig'},
                              {'type': 'server_tool_use', 'id': 's1', 'name': 'web_search', 'input': {'query': 'cold stores'}},
                              {'type': 'web_search_tool_result', 'tool_use_id': 's1', 'content': [{'type': 'web_search_result', 'url': NEWS}]},
                              {'type': 'text', 'text': 'Opening in May.', 'citations': [{'type': 'web_search_result_location', 'url': NEWS}]}]
    assert heard.count('content_block_delta') == 7
    with pytest.raises(DossierUnavailable, match='overloaded'):
        Assembler().feed('error', {'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'Overloaded'}})


def test_cached_input_is_priced_at_the_cache_rate():
    # Opus 5.5: $4 a million fresh, $0.20 a million read from the cache, writes at 1.25 times.
    assert cost_cents('claude-opus-5-5', {'input_tokens': 1_000_000}) == 400
    assert cost_cents('claude-opus-5-5', {'input_tokens': 1_000_000, 'cache_read_tokens': 1_000_000}) == 20
    assert cost_cents('claude-opus-5-5', {'input_tokens': 1_000_000, 'cache_write_tokens': 1_000_000}) == 500
    meter = Meter(lambda p: {'usage': {'input_tokens': 100_000, 'cache_read_input_tokens': 900_000, 'output_tokens': 0,
                                       'server_tool_use': {'web_search_requests': 2, 'web_fetch_requests': 3}}}, 'claude-opus-5-5', 'test')
    meter({})
    assert meter.usage['input_tokens'] == 1_000_000 and meter.usage['cache_read_tokens'] == 900_000 and meter.usage['pages_read'] == 3
    assert meter.cents == 40 + 18 + 2  # fresh, cached, two searches
    plain = Meter(lambda p: {'usage': {'input_tokens': 5}}, 'claude-opus-5-5', 'test')
    plain({})
    assert 'cache_read_tokens' not in plain.usage  # other research is unchanged


def test_a_provider_failure_part_way_keeps_what_the_reply_found(hosted):
    h = hosted
    c, org = workspace(h, 'ana', 'Alpha Fire Ltd')
    chat_id = _chat(h, c, org)
    ask = {'type': 'tool_use', 'id': 'toolu_1', 'name': 'check_known', 'input': {'names': ['Example Cold Store Ltd']}}
    answers = [{'content': [{'type': 'text', 'text': 'Found a lead.'}, ask], 'stop_reason': 'tool_use'}]

    def post(payload, listener=None):
        if not answers:
            raise DossierUnavailable('The research service returned an error (529). Overloaded')
        return {**answers.pop(0), 'usage': {'input_tokens': 1000, 'output_tokens': 10}}
    with h.as_workspace(org) as db:
        result = rc.reply(db, chat_id, 0, Meter(post, 'claude-opus-5-5', 'test'), step=lambda s: None)
        db.commit()
        stored = db.get(ResearchChat, chat_id)
        assert result['status'] == 'partial' and stored.turns[-1]['text'] == 'Found a lead.' and '529' in stored.turns[-1]['note']
        assert [m['role'] for m in stored.messages] == ['user', 'assistant', 'user']  # the tool answers are kept, so a follow-up can continue
    # Failing on the first call is a plain failure: nothing was done, and nothing is saved.
    chat2 = _chat(h, c, org)
    with h.as_workspace(org) as db:
        with pytest.raises(DossierUnavailable):
            rc.reply(db, chat2, 0, Meter(post, 'claude-opus-5-5', 'test'), step=lambda s: None)
