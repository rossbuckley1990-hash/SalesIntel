"""Keep one canonical row per contract, even as new records of it are published.

Once a record has joined a contract it stays there, so the key and any human
review survive when another source later publishes the same contract.
"""
from __future__ import annotations
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.renewal_radar import _buyer_key
from app.models.buyer_profile import BuyerProfile
from app.models.competitor_profile import CompetitorProfile
from app.models.market_contract import MarketContract, MarketContractLink
from app.models.market_network import MarketEntity, SourceRevision


def _identities(db: Session) -> dict:
    return {'companies': {x.identifier_value: x.id for x in db.scalars(select(MarketEntity).where(MarketEntity.identifier_scheme == 'GB-COH'))},
            'buyers': {_buyer_key(x.buyer_name): x.id for x in db.scalars(select(BuyerProfile))},
            'competitors': {_buyer_key(x.name): x.id for x in db.scalars(select(CompetitorProfile))}}


def _facts(item: dict, identities: dict) -> dict:
    view = item['view']
    return {'buyer_profile_id': identities['buyers'].get(_buyer_key(view['buyer'])), 'buyer_id': view.get('buyer_id') or None, 'suppliers': view['suppliers'],
            'company_numbers': view['company_numbers'], 'supplier_entity_ids': [identities['companies'][x] for x in view['company_numbers'] if x in identities['companies']],
            'competitor_profile_ids': [identities['competitors'][_buyer_key(x)] for x in view['suppliers'] if _buyer_key(x) in identities['competitors']],
            'identity_status': 'published_company_number' if view['company_numbers'] else 'name_only' if view['suppliers'] else 'unknown',
            'description': (view.get('description') or '')[:600], 'service_classification': view['fit_reason'], 'value': item['value'], 'award_date': view.get('award_date') or None,
            'start_date': view.get('start') or None, 'published_end_date': None if view['end_estimated'] else view.get('end') or None,
            'estimated_end_date': view.get('end') if view['end_estimated'] else None, 'end_basis': view['end_basis'], 'latest_end': view['latest_end'] or None,
            'latest_end_basis': view['latest_end_basis'] or None, 'extension_note': view['extension_note'] or None, 'evidence_status': item['status'], 'currency': item['currency'],
            'replacement': {'status': 'possible', 'title': view['successor_title'], 'published': view['successor_published'], 'url': view['successor_url']} if view['successor_url'] else None,
            'contradictions': view['contradictions'], 'checks': item['checks'], 'framework_stage': view['framework_stage'] or None, 'route': view.get('route') or None,
            'reference': view.get('reference') or None, 'published': view.get('published'), 'source_urls': [x['url'] for x in view['members'] if x.get('url')], 'evidence': item['evidence'],
            'link_confidence': view['link_confidence'], 'intelligence_status': item['category'] or item['status'], 'rule_version': view['rule_version']}


def sync_contracts(db: Session, evaluation: dict, now: datetime, complete: bool) -> dict:
    """Store every contract and return proposals keyed for market_opportunities."""
    identities = _identities(db)
    links = {x.member_key: x for x in db.scalars(select(MarketContractLink))}
    contracts = {x.id: x for x in db.scalars(select(MarketContract))}
    seen_at = {x.id: x.last_seen for x in db.scalars(select(SourceRevision))}
    candidates, active = dict(evaluation['proposals']), set()
    for item in evaluation['contracts']:
        view = item['view']
        members = [(f"{x['ocid']}:{x['lot']}", x) for x in view['members']]
        # A rule change can split records once held together, so a claimed row is not reused.
        known = sorted({links[key].contract_id for key, _ in members if key in links} - active)
        contract = contracts.get(known[0]) if known else None
        if contract is None:
            existing = next((x for x in contracts.values() if x.canonical_key == item['key']), None)
            key = item['key'] if existing is None or existing.id not in active else f"{item['key']}#{len(active)}"
            contract = existing if existing is not None and existing.id not in active else MarketContract(
                canonical_key=key, first_seen=now, last_evaluated=now, buyer=view['buyer'], title=view['title'], fit=view['fit'], lifecycle_status=item['status'], facts={})
            db.add(contract)
            db.flush()
            contracts[contract.id] = contract
        for other in known[1:]:
            # Two contracts proved to be one: keep the older and move its records.
            for link in links.values():
                if link.contract_id == other:
                    link.contract_id = contract.id
            db.flush()
            db.delete(contracts.pop(other))
            db.flush()
        for key, member in members:
            link = links.get(key)
            if link is None:
                link = MarketContractLink(contract_id=contract.id, member_key=key, source_key=member['source'], ocid=member['ocid'], lot=member['lot'],
                                          method=member['method'], confidence=member['confidence'], first_seen=now)
                db.add(link)
                links[key] = link
            else:
                link.contract_id, link.method, link.confidence = contract.id, member['method'], member['confidence']
        facts = _facts(item, identities)
        verified = [seen_at[x['source_revision_id']] for x in item['evidence'] if x['source_revision_id'] in seen_at]
        contract.ocid, contract.buyer, contract.supplier, contract.title = view['ocid'], view['buyer'], view['incumbent'] or None, view['title']
        contract.fit, contract.nation, contract.lifecycle_status, contract.category = view['fit'], view['nation'], item['status'], item['category']
        contract.end_date, contract.end_estimated, contract.last_evaluated = view.get('end') or None, view['end_estimated'], now
        contract.last_verified = max(verified) if verified else None
        if contract.facts != facts:
            contract.facts = facts
        active.add(contract.id)
        if item.get('proposal'):
            candidates[f'renewal:{contract.canonical_key}'] = {**item['proposal'], 'contract_id': contract.id}
    if complete:
        for contract in contracts.values():
            if contract.id not in active:
                contract.lifecycle_status, contract.category = 'no_longer_supported', None
    db.flush()
    return candidates
