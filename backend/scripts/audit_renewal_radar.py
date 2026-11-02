"""Draw a blind audit sample of the radar's opportunities and rejected records.

Usage: audit_renewal_radar.py OUTPUT_DIR SEED, run from the repository root.
The same seed and database give the same sample. Classifier output is left out
of the blind file, so a reviewer labels each row before seeing the decision.
"""
import json, random, sqlite3, sys, re
from datetime import date
sys.path.insert(0, 'backend'); sys.path.insert(0, 'backend/scripts')
from app.intelligence.renewal_radar import classify, families
S = sys.argv[1]
c = sqlite3.connect('file:.runtime/false-alarm-pilot-v2.db?mode=ro', uri=True)
opps = [json.loads(r[0]) for r in c.execute("select v.result from market_opportunities o join market_opportunity_revisions v on o.current_revision_id=v.id where o.state='suggested'")]
rng = random.Random(int(sys.argv[2]))
renew = [x for x in opps if x['kind'] == 'possible_renewal_window']
sig = [x for x in opps if x['kind'] != 'possible_renewal_window']
hv = sorted(renew, key=lambda x: -(x['value'].get('estimated_annualised') or x['value'].get('published_total') or 0))[:20]
hv_ids = {id(x) for x in hv}
rand = rng.sample([x for x in renew if id(x) not in hv_ids], 60)
sigs = rng.sample(sig, 20)
# rejected: sector words present, awarded, end inside the renewal window, classifier said exclude
notices = json.load(open('.runtime/renewal-radar/notices.json'))['notices'].values()
fts = json.load(open('.runtime/renewal-radar/find-a-tender.json'))
rej = []
today = date(2026, 11, 2)
for n in notices:
    if n['type'] == 'Contract' and n.get('end') and '2026-08-01' <= n['end'] <= '2028-05-31' and families(n['title'] + ' ' + (n.get('description') or '')):
        f, reason = classify(n)
        if f == 'exclude' and len(n.get('suppliers') or []) <= 4:
            rej.append({'source': 'cf', 'url': n['url'], 'buyer': n['buyer'], 'title': n['title'], 'description': (n.get('description') or '')[:420], 'supplier': ', '.join(n.get('suppliers') or []), 'end': n['end'], 'value': n.get('value'), 'reason': reason})
rej = rng.sample(rej, 30)
rows = []
for group, items in (('random', rand), ('high_value', hv), ('signal', sigs)):
    for x in items:
        desc = ''
        rows.append({'group': group, 'url': x['evidence'][0]['source_url'] if x['evidence'] else '', 'buyer': x['customer'], 'title': x['title'], 'supplier': x.get('supplier'), 'end': x.get('timing'), 'value': x['value'].get('published_total') or x['value'].get('framework_ceiling'), 'annual': x['value'].get('estimated_annualised'), 'why': x['brief']['why_it_matters'], '_cat': x['category'], '_fit': x['fit'], '_rev': x['evidence'][0]['source_revision_id'] if x['evidence'] else None, '_est': x.get('end_estimated'), '_lk': x['link']})
for r in rows:
    if r['_rev']:
        raw = json.loads(c.execute('select raw from market_source_revisions where id=?', (r['_rev'],)).fetchone()[0])
        r['description'] = ((raw.get('tender') or {}).get('description') or '')[:420]
for x in rej:
    rows.append({'group': 'rejected', **x})
json.dump(rows, open(f'{S}/audit_full.json', 'w'), indent=0)
blind = [{k: v for k, v in r.items() if not k.startswith('_') and k not in ('why', 'reason')} for r in rows]
open(f'{S}/audit_blind.txt', 'w').write('\n'.join(f"{i} [{r['group'][:3]}] {r['buyer'][:40]} | {r['title'][:110]} | sup={str(r.get('supplier'))[:40]} | end={r.get('end')} | £{r.get('value')} | {(r.get('description') or '')[:300]}" for i, r in enumerate(blind)))
print(len(rows))
