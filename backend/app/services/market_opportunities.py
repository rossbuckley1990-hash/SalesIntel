"""Deterministic, source-cited market suggestions; not predictions of buying intent.

A proposal is a lead to verify. No model, personal data, fabricated score or
contact is involved. The rule retains versions and can withdraw a previously
suggested candidate when the captured evidence no longer satisfies the rule.
"""
from __future__ import annotations
from datetime import UTC, datetime
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.renewal_intelligence import evaluate
from app.models.market_network import SourceRevision
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.services.market_contracts import sync_contracts

RULE_VERSION = 'market-suggestions-v2'


def _date(value):
    if not value:
        return None
    try:
        d = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)
    except (ValueError, TypeError):
        return None


def refresh_market_opportunities(db: Session, *, now: datetime | None = None, max_sources: int = 100000) -> dict:
    """Re-evaluate up to max_sources stored records into one deduplicated UK list.

    Every current record of a process is read together, across sources. We never
    pretend source coverage is exhaustive. If the scan is truncated, candidates
    omitted from the window are not withdrawn. Re-evaluation and caller commit are atomic.
    """
    if not 1 <= max_sources <= 100000:
        raise ValueError('max_sources must be between 1 and 100000')
    now = _date(now) or datetime.now(UTC)
    rows = db.scalars(select(SourceRevision).where(SourceRevision.superseded_at.is_(None), SourceRevision.ocid.is_not(None))
                      .order_by(SourceRevision.id.desc()).limit(max_sources + 1)).all()
    complete = len(rows) <= max_sources
    rows = rows[:max_sources]
    evaluation = evaluate(rows, now.date())
    candidates = sync_contracts(db, evaluation, now, complete)
    existing = {row.dedup_key: row for row in db.scalars(select(MarketOpportunity)).all()}
    # Older suggestions were keyed by contract id; carry them across rather than losing their review.
    for key, item in list(existing.items()):
        if key.startswith('renewal:') and key not in candidates:
            ocid = key.split(':')[1]
            matches = [x for x in candidates if x.startswith(f'renewal:{ocid}:') and x not in existing]
            if len(matches) == 1:
                item.dedup_key = matches[0]
                existing[matches[0]] = existing.pop(key)
    created = changed = withdrawn = 0
    for key, proposal in candidates.items():
        item = existing.get(key)
        if item is None:
            item = MarketOpportunity(dedup_key=key, state='suggested', review_state='unreviewed', first_seen=now, last_evaluated=now)
            db.add(item); db.flush(); created += 1
        item.state = 'suggested'
        item.withdrawal_reason = None
        item.last_evaluated = now
        fingerprint = hashlib.sha256(json.dumps(proposal, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        version = db.scalar(select(MarketOpportunityRevision).where(MarketOpportunityRevision.opportunity_id == item.id,
                                                                    MarketOpportunityRevision.fingerprint == fingerprint))
        if version is None:
            version = MarketOpportunityRevision(opportunity_id=item.id, fingerprint=fingerprint, result=proposal, created_at=now)
            db.add(version); db.flush(); changed += 1
        item.current_revision_id = version.id
    if complete:
        for key, item in existing.items():
            if key not in candidates and item.state != 'withdrawn':
                item.state = 'withdrawn'; item.last_evaluated = now
                item.withdrawal_reason = 'The captured current record no longer satisfies this suggestion rule; review the source history.'
                withdrawn += 1
    db.flush()
    categories = {}
    for proposal in candidates.values():
        categories[proposal['category']] = categories.get(proposal['category'], 0) + 1
    return {'scanned_sources': len(rows), 'complete_scan': complete, 'candidates': len(candidates), 'contracts': len(evaluation['contracts']),
            'by_category': categories, 'new': created, 'new_versions': changed, 'withdrawn': withdrawn, 'rule_version': RULE_VERSION}
