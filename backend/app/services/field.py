"""The field: what the published record already says about this buyer and this kind of work.

A salesperson deciding whether to pursue a tender or a contract nearing its end asks the same four things every time:
who holds this work today, what has this buyer bought before and from whom, which companies win this kind of work
around here, and what does it usually go for. The Contract Atlas already holds the published answers. This module
reads them for one opportunity.

It states counts, dates and values as published. It never predicts who will bid, never estimates a chance of winning,
and never calls a published supplier the current one: a published contract in term is exactly that and no more.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from statistics import median
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.renewal_radar import families
from app.models.atlas import AtlasContractParty, AtlasContractor
from app.models.market_contract import MarketContract
from app.models.market_network import MarketSourceState
from app.services import atlas, notice

NATIONS = ('England', 'Scotland', 'Wales', 'Northern Ireland')
IN_TERM = {'in_term', 'end_approaching', 'extension_possible'}
PAST = {'extension_window', 'end_passed_unknown', 'replacement_identified'}
RECENT_YEARS = 6
COVERAGE = ('Built from contracts published on Find a Tender, Contracts Finder and Public Contracts Scotland. Work let below the advertising '
            'threshold, through a facilities contract or privately does not appear, so an empty list is not proof that nobody holds the work.')
_INDEX: dict = {'key': None, 'rows': []}


def _index(db: Session) -> list[dict]:
    """Every supplier-to-contract link in the Atlas, slimmed. Rebuilt when the Atlas is: shared public facts only."""
    cursor = db.scalar(select(MarketSourceState.cursor).where(MarketSourceState.source_key == atlas.STATE_KEY))
    if not cursor:
        return []
    key = (id(db.get_bind()), cursor)
    if _INDEX['key'] == key:
        return _INDEX['rows']
    rows = []
    found = db.execute(select(AtlasContractParty, MarketContract, AtlasContractor).join(MarketContract, MarketContract.id == AtlasContractParty.contract_id)
                       .join(AtlasContractor, AtlasContractor.id == AtlasContractParty.contractor_id)).all()
    for party, contract, contractor in found:
        facts = contract.facts or {}
        evidence = [e for e in facts.get('evidence') or [] if isinstance(e, dict)]
        rows.append({
            'contract_id': contract.id, 'contractor_id': contractor.id, 'supplier': contractor.display_name, 'customer_key': party.customer_key,
            'buyer': contract.buyer, 'title': contract.title, 'families': set(party.disciplines or []), 'scope': party.scope, 'route': party.route,
            'region': party.region or '', 'nation': contract.nation, 'ocid': contract.ocid or '',
            'awarded': str(facts.get('award_date') or facts.get('published') or '')[:10],
            'dates': {k: facts.get(k) for k in ('published_end_date', 'estimated_end_date', 'latest_end', 'latest_end_basis', 'replacement')},
            'value': atlas.value_of(facts), 'revisions': [e['source_revision_id'] for e in evidence if e.get('source_revision_id')][:3],
            'url': next((e['source_url'] for e in evidence if e.get('source_url')), ''),
        })
    _INDEX.update(key=key, rows=rows)
    return rows


def _status(row: dict, today: date) -> dict:
    return atlas.status_of(SimpleNamespace(facts=row['dates']), row['route'], today)


def _annual(value: dict | None) -> float | None:
    if not value or value.get('kind') == 'framework_ceiling':
        return None
    if value.get('kind') == 'published_annual':
        return float(value['amount'])
    return float(value['annual_estimate']) if value.get('annual_estimate') else None


def _value_line(value: dict | None) -> str:
    if not value:
        return ''
    text = notice.money(float(value['amount']))
    if value.get('kind') == 'framework_ceiling':
        return f'{text} framework ceiling'
    if value.get('kind') == 'published_annual':
        return f'{text} a year'
    annual = value.get('annual_estimate')
    return f'{text} total' + (f' (about {notice.money(float(annual))} a year)' if annual else '')


def _long(day: str) -> str:
    try:
        return date.fromisoformat(str(day)[:10]).strftime('%-d %B %Y')
    except ValueError:
        return str(day or '')


def _labels(found: set[str]) -> list[str]:
    return [atlas.FAMILY_LABEL.get(f, f) for f in sorted(found)]


def _cards(rows: list[dict], fam: set[str], own: str, today: date) -> list[dict]:
    """One card per contract, with every supplier named on it."""
    grouped: dict[int, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r['contract_id'], []).append(r)
    out = []
    for cid, parts in grouped.items():
        r = parts[0]
        status = _status(r, today)
        found = set().union(*(p['families'] for p in parts))
        out.append({
            'key': f'mc:{cid}', 'title': r['title'], 'buyer': r['buyer'],
            'suppliers': [{'name': p['supplier'], 'contractor_id': p['contractor_id'], 'yours': atlas.own_company(p['supplier'], own)}
                          for p in sorted(parts, key=lambda p: p['supplier'])][:8],
            'supplier_count': len(parts), 'services': _labels(found), 'similar': bool(fam & found), 'route': atlas.ROUTE_LABEL.get(r['route'], ''),
            'call_off': r['route'] == 'call_off',
            'framework': r['route'] == 'framework_appointment', 'status': {'code': status['code'], 'label': status['label']}, 'end': status.get('end') or '',
            'awarded': r['awarded'], 'value': _value_line(r['value']), 'annual': _annual(r['value']), 'source': r['url'], 'ocid': r['ocid'],
            'revisions': r['revisions'],
        })
    return out


def _last_time(db: Session, card: dict) -> dict:
    """How this contract was bought, from its own award notice: bids received and how they were scored."""
    out: dict = {}
    for rid in card.get('revisions') or []:
        f = notice.for_revision(db, rid)
        if f.get('bids') and 'bids' not in out:
            out['bids'] = f['bids']['label']
            if f['bids'].get('bid_range'):
                out['bid_range'] = f['bids']['bid_range']['label']
        if (f.get('criteria') or {}).get('summary') and 'scoring' not in out:
            out['scoring'] = f['criteria']['summary']
            if f['criteria'].get('split'):
                out['split'] = f['criteria']['split']
        if (f.get('procedure') or {}).get('method_label') and 'procedure' not in out:
            out['procedure'] = f['procedure']['method_label']
    return out


def _public(card: dict) -> dict:
    return {k: v for k, v in card.items() if k not in ('revisions', 'ocid', 'annual')}


def _incumbent(cards: list[dict], fam: set[str], ocids: set[str]) -> dict:
    """The supplier the published record shows for similar work with this buyer. Never 'the current supplier'."""
    pool = [c for c in cards if not c['framework'] and c['ocid'] not in ocids and (c['similar'] or not fam)]
    live = sorted((c for c in pool if c['status']['code'] in IN_TERM), key=lambda c: c['end'], reverse=True)
    past = sorted((c for c in pool if c['status']['code'] in PAST), key=lambda c: c['end'], reverse=True)
    caveat = 'From the published record. It does not confirm who delivers the work today, or that the scope is the same.'
    for state, found in (('in_term', live), ('past', past)):
        if found:
            c = found[0]
            names = [s['name'] for s in c['suppliers']]
            who = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
            what, end = f"\u201c{c['title'][:110]}\u201d", _long(c['end'])
            text = (f"{who} {'holds' if len(names) == 1 else 'hold'} a published contract with this buyer for similar work, {what}, in term to {end}." if state == 'in_term' else
                    f"{who} {'was' if len(names) == 1 else 'were'} the published supplier on {what}, similar work for this buyer. Its published end ({end}) has passed "
                    'and the current position is not published.')
            return {'state': state, 'names': names, 'suppliers': c['suppliers'], 'text': text, 'contract': _public(c), 'caveat': caveat,
                    'others': len(found) - 1}
    return {'state': 'none', 'names': [], 'suppliers': [], 'text': 'No published contract for similar work with this buyer in the records collected.',
            'caveat': 'Most maintenance work below the advertising threshold is never published, so whoever does the work today may simply be unlisted.', 'others': 0}


def _winners(rows: list[dict], fam: set[str], nation: str, region: str, buyer_key: str, own: str, today: date) -> dict | None:
    """Companies with published contracts for this kind of work in this nation. A record of past awards, not a forecast."""
    if not fam:
        return None
    since = f'{today.year - RECENT_YEARS}-01-01'
    pool = [r for r in rows if r['route'] != 'framework_appointment' and fam & r['families'] and (not r['awarded'] or r['awarded'] >= since)]
    scope = nation if nation in NATIONS else ''
    if scope:
        pool = [r for r in pool if r['nation'] == scope]
    by: dict[int, dict] = {}
    for r in pool:
        entry = by.setdefault(r['contractor_id'], {'contractor_id': r['contractor_id'], 'name': r['supplier'], 'contracts': set(), 'buyers': set(), 'latest': '',
                                                   'latest_buyer': '', 'in_region': set(), 'this_buyer': False})
        entry['contracts'].add(r['contract_id'])
        entry['buyers'].add(r['customer_key'])
        if region and r['region'] == region:
            entry['in_region'].add(r['contract_id'])
        if r['customer_key'] == buyer_key:
            entry['this_buyer'] = True
        if r['awarded'] > entry['latest']:
            entry['latest'], entry['latest_buyer'] = r['awarded'], r['buyer']
    ranked = sorted(by.values(), key=lambda e: (e['this_buyer'], len(e['in_region']), len(e['contracts']), e['latest']), reverse=True)
    out = [{'contractor_id': e['contractor_id'], 'name': e['name'], 'contracts': len(e['contracts']), 'buyers': len(e['buyers']), 'latest': e['latest'],
            'latest_buyer': e['latest_buyer'], 'in_region': len(e['in_region']), 'this_buyer': e['this_buyer'], 'yours': atlas.own_company(e['name'], own)}
           for e in ranked[:6]]
    if not out:
        return None
    where = scope or 'the UK'
    return {'items': out, 'suppliers': len(by), 'contracts': len({r['contract_id'] for r in pool}),
            'basis': f"Suppliers named on published contracts for {', '.join(_labels(fam)).lower()} in {where} since {today.year - RECENT_YEARS}"
                     + (f', those with work in {region} first' if region and region != scope and any(e['in_region'] for e in out) else '') + '.',
            'caveat': 'A record of published awards. It does not say who will bid.'}


def _prices(rows: list[dict], fam: set[str], nation: str, skip: set[str], today: date) -> dict | None:
    """Recent published awards for similar work, and the range of their yearly values where the record gives one."""
    if not fam:
        return None
    pool: dict[int, dict] = {}
    for r in rows:
        if r['route'] == 'framework_appointment' or not fam & r['families'] or r['ocid'] in skip:
            continue
        pool.setdefault(r['contract_id'], r)
    scope = nation if nation in NATIONS else ''
    local = [r for r in pool.values() if r['nation'] == scope] if scope else []
    chosen, where = (local, scope) if len([r for r in local if _annual(r['value'])]) >= 5 else (list(pool.values()), 'the UK')
    yearly = sorted(a for a in (_annual(r['value']) for r in chosen) if a)
    recent = sorted((r for r in chosen if r['value'] and r['value'].get('kind') != 'framework_ceiling' and r['awarded']), key=lambda r: r['awarded'], reverse=True)[:5]
    if len(yearly) < 5 and not recent:
        return None
    out: dict = {'where': where, 'recent': [{'key': f"mc:{r['contract_id']}", 'buyer': r['buyer'], 'supplier': r['supplier'], 'title': r['title'], 'awarded': r['awarded'],
                                             'value': _value_line(r['value']), 'source': r['url']} for r in recent]}
    if len(yearly) >= 5:
        q = lambda p: yearly[min(len(yearly) - 1, int(p * (len(yearly) - 1) + 0.5))]  # noqa: E731
        out['range'] = {'count': len(yearly), 'low': q(0.25), 'median': median(yearly), 'high': q(0.75),
                        'label': f'{notice.money(q(0.25))} to {notice.money(q(0.75))} a year',
                        'basis': f'The middle half of {len(yearly)} published contracts for similar work in {where} with a yearly value on the record. '
                                 'Contracts differ in size and scope: a guide to the range, not a price for this one.'}
    return out


def _price_weight(split: list[dict] | None) -> float | None:
    return next((float(s['weight']) for s in split or [] if s.get('label') == 'Price'), None)


def _compared(now: dict, card: dict, last: dict) -> list[dict]:
    """This tender set against the buyer's last published award for similar work. Each line needs the figure in both records."""
    out = []
    then, this = _price_weight(last.get('split')), _price_weight((now.get('criteria') or {}).get('split'))
    if then is not None and this is not None:
        out.append({'label': 'Scoring', 'text': f'Price counts for {this:g}% of the score, the same as last time.' if abs(then - this) < 1 else
                    f"Price counted for {then:g}% of the score last time and counts for {this:g}% now: "
                    f"{'quality' if this < then else 'price'} carries more weight than it did."})
    value, months = now.get('value') or {}, (now.get('term') or {}).get('months') or 0
    if value.get('amount') and months >= 6 and card.get('annual'):
        yearly = float(value['amount']) / (months / 12)
        out.append({'label': 'Size', 'text': f"This notice works out at about {notice.money(yearly)} a year. The last published award worked out at about "
                                             f"{notice.money(card['annual'])} a year."})
    lots = len(now.get('lots') or [])
    if lots > 1 and card.get('supplier_count') == 1:
        out.append({'label': 'Shape', 'text': f'This tender is split into {lots} lots. The last published award named one supplier.'})
    if last.get('bids'):
        spread = last.get('bid_range') or ''
        out.append({'label': 'Competition', 'text': f"{last['bids']} last time" + (f'; {spread[0].lower() + spread[1:]}' if spread else '') + '.'})
    return out


