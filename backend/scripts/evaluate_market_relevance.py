"""Evaluate stored notice classifications against the small reviewed source sample."""
import json
from pathlib import Path
from sqlalchemy import select
from app.config import REPO_ROOT
from app.db import SessionLocal
from app.ingestion.market_find_tender import classify_release
from app.models.market_network import SourceRevision


def main():
    sample = json.loads((REPO_ROOT / 'backend/reference_data/market_relevance_sample.json').read_text())
    results = []
    with SessionLocal() as db:
        for item in sample['records']:
            record = db.scalar(select(SourceRevision).where(SourceRevision.source_key == sample['source_key'],
                               SourceRevision.record_key == item['id'], SourceRevision.superseded_at.is_(None)))
            if not record:
                results.append({'id': item['id'], 'status': 'missing'})
                continue
            decision = classify_release(record.raw)['level']
            results.append({'id': item['id'], 'primary_sector_scope': item['primary_sector_scope'],
                            'decision': decision, 'source_url': record.source_url})
    measured = [r for r in results if r.get('decision')]
    accepted = [r for r in measured if r['decision'] == 'relevant']
    positive = [r for r in measured if r['primary_sector_scope']]
    tp = sum(1 for r in accepted if r['primary_sector_scope'])
    print(json.dumps({'sample': len(sample['records']), 'available': len(measured), 'accepted': len(accepted),
                      'true_positives': tp, 'accepted_precision': tp / len(accepted) if accepted else None,
                      'positive_recall': tp / len(positive) if positive else None,
                      'abstained': sum(1 for r in measured if r['decision'] == 'ambiguous'),
                      'excluded': sum(1 for r in measured if r['decision'] == 'excluded'),
                      'limitations': sample['review_method'], 'results': results}, indent=2))


if __name__ == '__main__':
    main()
