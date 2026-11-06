"""Two discovery pathways.

- Qualified: an evidenced requirement for something you sell.
- Exploratory: a credible, sourced change at an organisation or site that may justify investigation, labelled as unconfirmed.

Written to fail against PR #9 as first opened (1b37e42). Then a private lead qualified on the research model's own list of
services and its "engage now" timing, and every lead whose record named no service was only counted, never shown."""
from __future__ import annotations

from app.models.prospect import Prospect
from app.services import best
from app.services.shadow_fixtures import load
from tenancy_support import hosted  # noqa: F401
from test_opportunity_quality import prospect, signal
from test_shadow_radar import workspace


def lists(c):
    data = c.get('/api/si/best').json()
    return data, {x['key']: x for x in data['items']}, {x['key']: x for x in data['exploratory']}


def test_a_sourced_change_with_no_fire_or_security_words_is_explored_not_hidden(hosted):
    h = hosted
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')  # sells fire alarms and access control in England
    hub = f"pr:{prospect(h, org, 'Example Distribution Ltd', [signal('new_site', 'New 200,000 sq ft distribution centre in Doncaster opening in 2027')], services=())}"
    _, qualified, explored = lists(alice)
    assert hub not in qualified  # not a confirmed requirement
    lead = explored[hub]
    assert lead['pathway'] == 'exploratory' and lead['tier'] == 'explore'
    assert any('need not confirmed' in u.lower() for u in lead['uncertainty']) and any('single source' in u.lower() for u in lead['uncertainty'])
    assert 'confirm' in lead['next'].lower() and 'introduce' not in lead['next'].lower()  # an investigation, not a pitch
    assert lead['known'] and all(k.get('source_url') for k in lead['known'])  # shown with its sourced evidence


def test_only_a_sourced_requirement_for_what_you_sell_qualifies_a_private_lead(hosted):
    h = hosted
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')
    guessed = f"pr:{prospect(h, org, 'Example Guessed Ltd', [signal('leadership_change', 'New Head of Facilities appointed')], services=('fire_alarm', 'access_control'))}"
    stated = f"pr:{prospect(h, org, 'Example Stated Ltd', [signal('stated_requirement', 'Invitation to quote for fire alarm replacement across 12 depots')])}"
    unsourced = f"pr:{prospect(h, org, 'Example Unsourced Ltd', [signal('stated_requirement', 'Fire alarm replacement planned', url='')])}"
    _, qualified, explored = lists(alice)
    assert guessed not in qualified and guessed in explored  # the research's guessed services are not evidence of a need
    assert qualified[stated]['pathway'] == 'qualified' and any(r.startswith('Stated requirement') for r in qualified[stated]['reasons'])
    assert unsourced not in qualified and unsourced not in explored  # no source, no lead
    assert not set(qualified) & set(explored)  # a lead is never on both lists


def test_weak_stale_strategic_or_distant_signals_are_not_explored(hosted):
    h = hosted
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')
    weak = [prospect(h, org, 'Example Inferred Ltd', [signal('new_site', 'Probably opening a depot', basis='inferred')], services=()),
            prospect(h, org, 'Example Stale Ltd', [{**signal('new_site', 'New depot opened'), 'date': '2023-02-01'}], services=()),
            prospect(h, org, 'Example Strategy Ltd', [signal('esg_strategy', 'Net zero commitment published')], services=())]
    distant = prospect(h, org, 'Example Belfast Ltd', [signal('new_site', 'New Belfast warehouse')], services=())
    with h.as_workspace(org) as db:
        row = db.get(Prospect, distant)
        row.data = {**row.data, 'location': 'Belfast, Northern Ireland'}
        db.commit()
    data, qualified, explored = lists(alice)
    for pid in [*weak, distant]:
        assert f'pr:{pid}' not in explored and f'pr:{pid}' not in qualified
    assert data['in_view'] >= 1  # still counted in Discover, not silently dropped


def test_indirect_evidence_is_explored_with_its_uncertainty_and_never_qualified(hosted):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')
    data, qualified, explored = lists(alice)
    assert all(x['type'] != 'shadow' or x['kind'] == 'customer_expansion' for x in qualified.values())  # an inference is never a confirmed requirement
    harbourside = next(x for x in explored.values() if x['organisation'].startswith('Harbourside'))
    assert any('Corroborated by 2 independent sources' in r for r in harbourside['reasons'])
    assert any('need not confirmed' in u.lower() for u in harbourside['uncertainty'])
    assert all(x.get('evidence_state') != 'challenged' for x in explored.values())  # contradicted readings are not offered
    assert len(explored) <= best.EXPLORE_LIMIT and set(data['tiers']) <= {'act_now', 'this_week', 'watch', 'explore'}


def test_the_qualified_list_is_unchanged_by_adding_the_exploratory_pathway(hosted, monkeypatch):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')
    prospect(h, org, 'Example Distribution Ltd', [signal('new_site', 'New distribution centre in Doncaster')], services=())
    with_explore = [x['key'] for x in alice.get('/api/si/best').json()['items']]
    monkeypatch.setattr(best, 'EXPLORE_LIMIT', 0)
    without = alice.get('/api/si/best').json()
    assert [x['key'] for x in without['items']] == with_explore and without['exploratory'] == []  # exploration never pads or reorders the day
    with h.as_workspace(org) as db:  # PR #8's behaviour, kept as an evaluation arm, has no exploratory pathway
        assert best.opportunities(db, strict_service=False)['exploratory'] == []