def _ways(history: dict, others: list[dict], last: dict, this_end: str, also_ending: int = 0, replaces: str = '') -> list[dict]:
    """Openings the published record shows, each resting on one fact. Never advice to go around a procurement."""
    out = []
    if last:
        parts = [last.get('procedure'), last.get('bids'), f"scored {last['scoring']}" if last.get('scoring') else '']
        out.append({'label': 'How it was bought last time', 'text': '; '.join(p for p in parts if p) + '. The last award is the best published guide to the next one.'})
    nxt = history.get('next_end')
    if nxt and nxt['key'] != replaces and (not this_end or nxt['end'] < this_end):
        out.append({'label': 'An earlier opening with this buyer', 'key': nxt['key'],
                    'text': f"\u201c{nxt['title'][:110]}\u201d reaches its published end on {_long(nxt['end'])}" + (', before this one.' if this_end else '.')})
    routed = sum(1 for c in others if c['call_off']) + history.get('frameworks', 0)
    if routed:
        out.append({'label': 'Frameworks', 'text': f"{routed} of this buyer\u2019s published contracts {'was' if routed == 1 else 'were'} let through a framework. "
                    'If it buys this way again, a place on that framework is the way in.'})
    if also_ending:
        n = also_ending
        out.append({'label': 'The holder\u2019s other contracts', 'text': f"The published holder has {n} other contract{'s' if n != 1 else ''} approaching "
                    f"{'their' if n != 1 else 'its'} published end. Each is a buyer making the same decision."})
    return out


