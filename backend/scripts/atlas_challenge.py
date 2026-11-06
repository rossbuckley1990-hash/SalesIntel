"""Contract Atlas challenge: a frozen contractor sample, its reconstructed relationships, an independent check of the
source evidence, bounded private research, and the commercial-utility comparison.

Runs only on the isolated copy in ~/.salesintel/atlas (never the live database).

  freeze       select the sample with a recorded random seed, before any result is seen
  reconstruct  the Atlas's public relationships for each sampled contractor
  verify       an independent check of every public assertion against the raw source records, with its own parser
  private      live research of a seeded subset's published customers, inside a hard budget
  recheck      an independent re-fetch of every reported page to look for the quote, supplier and customer
  utility      the reference salesperson's new accounts, against the Renewal Radar and Shadow Radar baselines
  report       the public summary (organisations in the blind review are withheld) and a private review sheet

Full results with every organisation name stay in ~/.salesintel/atlas/challenge. The public documents in docs/saas/atlas
withhold any organisation that appears in the frozen blind-review set until that review is locked.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import random
import re
import secrets
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

PUBLIC = ROOT / 'docs' / 'saas' / 'atlas'
PRIVATE = Path.home() / '.salesintel' / 'atlas' / 'challenge'
SAMPLE = PUBLIC / 'challenge-sample.json'
SIZE, PRIVATE_SUBSET, BUDGET_CENTS, PER_JOB_CENTS = 24, 8, 1000, 150
REVIEW_SET = ROOT / 'backend' / 'reference_data' / 'evaluation' / 'opportunities-2026-11-05-v2.json'
RULE = ('Every contractor named as supplier on at least one fire or security contract in the Market Network, excluding the reference '
        "company's own group; stratified by the number of its published contracts (1, 2 to 4, 5 or more) and by identity (a published "
        'company number, or a name only); a simple random sample within each stratum, proportional with at least 2 per stratum, from a '
        'seed drawn with secrets and recorded before any result was seen. The private-research subset is a second seeded draw from the sample.')


def _session():
    from app.config import get_settings
    url = get_settings().database_url
    if '/.salesintel/atlas/' not in url:
        sys.exit('Refusing to run: the challenge runs only on the isolated copy in ~/.salesintel/atlas.')
    from app.db import SessionLocal
    return SessionLocal(), url


def _commit() -> dict:
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    return {'commit': head, 'tracked_changes': dirty}


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str) + '\n')
    if str(path).startswith(str(PRIVATE)):
        path.chmod(0o600)


def _band(n: int) -> str:
    return '1' if n == 1 else '2-4' if n <= 4 else '5+'


# ------------------------------------------------------------------ freeze

def freeze(args) -> None:
    from sqlalchemy import select
    from app.intelligence.renewal_radar import OWN_GROUP
    from app.models.atlas import AtlasContractor
    from app.services import atlas
    if SAMPLE.exists() and not args.replace:
        sys.exit(f'{SAMPLE} is frozen. Never redraw a sample to get a different result.')
    db, url = _session()
    with db:
        atlas.ensure_built(db)
        db.commit()
        universe = [c for c in db.scalars(select(AtlasContractor).where(AtlasContractor.contract_count > 0)) if not OWN_GROUP.search(c.display_name)]
    strata: dict[str, list] = defaultdict(list)
    for c in universe:
        strata[f"{_band(c.contract_count)}|{'number' if c.company_number else 'name_only'}"].append(c)
    seed = secrets.randbits(64)
    rng = random.Random(seed)
    sizes = {k: len(v) for k, v in strata.items()}
    want = {k: max(min(2, n), round(SIZE * n / len(universe))) for k, n in sizes.items()}
    while sum(want.values()) > SIZE:  # trim the largest allocations first
        k = max(want, key=lambda x: (want[x] - 2, sizes[x]))
        want[k] -= 1
    while sum(want.values()) < SIZE:
        k = max((x for x in want if want[x] < sizes[x]), key=lambda x: sizes[x] - want[x])
        want[k] += 1
    picked = []
    for k in sorted(strata):
        members = sorted(strata[k], key=lambda c: c.key)
        for c in rng.sample(members, want[k]):
            picked.append({'key': c.key, 'name': c.display_name, 'company_number': c.company_number, 'stratum': k, 'published_contracts': c.contract_count})
    picked.sort(key=lambda x: x['key'])
    subset = sorted(random.Random(f'{seed}:private').sample([p['key'] for p in picked], min(PRIVATE_SUBSET, len(picked))))
    database = Path(url.removeprefix('sqlite:///'))
    _write(SAMPLE, {'created_at': datetime.now(UTC).isoformat(), 'code': _commit(), 'rule': RULE, 'seed': seed, 'size': SIZE,
                    'universe': len(universe), 'strata': {k: {'contractors': sizes[k], 'sampled': want[k]} for k in sorted(strata)},
                    'database_sha256': hashlib.sha256(database.read_bytes()).hexdigest(), 'sample': picked, 'private_subset': subset,
                    'private_budget_cents': BUDGET_CENTS})
    print(f'Frozen {len(picked)} contractors from {len(universe)} (seed recorded).')


def _sample() -> dict:
    if not SAMPLE.exists():
        sys.exit('Freeze the sample first.')
    return json.loads(SAMPLE.read_text())


# ------------------------------------------------------------------ reconstruct

def reconstruct(args) -> None:
    from sqlalchemy import select
    from app.models.atlas import AtlasContractor
    from app.services import atlas
    sample, today = _sample(), date.today()
    db, _ = _session()
    out = []
    with db:
        for s in sample['sample']:
            c = db.scalar(select(AtlasContractor).where(AtlasContractor.key == s['key']))
            if c is None:
                out.append({**s, 'missing': True})
                continue
            record = atlas.contractor_record(db, c.id, today=today)
            out.append({**s, 'id': c.id, 'identity': record['identity'], 'services': record['services'],
                        'contracts': [{k: x[k] for k in ('id', 'customer', 'title', 'supplier_name_seen', 'match', 'services', 'scope', 'route', 'region', 'nation',
                                                          'value', 'dates', 'status', 'sources')} for x in record['contracts']],
                        'relationships': record['relationships']})
    _write(PRIVATE / 'reconstructed.json', {'as_of': str(today), 'code': _commit(), 'contractors': out})
    print(f"Reconstructed {sum(len(x.get('contracts', [])) for x in out)} published relationships for {len(out)} contractors.")


# ------------------------------------------------------------------ independent verification of public assertions

def _n(s: str) -> str:
    """The checker's own name normaliser: deliberately separate from the Atlas code."""
    s = (s or '').lower().replace('&', ' and ')
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    s = re.sub(r'\blimited\b', 'ltd', s)
    return re.sub(r'^the ', '', ' '.join(s.split()))


