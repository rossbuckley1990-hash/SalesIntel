"""Carry public observations through to hypotheses and MiSi opportunities.

Automatic steps cost no model calls. Unchanged observations are recognised by
fingerprint, and a hypothesis gets a new revision only when its reasoning changes.
"""
from __future__ import annotations
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import REPO_ROOT, get_settings
from app.ingestion import market_public_signals as public
from app.ingestion.companies_house import CompaniesHouseError, fetch_company_profile, fetch_corporate_control_snapshot
from app.intelligence.renewal_radar import _buyer_key
from app.intelligence.signal_inference import (COMPETITOR_GROUPS, TAXONOMY, assessment_fingerprint, buyer_hypotheses, competitor_group, competitor_hypotheses, contract_hypotheses, council_key, fire_service_rises, observation, plausible_competitors, procurement_observations, sequence_observations)
from app.models.lfb_incident import LfbIncident
from app.models.lfb_inspection_match import LfbInspectionMatch
from app.models.market_contract import MarketContract, MarketContractLink
from app.models.market_inference import MarketHypothesis, MarketHypothesisRevision, MarketObservation
from app.models.market_network import MarketSourceState
from app.models.public_site_reference import PublicSiteReference

STATE = 'market_inference'
CURATED = REPO_ROOT / 'backend' / 'reference_data' / 'public_signal_observations.json'
FIRE_DATA_URL = 'https://data.london.gov.uk/dataset/london-fire-brigade-incident-records'
JUDGEMENT_LIMIT_PER_DAY = 80
GAZETTE_FIRST_DAYS = 730
COMPANY_STATE = 'companies_house_signals'
COMPANY_CHECKS_PER_DAY = 100
COMPANY_RECHECK_DAYS = 30
COMPANY_PAUSE = 1
CONTROL_CHANGE_DAYS = 730
INSOLVENT_STATUSES = {'liquidation', 'administration', 'receivership', 'insolvency-proceedings', 'voluntary-arrangement'}
ENFORCEMENT = {'Premises Non Compliant', 'Issue Enforcement Notice', 'Enforcement Notice Extended', 'Notice of Deficiences Issued'}
VISIBLE = {'pursue', 'verify'}


def _site_map(db: Session) -> dict:
    return {x.uprn: x for x in db.scalars(select(PublicSiteReference))}


def fire_service_observations(db: Session, *, as_of: date) -> list[dict]:
    """Alarm attendance rises and inspection outcomes at sites published for a named organisation."""
    sites = _site_map(db)
    incidents = [(uprn, day) for uprn, day in db.execute(select(LfbIncident.uprn, LfbIncident.incident_date).where(LfbIncident.stop_code_description == 'AFA')) if uprn in sites]
    found = []
    for rise in fire_service_rises(incidents, as_of=as_of):
        site = sites[rise['uprn']]
        statement = f"London Fire Brigade attended {rise['recent']} automatic alarm calls at {site.site_name} in six months, against about {rise['expected']} expected from its earlier rate. The cause is not published."
        found.append(observation('false_alarm_rise', statement=statement, occurred=rise['as_of'], available=rise['as_of'] + timedelta(days=45), url=FIRE_DATA_URL, group='fire_service', reliability='statutory_record', buyer=site.organisation_name, fams=['fire_alarm'], scope='site', detail={**rise, 'as_of': rise['as_of'].isoformat(), 'site': site.site_name}))
    for match in db.scalars(select(LfbInspectionMatch).where(LfbInspectionMatch.reason_or_outcome.in_(ENFORCEMENT))):
        found.append(observation('fire_enforcement_outcome', statement=f"London Fire Brigade recorded \"{match.reason_or_outcome}\" at {match.site_name} on {match.completed_on}. Responsibility is not published.", occurred=match.completed_on, available=match.completed_on + timedelta(days=60), url=FIRE_DATA_URL, group='fire_service', reliability='statutory_record', buyer=match.organisation_name, scope='site', detail={'site': match.site_name}))
    return found


def curated_observations(path: Path = CURATED) -> list[dict]:
    """Public facts a person read at source, kept apart from automatic capture."""
    if not path.exists():
        return []
    found = []
    for row in json.loads(path.read_text()):
        found.append(observation(row['signal_type'], statement=row['statement'], occurred=date.fromisoformat(row['occurred_on']), available=date.fromisoformat(row.get('available_on') or row['occurred_on']), url=row['source_url'], group=row['source_group'], reliability=row['reliability'],
                                 buyer=row.get('buyer'), supplier=row.get('supplier'), fams=row.get('families', []), scope=row.get('scope', 'organisation'), attribution=row.get('attribution', 'none'), capture='analyst_assisted'))
    return found


