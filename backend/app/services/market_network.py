"""Store immutable, minimally scoped OCDS revisions and explicit award claims.

Identity is never resolved by a name similarity. Only valid GB-COH identifiers
are shared across records; other suppliers remain local notice identities.
"""
from datetime import UTC, datetime
import hashlib
import json
import re
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.market_network import MarketAward, MarketEntity, SourceRevision

_COMPANY_NUMBER = re.compile(r'^(?:[0-9]{8}|[A-Z]{2}[0-9]{6})$')
_PRIVATE_FIELDS = {'contactpoint', 'contactpoints', 'additionalcontactpoints', 'person', 'persons',
                   'people', 'officers', 'officer', 'email', 'telephone', 'phone', 'faxnumber'}


def _minimal(value):
    if isinstance(value, dict):
        return {k: _minimal(v) for k, v in value.items() if k.casefold() not in _PRIVATE_FIELDS}
    if isinstance(value, list):
        return [_minimal(v) for v in value]
    return value


def _date(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None


def _string(value, limit=2000):
    return ' '.join(str(value or '').split())[:limit]


def _identity(source, record_key, supplier, parties):
    party_id = _string(supplier.get('id'), 256)
    party = parties.get(party_id, {})
    identifier = party.get('identifier') or supplier.get('identifier') or {}
    if not isinstance(identifier, dict):
        identifier = {}
    scheme = _string(identifier.get('scheme'), 128).upper()
    number = _string(identifier.get('id'), 256).upper()
    if scheme == 'GB-COH' and _COMPANY_NUMBER.fullmatch(number):
        return 'GB-COH', number, 'published_company_number'
    if not party_id:
        return None
    # A source party identifier is scoped to this release and is not evidence
    # that a similarly named supplier elsewhere is the same legal entity.
    local_key = hashlib.sha256(f'{record_key}\0{party_id}'.encode()).hexdigest()
    return f'{source}:notice-party'[:128], local_key, 'source_party_unresolved'


def ingest_market_release(db: Session, record: dict) -> dict:
    source = _string(record.get('source_key'), 80)
    record_key = _string(record.get('release_id'), 256)
    raw = record.get('raw')
    retrieved = _date(record.get('retrieved_at')) or datetime.now(UTC)
    if not source or not record_key or not isinstance(raw, dict):
        raise ValueError('A source, release identifier and OCDS release are required')
    raw = _minimal(raw)
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    old = db.scalar(select(SourceRevision).where(SourceRevision.source_key == source,
                       SourceRevision.record_key == record_key, SourceRevision.superseded_at.is_(None))
                    .order_by(SourceRevision.id.desc()).limit(1))
    if old and old.content_hash == digest:
        old.last_seen = retrieved
        db.flush()
        return {'state': 'unchanged', 'companies': 0, 'awards': 0, 'revision_id': old.id}
    incoming_published = _date(record.get('published_at'))
    def comparable(value):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    historical = bool(old and old.published_at and incoming_published and
                      comparable(incoming_published) < comparable(old.published_at))
    if historical:
        same = db.scalar(select(SourceRevision).where(SourceRevision.source_key == source,
                         SourceRevision.record_key == record_key, SourceRevision.content_hash == digest).limit(1))
        if same:
            same.last_seen = retrieved
            db.flush()
            return {'state': 'unchanged', 'companies': 0, 'awards': 0, 'revision_id': same.id}
    if old and not historical:
        old.superseded_at = retrieved
        # Release the partial unique index before inserting a replacement.
        db.flush()
    revision = SourceRevision(source_key=source, record_key=record_key,
                              ocid=_string(record.get('ocid') or raw.get('ocid'), 256) or None,
                              source_url=_string(record.get('source_url'), 2000),
                              content_hash=digest, raw=raw, published_at=_date(record.get('published_at')),
                              retrieved_at=retrieved, last_seen=retrieved, superseded_at=retrieved if historical else None)
    db.add(revision)
    db.flush()
    parties = {str(p.get('id')): p for p in raw.get('parties', []) if isinstance(p, dict) and p.get('id') is not None} if isinstance(raw.get('parties'), list) else {}
    tender = raw.get('tender') if isinstance(raw.get('tender'), dict) else {}
    buyer = raw.get('buyer') if isinstance(raw.get('buyer'), dict) else {}
    awards = raw.get('awards') if isinstance(raw.get('awards'), list) else []
    new_companies = count_awards = 0
    for award in awards:
        if not isinstance(award, dict):
            continue
        suppliers = award.get('suppliers') if isinstance(award.get('suppliers'), list) else []
        suppliers = [s for s in suppliers if isinstance(s, dict)] or [None]
        for supplier in suppliers:
            entity = None
            name = _string(supplier.get('name')) if supplier else ''
            identity = _identity(source, record_key, supplier, parties) if supplier else None
            if identity and name:
                scheme, number, identity_status = identity
                entity = db.scalar(select(MarketEntity).where(MarketEntity.identifier_scheme == scheme,
                                    MarketEntity.identifier_value == number))
                if not entity:
                    entity = MarketEntity(name=name, identifier_scheme=scheme, identifier_value=number,
                                          identity_status=identity_status, first_seen=retrieved, last_seen=retrieved)
                    db.add(entity)
                    db.flush()
                    new_companies += 1
                else:
                    entity.last_seen = retrieved
            value = award.get('value') if isinstance(award.get('value'), dict) else {}
            amount = value.get('amount')
            db.add(MarketAward(source_revision_id=revision.id, supplier_id=entity.id if entity else None,
                award_id=_string(award.get('id'), 256) or None, title=_string(award.get('title') or tender.get('title')),
                buyer=_string(buyer.get('name')) or None, supplier=name or None,
                status=_string(award.get('status'), 64) or None,
                award_date=_string(award.get('date'), 64) or None,
                amount=str(amount)[:64] if isinstance(amount, (int, float)) and not isinstance(amount, bool) else None,
                currency=_string(value.get('currency'), 16) or None, classification='unknown'))
            count_awards += 1
    db.flush()
    return {'state': 'historical' if historical else ('changed' if old else 'new'),
            'companies': new_companies, 'awards': count_awards, 'revision_id': revision.id}


def ingest_market_company(db: Session, record: dict) -> dict:
    """Remember an official Companies House company profile, with source provenance.

    A published registry profile establishes the legal entity exists, not that it
    has fire/security capability or has won a particular contract.
    """
    from app.models.market_network import MarketEntityEvidence
    profile = record.get('raw')
    if not isinstance(profile, dict):
        raise ValueError('Company profile must be an object')
    number = _string(profile.get('company_number'), 32).upper()
    name = _string(profile.get('company_name'))
    if not _COMPANY_NUMBER.fullmatch(number) or not name or _string(record.get('release_id'), 32).upper() != number:
        raise ValueError('Company number and name must match the requested official profile')
    # Limit personal-data retention and keep only useful, public organisational fields.
    allowed = ('company_number', 'company_name', 'company_status', 'type', 'date_of_creation',
               'date_of_cessation', 'sic_codes', 'has_insolvency_history', 'registered_office_address',
               'previous_company_names')
    clean = {key: profile[key] for key in allowed if key in profile}
    address = clean.get('registered_office_address')
    if isinstance(address, dict):
        clean['registered_office_address'] = {key: address[key] for key in
            ('locality', 'region', 'country', 'postal_code') if key in address}
    else:
        clean.pop('registered_office_address', None)
    updated_record = {**record, 'source_key': 'companies_house', 'raw': clean, 'ocid': None}
    outcome = ingest_market_release(db, updated_record)
    revision = db.get(SourceRevision, outcome['revision_id'])
    entity = db.scalar(select(MarketEntity).where(MarketEntity.identifier_scheme == 'GB-COH',
                       MarketEntity.identifier_value == number))
    retrieved = _date(record.get('retrieved_at')) or datetime.now(UTC)
    created = entity is None
    if created:
        entity = MarketEntity(name=name, identifier_scheme='GB-COH', identifier_value=number,
                              identity_status='registry_profile', first_seen=retrieved, last_seen=retrieved)
        db.add(entity)
        db.flush()
    else:
        if outcome['state'] != 'historical':
            entity.name = name
        entity.identity_status = 'registry_profile'
        entity.last_seen = retrieved
    evidence = db.scalar(select(MarketEntityEvidence).where(MarketEntityEvidence.entity_id == entity.id,
                         MarketEntityEvidence.source_revision_id == revision.id))
    if not evidence:
        db.add(MarketEntityEvidence(entity_id=entity.id, source_revision_id=revision.id, assertion='registry_profile'))
    db.flush()
    outcome['companies'] = int(created)
    outcome['entity_id'] = entity.id
    return outcome