def _releases(raw: dict) -> list[dict]:
    return [r for r in raw.get('releases') or [] if isinstance(r, dict)] if isinstance(raw.get('releases'), list) else [raw]


def _facts(raws: list[dict]) -> dict:
    out = {'buyers': set(), 'suppliers': set(), 'ids': '', 'ends': set(), 'values': set(), 'text': ''}
    for raw in raws:
        out['ids'] += json.dumps(raw)
        for rel in _releases(raw):
            if isinstance(rel.get('buyer'), dict):
                out['buyers'].add(_n(rel['buyer'].get('name') or ''))
            for p in rel.get('parties') or []:
                roles = p.get('roles') or []
                if 'buyer' in roles:
                    out['buyers'].add(_n(p.get('name') or ''))
                if 'supplier' in roles:
                    out['suppliers'].add(_n(p.get('name') or ''))
            tender = rel.get('tender') or {}
            out['text'] += f" {tender.get('title') or ''} {tender.get('description') or ''}"
            for a in rel.get('awards') or []:
                for s in a.get('suppliers') or []:
                    out['suppliers'].add(_n(s.get('name') or ''))
                if (a.get('contractPeriod') or {}).get('endDate'):
                    out['ends'].add(str(a['contractPeriod']['endDate'])[:10])
                if (a.get('value') or {}).get('amount') is not None:
                    out['values'].add(float(a['value']['amount']))
                out['text'] += f" {a.get('title') or ''} {a.get('description') or ''}"
            for k in rel.get('contracts') or []:
                if (k.get('period') or {}).get('endDate'):
                    out['ends'].add(str(k['period']['endDate'])[:10])
                if (k.get('value') or {}).get('amount') is not None:
                    out['values'].add(float(k['value']['amount']))
            if (tender.get('contractPeriod') or {}).get('endDate'):
                out['ends'].add(str(tender['contractPeriod']['endDate'])[:10])
    return out


