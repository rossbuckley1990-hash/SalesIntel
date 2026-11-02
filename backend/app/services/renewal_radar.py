"""Run the UK renewal radar on a schedule and report its state honestly.

Source monitors collect; this module decides when to re-evaluate, which older
weeks are worth a selective look, and whether each source is fresh. Everything
runs on this host, so nothing is collected while the host is off or asleep.
"""
from __future__ import annotations
from collections import Counter
from datetime import UTC, date, datetime, timedelta
import csv
import io
import json

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.intelligence.renewal_radar import OWN_GROUP
from app.models.market_contract import MarketContract, MarketContractLink
from app.models.market_network import MarketAward, MarketSourceState, SourceRevision
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.services.market_opportunities import refresh_market_opportunities
from app.services.renewal_history import HISTORY_STATE, OUTPUT, fetch_tenders, import_checkpoints, load_tenders, weeks_between

STATE = 'renewal_radar'
SOURCES = {'find_a_tender': timedelta(hours=6), 'contracts_finder': timedelta(hours=6), 'public_contracts_scotland': timedelta(hours=48)}
ENGINE_MAX_AGE = timedelta(hours=26)
SELECTIVE_REQUESTS_PER_DAY = 40
SELECTIVE_MIN_VALUE = 500_000
SELECTIVE_MIN_DAYS = 1460
COVERAGE_LIMITS = ['Find a Tender is read as an unbroken run back to the date shown; older long contracts published only there can be missing unless a selective lookup finds them.',
                   'Contracts Finder rows come from targeted fire and security searches back to 2021, then from the live monitor.',
                   'Public Contracts Scotland award notices publish no contract dates, so Scottish end dates are often estimates.',
                   'Sell2Wales and eTendersNI are not read, so lower-value Welsh and Northern Irish contracts can be missing.',
                   'Private-sector contracts are not covered.']


def _utc(value):
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def _state(db: Session) -> MarketSourceState:
    state = db.get(MarketSourceState, STATE)
    if state is None:
        db.add(MarketSourceState(source_key=STATE))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # another worker created the state
        state = db.get(MarketSourceState, STATE)
    return state


def refresh_if_due(db: Session, *, now: datetime | None = None, force: bool = False) -> dict | None:
    """Re-evaluate after new records, or once a day so dated windows keep moving."""
    now = now or datetime.now(UTC)
    state = _state(db)
    seen = json.loads(state.cursor) if state.cursor else {}
    latest = db.scalar(select(func.max(SourceRevision.id))) or 0
    if not force and seen.get('revision') == latest and seen.get('day') == now.date().isoformat():
        db.rollback()
        return None
    state.last_checked_at = now
    try:
        result = refresh_market_opportunities(db, now=now)
    except Exception as exc:
        db.rollback()
        state = _state(db)
        state.last_error, state.failure_count, state.last_checked_at = type(exc).__name__, (state.failure_count or 0) + 1, now
        db.commit()
        raise
    state.cursor = json.dumps({**seen, 'revision': latest, 'day': now.date().isoformat()})
    state.last_success_at, state.last_error, state.failure_count = now, None, 0
    if result['new'] or result['new_versions']:
        state.last_new_at = now
    db.commit()
    return result


def source_health(db: Session, *, now: datetime | None = None) -> list[dict]:
    """Fresh, stale or failing per source; a failing source is never shown as healthy."""
    now = now or datetime.now(UTC)
    rows = []
    for key, limit in [*SOURCES.items(), (STATE, ENGINE_MAX_AGE)]:
        state = db.get(MarketSourceState, key)
        success = _utc(state.last_success_at) if state else None
        failing = bool(state and (state.failure_count or 0) >= 3)
        status = 'never_run' if success is None and not failing else 'failing' if failing else 'stale' if now - success > limit else 'fresh'
        rows.append({'source_key': key, 'status': status, 'last_success_at': success, 'last_checked_at': _utc(state.last_checked_at) if state else None,
                     'failure_count': state.failure_count if state else 0, 'last_error': state.last_error if state else None, 'allowed_age_hours': limit.total_seconds() / 3600})
    return rows


