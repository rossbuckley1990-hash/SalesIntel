"""Record corporate-control assertions from a reviewed public registry snapshot.

The public register records what was filed; it is not an independent audit of
corporate control. Snapshot data is explicitly marked as manually reviewed.
"""
from __future__ import annotations
from datetime import UTC, datetime
import re
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.market_graph import MarketRelationship
from app.models.market_network import MarketEntity, MarketEntityEvidence
from app.services.market_network import ingest_market_release

_COMPANY_NUMBER = re.compile(r'^(?:[0-9]{8}|[A-Z]{2}[0-9]{6})$')


def _number(value):
    s = str(value or '').strip().upper()
    if not _COMPANY_NUMBER.fullmatch(s):
        raise ValueError('Expected an exact Companies House company number')
    return s


def _date(value):
    if value is None:
        return None
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def ingest_reviewed_psc_snapshot(db: Session, snapshot: dict, *, from_official_api: bool = False) -> dict:
    """Import reviewed company-only PSC entries; caller owns the transaction.

    Do not use for unidentified companies, individual controllers or guessed
    names. Sources and assertion dates are preserved and replay is idempotent.
    """
    number = _number(snapshot.get('company_number'))
    company_name = str(snapshot.get('company_name') or '').strip()
    url = f'https://find-and-update.company-information.service.gov.uk/company/{number}/persons-with-significant-control'
    if snapshot.get('source_url') != url or not company_name:
        raise ValueError('Snapshot requires the official company PSC page and company name')
    items = snapshot.get('controllers')
    if not isinstance(items, list) or not items:
        raise ValueError('At least one reviewed corporate controller is required')
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Invalid corporate controller')
        controller = _number(item.get('company_number'))
        name = str(item.get('company_name') or '').strip()
        if not name or controller == number:
            raise ValueError('Controller must be a separate identified company')
        start, end = _date(item.get('notified_on')), _date(item.get('ceased_on'))
        if start and end and end < start:
            raise ValueError('Control cannot end before notification')
        nature = item.get('nature_of_control')
        if not isinstance(nature, list) or not nature or not all(isinstance(n, str) for n in nature):
            raise ValueError('Nature of control must be a non-empty list of source claims')
        cleaned.append({'company_number': controller, 'company_name': name, 'notified_on': start.isoformat() if start else None,
                        'ceased_on': end.isoformat() if end else None, 'nature_of_control': nature})
    observed = _date(snapshot.get('retrieved_at')) or datetime.now(UTC)
    method = 'companies_house_rest_api' if from_official_api else 'manually_reviewed_cached_public_registry_page'
    source_key = 'companies_house_psc_api' if from_official_api else 'companies_house_reviewed'
    result = ingest_market_release(db, {'source_key':source_key, 'release_id':f'psc:{number}',
        'source_url':url, 'retrieved_at':observed,
        'raw':{'company_number':number,'company_name':company_name,'controllers':cleaned,
               'method':method, 'coverage':'selected corporate entries; not a complete register extract'}})
    revision_id = result['revision_id']
    def entity(company_number, name):
        existing = db.scalar(select(MarketEntity).where(MarketEntity.identifier_scheme=='GB-COH',
                                                       MarketEntity.identifier_value==company_number))
        if existing is None:
            existing = MarketEntity(name=name, identifier_scheme='GB-COH', identifier_value=company_number,
                                    identity_status='reviewed_registry_listing',first_seen=observed,last_seen=observed)
            db.add(existing); db.flush()
        else:
            existing.last_seen=observed
        if not db.scalar(select(MarketEntityEvidence.id).where(MarketEntityEvidence.entity_id==existing.id,
                                MarketEntityEvidence.source_revision_id==revision_id)):
            db.add(MarketEntityEvidence(entity_id=existing.id,source_revision_id=revision_id,assertion='registry_psc_listing'))
        return existing
    subject=entity(number, company_name)
    created=0
    for item in cleaned:
        target=entity(item['company_number'],item['company_name'])
        start,end=_date(item['notified_on']),_date(item['ceased_on'])
        existing=db.scalar(select(MarketRelationship).where(MarketRelationship.source_revision_id==revision_id,
                         MarketRelationship.subject_entity_id==subject.id,MarketRelationship.object_entity_id==target.id,
                         MarketRelationship.relation_type=='SIGNIFICANT_CONTROL_BY',MarketRelationship.effective_from==start))
        if not existing:
            db.add(MarketRelationship(subject_entity_id=subject.id,object_entity_id=target.id,source_revision_id=revision_id,
                relation_type='SIGNIFICANT_CONTROL_BY',effective_from=start,effective_to=end,observed_at=observed,
                assertion_status='registry_api_filing' if from_official_api else 'reviewed_cached_registry_filing',
                evidence_excerpt='; '.join(item['nature_of_control'])[:2000])); created += 1
    db.flush()
    return {'state':result['state'],'source_revision_id':revision_id,'relationships_created':created}
