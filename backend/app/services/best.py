"""My best opportunities: the day's short list of organisations worth a salesperson's time, and why.

Ranking is by plain tiers, each with the reasons that put a lead there, never by an invented score:
  act_now      a published deadline close at hand, a requirement a customer has stated, or a promise you made that is overdue
  this_week    a reported contract end within four months, corroborated indirect evidence whose window is open, an existing
               customer's new signal, or a tender a few weeks out
  watch        everything else that fits what you sell
Leads for services you do not sell are set aside and counted, not hidden silently. Signal count is not treated as
buying probability, and a long AI report earns nothing. Within a tier: published before inferred, better fit, sooner.

The customer profile is what you said you want (services, territory, sectors, deal size) and, once there are enough
won deals in this workspace, the patterns among them. Patterns are correlation in your own history, not causes, and
are never learned from another workspace.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.crm import Account, Activity, DealRecord, FunnelEvent, Task
from app.services import si_core as core

MIN_WON = 5  # below this, patterns in won deals are too few to show
TIERS = {'act_now': 'Act now', 'this_week': 'Worth your time this week', 'watch': 'Keep in view'}
OPEN_STAGES = ('qualify', 'engage', 'survey', 'proposal', 'bid_review', 'negotiation', 'approval')


def profile(db: Session) -> dict:
    """The ideal-customer profile in use: stated rules, plus learned patterns when this workspace has enough wins."""
    prefs = core.preferences(db)
    won = db.scalars(select(DealRecord).where(DealRecord.stage == 'won')).all()
    lost = db.scalars(select(DealRecord).where(DealRecord.stage == 'lost')).all()
    stated = {'services': prefs['services'], 'territory': prefs['territory'], 'sectors': prefs['sectors'],
              'deal_size_min': prefs.get('deal_size_min'), 'deal_size_max': prefs.get('deal_size_max'), 'capabilities': prefs.get('capabilities') or []}
    learned = None
    if len(won) >= MIN_WON:
        accounts = {a.id: a for a in db.scalars(select(Account).where(Account.id.in_([d.account_id for d in won])))}
        sectors = Counter((accounts[d.account_id].sector or 'Not recorded') for d in won if d.account_id in accounts)
        services = Counter(s for d in won for s in (d.services or []))
        values = [d.value_total for d in won if d.value_total is not None]
        cycle = [(d.updated_at.date() - d.created_at.date()).days for d in won if d.updated_at and d.created_at]
        learned = {'won': len(won), 'lost': len(lost),
                   'sectors': [{'name': k, 'won': v} for k, v in sectors.most_common(4)],
                   'services': [{'name': k, 'won': v} for k, v in services.most_common(4)],
                   'median_total_value': median(values) if values else None, 'priced': len(values),
                   'median_days_to_win': median(cycle) if cycle else None}
    complete = bool(stated['services'] and stated['territory'])
    return {'basis': 'learned' if learned else 'stated', 'stated': stated, 'learned': learned, 'won': len(won), 'lost': len(lost), 'minimum_won': MIN_WON,
            'complete': complete,
            'caveat': ('Patterns among your own won deals. They describe who you have won, not why you won; they are never learned from another company.'
                       if learned else f"Using what you told SalesIntel. Patterns from your won deals appear once there are {MIN_WON}.")}


def _relationships(db: Session, today: date) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for a in db.scalars(select(Account)):
        out[a.id] = {'status': a.status, 'name': a.name, 'sector': a.sector, 'open_deals': 0, 'overdue': [], 'requirement': None, 'last_activity': None}
    for d in db.scalars(select(DealRecord).where(DealRecord.stage.in_(OPEN_STAGES))):
        if d.account_id in out:
            out[d.account_id]['open_deals'] += 1
    for t in db.scalars(select(Task).where(Task.status == 'open', Task.due_on < today)):
        if t.account_id in out:
            out[t.account_id]['overdue'].append({'title': t.title, 'due_on': t.due_on.isoformat()})
    for act in db.scalars(select(Activity).order_by(Activity.occurred_at)):
        r = out.get(act.account_id)
        if r is None:
            continue
        r['last_activity'] = act.occurred_at.date().isoformat()
        if act.outcome == 'requirement_captured' or (act.requirements or '').strip():
            r['requirement'] = {'text': (act.requirements or act.summary)[:240], 'on': act.occurred_at.date().isoformat()}
    return out


def _tier(x: dict, rel: dict | None) -> tuple[str, list[str]]:
    days, kind, why = x.get('days'), x['kind'], []
    if rel and rel['requirement'] and not rel['open_deals']:
        why.append(f"The customer stated a requirement on {date.fromisoformat(rel['requirement']['on']):%-d %b}, and there is no deal yet")
    if rel and rel['overdue']:
        why.append(f"You committed to a follow-up that is overdue: {rel['overdue'][0]['title']}")
    if kind == 'published_procurement' and days is not None and 0 <= days <= 21:
        what = 'deadline' if 'deadline' in (x.get('timing_label') or '').lower() else 'expected tender date'  # say which date it is
        why.append(f"Published {what} in {days} day{'s' if days != 1 else ''}")
    if why:
        return 'act_now', why
    if kind == 'customer_expansion':
        why.append('Existing customer with a new signal')
    if kind == 'published_procurement' and days is not None and 21 < days <= 60:
        why.append(f"Published tender or expected date in {days} days")
    if kind == 'contract_ending' and days is not None and 0 <= days <= 120:  # late in the renewal-planning window
        why.append(f"Reported contract end in {max(days // 30, 1)} month{'s' if days >= 60 else ''}: the buyer should be deciding what comes next")
    shadow = x.get('shadow') or {}
    if x['type'] == 'shadow' and shadow.get('state') == 'corroborated':
        why.append(f"Corroborated by {shadow.get('independent_sources', 2)} independent sources")
    window_open = x['type'] == 'shadow' and days is not None and days <= 0 and bool(shadow.get('window')) and shadow['window'][1] >= date.today().isoformat()
    if window_open and shadow.get('state') in ('corroborated', 'surfaced'):
        why.append('Its investigation window is open now')
    if x['type'] == 'private' and x.get('category') == 'private_engage_now':
        why.append('Research says engage now')
    if why:
        return 'this_week', why
    if kind == 'contract_ending' and days is not None and 120 < days <= 730:
        why.append(f"Reported contract end in {days // 30} months: early enough to build the relationship")
    if window_open:
        why.append('Investigation window open, on one line of evidence so far')
    return 'watch', why


def _when(day: str | None) -> str:
    try:
        return date.fromisoformat(str(day)[:10]).strftime('%-d %B %Y') if day else ''
    except ValueError:
        return ''


def next_action(lead: dict, rel: dict | None, stated: dict) -> str:
    """One specific next step, built from this lead's own evidence and what the salesperson said they can deliver.
    Nothing here is generated by a model, and nothing it names is assumed beyond the record."""
    org, kind, who = lead['organisation'], lead['kind'], (lead['brief']['who']['roles'] or ['the right person'])[0]
    caps = ', '.join((stated.get('capabilities') or [])[:2])
    when = _when(lead.get('timing'))
    if rel and rel.get('requirement') and not rel.get('open_deals'):
        return f"Qualify it: {org} told you they need \"{rel['requirement']['text'][:90]}\". Create the deal while it is fresh."
    if rel and rel.get('overdue'):
        return f"Do what you promised: {rel['overdue'][0]['title']} (overdue since {_when(rel['overdue'][0]['due_on'])})."
    if kind == 'published_procurement':
        step = f"Read the notice and decide bid or no-bid before {when}" if when else "Read the notice and decide bid or no-bid"
        return step + (f"; check its mandatory requirements against {caps}" if caps else "; check its mandatory requirements") + \
            ". Ask questions only through the buyer's portal."
    if kind == 'contract_ending':
        supplier = lead.get('supplier')
        return (f"Ask {org}'s procurement team how they will replace the {('contract with ' + supplier) if supplier else 'current contract'}"
                f"{' ending ' + when if when else ''}: re-tender, extension or framework, and when.")
    if kind == 'customer_expansion':
        return f"Ask your contact at {org} whether this new site or change falls under your current contract, and who decides for it."
    if lead['type'] == 'shadow':
        return (lead.get('shadow') or {}).get('first_action') or lead['brief']['next']
    if lead['type'] == 'private':
        types = set(lead.get('signal_types') or [])
        if 'leadership_change' in types:
            return (f"Introduce yourself to the new leader at {org}: new facilities or estates heads often review suppliers in their first months. "
                    "Ask how fire and security is handled today and who maintains it.")
        if types & {'new_site', 'relocation', 'planning_application', 'expansion'}:
            return f"Ask the {who.lower()} at {org} who will specify and maintain fire and security for the new site, and when."
        if types & {'enforcement_action', 'fire_incident', 'security_incident', 'regulatory_deadline', 'insurance_or_audit_pressure'}:
            return f"Offer {org} a practical response to the published finding: ask who is accountable for putting it right, and by when."
        headline = (lead.get('title') or lead['why_now'] or '').rstrip('.')
        return f"Ask the {who.lower()} at {org} whether this affects their fire and security: {headline[:110]}."
    return lead['brief']['next']


def opportunities(db: Session, *, limit: int = 10, strict_service: bool = True) -> dict:
    """strict_service: the daily list needs a positive match to a service you sell (or an existing relationship).
    PR #8 did not require it; the evaluation keeps that behaviour as its own arm (strict_service=False)."""
    today = core.uk_today()
    prof = profile(db)
    items = core.discover_items(db, limit=None)
    rel = _relationships(db, today)
    learned_sectors = {s['name'].lower() for s in (prof['learned'] or {}).get('sectors', []) if s['name'] != 'Not recorded'}
    set_aside: Counter = Counter()
    groups: dict[str, list[dict]] = {}
    for x in items:
        if x['status'] == 'dismissed':
            continue
        if any(g == 'Services outside what you sell' for g in x['brief']['fit']['gaps']):
            set_aside['Services you do not sell'] += 1
            continue
        if x['kind'] == 'unverified_candidate':
            set_aside['Unverified research candidates'] += 1
            continue
        # Identity is never merged on a name alone: rows share a line only through a confirmed account link, or when a
        # procurement buyer published under the identical name. Anything else stays its own row.
        if x.get('account_id'):
            key = f"a:{x['account_id']}"
        elif x['type'] == 'public':
            key = f"p:{x['organisation']}"
        else:
            key = f"k:{x['key']}"
        groups.setdefault(key, []).append(x)

    rows = []
    for key, members in groups.items():
        lead = members[0]  # discover_items is already ordered: published deadlines first, then fit
        r = rel.get(lead.get('account_id')) if lead.get('account_id') else None
        tier, why = _tier(lead, r)
        fit = lead['brief']['fit']
        sells = any(m.startswith('Sells what you sell') for m in fit['matched'])
        relationship = bool(r and (r['requirement'] or r['overdue'] or r['status'] == 'customer'))
        unproven_service = strict_service and bool(prof['stated']['services']) and not sells and not relationship
        outside = strict_service and 'Outside your recorded territory' in fit['gaps'] and not relationship
        reasons = list(why) + fit['matched']
        if r and r['status'] == 'customer' and 'Existing customer with a new signal' not in reasons:
            reasons.append('Already a customer: you have a relationship to build on')
        sector = (r or {}).get('sector') or lead.get('sector') or ''
        if learned_sectors and sector and sector.lower() in learned_sectors:
            reasons.append(f"Like customers you have won ({sector})")
        kinds = sorted({m['type'] for m in members})
        if len(kinds) > 1:
            reasons.append(f"Seen in {len(kinds)} kinds of source: {', '.join(kinds)}")
        cautions = list(fit['gaps'])
        if unproven_service:
            tier = 'watch'  # a near deadline is not enough when the record does not say it needs what you sell
            cautions.insert(0, 'The record does not say it needs a service you sell: check before spending time')
        if outside:
            tier = 'watch'  # outside the territory you said you cover: kept in view, not put on today's list
        if lead['basis'] == 'inferred':
            cautions.insert(0, 'Inferred, not advertised: a reason to investigate, not proof of a requirement')
        if lead['type'] == 'shadow' and (lead.get('shadow') or {}).get('state') == 'challenged':
            cautions.insert(0, 'Later evidence challenges this reading')
        brief = lead['brief']
        rows.append({
            'key': lead['key'], 'organisation': lead['organisation'], 'account_id': lead.get('account_id'), 'type': lead['type'], 'kind': lead['kind'],
            'kind_label': lead['kind_label'], 'title': lead['title'], 'site': (lead.get('shadow') or {}).get('site'), 'tier': tier, 'tier_label': TIERS[tier],
            'reasons': reasons, 'cautions': cautions[:3], 'why_customer': brief['why_customer'], 'why_now': brief['why_now'], 'why_now_basis': brief['why_now_basis'],
            'known': brief['known'][:3], 'unknown': brief['unknown'][:3], 'speak_to': brief['who'], 'next': next_action(lead, r, prof['stated']), 'timing': lead.get('timing'),
            'days': lead.get('days'), 'services': lead['services'],
            'signals': [{'key': m['key'], 'type': m['type'], 'label': m['kind_label'], 'why_now': m['why_now']} for m in members[:4]],
            'relationship': {k: r[k] for k in ('status', 'open_deals', 'overdue', 'requirement', 'last_activity')} if r else None,
            '_sort': ({'act_now': 0, 'this_week': 1, 'watch': 2}[tier], lead['basis'] != 'published', -(len(fit['matched']) - len(fit['gaps'])),
                      0 if r else 1, lead['days'] if lead.get('days') is not None and lead['days'] >= 0 else 9999, lead['organisation']),
        })
    rows.sort(key=lambda x: x['_sort'])
    for x in rows:
        x.pop('_sort')
    # A focused day: only what is worth acting on today or this week. Everything else stays in Discover, counted, not listed.
    focus = [x for x in rows if x['tier'] != 'watch'][:limit]
    if len(focus) < 3:  # a quiet day still shows the strongest leads in view, labelled as such
        focus += [x for x in rows if x['tier'] == 'watch'][:3 - len(focus)]
    shown = focus
    return {'as_of': today.isoformat(), 'items': shown, 'total': len(rows), 'tiers': dict(Counter(x['tier'] for x in rows)),
            'in_view': sum(1 for x in rows if x['tier'] == 'watch' and x not in shown),
            'set_aside': [{'reason': k, 'count': v} for k, v in set_aside.items()], 'profile': prof,
            'method': ('Ordered by tier, then published evidence before inferred, closer fit to your profile, existing relationships, and the soonest date. '
                       'No probability is shown: none has been validated.')}