def selective_weeks(db: Session, *, limit: int = 4) -> list[tuple[date, date]]:
    """Older Find a Tender weeks around large or long contracts known only from elsewhere."""
    state = db.get(MarketSourceState, HISTORY_STATE)
    if state is None or state.window_from is None:
        return []
    start = _utc(state.window_from).date()
    done = set(json.loads(state.cursor or '{}').get('weeks_outside_run', []))
    weeks = []
    contracts = db.scalars(select(MarketContract).where(MarketContract.category.is_not(None), MarketContract.fit.in_(('core', 'bundled')))).all()
    for contract in sorted(contracts, key=lambda x: x.end_date or ''):
        facts = contract.facts
        published = date.fromisoformat(facts['published']) if facts.get('published') else None
        value = facts['value'].get('published_total') or 0
        sources = db.scalars(select(MarketContractLink.source_key).where(MarketContractLink.contract_id == contract.id)).all()
        term = None
        if facts.get('start_date') and contract.end_date:
            term = (date.fromisoformat(contract.end_date) - date.fromisoformat(facts['start_date'])).days
        if not published or published >= start or 'find_a_tender' in sources or (value < SELECTIVE_MIN_VALUE and (term or 0) < SELECTIVE_MIN_DAYS):
            continue
        monday = published - timedelta(days=published.weekday())
        if monday.isoformat() not in done and monday not in [x[0] for x in weeks]:
            weeks.append((monday, monday + timedelta(days=6)))
        if len(weeks) == limit:
            break
    return weeks


def run_daily_cycle(db: Session, *, now: datetime | None = None, fetch=fetch_tenders, refresh: bool = True) -> dict:
    """One hourly pass: at most one selective history step a day, then re-evaluate if due.

    The worker passes refresh=False and re-evaluates under the shared inference lock.
    """
    now = now or datetime.now(UTC)
    state = _state(db)
    history_day = (json.loads(state.cursor).get('history_day') if state.cursor else None)
    history = None
    if history_day != now.date().isoformat():
        weeks = selective_weeks(db)
        if weeks:
            cache = load_tenders()
            history = fetch(cache, now.date(), weeks, SELECTIVE_REQUESTS_PER_DAY)
            import_checkpoints(db)
        state = _state(db)
        state.cursor = json.dumps({**(json.loads(state.cursor) if state.cursor else {}), 'history_day': now.date().isoformat()})
        db.commit()
    result = refresh_if_due(db, now=now) if refresh else None
    if result is not None:
        write_report(db, today=now.date())
    return {'incomplete': False, 'history': history, 'refresh': result, 'health': {x['source_key']: x['status'] for x in source_health(db, now=now)}}


def current_opportunities(db: Session) -> list[tuple[MarketOpportunity, dict]]:
    rows = db.execute(select(MarketOpportunity, MarketOpportunityRevision).join(MarketOpportunityRevision, MarketOpportunity.current_revision_id == MarketOpportunityRevision.id)
                      .where(MarketOpportunity.state == 'suggested')).all()
    items = [(item, version.result) for item, version in rows if version.result.get('category')]
    return sorted(items, key=lambda x: x[1].get('priority', {}).get('sort') or [9])


def _sum(rows: list[dict], field: str) -> float:
    return round(sum(x['value'].get(field) or 0 for x in rows), 2)