def store_observations(db: Session, items: list[dict], now: datetime) -> dict:
    """Keep each observation once. Re-reading the same fact only updates when it was last seen."""
    known = {x.fingerprint: x for x in db.scalars(select(MarketObservation))}
    new = 0
    for item in items:
        if item['signal_type'] not in TAXONOMY:
            raise ValueError(f"Unknown signal type {item['signal_type']}")
        row = known.get(item['fingerprint'])
        if row:
            row.last_seen, row.statement, row.retracted_on = now, item['statement'], None
            if row.detail != item['detail']:
                row.detail = item['detail']
            continue
        row = MarketObservation(**item, first_seen=now, last_seen=now)
        db.add(row)
        known[item['fingerprint']] = row
        new += 1
    db.flush()
    return {'observed': len(items), 'new': new}


def stored_observations(db: Session) -> list[dict]:
    rows = db.scalars(select(MarketObservation)).all()
    return [{k: getattr(x, k) for k in ('fingerprint', 'signal_type', 'scope', 'buyer', 'buyer_key', 'supplier', 'supplier_key', 'company_number', 'families', 'statement', 'occurred_on', 'available_on', 'source_group', 'reliability', 'attribution', 'capture', 'source_url', 'source_revision_id', 'detail', 'retracted_on')} for x in rows]


def _store_hypothesis(db: Session, key: str, assessment: dict, contract_id: int | None, known: dict, now: datetime) -> tuple[MarketHypothesis, bool]:
    item = known.get(key)
    if item is None:
        item = MarketHypothesis(dedup_key=key, kind=assessment['kind'], contract_id=contract_id, buyer=assessment['buyer'], supplier=assessment['supplier'], decision=assessment['decision'], evidence_state=assessment['evidence_state'], first_seen=now, last_evaluated=now)
        db.add(item)
        db.flush()
        known[key] = item
    print_hash = assessment_fingerprint(assessment)
    revision = db.scalar(select(MarketHypothesisRevision).where(MarketHypothesisRevision.hypothesis_id == item.id, MarketHypothesisRevision.fingerprint == print_hash))
    changed = revision is None
    if changed:
        revision = MarketHypothesisRevision(hypothesis_id=item.id, fingerprint=print_hash, assessment=assessment, created_at=now)
        db.add(revision)
        db.flush()
    item.decision, item.evidence_state, item.current_revision_id, item.contract_id, item.last_evaluated = assessment['decision'], assessment['evidence_state'], revision.id, contract_id, now
    item.state = 'withdrawn' if assessment['decision'] == 'dismiss' else 'active'
    return item, changed


def _opportunity(hypothesis: MarketHypothesis, assessment: dict, *, rivals: list[str]) -> dict:
    tier = 1 if assessment['decision'] == 'pursue' else 2
    evidence = [{'source_revision_id': hypothesis.id * 1000 + n, 'source_url': x['source_url'], 'source_key': x['source_group'], 'record_key': x['signal_type'], 'source': x['label'], 'published_at': x['occurred_on'], 'ocid': None, 'fields': []} for n, x in enumerate(assessment['supporting'])]
    value = {'published_total': None, 'published_annual': None, 'estimated_annualised': None, 'framework_ceiling': None, 'type': 'unknown', 'basis': 'No contract value applies to this signal yet.', 'scope_note': ''}
    return {'kind': 'inferred_signal', 'rule_version': assessment['rule_version'], 'category': 'inferred_signal', 'category_label': assessment['label'], 'customer': assessment['buyer'] or assessment['supplier'], 'title': assessment['supporting'][0]['statement'][:160] if assessment['supporting'] else assessment['label'],
            'supplier': None, 'timing': None, 'timing_basis': 'none', 'end_estimated': False, 'latest_end': None, 'nation': 'Not stated', 'fit': 'inferred', 'fit_reason': assessment['label'], 'value': value,
            'priority': {'tier': tier, 'sort': [tier, 1, '9999-12', 1, 3, assessment['last_signal']], 'reasons': assessment['decision_reasons']}, 'observation': assessment['label'], 'commercial_relevance': assessment['link'], 'inference': assessment['caution'], 'counter_evidence': [x['statement'] for x in assessment['contradicting']], 'unknowns': assessment['unknowns'],
            'next_action': assessment['actions'][0], 'next_actions': assessment['actions'], 'extension': '', 'replacement': None, 'link': {'confidence': 'possible', 'records': len(assessment['supporting']), 'sources': assessment['independent_sources']},
            'brief': {'customer': assessment['buyer'] or '', 'service_requirement': assessment['label'], 'incumbent': assessment['supplier'] or 'Not known', 'commercial_value': value['basis'], 'contract_lifecycle': 'No contract linked', 'procurement_route': 'Not published', 'timing': 'No date published', 'why_it_matters': assessment['link'], 'missing_information': assessment['unknowns'], 'next_action': assessment['actions'][0]},
            'evidence': evidence, 'signal': _summary(hypothesis, assessment), 'plausible_competitors': rivals}


