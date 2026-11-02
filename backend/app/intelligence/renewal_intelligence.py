"""Turn stored procurement records into one evidence-backed UK opportunity list.

Every record passes through the same reduction whichever source published it. A
category and a next action come from fixed rules over published evidence. There
is no model, no probability and no invented contact. A priority tier orders work
by relevance, evidence, timing and actionability, and it says why.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta

from app.ingestion.market_find_tender_radar import ingest, notices as process_notices
from app.intelligence.contract_terms import BASIS_LABELS, PUBLISHED_BASES
from app.intelligence.renewal_radar import (ACT_NOW_FROM_DAYS, ACT_NOW_TO_DAYS, FRAMEWORK_REASON, RULE_VERSION, STALE_SIGNAL_DAYS, WINDOW_FUTURE_DAYS,
                                            _buyer_key, classify, contract_views, early_signals, families, nation_of)

CATEGORY_LABELS = {'pre_tender': 'Pre-tender opportunity', 'official_early_signal': 'Official early signal', 'live_procurement': 'Live procurement',
                   'contract_defence': 'Contract defence', 'verify_first': 'Uncertain: verify first'}
SOURCE_LABELS = {'contracts_finder': 'Contracts Finder', 'find_a_tender': 'Find a Tender', 'public_contracts_scotland': 'Public Contracts Scotland'}
HIGH_ANNUAL_VALUE = 250_000
MEDIUM_ANNUAL_VALUE = 50_000
LEAD_IN_DAYS = 180
MAX_EVIDENCE = 8
_BUNDLED_NOTE = 'The value covers wider maintenance, not only fire and security work.'
_STANDARD_UNKNOWNS = ['Whether the contract remains in force or has been extended, replaced or terminated.',
                      'Whether the original supplier currently delivers the service, and whether a competitive process is planned.']


def _day(value):
    return date.fromisoformat(value) if value else None


def _evidence(row, fields: list[str]) -> dict:
    return {'source_revision_id': row.id, 'source_url': row.source_url, 'source_key': row.source_key, 'record_key': row.record_key,
            'source': SOURCE_LABELS.get(row.source_key, row.source_key), 'published_at': row.published_at.isoformat() if row.published_at else None,
            'ocid': row.ocid, 'fields': fields}


def stored_notices(rows: list) -> dict:
    """Stored records by process, because several notices can describe one procurement."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.ocid].append(row)
    return grouped


def reduce_processes(grouped: dict, today: date) -> list[dict]:
    """One notice per awarded lot of each process, plus its planning notices."""
    found = []
    for ocid, group in grouped.items():
        cache = {'tenders': {}, 'processes': {}, 'planning': {}}
        for row in sorted(group, key=lambda x: (str(x.published_at or ''), x.id)):
            stamp = row.raw.get('date') or (row.published_at.isoformat() if row.published_at else None)
            ingest(cache, {**row.raw, 'date': stamp, 'x_misi': {'source': row.source_key, 'url': row.source_url}})
        for key, record in cache['tenders'].items():
            found += process_notices(record, cache['processes'].get(key, {}).get('releases', []), today)
        found += list(cache['planning'].values())
    return found


def lifecycle_status(view: dict, today: date) -> str:
    """What the published dates show. None of these says a contract is being delivered."""
    if view['fit'] == 'framework':
        return 'framework_agreement'
    end = _day(view.get('end'))
    if end is None:
        return 'term_unknown'
    if end < today:
        return 'ended_recently' if view['timing'] else 'historical'
    if view['end_estimated']:
        return 'in_term_estimated'
    return 'in_term_published' if (end - today).days <= WINDOW_FUTURE_DAYS else 'in_term_beyond_window'


def currency(status: str) -> str:
    return {'in_term_published': 'current', 'in_term_beyond_window': 'current', 'historical': 'historical'}.get(status, 'uncertain')


def _extended_into_window(view: dict, today: date) -> bool:
    """An initial term that has passed while a published or stated extension could still run."""
    end, latest = _day(view.get('end')), _day(view.get('latest_end'))
    return bool(end and latest and end < today <= latest and (latest - today).days <= WINDOW_FUTURE_DAYS)