def view(db: Session, *, customer: str, title: str, description: str = '', nation: str = '', region: str = '', own_name: str = '', ocids: set[str] | None = None,
         contract_id: int | None = None, supplier: str = '', contract_ending: bool = False, this_notice: dict | None = None, today: date | None = None) -> dict:
    """What the published record says about the buyer, the holder, the winners of similar work and their prices.
    `ocids` are this opportunity's own procurements. A procurement let in lots has several contracts: `contract_id`, or failing that
    the `supplier` named on the opportunity, narrows the holder to the one this opportunity is about. `this_notice` is what the
    opportunity's own tender notice states, so it can be set against the buyer's last award."""
    today = today or date.today()
    rows = _index(db)
    if not rows:
        return {'available': False, 'coverage': COVERAGE}
    ocids = {o for o in (ocids or set()) if o}
    own_row = (lambda r: r['contract_id'] == contract_id) if contract_id else (lambda r: r['ocid'] in ocids)
    own_card = (lambda c: c['key'] == f'mc:{contract_id}') if contract_id else (lambda c: c['ocid'] in ocids)
    fam = families(title) or families(description[:2000]) or set().union(*(r['families'] for r in rows if own_row(r)))
    buyer_key = atlas.normalise(customer)
    cards = _cards([r for r in rows if r['customer_key'] == buyer_key], fam, own_name, today)
    order = {'end_approaching': 0, 'extension_possible': 1, 'in_term': 2, 'extension_window': 3, 'end_passed_unknown': 4, 'replacement_identified': 5}
    cards.sort(key=lambda c: (not c['similar'], c['framework'], order.get(c['status']['code'], 8), c['end'] or '9999'))
    this = [c for c in cards if own_card(c)]
    named = atlas.normalise(supplier) if supplier and not contract_id else ''
    if named and any(atlas.normalise(s['name']) == named for c in this for s in c['suppliers']):
        keep = {c['key'] for c in this if any(atlas.normalise(s['name']) == named for s in c['suppliers'])}
        this, own_row = [c for c in this if c['key'] in keep], (lambda r: f"mc:{r['contract_id']}" in keep)
        own_card = lambda c: c['key'] in keep  # noqa: E731
    others = [c for c in cards if not own_card(c)]
    suppliers = sorted({s['name'] for c in others if not c['framework'] for s in c['suppliers']})
    upcoming = sorted((c for c in others if not c['framework'] and c['status']['code'] in IN_TERM and c['end'] and c['end'] >= today.isoformat()), key=lambda c: c['end'])
    history = {'key': buyer_key, 'contracts': len(others), 'similar': sum(1 for c in others if c['similar'] and not c['framework']), 'suppliers': suppliers[:12],
               'supplier_count': len(suppliers), 'frameworks': sum(1 for c in others if c['framework']),
               'regions': sorted({r['region'] for r in rows if r['customer_key'] == buyer_key and r['region']}),  # where its published contracts place it
               'next_end': {'end': upcoming[0]['end'], 'title': upcoming[0]['title'], 'key': upcoming[0]['key']} if upcoming else None,
               'items': [{**_public(c), **({'last_time': {k: v for k, v in lt.items() if k != 'split'}} if (lt := _last_time(db, c)) else {})} for c in others[:6]]}
    out: dict = {'available': True, 'services': _labels(fam), 'buyer': history, 'coverage': COVERAGE,
                 'winners': _winners(rows, fam, nation, region, buyer_key, own_name, today), 'prices': _prices(rows, fam, nation, ocids, today)}
    holder = None
    if contract_ending:
        holders = list({s['contractor_id']: s for c in this for s in c['suppliers']}.values())  # one notice with several lots names a supplier once
        ids = {s['contractor_id'] for s in holders}
        held = [r for r in rows if r['contractor_id'] in ids and r['route'] != 'framework_appointment']
        ending = [r for r in held if _status(r, today)['code'] in ('end_approaching', 'extension_possible') and not own_row(r)]
        holder = out['holder'] = {'suppliers': holders, 'contracts': len({r['contract_id'] for r in held}), 'buyers': len({r['customer_key'] for r in held}),
                                  'also_ending': len({r['contract_id'] for r in ending}), 'with_this_buyer': len({r['contract_id'] for r in held if r['customer_key'] == buyer_key}),
                                  'last_time': {k: v for k, v in _last_time(db, this[0]).items() if k != 'split'} if this else {}} if holders else None
        out['ways'] = _ways(history, others, (holder or {}).get('last_time') or {}, this[0]['end'] if this else '', (holder or {}).get('also_ending') or 0)
        return out
    found = out['incumbent'] = _incumbent(cards, fam, ocids)
    last, replaces = {}, ''
    if found['state'] != 'none':
        replaces = found['contract']['key']
        card = next(c for c in cards if c['key'] == replaces)
        last = _last_time(db, card)
        if last:
            found['last_time'] = {k: v for k, v in last.items() if k != 'split'}
        compared = _compared(this_notice or {}, card, last)
        if compared:
            out['compared'] = compared
    out['ways'] = _ways(history, others, last, '', replaces=replaces)
    return out