def _summary(hypothesis: MarketHypothesis, assessment: dict) -> dict:
    return {'hypothesis_id': hypothesis.id, 'label': assessment['label'], 'decision': assessment['decision'], 'decision_reasons': assessment['decision_reasons'], 'evidence_state': assessment['evidence_state'], 'independent_sources': assessment['independent_sources'], 'link': assessment['link'],
            'supporting': assessment['supporting'], 'contradicting': assessment['contradicting'], 'explanations': assessment['explanations'], 'unknowns': assessment['unknowns'], 'actions': assessment['actions'], 'caution': assessment['caution']}


def apply_inference(db: Session, evaluation: dict, candidates: dict, rows: list, now: datetime, *, complete: bool = True) -> dict:
    """Refresh observations, re-decide every hypothesis, and attach results to one opportunity each."""
    today = now.date()
    views = [x['view'] for x in evaluation['contracts']]
    derived = procurement_observations(rows) + sequence_observations(views, evaluation['notices'])
    stats = store_observations(db, derived + fire_service_observations(db, as_of=today), now)
    if complete:
        # A derived observation the current rules no longer produce is retracted, not erased.
        current = {x['fingerprint'] for x in derived}
        for row in db.scalars(select(MarketObservation).where(MarketObservation.source_group == 'procurement', MarketObservation.retracted_on.is_(None))):
            if row.fingerprint not in current:
                row.retracted_on = today
    observations = stored_observations(db)
    produced = {**contract_hypotheses(views, observations, today), **buyer_hypotheses(views, observations, evaluation['notices'], today), **competitor_hypotheses(views, observations, today)}
    known = {x.dedup_key: x for x in db.scalars(select(MarketHypothesis))}
    links = {x.member_key: x.contract_id for x in db.scalars(select(MarketContractLink))}
    canonical = {x.id: x.canonical_key for x in db.scalars(select(MarketContract))}
    counts = {}
    for key, (assessment, member) in produced.items():
        contract_id = links.get(member) if member else None
        item, _ = _store_hypothesis(db, key, assessment, contract_id, known, now)
        counts[assessment['decision']] = counts.get(assessment['decision'], 0) + 1
        if assessment['decision'] not in VISIBLE:
            continue
        target = candidates.get(f'renewal:{canonical[contract_id]}') if contract_id in canonical else None
        if target is not None:
            target.setdefault('signals', []).append(_summary(item, assessment))
            target['plausible_competitors'] = plausible_competitors(target['title'], target['customer'], views)
        elif assessment['kind'] == 'hidden_requirement':
            # One customer stays one lead: add to its renewals before opening anything new.
            held = [x for x in candidates.values() if x.get('kind') == 'possible_renewal_window' and council_key(x['customer']) == council_key(assessment['buyer'])]
            for proposal in held:
                proposal.setdefault('signals', []).append(_summary(item, assessment))
            if not held:
                candidates[f'signal:{key}'] = _opportunity(item, assessment, rivals=[])
    if complete:
        # A condition no longer supported stays on record but stops being acted on.
        for key, item in known.items():
            if key not in produced and item.state == 'active':
                item.state, item.decision = 'withdrawn', 'dismiss'
                item.last_evaluated = now
    db.flush()
    return {**stats, 'hypotheses': len(produced), 'by_decision': counts}