def category_of(view: dict, today: date) -> tuple[str | None, list[str]]:
    """(category, reasons a person must check first); no category means no opportunity."""
    extended = _extended_into_window(view, today)
    if view['fit'] == 'framework' or (not view['bucket'] and not extended):
        return None, []
    checks = list(view['contradictions'])
    if view['successor_url']:
        checks.append(f"A similar newer notice exists: {view['successor_title']} ({view['successor_published']}). This is a title match, not a confirmed replacement.")
    if view['timing'] == 'overdue_check' or extended:
        checks.append(f"The initial term ended on {view['end']}; it may have been extended, re-let or stopped.")
    if view['link_confidence'] == 'possible':
        checks.append('Records were joined on a similar title and end date, without a shared supplier or reference.')
    if view['end_basis'] == 'stated_term':
        checks.append('The end date is worked out from wording in the notice, not from a published date.')
    if view['own_group']:
        return 'contract_defence', checks
    return ('verify_first' if checks else 'pre_tender'), checks


def value_facts(view: dict) -> dict:
    """Published and derived figures kept apart; none is guaranteed or fully addressable spend."""
    total, annual, years = view.get('value'), view.get('annual_value'), (view.get('term_days') or 0) / 365.25
    facts = {'published_total': None, 'published_annual': None, 'estimated_annualised': None, 'framework_ceiling': None, 'type': 'unknown', 'basis': 'No value is published.', 'scope_note': ''}
    if not total:
        return facts
    if view['fit'] == 'framework':
        return {**facts, 'framework_ceiling': total, 'type': 'framework_ceiling', 'basis': 'Published framework value: a ceiling across suppliers, not spend on one contract.'}
    facts.update(published_total=total, type='published_total', basis='Published award value; the term is not published, so no annual figure is derived.')
    if annual:
        term = 'estimated' if view['end_estimated'] else 'published'
        facts.update(estimated_annualised=annual, type='estimated_annualised', basis=f'Published award value divided by the {term} term of {years:.1f} years.')
    if view['fit'] == 'bundled':
        facts['scope_note'] = _BUNDLED_NOTE
    return facts


def _value_rank(annual) -> int:
    return 0 if (annual or 0) >= HIGH_ANNUAL_VALUE else 1 if (annual or 0) >= MEDIUM_ANNUAL_VALUE else 2 if annual else 3


def _action_month(day: date, today: date) -> str:
    return max(day, today).strftime('%Y-%m')


def contract_priority(view: dict, category: str, checks: list[str], today: date) -> dict:
    """Tier 1 is ready for commercial work, tier 2 needs one more fact, tier 3 is background."""
    days = (_day(view['end']) - today).days
    published = view['end_basis'] in PUBLISHED_BASES
    in_action_window = ACT_NOW_FROM_DAYS <= days <= ACT_NOW_TO_DAYS
    extension_outside = bool(view['latest_end'] and (_day(view['latest_end']) - today).days > WINDOW_FUTURE_DAYS)
    reasons = [f"{view['fit'].capitalize()} fit", f"End date: {BASIS_LABELS.get(view['end_basis'], 'unknown')}"]
    if category == 'contract_defence' and view['fit'] != 'adjacent':
        tier = 1
        reasons.append('Held by the Mitie group, so retention planning comes first')
    elif category == 'verify_first':
        tier = 3 if view['fit'] == 'adjacent' else 2
        reasons.append('Evidence must be checked before pursuit')
    elif view['fit'] == 'core' and published and in_action_window and view['incumbent'] and not extension_outside:
        tier = 1
        reasons.append('Published end falls 3 to 12 months away, with a named incumbent')
    elif view['fit'] == 'adjacent':
        tier = 3
    else:
        tier = 2
    if extension_outside:
        reasons.append(f"Extensions could run to {view['latest_end']}")
    # Order by when work must start, so a near deadline outranks a larger distant contract.
    action = _action_month(_day(view['end']) - timedelta(days=LEAD_IN_DAYS), today)
    rank = (tier, 0 if category == 'contract_defence' else 1, action, 0 if published else 1, _value_rank(view.get('annual_value')), view['end'])
    return {'tier': tier, 'sort': list(rank), 'reasons': reasons}


