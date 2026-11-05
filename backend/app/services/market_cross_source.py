"""Link reported procurement and corporate filings on an exact company number.

The two sources describe different facts, not independent confirmation of the
same claim. The control filing is not an award to the controller and a past
award is not evidence of current delivery, parent revenue or bidding intent.
"""
from __future__ import annotations
from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased
from app.models.market_graph import MarketRelationship
from app.models.market_network import MarketAward, MarketEntity, SourceRevision

_PROCUREMENT = {'find_a_tender', 'contracts_finder', 'public_contracts_scotland'}
_REGISTRY = {'companies_house_reviewed', 'companies_house_psc_api'}


def _utc(value):
    if not value:
        return None
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)
    except (TypeError, ValueError):
        return None


def _supplier_is_explicit(raw, award_id, number):
    """Recheck the exact identifier in the captured award, not only the DB join."""
    if not isinstance(raw, dict) or not award_id:
        return False
    awards = raw.get('awards') if isinstance(raw.get('awards'), list) else []
    matches = [a for a in awards if isinstance(a, dict) and str(a.get('id')) == str(award_id)]
    if len(matches) != 1:
        return False
    parties = raw.get('parties') if isinstance(raw.get('parties'), list) else []
    suppliers = matches[0].get('suppliers') if isinstance(matches[0].get('suppliers'), list) else []
    for supplier in suppliers:
        if not isinstance(supplier, dict):
            continue
        matching_parties = [p for p in parties if isinstance(p, dict) and p.get('id') == supplier.get('id')]
        if len(matching_parties) > 1:
            continue
        identifier = (matching_parties[0].get('identifier') if matching_parties else None) or supplier.get('identifier')
        if (isinstance(identifier, dict) and str(identifier.get('scheme','')).upper() == 'GB-COH'
                and str(identifier.get('id','')).upper() == number):
            return True
    return False


def _control_is_explicit(raw, subject_number, object_number):
    if not isinstance(raw, dict) or str(raw.get('company_number','')).upper() != subject_number:
        return False
    controllers = raw.get('controllers') if isinstance(raw.get('controllers'), list) else []
    return any(isinstance(c, dict) and str(c.get('company_number','')).upper() == object_number for c in controllers)


def _temporal_context(award_date, start, end):
    award, start, end = _utc(award_date), _utc(start), _utc(end)
    if not award:
        return 'Award date was not captured; its timing relative to the control filing is unknown.'
    if start and award.date() < start.date():
        return 'The control notification is later than the award date; the filing does not establish control at the time of award.'
    if end and award.date() >= end.date():
        return 'The captured filing records control ceasing on or before the award date; control at award is not established by this filing.'
    if start:
        return 'The award date falls within the dates reported in the captured filing; those dates do not independently establish the corporate relationship at award or now.'
    return 'The control notification date was not captured; its timing relative to the award is unknown.'


def company_award_context(db: Session, entity_id: int, limit: int = 50) -> list[dict]:
    entity = db.get(MarketEntity, entity_id)
    if entity is None:
        raise LookupError('Company not found')
    if entity.identifier_scheme != 'GB-COH' or not entity.identifier_value:
        return []
    obj, registry = aliased(MarketEntity), aliased(SourceRevision)
    relations = db.execute(select(MarketRelationship, obj, registry).join(obj, MarketRelationship.object_entity_id == obj.id)
                           .join(registry, MarketRelationship.source_revision_id == registry.id)
                           .where(MarketRelationship.subject_entity_id == entity_id,
                                  MarketRelationship.relation_type == 'SIGNIFICANT_CONTROL_BY',
                                  obj.identifier_scheme == 'GB-COH', registry.source_key.in_(_REGISTRY),
                                  registry.superseded_at.is_(None))).all()
    awards = db.execute(select(MarketAward, SourceRevision).join(SourceRevision)
                        .where(MarketAward.supplier_id == entity_id, SourceRevision.source_key.in_(_PROCUREMENT),
                               SourceRevision.superseded_at.is_(None))
                        .order_by(SourceRevision.published_at.desc(), SourceRevision.id.desc()).limit(500)).all()
    results, seen = [], set()
    for award, notice in awards:
        if not notice.ocid or not award.award_id or not _supplier_is_explicit(notice.raw, award.award_id, entity.identifier_value):
            continue
        for rel, controller, filing in relations:
            if not _control_is_explicit(filing.raw, entity.identifier_value, controller.identifier_value):
                continue
            # Multiple versions/notices for the same OCDS award are not separate wins.
            key = (notice.ocid, award.award_id, rel.id)
            if key in seen:
                continue
            seen.add(key)
            results.append({
                'award_id': award.id, 'award_identifier': award.award_id, 'ocid': notice.ocid,
                'supplier': award.supplier, 'supplier_company_number': entity.identifier_value,
                'buyer': award.buyer, 'title': award.title, 'award_date': award.award_date,
                'notice': {'source_key': notice.source_key, 'source_url': notice.source_url,
                           'source_revision_id': notice.id, 'published_at': notice.published_at},
                'control': {'subject': entity.name, 'controller': controller.name,
                            'controller_company_number': controller.identifier_value,
                            'relationship': rel.relation_type, 'notified_on': rel.effective_from,
                            'ceased_on': rel.effective_to, 'assertion_status': rel.assertion_status,
                            'source_key': filing.source_key, 'source_url': filing.source_url,
                            'source_revision_id': filing.id, 'retrieved_at': filing.retrieved_at},
                'timing': _temporal_context(award.award_date, rel.effective_from, rel.effective_to),
                'unknowns': ['Whether the original award is still being delivered or has been extended or replaced.',
                             'Whether the control relationship is current or applied on the award date.',
                             'The controller is not identified as the awarded supplier by this connection.'],
            })
            if len(results) >= limit:
                return results
    return results