def collect_public_signals(db: Session, *, now: datetime | None = None, http=None, sleep=None, curated: Path = CURATED) -> dict:
    """One day's bounded reading of the open sources. A failure is recorded and raised."""
    now = now or datetime.now(UTC)
    state = db.get(MarketSourceState, STATE)
    if state is None:
        db.add(MarketSourceState(source_key=STATE))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # another worker created the state
        state = db.get(MarketSourceState, STATE)
    progress = json.loads(state.cursor) if state.cursor else {}
    if progress.get('day') == now.date().isoformat():
        return {'skipped': 'already collected today'}
    owned = http is None
    http = http or public.client()
    pause = {'sleep': sleep} if sleep else {}
    try:
        buyers = {council_key(x) for x in db.scalars(select(MarketContract.buyer))}
        suppliers = {_buyer_key(x.strip()) for row in db.scalars(select(MarketContract.supplier).where(MarketContract.supplier.is_not(None))) for x in row.split(',')}
        read = set(progress.get('judgements', []))
        found, reached = [], 0
        for page in public.judgement_links(http):
            if reached == JUDGEMENT_LIMIT_PER_DAY:
                break
            stamp = f"{page['link']}|{str(page.get('public_timestamp'))[:10]}"
            if stamp in read or council_key(page['title']) not in buyers:
                continue
            reached += 1
            read.add(stamp)
            judgement = public.read_judgement(http, page['link'], **pause)
            if judgement and judgement['fire_sentences'] and judgement['grades'] and max(judgement['grades']) >= 3:
                day = date.fromisoformat(str(page['public_timestamp'])[:10])
                found.append(observation('regulator_compliance_finding', statement=f"The Regulator of Social Housing graded {page['title']} C{max(judgement['grades'])}. It says: {judgement['fire_sentences'][0]}", occurred=day, url=judgement['url'], group='regulator', reliability='statutory_record', buyer=page['title'], fams=['fire_risk_assessment'], attribution='customer', detail={'grades': judgement['grades'], 'sentences': judgement['fire_sentences']}))
            elif judgement and judgement['grades'] and max(judgement['grades']) <= 2:
                day = date.fromisoformat(str(page['public_timestamp'])[:10])
                found.append(observation('issue_resolved', statement=f"The Regulator of Social Housing's latest judgement grades {page['title']} C{max(judgement['grades'])}.", occurred=day, url=judgement['url'], group='regulator', reliability='statutory_record', buyer=page['title'], detail={'answers': ['regulator_compliance_finding']}))
        first, last = public.gazette_window(now.date(), days=max(3, (now.date() - date.fromisoformat(progress['gazette_to'])).days + 1) if progress.get('gazette_to') else GAZETTE_FIRST_DAYS)
        for term in ('fire', 'security'):
            for notice in public.gazette_notices(http, first, last, text=term, **pause):
                if _buyer_key(notice['title']) in suppliers and notice['url']:
                    found.append(observation('supplier_insolvency', statement=f"The Gazette published an insolvency notice for {notice['title']}. Confirm the company number before relying on this match.", occurred=date.fromisoformat(notice['published']), url=notice['url'], group='gazette', reliability='statutory_record', supplier=notice['title'], company_number=notice['company_number'], scope='organisation', detail={'summary': notice['summary']}))
        stored = store_observations(db, found + curated_observations(curated), now)
        state.cursor = json.dumps({'day': now.date().isoformat(), 'judgements': sorted(read), 'gazette_to': last.isoformat()})
        state.last_success_at, state.last_checked_at, state.last_error, state.failure_count = now, now, None, 0
        db.commit()
        return {**stored, 'judgements_read': reached}
    except Exception as exc:
        db.rollback()
        state = db.get(MarketSourceState, STATE)
        state.last_error, state.last_checked_at, state.failure_count = type(exc).__name__, now, (state.failure_count or 0) + 1
        db.commit()
        raise
    finally:
        if owned:
            http.close()


def _watched_companies(db: Session) -> list[str]:
    """Published company numbers on live contracts first, then every watched competitor."""
    live, watched = [], []
    for row in db.scalars(select(MarketContract)):
        numbers = row.facts.get('company_numbers') or []
        if row.category:
            live += numbers
        elif any(competitor_group(x) in COMPETITOR_GROUPS for x in row.facts.get('suppliers') or []):
            watched += numbers
    return list(dict.fromkeys(live + watched))