def contract_actions(view: dict, category: str, checks: list[str]) -> list[str]:
    actions = []
    if category == 'contract_defence':
        actions.append('Escalate to the account lead for retention planning, and confirm the current contract position internally.')
    if view['extension_mentioned']:
        actions.append('Verify whether an extension has been exercised, and to what date.')
    if view['successor_url']:
        actions.append('Open the newer notice and confirm whether it replaces this contract.')
    if view['end_estimated']:
        actions.append('Confirm the true end date; the date shown is an estimate.')
    if view['timing'] == 'overdue_check':
        actions.append('Confirm the current supplier arrangement now the published term has ended.')
    if view['framework_stage'] == 'framework_second_stage':
        actions.append('Investigate framework eligibility: this was called off a framework, so the next round may be closed to non-members.')
    if category == 'pre_tender':
        actions += ["Investigate the customer's next procurement programme and pipeline notices.", 'Identify the appropriate procurement or estates decision-making role through public sources.',
                    'Prepare a capability-led introduction once timing is confirmed.']
    elif category == 'verify_first' and not actions:
        actions.append('Confirm the current supplier arrangement before any commercial approach.')
    return actions


def missing_information(view: dict) -> list[str]:
    missing = []
    if view['end_estimated']:
        missing.append('Published contract end date.')
    if view['extension_mentioned'] and not view['latest_end']:
        missing.append('Extension length and whether it has been used.')
    if not view['value']:
        missing.append('Contract value.')
    if not view['company_numbers']:
        missing.append('Incumbent company number; only a name is published.')
    missing.append('Procurement route for the next contract.')
    return missing


def contract_brief(view: dict, category: str, value: dict, checks: list[str], actions: list[str]) -> dict:
    """The ten commercial questions, answered only from what is established."""
    term = f"{view['start'] or 'unknown start'} to {view['end']}{' (estimated)' if view['end_estimated'] else ''}"
    if view['latest_end']:
        term += f", can run to {view['latest_end']}{' (from notice wording)' if view['latest_end_basis'] == 'extension_wording' else ''}"
    route = view['route'] or ('Call-off from a framework' if view['framework_stage'] == 'framework_second_stage' else 'Not published for the next contract')
    why = f"{view['fit_reason'].capitalize()}. The published term ends {view['end']}."
    return {'customer': view['buyer'], 'service_requirement': view['title'], 'incumbent': view['incumbent'] or 'Not named in the notice', 'commercial_value': value['basis'],
            'contract_lifecycle': term, 'procurement_route': route, 'timing': CATEGORY_LABELS[category], 'why_it_matters': why,
            'missing_information': missing_information(view), 'next_action': actions[0] if actions else 'Review the source notice.'}


def contract_proposal(view: dict, evidence: list[dict], category: str, checks: list[str], today: date) -> dict:
    value, priority = value_facts(view), contract_priority(view, category, checks, today)
    actions = contract_actions(view, category, checks)
    extension = view['extension_note'] or ('A later possible end date is published.' if view['latest_end'] else '')
    return {'kind': 'possible_renewal_window', 'rule_version': RULE_VERSION, 'category': category, 'category_label': CATEGORY_LABELS[category], 'customer': view['buyer'],
            'title': view['title'], 'supplier': view['incumbent'] or None, 'timing': view['end'], 'timing_basis': BASIS_LABELS.get(view['end_basis'], 'unknown'),
            'end_estimated': view['end_estimated'], 'latest_end': view['latest_end'] or None, 'nation': view['nation'], 'fit': view['fit'], 'fit_reason': view['fit_reason'],
            'value': value, 'priority': priority, 'observation': f"Published records show this contract's term ending {view['end']}{' (estimated)' if view['end_estimated'] else ''}.",
            'commercial_relevance': 'Retention planning may be needed.' if category == 'contract_defence' else 'The published term may be a useful point to check for a future service conversation.',
            'inference': 'The end date may indicate a renewal window, subject to extensions or subsequent changes.', 'counter_evidence': checks,
            'unknowns': [*_STANDARD_UNKNOWNS, 'Applicable framework or call-off status.'], 'next_action': actions[0] if actions else 'Review the source notice.', 'next_actions': actions,
            'extension': extension, 'replacement': {'status': 'possible', 'title': view['successor_title'], 'published': view['successor_published'], 'url': view['successor_url']} if view['successor_url'] else None,
            'link': {'confidence': view['link_confidence'], 'records': len(view['members']), 'sources': sorted({SOURCE_LABELS.get(x['source'], x['source']) for x in view['members']})},
            'brief': contract_brief(view, category, value, checks, actions), 'evidence': evidence}