def results(db: Session) -> dict:
    """What discovery led to, by where the account came from. Counts accounts reaching each step, from recorded events and records;
    order in time is shown, causation is not claimed."""
    from app.models.acquisition import ResearchJob
    events = db.scalars(select(FunnelEvent).where(FunnelEvent.account_id.is_not(None))).all()
    steps = [('accepted', 'Accounts opened from a lead', ('account_created', 'lead_investigated')),
             ('investigated', 'Investigated', ('investigation_started',)),
             ('contacts', 'Contact routes found', ('contacts_found', 'contact_verified')),
             ('prepared', 'Introduction prepared', ('draft_saved',)),
             ('outreach', 'Outreach recorded', ('outreach_recorded',)),
             ('response', 'Customer responded', ('customer_response',)),
             ('meeting', 'Meeting booked', ('meeting_booked',)),
             ('requirement', 'Requirement confirmed', ('requirement_confirmed',)),
             ('qualified', 'Qualified into a deal', ('deal_created',)),
             ('proposal', 'Proposal or bid', ('deal_proposal', 'deal_bid_review', 'deal_negotiation', 'deal_approval')),
             ('won', 'Won', ('deal_won',)), ('lost', 'Lost', ('deal_lost',))]
    origin_of = {}
    for e in sorted(events, key=lambda e: e.id):
        origin_of.setdefault(e.account_id, e.source_type or 'manual')
    by_source: dict[str, dict] = {}
    for src in ('shadow', 'public', 'private', 'manual'):
        accounts = {a for a, s in origin_of.items() if s == src}
        if not accounts:
            continue
        mine = [e for e in events if e.account_id in accounts]
        counts = {k: len({e.account_id for e in mine if e.event in names}) for k, _, names in steps}
        won_value = [e for e in mine if e.event == 'deal_won' and e.amount is not None]
        jobs_cost = sum(j.actual_cents for j in db.scalars(select(ResearchJob).where(ResearchJob.account_id.in_(list(accounts)))))
        first = {}
        for e in sorted(mine, key=lambda e: e.id):
            first.setdefault((e.account_id, e.event), e.at.date() if e.at else e.day)
        lags = []
        for a in accounts:
            start = first.get((a, 'account_created')) or first.get((a, 'lead_investigated'))
            act = first.get((a, 'outreach_recorded'))
            if start and act:
                lags.append((act - start).days)
        contacts = counts['contacts']
        by_source[src] = {
            'accounts': len(accounts), 'steps': [{'key': k, 'label': label, 'accounts': counts[k]} for k, label, _ in steps],
            'won_value': {basis: sum(e.amount for e in won_value if e.amount_basis == basis) for basis in {e.amount_basis for e in won_value}},
            'research_cents': jobs_cost,
            'cost_per_researched_account': round(jobs_cost / max(counts['investigated'] or counts['contacts'], 1)) if jobs_cost else 0,
            'cost_per_account_with_contacts': round(jobs_cost / contacts) if contacts and jobs_cost else None,
            'cost_per_qualified': round(jobs_cost / counts['qualified']) if counts['qualified'] and jobs_cost else None,
            'median_days_to_first_outreach': median(lags) if lags else None}
    presented = db.scalar(select(func.count(func.distinct(FunnelEvent.ref))).where(FunnelEvent.event == 'lead_presented')) or 0
    opened = len({e.ref for e in events if e.event in ('lead_investigated',) and e.ref})
    return {'sources': by_source, 'leads_presented': presented, 'leads_opened': opened,
            'labels': {'shadow': 'Shadow Radar', 'public': 'Public procurement', 'private': 'Private research', 'manual': 'Added by hand'},
            'note': 'Counts accounts that reached each step, from what was recorded. A source appearing earlier does not prove it caused the result.'}


def seen(db: Session, keys: list[str]) -> int:
    """Record that these leads were actually shown to the salesperson (reported by the interface when each card is on
    screen), once per lead per day. Reading the list through the API is not exposure and records nothing."""
    from app.models.crm import AccountLink
    today = core.uk_today()
    already = set(db.scalars(select(FunnelEvent.ref).where(FunnelEvent.event == 'lead_presented', FunnelEvent.day == today)))
    entity = {'mo': 'market_opportunity', 'pr': 'prospect', 'sh': 'shadow_hypothesis'}
    recorded = 0
    for key in dict.fromkeys(keys):
        if key in already:
            continue
        prefix, _, raw = key.partition(':')
        link = db.scalar(select(AccountLink).where(AccountLink.entity_type == entity[prefix], AccountLink.entity_id == int(raw)))
        core.track(db, 'lead_presented', account_id=link.account_id if link else None, ref=key, origin=None if link else key)
        recorded += 1
    return recorded
