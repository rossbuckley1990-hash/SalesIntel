"""Read-only market evidence, intentionally distinct from confirmed incumbency."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
import re
from app.db import get_db
from app.models.market_network import MarketAward, MarketEntity, MarketEntityEvidence, MarketSourceState, SourceRevision
from app.intelligence.contract_lifecycle import contract_lifecycle
from app.ingestion.market_find_tender import classify_release

router = APIRouter(prefix='/api/market-network', tags=['market network'])

LIMITATIONS = [
    'Coverage is limited to collected sources and windows; there is no complete UK market denominator.',
    'A published supplier identity or award is not proof of current delivery, a framework call-off, revenue, or intent to bid.',
    'Only matching published Companies House numbers are linked across notices; other identities remain unresolved.',
    'Notice relevance is a discovery filter, not independent proof of service capability or a buying opportunity.',
]


SOURCE_METADATA = {
    'find_a_tender': {
        'documentation': 'https://www.find-tender.service.gov.uk/Developer/Documentation',
        'method': 'Bounded incremental OCDS API polling',
        'reuse': 'Published notice data: Open Government Licence v3; check the original document for any additional rights.'
    },
    'companies_house': {
        'documentation': 'https://developer.company-information.service.gov.uk/',
        'method': 'Individual public company profiles via authenticated API',
        'reuse': 'Check Companies House terms and the originating record before reuse.'
    },
    'contracts_finder': {
        'documentation': 'https://www.contractsfinder.service.gov.uk/apidocumentation',
        'method': 'Bounded incremental OCDS API polling and checkpointed historical sampling',
        'reuse': 'Open Government Licence v3 for published data; verify rights in underlying documents.'
    },
    'public_contracts_scotland': {
        'documentation': 'https://api.publiccontractsscotland.gov.uk/v1',
        'method': 'Monthly OCDS award packages, periodically refreshed',
        'reuse': 'The retrieved OCDS package identifies Open Government Licence v3; verify rights in underlying documents.'
    },
}


def _state(row):
    return {**{key: getattr(row, key) for key in ('source_key', 'last_checked_at', 'last_success_at',
            'last_new_at', 'last_error', 'failure_count', 'watermark', 'window_from', 'window_to')},
            **SOURCE_METADATA.get(row.source_key, {})}


def _is_checkpoint_lane(key: str) -> bool:
    return (key in {'market_backfill_budget', 'renewal_radar', 'find_a_tender_history'} or
            bool(re.fullmatch(r'contracts_finder_backfill_20\d{2}', key)) or
            bool(re.fullmatch(r'pcs_20\d{2}_\d{2}_\d+', key)) or
            bool(re.fullmatch(r'find_a_tender_backfill_20\d{2}', key)))


@router.get('/summary')
def summary(db: Session = Depends(get_db)):
    from datetime import UTC
    sources = db.scalars(select(MarketSourceState).order_by(MarketSourceState.source_key)).all()
    source_rows = [row for row in sources if not _is_checkpoint_lane(row.source_key)]
    lanes = [row for row in sources if _is_checkpoint_lane(row.source_key)]
    def source_status(row):
        status = _state(row)
        latest = db.scalar(select(SourceRevision).where(SourceRevision.source_key == row.source_key)
                           .order_by(SourceRevision.retrieved_at.desc(), SourceRevision.id.desc()).limit(1))
        if latest and latest.published_at:
            published = latest.published_at.replace(tzinfo=UTC) if latest.published_at.tzinfo is None else latest.published_at.astimezone(UTC)
            retrieved = latest.retrieved_at.replace(tzinfo=UTC) if latest.retrieved_at.tzinfo is None else latest.retrieved_at.astimezone(UTC)
            lag = (retrieved - published).total_seconds()
            status['latest_record_latency_seconds'] = int(lag) if lag >= 0 else None
        else:
            status['latest_record_latency_seconds'] = None
        return status
    count = lambda model: db.scalar(select(func.count()).select_from(model)) or 0
    return {'companies': count(MarketEntity), 'verified_companies': db.scalar(select(func.count()).select_from(MarketEntity)
            .where(MarketEntity.identity_status == 'registry_profile')) or 0,
            'unresolved_companies': db.scalar(select(func.count()).select_from(MarketEntity)
            .where(MarketEntity.identity_status == 'source_party_unresolved')) or 0,
            'awards': db.scalar(select(func.count()).select_from(MarketAward).join(SourceRevision)
                                .where(SourceRevision.superseded_at.is_(None))) or 0,
            'source_records': db.scalar(select(func.count()).select_from(SourceRevision)
                                       .where(SourceRevision.superseded_at.is_(None))) or 0,
            'source_revisions': count(SourceRevision), 'sources': [source_status(row) for row in source_rows],
            'checkpoint_lanes': [_state(row) for row in lanes],
            'limitations': LIMITATIONS}


@router.get('/companies')
def companies(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
              q: str = Query('', max_length=100), db: Session = Depends(get_db)):
    query = select(MarketEntity)
    count_query = select(func.count()).select_from(MarketEntity)
    if q.strip():
        condition = MarketEntity.name.ilike(f'%{q.strip()}%')
        query = query.where(condition)
        count_query = count_query.where(condition)
    items = db.scalars(query.order_by(MarketEntity.name, MarketEntity.id).limit(limit).offset(offset)).all()
    rows = []
    for entity in items:
        award_count = db.scalar(select(func.count()).select_from(MarketAward).join(SourceRevision)
                         .where(MarketAward.supplier_id == entity.id, SourceRevision.superseded_at.is_(None))) or 0
        rows.append({'id': entity.id, 'name': entity.name, 'identifier_scheme': entity.identifier_scheme,
                     'identifier_value': entity.identifier_value, 'first_seen': entity.first_seen,
                     'last_seen': entity.last_seen, 'identity_status': entity.identity_status, 'award_count': award_count})
    return {'items': rows, 'total': db.scalar(count_query) or 0}


@router.get('/awards')
def awards(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
           supplier_id: int | None = Query(None, ge=1), q: str = Query('', max_length=100), db: Session = Depends(get_db)):
    query = select(MarketAward, SourceRevision).join(SourceRevision).where(SourceRevision.superseded_at.is_(None))
    count_query = select(func.count()).select_from(MarketAward).join(SourceRevision).where(SourceRevision.superseded_at.is_(None))
    if supplier_id is not None:
        query = query.where(MarketAward.supplier_id == supplier_id)
        count_query = count_query.where(MarketAward.supplier_id == supplier_id)
    if q.strip():
        condition = or_(MarketAward.title.ilike(f'%{q.strip()}%'), MarketAward.supplier.ilike(f'%{q.strip()}%'), MarketAward.buyer.ilike(f'%{q.strip()}%'))
        query = query.where(condition)
        count_query = count_query.where(condition)
    rows = db.execute(query.order_by(SourceRevision.published_at.desc(), MarketAward.id.desc()).limit(limit).offset(offset)).all()
    return {'items': [{'id': award.id, 'ocid': source.ocid, 'award_id': award.award_id,
            'title': award.title, 'buyer': award.buyer, 'supplier': award.supplier,
            'supplier_id': award.supplier_id, 'status': award.status, 'award_date': award.award_date,
            'amount': award.amount, 'currency': award.currency, 'classification': award.classification,
            'lifecycle': contract_lifecycle(source.raw, award.award_id),
            'relevance': classify_release(source.raw),
            'source_url': source.source_url, 'source_revision_id': source.id} for award, source in rows],
            'total': db.scalar(count_query) or 0}


@router.get('/sources/{revision_id}')
def source_detail(revision_id: int, db: Session = Depends(get_db)):
    source = db.get(SourceRevision, revision_id)
    if source is None:
        raise HTTPException(status_code=404, detail='Source revision not found')
    return {'id': source.id, 'source_key': source.source_key, 'record_key': source.record_key,
            'ocid': source.ocid, 'source_url': source.source_url, 'content_hash': source.content_hash,
            'published_at': source.published_at, 'retrieved_at': source.retrieved_at,
            'last_seen': source.last_seen, 'superseded_at': source.superseded_at, 'raw': source.raw}


@router.get('/companies/{entity_id}/sources')
def company_sources(entity_id: int, db: Session = Depends(get_db)):
    if not db.get(MarketEntity, entity_id):
        raise HTTPException(status_code=404, detail='Company not found')
    ids = db.scalars(select(MarketEntityEvidence.source_revision_id).where(MarketEntityEvidence.entity_id == entity_id)).all()
    award_ids = db.scalars(select(MarketAward.source_revision_id).where(MarketAward.supplier_id == entity_id)).all()
    return {'source_revision_ids': sorted(set(ids) | set(award_ids))}


@router.get('/relationships')
def relationships(entity_id: int | None = Query(None, ge=1), as_of: str | None = None,
                  limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    """Source assertions observed now, optionally filtered by stated effective dates."""
    from datetime import UTC, datetime
    from sqlalchemy import or_
    from sqlalchemy.orm import aliased
    from app.models.market_graph import MarketRelationship
    subject, obj = aliased(MarketEntity), aliased(MarketEntity)
    query = (select(MarketRelationship, subject, obj, SourceRevision)
             .join(subject, MarketRelationship.subject_entity_id==subject.id)
             .join(obj, MarketRelationship.object_entity_id==obj.id)
             .join(SourceRevision, MarketRelationship.source_revision_id==SourceRevision.id)
             .where(SourceRevision.superseded_at.is_(None)))
    if entity_id is not None:
        query = query.where(or_(MarketRelationship.subject_entity_id==entity_id,MarketRelationship.object_entity_id==entity_id))
    if as_of:
        try:
            date = datetime.fromisoformat(as_of.replace('Z','+00:00'))
            date = date.replace(tzinfo=UTC) if date.tzinfo is None else date.astimezone(UTC)
        except ValueError:
            raise HTTPException(status_code=422,detail='as_of must be an ISO date')
        query=query.where(MarketRelationship.effective_from.is_not(None),MarketRelationship.effective_from<=date,
                          or_(MarketRelationship.effective_to.is_(None),MarketRelationship.effective_to>date))
    rows=db.execute(query.order_by(MarketRelationship.id).limit(limit)).all()
    return {'items':[{'id':r.id,'subject':s.name,'subject_id':s.id,'subject_identifier':s.identifier_value,
            'object':o.name,'object_id':o.id,'object_identifier':o.identifier_value,'relation_type':r.relation_type,
            'effective_from':r.effective_from,'effective_to':r.effective_to,'observed_at':r.observed_at,
            'assertion_status':r.assertion_status,'evidence_excerpt':r.evidence_excerpt,'source_url':src.source_url,
            'source_revision_id':src.id} for r,s,o,src in rows],
            'limitations':['Entries labelled reviewed_cached_registry_filing came from cached pages and may not reflect the current register.',
                           'Registry entries are reported filings; Companies House does not verify filed information.',
                           'A cached page and the Companies House API are the same source lineage, not independent corroboration.',
                           'As-of filtering uses effective dates in the latest captured source, not a historical knowledge snapshot.',
                           'A significant-control filing does not automatically establish a complete corporate ownership chain.']}