def _sector_framework(notice: dict) -> bool:
    fit, reason = classify({**notice, 'start': None})
    return fit == 'exclude' and reason == FRAMEWORK_REASON and bool(families(notice['title']))


def signal_proposal(notice: dict, evidence: list[dict], category: str, fit: str, reason: str, timing: str | None, today: date) -> dict:
    live = category == 'live_procurement'
    framework = fit == 'framework'
    actions = (['Review the tender documents and deadline today, and decide whether to bid.', 'Confirm eligibility and capacity to respond before the deadline.'] if live
               else ['Monitor the expected procurement date and register on the buyer portal.', "Investigate the customer's procurement programme and any market engagement event."])
    if framework:
        actions.insert(0, 'Investigate framework eligibility: winning a place decides access to later call-offs.')
    if category == 'verify_first':
        actions.insert(0, 'Confirm whether this tender is still open; no deadline is published.')
    passed = category == 'official_early_signal' and bool(timing) and _day(timing) < today
    if passed:
        actions.insert(0, 'Check whether this tender has already been published: the expected date has passed.')
    annual = notice.get('value')
    value = {'published_total': annual, 'published_annual': None, 'estimated_annualised': None, 'framework_ceiling': annual if framework else None,
             'type': ('framework_ceiling' if framework else 'published_total') if annual else 'unknown',
             'basis': 'Value published on the notice; it can be a ceiling.' if annual else 'No value is published.', 'scope_note': ''}
    if framework:
        value['published_total'] = None
    tier = 1 if live and fit in {'core', 'framework'} else 2 if fit in {'core', 'bundled', 'framework'} else 3
    if category == 'official_early_signal' and fit == 'core' and timing and not passed:
        tier = 1
    action = _action_month(_day(timing), today) if timing else '9999-12'
    priority = {'tier': tier, 'sort': [tier, 1, action, 0 if timing else 1, _value_rank(annual), timing or '9999-12-31'],
                'reasons': [f'{fit.capitalize()} fit', 'A published deadline' if live else 'The expected date has passed' if passed else 'A published expected date' if timing else 'No published date']}
    observation = 'A public notice describes planned or tender-stage fire or security service activity.'
    return {'kind': 'published_procurement_signal', 'rule_version': RULE_VERSION, 'category': category, 'category_label': CATEGORY_LABELS[category], 'customer': notice['buyer'],
            'title': notice['title'], 'supplier': None, 'timing': timing, 'timing_basis': 'published deadline' if live else 'published expected date' if timing else 'none', 'end_estimated': False,
            'latest_end': None, 'nation': nation_of(notice), 'fit': fit, 'fit_reason': reason, 'value': value, 'priority': priority, 'observation': observation,
            'commercial_relevance': 'Review the scope for a possible service fit and the route for engagement.',
            'inference': 'A future opportunity may exist; the publication alone does not establish a current requirement, eligibility, or an open tender.' if not live else 'A published tender is open until its deadline, unless later withdrawn.',
            'counter_evidence': [], 'unknowns': ['Current procurement status and whether the requirement has changed.', 'Existing suppliers, eligibility, service fit and contact route.'],
            'next_action': actions[0], 'next_actions': actions, 'extension': '', 'replacement': None, 'link': {'confidence': 'exact', 'records': 1, 'sources': [SOURCE_LABELS.get(notice.get('source'), notice.get('source'))]},
            'brief': {'customer': notice['buyer'], 'service_requirement': notice['title'], 'incumbent': 'Not named in the notice', 'commercial_value': value['basis'],
                      'contract_lifecycle': 'Not yet awarded', 'procurement_route': notice.get('route') or ('Framework' if framework else 'Not published'), 'timing': timing or 'No date published',
                      'why_it_matters': reason.capitalize() + '.', 'missing_information': ['Current supplier.', 'Scope and eligibility.'], 'next_action': actions[0]}, 'evidence': evidence}