def radar_summary(db: Session, *, now: datetime | None = None) -> dict:
    """Totals an operator can reconcile against the stored records."""
    now = now or datetime.now(UTC)
    today = now.date()
    rows = [proposal for _, proposal in current_opportunities(db)]
    renewals = [x for x in rows if x['kind'] == 'possible_renewal_window']
    def within(months):
        limit = today + timedelta(days=round(months * 30.44))
        return sum(1 for x in renewals if today <= date.fromisoformat(x['timing']) <= limit)
    contracts = db.scalars(select(MarketContract)).all()
    frameworks = [x for x in contracts if x.fit == 'framework' and x.lifecycle_status == 'framework_agreement']
    sources = db.execute(select(SourceRevision.source_key, func.count(), func.min(SourceRevision.published_at), func.max(SourceRevision.published_at))
                         .where(SourceRevision.superseded_at.is_(None), SourceRevision.ocid.is_not(None)).group_by(SourceRevision.source_key)).all()
    history = db.get(MarketSourceState, HISTORY_STATE)
    return {'as_of': now, 'opportunities': len(rows), 'by_category': dict(Counter(x['category'] for x in rows)), 'by_tier': dict(Counter(x['priority']['tier'] for x in rows)),
            'by_nation': dict(Counter(x.get('nation') or 'Not stated' for x in rows)), 'renewals_within_months': {str(m): within(m) for m in (3, 6, 12, 18)},
            'relevant_contracts': len(contracts), 'contracts_by_status': dict(Counter(x.lifecycle_status for x in contracts)), 'contracts_by_currency': dict(Counter(x.facts.get('currency', 'uncertain') for x in contracts)),
            'value': {'published_total': _sum(renewals, 'published_total'), 'published_annual': _sum(renewals, 'published_annual'), 'estimated_annualised': _sum(renewals, 'estimated_annualised'),
                      'framework_ceilings_stored': round(sum(x.facts['value'].get('framework_ceiling') or 0 for x in frameworks), 2), 'unknown_value_renewals': sum(1 for x in renewals if x['value']['type'] == 'unknown'),
                      'estimated_annualised_core_only': _sum([x for x in renewals if x.get('fit') == 'core'], 'estimated_annualised')},
            'evidence': {'published_end': sum(1 for x in renewals if not x['end_estimated']), 'estimated_end': sum(1 for x in renewals if x['end_estimated']),
                         'cross_source_links': sum(1 for x in rows if len(x['link']['sources']) > 1), 'possible_links': sum(1 for x in rows if x['link']['confidence'] == 'possible')},
            'sources': [{'source_key': k, 'records': n, 'first_published': a, 'last_published': b} for k, n, a, b in sources],
            'find_a_tender_unbroken_from': history.window_from if history else None, 'health': source_health(db, now=now), 'limits': COVERAGE_LIMITS}


CSV_FIELDS = ('tier', 'category', 'nation', 'customer', 'title', 'supplier', 'fit', 'timing', 'timing_basis', 'end_estimated', 'latest_end', 'value_type', 'published_total', 'estimated_annualised',
              'framework_ceiling', 'next_action', 'link_confidence', 'sources', 'source_url')


def export_rows(db: Session) -> list[dict]:
    rows = []
    for _, x in current_opportunities(db):
        value = x['value']
        rows.append({'tier': x['priority']['tier'], 'category': x['category_label'], 'nation': x.get('nation'), 'customer': x['customer'], 'title': x['title'], 'supplier': x.get('supplier'), 'fit': x.get('fit'),
                     'timing': x.get('timing'), 'timing_basis': x.get('timing_basis'), 'end_estimated': x.get('end_estimated'), 'latest_end': x.get('latest_end'), 'value_type': value['type'],
                     'published_total': value['published_total'], 'estimated_annualised': value['estimated_annualised'], 'framework_ceiling': value['framework_ceiling'], 'next_action': x['next_action'],
                     'link_confidence': x['link']['confidence'], 'sources': ' + '.join(x['link']['sources']), 'source_url': x['evidence'][0]['source_url'] if x['evidence'] else ''})
    return rows


def export_csv(db: Session) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for row in export_rows(db):
        # A published title could begin with a spreadsheet formula character.
        writer.writerow({k: f"'{v}" if isinstance(v, str) and v[:1] in '=+-@' else v for k, v in row.items()})
    return buffer.getvalue()


def _money(value) -> str:
    return f'£{value:,.0f}' if value else 'not published'


def top_priorities(db: Session, *, limit: int = 20, live: int = 5, signals: int = 5) -> list[dict]:
    """Tier 1 across the workstreams, so near tenders do not crowd out renewal work."""
    rows = [x for _, x in current_opportunities(db) if x['priority']['tier'] == 1]
    def take(category, count=None):
        return [x for x in rows if x['category'] == category][:count]
    chosen = [*take('contract_defence'), *take('live_procurement', live), *take('official_early_signal', signals)]
    return (chosen + take('pre_tender'))[:limit]


