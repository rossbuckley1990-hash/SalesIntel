"""Shadow Radar service: keep hypotheses current from shared observations, and serve them to workspaces.

Hypotheses are shared public intelligence (computed only from published observations). What a
workspace does with one (investigate, dismiss, qualify) is private to that workspace.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence import shadow_radar as radar
from app.models.market_inference import MarketObservation
from app.models.shadow import ShadowHypothesis, ShadowHypothesisRevision
from app.tenancy import SYSTEM

FIELDS = ('id', 'fingerprint', 'signal_type', 'buyer', 'buyer_key', 'supplier', 'company_number', 'statement', 'occurred_on', 'available_on', 'source_group',
          'reliability', 'source_url', 'detail', 'first_seen', 'retrieved_at', 'origin_key', 'retracted_on')


def observations(db: Session) -> list[dict]:
    return [{k: getattr(o, k) for k in FIELDS} for o in db.scalars(select(MarketObservation))]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def refresh(db: Session, *, now: datetime | None = None, as_of: date | None = None) -> dict:
    """Re-evaluate every sensor. A changed assessment adds a revision; nothing is overwritten or deleted."""
    now = now or datetime.now(UTC)
    as_of = as_of or now.date()
    if not db.info.get(SYSTEM):
        raise RuntimeError('Shadow Radar refresh reads shared evidence and must run in a system session.')
    assessments = radar.evaluate(observations(db), as_of)
    rows = {h.key: h for h in db.scalars(select(ShadowHypothesis))}
    produced, created, revised = set(), 0, 0
    for a in assessments:
        produced.add(a['key'])
        row = rows.get(a['key'])
        seen = datetime.fromisoformat(a['first_seen']) if a['first_seen'] else now
        if row is None:
            row = ShadowHypothesis(key=a['key'], sensor=a['sensor'], entity_name=a['entity_name'][:255], entity_key=a['entity_key'][:200], company_number=a['company_number'],
                                   state=a['state'], first_published_on=date.fromisoformat(a['first_published_on']), first_seen_at=_aware(seen), formed_at=now,
                                   rule_version=radar.RULE_VERSION, active=True, last_evaluated=now)
            db.add(row)
            db.flush()
            created += 1
        fingerprint = radar.assessment_fingerprint(a)
        current = db.get(ShadowHypothesisRevision, row.current_revision_id) if row.current_revision_id else None
        if current is None or current.fingerprint != fingerprint:
            revision = ShadowHypothesisRevision(hypothesis_id=row.id, fingerprint=fingerprint, as_of=as_of, assessment=a, created_at=now)
            db.add(revision)
            db.flush()
            row.current_revision_id = revision.id
            revised += 1
        row.state, row.active, row.last_evaluated, row.rule_version = a['state'], True, now, radar.RULE_VERSION
        row.window_start, row.window_end = date.fromisoformat(a['window'][0]), date.fromisoformat(a['window'][1])
    retired = 0
    for key, row in rows.items():
        if key not in produced and row.active:  # the evidence no longer supports it: keep the record, mark it retired
            row.active, row.last_evaluated = False, now
            retired += 1
    db.flush()
    return {'hypotheses': len(produced), 'created': created, 'revised': revised, 'retired': retired, 'as_of': str(as_of)}


def current(db: Session, hypothesis_id: int) -> tuple[ShadowHypothesis, dict] | None:
    row = db.get(ShadowHypothesis, hypothesis_id)
    if row is None or row.current_revision_id is None:
        return None
    return row, db.get(ShadowHypothesisRevision, row.current_revision_id).assessment


def active(db: Session) -> list[tuple[ShadowHypothesis, dict]]:
    rows = db.scalars(select(ShadowHypothesis).where(ShadowHypothesis.active.is_(True), ShadowHypothesis.state.in_(['indicated', 'corroborated', 'surfaced', 'challenged']))).all()
    revisions = {r.id: r for r in db.scalars(select(ShadowHypothesisRevision).where(ShadowHypothesisRevision.id.in_([x.current_revision_id for x in rows if x.current_revision_id])))}
    return [(row, revisions[row.current_revision_id].assessment) for row in rows if row.current_revision_id in revisions]


def history(db: Session, hypothesis_id: int) -> list[dict[str, Any]]:
    return [{'as_of': str(r.as_of), 'state': r.assessment.get('state'), 'recorded': r.created_at.isoformat()}
            for r in db.scalars(select(ShadowHypothesisRevision).where(ShadowHypothesisRevision.hypothesis_id == hypothesis_id).order_by(ShadowHypothesisRevision.id))]