def footprint(db: Session, contractor_id: int, *, own_name: str = '', today: date | None = None) -> dict | None:
    """Where one supplier's published work sits and when it comes up: the contracts reaching a published end, the buyers and
    regions it is concentrated in, the size it usually wins at, how it wins, and who else is named at the same buyers.
    Counted from published contracts only. A place on a framework is counted apart: it is not a contract."""
    today = today or date.today()
    every = _index(db)
    mine: dict[int, dict] = {}
    frameworks = 0
    for r in every:
        if r['contractor_id'] != contractor_id:
            continue
        if r['route'] == 'framework_appointment':
            frameworks += 1
        else:
            mine.setdefault(r['contract_id'], r)
    if not mine and not frameworks:
        return None
    contracts = list(mine.values())
    named = Counter(r['contract_id'] for r in every)
    horizon = (today + timedelta(days=atlas.HORIZON_DAYS)).isoformat()

    def card(r: dict, status: dict | None = None) -> dict:
        end = (status or {}).get('end') or ''
        return {'key': f"mc:{r['contract_id']}", 'buyer': r['buyer'], 'customer_key': r['customer_key'], 'title': r['title'], 'end': end,
                'days': (date.fromisoformat(end[:10]) - today).days if end else None, 'awarded': r['awarded'], 'value': _value_line(r['value']),
                'services': _labels(r['families']), 'where': r['region'] or r['nation'] or '', 'shared': named[r['contract_id']] > 1,
                'status': (status or {}).get('label') or ''}

    upcoming, lapsed, years = [], 0, {}
    for r in contracts:
        status = _status(r, today)
        end = str(status.get('end') or '')[:10]
        if status['code'] in IN_TERM and end >= today.isoformat():
            year = years.setdefault(end[:4], {'year': end[:4], 'contracts': 0, 'annual': 0.0, 'valued': 0})
            year['contracts'] += 1
            if yearly := _annual(r['value']):
                year['annual'], year['valued'] = year['annual'] + yearly, year['valued'] + 1
            if end <= horizon:
                upcoming.append((end, r, status))
        elif status['code'] in ('extension_window', 'end_passed_unknown'):
            lapsed += 1
    upcoming.sort(key=lambda x: (x[0], x[1]['buyer']))
    valued = [a for a in (_annual(r['value']) for _, r, _ in upcoming) if a]
    n = len(upcoming)
    exposure = {
        'months': round(atlas.HORIZON_DAYS / 30.4), 'until': horizon, 'contracts': n, 'items': [card(r, s) for _, r, s in upcoming[:8]],
        'valued': len(valued), 'annual': round(sum(valued)), 'lapsed': lapsed,
        'label': (f"{n} published contract{'s' if n != 1 else ''} reach{'es' if n == 1 else ''} {'its' if n == 1 else 'their'} published end by {_long(horizon)}"
                  if n else f'No published contract reaches a published end by {_long(horizon)}'),
        'value_label': ('' if not n else 'None of them carries a published value.' if not valued else
                        f'About {notice.money(sum(valued))} a year in published value.' if len(valued) == n else
                        f'About {notice.money(sum(valued))} a year across the {len(valued)} of {n} that carry a published value.'),
        'caveat': 'Published end dates only. A contract can be extended, or re-let without a notice, so confirm each before relying on it.'}

    yearly = sorted(a for a in (_annual(r['value']) for r in contracts) if a)
    size: dict = {'count': len(yearly), 'contracts': len(contracts)}
    if len(yearly) >= 5:
        q = lambda p: yearly[min(len(yearly) - 1, int(p * (len(yearly) - 1) + 0.5))]  # noqa: E731
        size.update(low=q(0.25), median=median(yearly), high=q(0.75), label=f'{notice.money(q(0.25))} to {notice.money(q(0.75))} a year',
                    basis=f'The middle half of its {len(yearly)} published contracts with a yearly value on the record. The median is {notice.money(median(yearly))} a year.')
    elif yearly:
        size['basis'] = f"Only {len(yearly)} of its published contracts carr{'ies' if len(yearly) == 1 else 'y'} a yearly value: too few to state a typical size."
    biggest = max((r for r in contracts if _annual(r['value'])), key=lambda r: _annual(r['value']), default=None)
    if biggest:
        size['largest'] = card(biggest, _status(biggest, today))

    buyers: dict[str, dict] = {}
    for r in contracts:
        b = buyers.setdefault(r['customer_key'], {'key': r['customer_key'], 'name': r['buyer'], 'contracts': 0, 'in_term': 0, 'latest': ''})
        b['contracts'] += 1
        b['in_term'] += _status(r, today)['code'] in IN_TERM
        b['latest'] = max(b['latest'], r['awarded'])
    top = sorted(buyers.values(), key=lambda b: (b['in_term'], b['contracts'], b['latest']), reverse=True)
    regions = Counter(r['region'] or r['nation'] or 'Not published' for r in contracts)
    since = today.year - 4
    awards = Counter(r['awarded'][:4] for r in contracts if r['awarded'] and int(r['awarded'][:4]) >= since)
    recent = sorted((r for r in contracts if r['awarded']), key=lambda r: r['awarded'], reverse=True)[:5]
    routes = Counter(r['route'] for r in contracts)

    # Who else the published record names at the same buyers for the same kind of work, on a different contract.
    work = {(r['customer_key'], f) for r in contracts for f in r['families']}
    seen: dict[int, dict] = {}
    for r in every:
        if r['contractor_id'] == contractor_id or r['route'] == 'framework_appointment' or r['contract_id'] in mine:
            continue
        if any((r['customer_key'], f) in work for f in r['families']):
            entry = seen.setdefault(r['contractor_id'], {'contractor_id': r['contractor_id'], 'name': r['supplier'], 'buyers': set()})
            entry['buyers'].add(r['customer_key'])
    rivals = sorted((e for e in seen.values() if len(e['buyers']) >= 2), key=lambda e: (-len(e['buyers']), e['name']))[:6]  # one shared buyer is chance

    return {
        'contracts': len(contracts), 'frameworks': frameworks, 'buyers': len(buyers), 'exposure': exposure,
        'ends_by_year': [{**years[y], 'annual': round(years[y]['annual'])} for y in sorted(years)][:6], 'size': size,
        'top_buyers': top[:6], 'regions': [{'name': k, 'contracts': v} for k, v in regions.most_common(6)],
        'awards_by_year': [{'year': str(y), 'awards': awards.get(str(y), 0)} for y in range(since, today.year + 1)] if awards else [],
        'recent': [card(r, _status(r, today)) for r in recent],
        'routes': [{'code': k, 'label': {'direct_award': 'Awarded by the buyer', 'call_off': 'Called off a framework'}.get(k, atlas.ROUTE_LABEL.get(k, k)), 'contracts': v}
                   for k, v in routes.most_common()],
        'rivals': [{'contractor_id': e['contractor_id'], 'name': e['name'], 'buyers': len(e['buyers']), 'yours': atlas.own_company(e['name'], own_name)} for e in rivals],
        'rivals_basis': 'Suppliers named on a different published contract for the same kind of work at the same buyers. It shows where their markets overlap, not who won against whom.',
        'coverage': COVERAGE}