def company_observations(profile: dict, control: dict, today: date) -> list[dict]:
    """What the register shows for one company. Personal data is never read."""
    number, name = profile['company_number'], profile['company_name']
    url = f'https://find-and-update.company-information.service.gov.uk/company/{number}'
    shared = {'url': url, 'group': 'companies_house', 'reliability': 'statutory_record', 'supplier': name, 'company_number': number}
    found = []
    status = str(profile.get('company_status') or '')
    if status in INSOLVENT_STATUSES:
        found.append(observation('supplier_insolvency', statement=f"Companies House lists {name} as {status.replace('-', ' ')}.", occurred=today, **shared, detail={'status': status}))
    if profile.get('accounts_overdue'):
        found.append(observation('supplier_filing_overdue', statement=f'Companies House shows accounts overdue for {name}.', occurred=today.replace(day=1), **shared))
    for controller in control.get('controllers', []):
        notified = date.fromisoformat(controller['notified_on']) if controller.get('notified_on') else None
        if notified and not controller.get('ceased_on') and (today - notified).days <= CONTROL_CHANGE_DAYS:
            found.append(observation('control_change', statement=f"Companies House records {controller['company_name']} as a controlling company of {name} from {notified}. This is a reported filing.", occurred=notified, **{**shared, 'url': control.get('source_url') or url}, detail={'controller_number': controller['company_number']}))
    return found


def collect_company_signals(db: Session, *, now: datetime | None = None, client=None, sleep=time.sleep, limit: int = COMPANY_CHECKS_PER_DAY) -> dict:
    """Check a bounded number of companies, oldest check first. Nothing runs without a key."""
    now = now or datetime.now(UTC)
    get_settings.cache_clear()
    key = get_settings().companies_house_api_key
    if not key:
        return {'skipped': 'no key configured'}
    state = db.get(MarketSourceState, COMPANY_STATE)
    if state is None:
        db.add(MarketSourceState(source_key=COMPANY_STATE))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        state = db.get(MarketSourceState, COMPANY_STATE)
    checked = json.loads(state.cursor) if state.cursor else {}
    due = [x for x in _watched_companies(db) if (now.date() - date.fromisoformat(checked.get(x, '2000-01-01'))).days >= COMPANY_RECHECK_DAYS]
    found, done = [], 0
    try:
        for number in sorted(due, key=lambda x: checked.get(x, ''))[:limit]:
            profile = fetch_company_profile(number, api_key=key, client=client)['raw']
            control = fetch_corporate_control_snapshot(number, api_key=key, client=client)
            found += company_observations(profile, control, now.date())
            checked[number] = now.date().isoformat()
            done += 1
            sleep(COMPANY_PAUSE)
    except CompaniesHouseError as exc:
        # Keep what was read. A refused key or rate limit stops the run rather than retrying.
        state.last_error, state.last_checked_at, state.failure_count = str(exc)[:120], now, (state.failure_count or 0) + 1
        store_observations(db, found, now)
        state.cursor = json.dumps(checked)
        db.commit()
        raise
    stored = store_observations(db, found, now)
    state.cursor = json.dumps(checked)
    state.last_success_at, state.last_checked_at, state.last_error, state.failure_count = now, now, None, 0
    db.commit()
    return {**stored, 'companies_checked': done, 'still_due': max(0, len(due) - done)}


def collect_all(db: Session, *, now: datetime | None = None) -> dict:
    """Each source fails alone, so one refusal never stops the others."""
    results = {}
    for name, collect in (('public', collect_public_signals), ('companies_house', collect_company_signals)):
        try:
            results[name] = collect(db, now=now)
        except Exception as exc:
            results[name] = {'error': type(exc).__name__}
    return results


def signal_summary(db: Session) -> dict:
    rows = db.scalars(select(MarketHypothesis)).all()
    observations = db.scalars(select(MarketObservation)).all()
    company = db.get(MarketSourceState, COMPANY_STATE)
    def tally(values):
        found = {}
        for value in values:
            found[value] = found.get(value, 0) + 1
        return found
    return {'observations': len(observations), 'observations_by_source': tally(x.source_group for x in observations), 'observations_by_type': tally(x.signal_type for x in observations), 'automatic_observations': sum(1 for x in observations if x.capture == 'automatic'),
            'hypotheses': len(rows), 'active': sum(1 for x in rows if x.state == 'active'), 'withdrawn': sum(1 for x in rows if x.state == 'withdrawn'), 'by_decision': tally(x.decision for x in rows if x.state == 'active'),
            'by_kind': tally(x.kind for x in rows if x.state == 'active'), 'independently_corroborated': sum(1 for x in rows if x.state == 'active' and x.evidence_state == 'independently_corroborated'),
            'companies_checked': len(json.loads(company.cursor)) if company and company.cursor else 0}