def report_lines(db: Session, *, today: date, limit: int = 20) -> list[str]:
    """The operational report, rebuilt only from the database."""
    summary = radar_summary(db, now=datetime(today.year, today.month, today.day, 12, tzinfo=UTC))
    value, windows, health = summary['value'], summary['renewals_within_months'], summary['health']
    lines = [f'# UK renewal radar: {today}', '', 'Every line is a published record to check, not a confirmed requirement. A date marked ~ is an estimate.', '',
             f"{summary['opportunities']:,} opportunities from {summary['relevant_contracts']:,} relevant contracts and frameworks.", '', '## Sources', '', '| Source | Stored records | First | Last | Status |', '|---|---:|---|---|---|']
    status = {x['source_key']: x for x in health}
    for row in summary['sources']:
        state = status.get(row['source_key'], {})
        lines.append(f"| {row['source_key']} | {row['records']:,} | {str(row['first_published'])[:10]} | {str(row['last_published'])[:10]} | {state.get('status', 'not monitored')} |")
    lines += ['', f"Find a Tender unbroken history from: {str(summary['find_a_tender_unbroken_from'])[:10]}", '', '## Pipeline', '',
              *[f"- {k}: {v}" for k, v in sorted(summary['by_category'].items())], '', f"Renewals ending within 3, 6, 12 and 18 months: {windows['3']}, {windows['6']}, {windows['12']}, {windows['18']}.", '',
              '## Value, shown separately', '', f"- Published total on renewals: {_money(value['published_total'])}", f"- Published annual values: {_money(value['published_annual'])}",
              f"- Estimated annualised: {_money(value['estimated_annualised'])}, of which core fit {_money(value['estimated_annualised_core_only'])}", f"- Framework ceilings stored: {_money(value['framework_ceilings_stored'])} across overlapping lots and suppliers, so this overstates any real market and must not be added to the figures above",
              f"- Renewals with no published value: {value['unknown_value_renewals']}", '', 'None of these is guaranteed or fully addressable spend.', '', f'## Top {limit} priorities', '', 'Contract defence first, then the five nearest live tenders, the five soonest official signals and the pre-tender work to start soonest.', '']
    for number, x in enumerate(top_priorities(db, limit=limit), 1):
        amount = x['value'].get('estimated_annualised') or x['value'].get('published_total')
        lines += [f"{number}. **{x['customer']}**: {x['title']}", f"   - {x['category_label']}, tier {x['priority']['tier']}, {x.get('nation')}. Supplier: {x.get('supplier') or 'not named'}. Timing: {x.get('timing') or 'no date'}{'~' if x.get('end_estimated') else ''} ({x.get('timing_basis')}).",
                  f"   - Value: {_money(amount)}. {x['value']['basis']}", f"   - Next: {x['next_action']}", f"   - Evidence: {x['evidence'][0]['source_url'] if x['evidence'] else 'none'}"]
    return lines + ['', '## Known limits', '', *[f'- {x}' for x in summary['limits']]]


def ensure_report(db: Session, *, today: date) -> dict | None:
    """Write today's report once, so a missed day recovers on the next pass."""
    return None if (OUTPUT / f'radar-{today}.md').exists() else write_report(db, today=today)


def write_report(db: Session, *, today: date) -> dict:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f'radar-{today}.md').write_text('\n'.join(report_lines(db, today=today)))
    (OUTPUT / f'radar-{today}.csv').write_text(export_csv(db))
    return {'report': str(OUTPUT / f'radar-{today}.md')}


def stored_counts(db: Session) -> dict:
    return {'revisions': db.scalar(select(func.count()).select_from(SourceRevision)) or 0, 'awards': db.scalar(select(func.count()).select_from(MarketAward)) or 0,
            'contracts': db.scalar(select(func.count()).select_from(MarketContract)) or 0, 'links': db.scalar(select(func.count()).select_from(MarketContractLink)) or 0,
            'own_group_contracts': sum(1 for x in db.scalars(select(MarketContract.supplier)) if x and OWN_GROUP.search(x))}