def _process_evidence(grouped: dict, ocids: list[str], fields: list[str]) -> list[dict]:
    rows = [row for ocid in dict.fromkeys(ocids) for row in grouped.get(ocid, [])]
    rows.sort(key=lambda x: (str(x.published_at or ''), x.id), reverse=True)
    return [_evidence(row, fields) for row in rows[:MAX_EVIDENCE]]


def _end_fields(view: dict) -> list[str]:
    paths = {'contract_period': 'contracts.period.endDate', 'award_contract_period': 'awards.contractPeriod.endDate', 'published_duration': 'contractPeriod.durationInDays',
             'tender_planned_end': 'tender.lots.contractPeriod.endDate', 'tender_duration': 'tender.lots.contractPeriod.durationInDays', 'stated_term': 'tender.description'}
    return ['buyer.name', 'tender.title', 'awards.suppliers', paths.get(view['end_basis'], 'tender.description')]


def evaluate(rows: list, today: date) -> dict:
    """Contracts and proposals for every stored record, deduplicated across sources."""
    grouped = stored_notices(rows)
    notices = reduce_processes(grouped, today)
    contracts, proposals = [], {}
    for view in contract_views(notices, today):
        view['nation'] = nation_of(view)
        category, checks = category_of(view, today)
        status = lifecycle_status(view, today)
        evidence = _process_evidence(grouped, [x['ocid'] for x in view['members']], _end_fields(view))
        key = f"{view['ocid']}:{view['lot']}"
        record = {'view': view, 'key': key, 'status': status, 'currency': currency(status), 'category': category, 'checks': checks, 'evidence': evidence, 'value': value_facts(view)}
        if category:
            record['proposal'] = contract_proposal(view, evidence, category, checks, today)
        contracts.append(record)
    awarded = {x['ocid'] for x in notices if x.get('type') == 'Contract' and x.get('status') == 'Awarded'}
    seen = set()
    for notice in notices:
        if notice.get('type') != 'Contract' or notice.get('status') not in {'Open', 'Closed'} or notice['ocid'] in awarded:
            continue
        fit, reason = classify({**notice, 'start': None})
        if _sector_framework(notice):
            fit = 'framework'
        if fit == 'exclude':
            continue
        deadline, published = notice.get('deadline') or None, _day(notice.get('published'))
        undated_open = notice.get('tender_status') == 'active' and not deadline and published and published >= today - timedelta(days=STALE_SIGNAL_DAYS)
        if notice['status'] != 'Open' and not undated_open:
            continue
        label = (_buyer_key(notice['buyer']), notice['title'].lower())
        if label in seen:
            continue
        seen.add(label)
        category = 'live_procurement' if notice['status'] == 'Open' else 'verify_first'
        proposals[f"procurement:{notice['ocid']}"] = signal_proposal(notice, _process_evidence(grouped, [notice['ocid']], ['buyer.name', 'tender.title', 'tender.description', 'tender.status', 'tender.tenderPeriod']),
                                                                     category, fit, reason, deadline, today)
    for signal in early_signals(notices, today):
        if signal.get('ocid') and f"procurement:{signal['ocid']}" not in proposals:
            label = (_buyer_key(signal['buyer']), signal['title'].lower())
            if label not in seen:
                seen.add(label)
                proposals[f"procurement:{signal['ocid']}"] = signal_proposal({**signal, 'source': signal['source']}, _process_evidence(grouped, [signal['ocid']], ['buyer.name', 'tender.title', 'tender.description', 'tender.status']),
                                                                             'official_early_signal', signal['fit'], signal['fit_reason'], signal['expected_tender'] or None, today)
    return {'contracts': contracts, 'proposals': proposals, 'notices': notices}