WORDS = {'fire_alarm': r'fire\s*(alarm|detection)|fire\s*(and|&)\s*(intruder|security)|voice\s*alarm', 'emergency_lighting': r'emergency\s*light',
         'extinguishers': r'extinguisher|fire\s*(fighting|safety)?\s*equipment', 'sprinklers': r'sprinkler|riser|suppression',
         'smoke_control': r'smoke\s*(control|vent|extract)|damper', 'cctv': r'cctv|video\s*surveillance', 'access_control': r'access\s*control|door\s*entry',
         'intruder': r'intruder|burglar|alarm\s*(monitoring|receiving)|security\s*(system|alarm)', 'passive_fire': r'fire\s*door|compartment|fire\s*stopping|passive\s*fire',
         'fire_risk_assessment': r'fire\s*risk\s*assess'}


def verify(args) -> None:
    from sqlalchemy import select
    from app.models.market_contract import MarketContract
    from app.models.market_network import SourceRevision
    data = json.loads((PRIVATE / 'reconstructed.json').read_text())
    today = date.fromisoformat(data['as_of'])
    db, _ = _session()
    rows, numbered_names = [], defaultdict(set)
    with db:
        for c in data['contractors']:
            for x in c.get('contracts') or []:
                contract = db.get(MarketContract, x['id'])
                ids = [e.get('source_revision_id') for e in (contract.facts or {}).get('evidence') or [] if e.get('source_revision_id')]
                raws = [r.raw for r in db.scalars(select(SourceRevision).where(SourceRevision.id.in_(ids)))]
                f = _facts([r for r in raws if isinstance(r, dict)])
                number = c.get('company_number')
                check = {'contractor': c['key'], 'contract': x['id'], 'basis': x['match']['basis'],
                         'supplier_in_source': _n(x['supplier_name_seen']) in f['suppliers'],
                         'customer_in_source': _n(x['customer']) in f['buyers']}
                if x['match']['basis'] == 'company_number':
                    check['number_in_source'] = bool(number) and (number in f['ids'] or number.lstrip('0') in f['ids'])
                    if check['number_in_source']:
                        numbered_names[c['key']].add(_n(x['supplier_name_seen']))
                end = (x['dates'] or {}).get('end')
                if end:
                    check['end_in_source'] = str(end)[:10] in f['ends']
                    check['status_consistent'] = (x['status']['code'] in {'in_term', 'end_approaching', 'extension_possible'}) == (date.fromisoformat(str(end)[:10]) >= today) \
                        if x['status']['code'] != 'framework' else True
                v = x.get('value')
                if v and v['kind'] in ('published_total', 'framework_ceiling'):
                    check['value_in_source'] = any(abs(v['amount'] - a) < 1 for a in f['values'])
                check['service_words_in_source'] = any(re.search(WORDS[s['family']], f['text'], re.I) for s in x['services']) if x['services'] else None
                if x['scope']['code'] == 'installation':
                    check['scope_consistent'] = bool(re.search(r'install|replac|upgrad|supply and fit|new system', f['text'], re.I))
                elif x['scope']['code'] == 'maintenance':
                    check['scope_consistent'] = bool(re.search(r'mainten|servic|inspect|test|ppm|repair', f['text'], re.I))
                rows.append(check)
    for r in rows:  # a name joined to a numbered contractor is right if the same name appears on a record that carries the number
        if r['basis'] == 'identical_legal_name':
            name = next(_n(x['supplier_name_seen']) for c in data['contractors'] if c['key'] == r['contractor'] for x in c['contracts'] if x['id'] == r['contract'])
            r['name_join_supported'] = name in numbered_names[r['contractor']]

    def rate(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return {'checked': len(vals), 'passed': sum(vals), 'rate': round(sum(vals) / len(vals), 3) if vals else None}
    keys = ['supplier_in_source', 'customer_in_source', 'number_in_source', 'name_join_supported', 'end_in_source', 'value_in_source', 'status_consistent',
            'service_words_in_source', 'scope_consistent']
    unsupported = [r for r in rows if any(r.get(k) is False for k in ('supplier_in_source', 'customer_in_source', 'end_in_source', 'value_in_source'))]
    false_matches = [r for r in rows if r.get('supplier_in_source') is False or r.get('number_in_source') is False or r.get('name_join_supported') is False]
    summary = {'as_of': data['as_of'], 'checked_by': 'scripts/atlas_challenge.py verify: its own OCDS parser and name normaliser, reading the raw source records',
               'assertions': len(rows), 'contractors': len(data['contractors']), 'by_check': {k: rate(k) for k in keys},
               'relationship_correct': rate_both(rows), 'unsupported_assertions': len(unsupported), 'false_relationship_matches': len(false_matches),
               'by_basis': dict(Counter(r['basis'] for r in rows))}
    _write(PRIVATE / 'verification.json', {'summary': summary, 'rows': rows})
    print(json.dumps(summary, indent=1))


def rate_both(rows: list[dict]) -> dict:
    vals = [bool(r['supplier_in_source'] and r['customer_in_source']) for r in rows]
    return {'checked': len(vals), 'passed': sum(vals), 'rate': round(sum(vals) / len(vals), 3) if vals else None}


# ------------------------------------------------------------------ private research, inside a hard budget

def private(args) -> None:
    from sqlalchemy import select
    from app.config import get_settings
    from app.models.atlas import AtlasContractor, AtlasRelationship
    from app.services import atlas_research
    from app.services.ai_costs import research_provider
    settings = get_settings()
    if not settings.anthropic_api_key or settings.research_provider == 'replay':
        sys.exit('Live research needs the Anthropic provider and key in this shell.')
    sample = _sample()
    ledger_path = PRIVATE / 'private-ledger.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {'runs': [], 'spent_cents': 0}
    done = {r['key'] for r in ledger['runs']}
    db, _ = _session()
    with db:
        for key in sample['private_subset']:
            if key in done:
                continue
            if ledger['spent_cents'] + PER_JOB_CENTS > BUDGET_CENTS:
                print(f"Stopped: another run could pass the ${BUDGET_CENTS / 100:.2f} budget (spent ${ledger['spent_cents'] / 100:.2f}).")
                break
            c = db.scalar(select(AtlasContractor).where(AtlasContractor.key == key))
            meter = research_provider(settings)
            meter.ceiling_cents = PER_JOB_CENTS
            started = time.time()
            try:
                result = atlas_research.run(db, 'contractor', c.display_name, meter, contractor_id=c.id)
                db.commit()
                error = ''
            except Exception as exc:  # recorded, never hidden
                db.rollback()
                result, error = {}, f'{type(exc).__name__}: {exc}'[:300]
            ledger['spent_cents'] += meter.cents
            ledger['runs'].append({'key': key, 'name': c.display_name, 'cents': meter.cents, 'usage': meter.summary(), 'seconds': round(time.time() - started),
                                   'result': {k: result.get(k) for k in ('reported', 'quote_verified', 'unsupported', 'historical', 'sources_reviewed', 'searched_for', 'not_found', 'message')},
                                   'error': error})
            _write(ledger_path, ledger)
            print(f"{c.display_name}: {result.get('message') or error} (${meter.cents / 100:.2f}; total ${ledger['spent_cents'] / 100:.2f})")
        rows = db.scalars(select(AtlasRelationship)).all()
        _write(PRIVATE / 'private-relationships.json', [{'id': r.id, 'supplier': r.supplier_name, 'customer': r.customer_name, 'kind': r.kind,
                                                          'intermediary': r.intermediary, 'services': r.services, 'published_on': r.published_on,
                                                          'currency': r.currency, 'source_url': r.source_url, 'source_type': r.source_type, 'quote': r.quote,
                                                          'quote_verified': r.quote_verified, 'checks': r.checks, 'status': r.status} for r in rows])


# ------------------------------------------------------------------ independent re-check of reported pages

def _page_text(body: str) -> str:
    body = re.sub(r'(?is)<(script|style|noscript).*?</\1>', ' ', body)
    return html.unescape(re.sub(r'(?s)<[^>]+>', ' ', body))


def recheck(args) -> None:
    import httpx
    rows = json.loads((PRIVATE / 'private-relationships.json').read_text())
    pages: dict[str, tuple[int | None, str]] = {}
    out = []
    for r in rows:
        url = r['source_url']
        if url not in pages:
            try:
                resp = httpx.get(url, timeout=20, follow_redirects=True, headers={'User-Agent': 'SalesIntel evidence check (one request per page)'})
                pages[url] = (resp.status_code, _page_text(resp.text[:3_000_000]) if resp.status_code == 200 else '')
            except httpx.HTTPError as exc:
                pages[url] = (None, '')
                print(f'{url}: {type(exc).__name__}')
            time.sleep(1)
        status, text = pages[url]
        page = _n(text)
        quote = _n(r['quote'])

        def named(name: str) -> bool:
            generic = {'ltd', 'plc', 'llp', 'group', 'holdings', 'services', 'fire', 'security', 'and', 'uk', 'the', 'limited', 'systems', 'solutions', 'protection', 'safety'}
            words = [w for w in _n(name).split() if w not in generic and len(w) > 1] or _n(name).split()
            return bool(words) and all(f' {w} ' in f' {page} ' for w in words)
        out.append({**r, 'page_status': status, 'page_available': bool(text),
                    'quote_on_live_page': bool(text) and quote in page, 'supplier_on_live_page': bool(text) and named(r['supplier']),
                    'customer_on_live_page': bool(text) and named(r['customer'])})
    reported = [o for o in out if o['status'] == 'reported']
    available = [o for o in reported if o['page_available']]
    summary = {'checked_by': 'scripts/atlas_challenge.py recheck: a fresh fetch of each page, with its own text extraction',
               'reported': len(reported), 'pages_available': len(available),
               'quote_confirmed_live': sum(o['quote_on_live_page'] for o in available), 'customer_named_live': sum(o['customer_on_live_page'] for o in available),
               'supplier_named_live': sum(o['supplier_on_live_page'] for o in available),
               'pipeline_quote_verified': sum(o['quote_verified'] for o in reported), 'unsupported_kept_hidden': len(out) - len(reported)}
    _write(PRIVATE / 'private-recheck.json', {'summary': summary, 'rows': out})
    print(json.dumps(summary, indent=1))


# ------------------------------------------------------------------ commercial utility

def utility(args) -> None:
    from sqlalchemy import select
    from app.intelligence.opportunity_review import REFERENCE_PROFILE
    from app.models.atlas import AtlasContractor
    from app.models.crm import Account
    from app.models.market_contract import MarketContract
    from app.models.market_network import SourceRevision
    from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
    from app.models.shadow import ShadowHypothesis
    from app.services import atlas
    today = date.today()
    db, _ = _session()
    with db:
        pursued = {atlas.normalise(a.name) for a in db.scalars(select(Account))}
        leads = {}
        for c in db.scalars(select(AtlasContractor).where(AtlasContractor.contract_count > 0)):
            record = atlas.contractor_record(db, c.id, prefs=REFERENCE_PROFILE, today=today)
            for x in record['worth_investigating']:
                if x['customer_key'] in pursued:
                    continue
                contract = db.get(MarketContract, x['id'])
                ids = [e.get('source_revision_id') for e in (contract.facts or {}).get('evidence') or [] if e.get('source_revision_id')]
                raw = json.dumps([r.raw for r in db.scalars(select(SourceRevision).where(SourceRevision.id.in_(ids)))])
                named_contact = bool(re.search(r'"contactPoint":\s*\{[^}]*"name":\s*"[^"]{3,}', raw))
                route = bool(re.search(r'"contactPoint":\s*\{[^}]*"(email|telephone)":\s*"[^"]{5,}', raw))
                lead = leads.setdefault(x['customer_key'], {'customer': x['customer'], 'contracts': 0, 'timing': False, 'named_contact': False, 'route_on_notice': False})
                lead['contracts'] += 1
                lead['timing'] |= bool((x['dates'] or {}).get('end'))
                lead['named_contact'] |= named_contact
                lead['route_on_notice'] |= route
        atlas_accounts = set(leads)
        radar = set()
        for mo in db.scalars(select(MarketOpportunity).where(MarketOpportunity.state != 'withdrawn')):
            rev = db.get(MarketOpportunityRevision, mo.current_revision_id) if mo.current_revision_id else None
            if rev and (rev.result or {}).get('customer'):
                radar.add(atlas.normalise(rev.result['customer']))
        shadow = {atlas.normalise(h.entity_name) for h in db.scalars(select(ShadowHypothesis).where(ShadowHypothesis.active.is_(True)))}
    n = len(leads)
    summary = {'as_of': str(today), 'reference_profile': {k: REFERENCE_PROFILE[k] for k in ('services', 'territory')}, 'accounts_already_pursued': len(pursued),
               'atlas': {'new_accounts': n, 'with_published_supplier_relationship': n, 'with_specific_reason': n,
                         'with_published_end_date': sum(v['timing'] for v in leads.values()), 'with_named_contact_on_notice': sum(v['named_contact'] for v in leads.values()),
                         'with_contact_route_on_notice': sum(v['route_on_notice'] for v in leads.values()), 'with_next_action': n},
               'baselines': {'renewal_radar_accounts': len(radar - pursued), 'shadow_radar_accounts': len(shadow - pursued)},
               'overlap': {'atlas_and_renewal_radar': len(atlas_accounts & radar), 'atlas_only': len(atlas_accounts - radar - shadow),
                           'renewal_radar_only': len(radar - atlas_accounts - pursued)},
               'note': ('Counts of what each list can show, not a judgement of quality. Whether these accounts are worth pursuing needs a '
                        'salesperson, as in the blind review; no improvement is claimed.')}
    _write(PRIVATE / 'utility.json', {'summary': summary, 'leads': leads})
    print(json.dumps(summary, indent=1))


# ------------------------------------------------------------------ report

def _withheld() -> set[str]:
    from app.services.atlas import normalise
    data = json.loads(REVIEW_SET.read_text())
    return {normalise(i['organisation']) for i in data['items']}


def report(args) -> None:
    from app.services.atlas import normalise
    withheld = _withheld()
    sample = _sample()
    ver = json.loads((PRIVATE / 'verification.json').read_text())['summary']
    rec = json.loads((PRIVATE / 'private-recheck.json').read_text()) if (PRIVATE / 'private-recheck.json').exists() else None
    ledger = json.loads((PRIVATE / 'private-ledger.json').read_text()) if (PRIVATE / 'private-ledger.json').exists() else {'runs': [], 'spent_cents': 0}
    util = json.loads((PRIVATE / 'utility.json').read_text())['summary'] if (PRIVATE / 'utility.json').exists() else None
    recon = json.loads((PRIVATE / 'reconstructed.json').read_text())

    def show(name: str) -> str:
        return 'an organisation in the blind review (withheld until it is locked)' if normalise(name) in withheld else name
    per = []
    for c in recon['contractors']:
        statuses = Counter(x['status']['code'] for x in c.get('contracts') or [])
        per.append({'contractor': show(c['name']), 'company_number': c.get('company_number'), 'stratum': c['stratum'], 'published_contracts': len(c.get('contracts') or []),
                    'customers': len({x['customer'] for x in c.get('contracts') or []}), 'in_term': statuses['in_term'] + statuses['end_approaching'] + statuses['extension_possible'],
                    'ending_within_18_months': statuses['end_approaching'] + statuses['extension_possible'], 'with_published_end': sum(1 for x in c.get('contracts') or [] if (x['dates'] or {}).get('end')),
                    'with_published_value': sum(1 for x in c.get('contracts') or [] if x.get('value'))})
    runs = [{'contractor': show(r['name']), 'cost_usd': round(r['cents'] / 100, 2), 'reported': (r['result'] or {}).get('reported'),
             'quote_verified': (r['result'] or {}).get('quote_verified'), 'unsupported_hidden': (r['result'] or {}).get('unsupported'),
             'historical': (r['result'] or {}).get('historical'), 'pages_reviewed': (r['result'] or {}).get('sources_reviewed'), 'error': r['error'] or None} for r in ledger['runs']]
    _write(PUBLIC / 'challenge-results.json', {'as_of': recon['as_of'], 'code': recon['code'], 'sample_seed': sample['seed'], 'contractors': per,
                                               'verification': ver, 'private_research': {'runs': runs, 'spent_usd': round(ledger['spent_cents'] / 100, 2),
                                                                                        'budget_usd': BUDGET_CENTS / 100, 'recheck': rec['summary'] if rec else None},
                                               'utility': util, 'withheld': 'Organisations that appear in the frozen blind-review set are withheld until that review is locked.'})
    with open(PRIVATE / 'review-sheet.csv', 'w', newline='') as fh:  # for a person: every reported relationship, and a sample of classifications
        w = csv.writer(fh)
        w.writerow(['item', 'claim', 'source', 'quote or record', 'automatic checks', 'correct? (yes / no / unsure)', 'notes'])
        if rec:
            for r in rec['rows']:
                if r['status'] == 'reported':
                    w.writerow([f"relationship {r['id']}", f"{r['supplier']} -> {r['customer']} ({r['kind']}{', via ' + r['intermediary'] if r['intermediary'] else ''})",
                                r['source_url'], r['quote'], f"quote on page: {r['quote_on_live_page']}; customer named: {r['customer_on_live_page']}", '', ''])
        rng = random.Random(f"{sample['seed']}:classification")
        contracts = [(c['name'], x) for c in recon['contractors'] for x in c.get('contracts') or []]
        for name, x in rng.sample(contracts, min(30, len(contracts))):
            w.writerow([f"contract {x['id']}", f"{name} -> {x['customer']}: {', '.join(s['label'] for s in x['services'])}; {x['scope']['label']}; {x['status']['label']}",
                        (x['sources'] or [{}])[0].get('url', ''), x['title'], '', '', ''])
    (PRIVATE / 'review-sheet.csv').chmod(0o600)
    print(f"Wrote {PUBLIC / 'challenge-results.json'} and the private review sheet {PRIVATE / 'review-sheet.csv'}.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('step', choices=['freeze', 'reconstruct', 'verify', 'private', 'recheck', 'utility', 'report'])
    p.add_argument('--replace', action='store_true', help='Only with freeze: replace an unused sample (never after results exist)')
    args = p.parse_args()
    {'freeze': freeze, 'reconstruct': reconstruct, 'verify': verify, 'private': private, 'recheck': recheck, 'utility': utility, 'report': report}[args.step](args)


if __name__ == '__main__':
    main()
