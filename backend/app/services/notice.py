"""What a published notice already states.

A buyer's notice usually answers the first questions a salesperson asks: what it is worth, when tenders are due, how
bids are scored, how long the contract runs, where the work is, where the documents are and who won last time. This
module reads those answers from the stored record. It never estimates, and it never fills a gap: a field the notice
does not publish is simply absent. Every value keeps the wording the buyer used and a basis saying which part of the
notice it came from.

Pure functions over one OCDS release, plus a small in-process cache keyed by source revision id: a revision is
immutable (a change in the source creates a new revision), so its facts never go stale.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_network import SourceRevision

# UK ITL (formerly NUTS) level-one areas, as Find a Tender and Public Contracts Scotland publish them.
ITL1 = {'UKC': 'North East', 'UKD': 'North West', 'UKE': 'Yorkshire and the Humber', 'UKF': 'East Midlands', 'UKG': 'West Midlands',
        'UKH': 'East of England', 'UKI': 'London', 'UKJ': 'South East', 'UKK': 'South West', 'UKL': 'Wales', 'UKM': 'Scotland',
        'UKN': 'Northern Ireland'}
METHOD = {'open': 'Open competition', 'selective': 'Restricted to shortlisted suppliers', 'limited': 'Limited competition',
          'direct': 'Direct award without competition'}
DOCUMENT = {'contractNotice': 'Contract notice', 'tenderNotice': 'Tender notice', 'biddingDocuments': 'Tender documents',
            'technicalSpecifications': 'Specification', 'awardNotice': 'Award notice', 'contractSigned': 'Signed contract',
            'marketEngagementNotice': 'Market engagement notice', 'plannedProcurementNotice': 'Planned procurement notice',
            'evaluationCriteria': 'Evaluation criteria', 'clarifications': 'Clarifications', 'contractDraft': 'Draft contract',
            'procurementPlan': 'Procurement plan', 'pipelineNotice': 'Pipeline notice'}
PLACEHOLDER_BELOW = 100  # buyers enter 0, 0.01 or 1 when a field is mandatory and the value is not decided
_URL = re.compile(r'https?://[^\s<>"\')\]]+', re.I)
_CACHE: dict[tuple[int, str], dict] = {}
_CACHE_MAX = 4000
_ISO_DATE = re.compile(r'\b(19\d\d|20\d\d)-(\d\d)-(\d\d)\b')


def readable(text: Any) -> str:
    """A stored sentence for people: 14 February 2027 rather than 2027-02-14, and one full stop, never two."""
    def long(match: re.Match) -> str:
        try:
            d = date(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            return match[0]
        return f'{d.day} {d:%B %Y}'
    return re.sub(r'(?<!\.)\.\.(?!\.)', '.', _ISO_DATE.sub(long, str(text or '')))


def clip(text: Any, limit: int) -> str:
    """A long published passage cut at a word, and marked as cut: never half a word passed off as the end of the notice."""
    s = str(text or '').strip()
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(None, 1)[0] if ' ' in s[:limit] else s[:limit]
    return cut.rstrip(' ,;:-(') + '…'


def _d(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _l(value: Any) -> list:
    return [v for v in value if v is not None] if isinstance(value, list) else []


def _s(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value)).strip() if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ''


def _release(raw: dict) -> dict:
    releases = _d(raw).get('releases')
    if isinstance(releases, list) and releases:
        return _d(releases[0])
    return _d(raw)


def _when(value: Any) -> datetime | None:
    text = _s(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        try:
            return datetime.fromisoformat(text[:10])
        except ValueError:
            return None


def _day(value: Any) -> str:
    at = _when(value)
    return at.date().isoformat() if at else ''


def _amount(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if PLACEHOLDER_BELOW <= n < 1e12 else None


def money(amount: float | None, currency: str = 'GBP') -> str:
    if amount is None:
        return ''
    sign = {'GBP': '£', 'EUR': '€', 'USD': '$'}.get(currency or 'GBP', '')
    if amount >= 1_000_000:
        text = f'{amount / 1_000_000:.1f}'.rstrip('0').rstrip('.') + 'm'
    elif amount >= 10_000:
        text = f'{amount / 1000:.0f}k'
    else:
        text = f'{amount:,.0f}'
    return f'{sign}{text}' if sign else f'{text} {currency}'


def _url(value: Any) -> str:
    m = _URL.search(_s(value))
    return m.group(0).rstrip('.,;') if m else ''


def region_label(value: Any) -> str:
    """A published region as a plain name: 'UKM82' and 'UKM' are Scotland; a name is kept as written."""
    text = _s(value)
    if not text:
        return ''
    if re.fullmatch(r'UK[A-N][0-9A-Z]{0,3}', text):
        return ITL1.get(text[:3], '')
    if text.upper() in ('UK', 'GB'):
        return 'United Kingdom'
    if re.search(r'[,;/]', text):  # a field listing several regions says nothing about where the buyer is
        parts = {part.strip() for part in re.split(r'[,;/]', text) if part.strip()}
        text = parts.pop() if len(parts) == 1 else ''
    if text.lower() in ('any region', 'all regions', 'not specified', 'n/a', 'none'):
        return ''
    return text if len(text) > 2 and not text.isupper() else ''


def place(buyer: dict) -> str:
    """'Town, Region' from a buyer's published address, each said once."""
    town, region = buyer.get('locality') or '', buyer.get('region') or ''
    town = town.title() if town.isupper() else town
    return region if town.lower() == region.lower() else ', '.join(x for x in (town, region) if x)


# ------------------------------------------------------------------ parts

def _buyer(rel: dict) -> dict:
    wanted = _s(_d(rel.get('buyer')).get('id'))
    parties = [p for p in _l(rel.get('parties')) if isinstance(p, dict)]
    party = next((p for p in parties if 'buyer' in _l(p.get('roles'))), None) or next((p for p in parties if wanted and _s(p.get('id')) == wanted), None)
    if not party:
        name = _s(_d(rel.get('buyer')).get('name'))
        return {'name': name} if name else {}
    address, details = _d(party.get('address')), _d(party.get('details'))
    kinds = [_s(c.get('description')) for c in _l(details.get('classifications')) if isinstance(c, dict) and _s(c.get('description'))]
    postcode = _s(address.get('postalCode')).upper()
    region = region_label(address.get('region'))
    if region in ('', 'England', 'United Kingdom') and postcode:
        from app.services.atlas import region_of  # the postcode area is more exact than 'England', and is the buyer's own address
        region = region_of(postcode) or region
    out = {'name': _s(party.get('name')), 'locality': _s(address.get('locality')), 'postcode': postcode,
           'region': region, 'website': _url(details.get('url')), 'type': kinds[0] if kinds else ''}
    return {k: v for k, v in out.items() if v}


def _value(rel: dict, stage: str) -> dict | None:
    tender = _d(rel.get('tender'))
    if stage != 'award':
        v = _d(tender.get('value'))
        net, gross = _amount(v.get('amount')), _amount(v.get('amountGross'))
        if net or gross:
            amount = net or gross
            basis = 'Estimated value in the notice' + (', excluding VAT' if net and gross and gross > net else ', including VAT' if gross and not net else '')
            return {'amount': amount, 'gross': gross, 'currency': _s(v.get('currency')) or 'GBP', 'basis': basis, 'kind': 'estimate',
                    'label': money(amount, _s(v.get('currency')) or 'GBP')}
        lots = [_amount(_d(_d(lot).get('value')).get('amount')) for lot in _l(tender.get('lots'))]
        lots = [n for n in lots if n]
        if lots:
            return {'amount': sum(lots), 'gross': None, 'currency': 'GBP', 'basis': f'Sum of the estimated values of {len(lots)} lot{"s" if len(lots) != 1 else ""}',
                    'kind': 'estimate', 'label': money(sum(lots))}
        return None
    awards = [_d(a) for a in _l(rel.get('awards')) if _s(_d(a).get('status')) not in ('unsuccessful', 'cancelled')]
    found = [(_amount(_d(a.get('value')).get('amount')) or _amount(_d(a.get('value')).get('amountGross')), _s(_d(a.get('value')).get('currency')) or 'GBP') for a in awards]
    found = [f for f in found if f[0]]
    basis = 'Award value in the notice'
    if not found:
        found = [(_amount(_d(_d(c).get('value')).get('amount')), _s(_d(_d(c).get('value')).get('currency')) or 'GBP') for c in _l(rel.get('contracts'))]
        found = [f for f in found if f[0]]
        basis = 'Contract value in the notice'
    if not found:
        return None
    total = sum(f[0] for f in found)
    if len(found) > 1:
        basis += f', summed over {len(found)} awards'
    return {'amount': total, 'gross': None, 'currency': found[0][1], 'basis': basis, 'kind': 'award', 'label': money(total, found[0][1])}


def _months_between(start: str, end: str) -> int | None:
    try:
        a, b = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        return None
    months = round((b - a).days / 30.44)
    return months if 0 < months <= 600 else None


def _span(months: int | None) -> str:
    if not months:
        return ''
    if months % 12 == 0:
        years = months // 12
        return f'{years} year{"s" if years != 1 else ""}'
    return f'{months} months'


def _term(rel: dict, stage: str) -> dict | None:
    tender = _d(rel.get('tender'))
    lots = [_d(lot) for lot in _l(tender.get('lots'))]
    periods: list[dict] = []
    if stage == 'award':
        periods = [_d(_d(a).get('contractPeriod')) for a in _l(rel.get('awards'))] + [_d(_d(c).get('period')) for c in _l(rel.get('contracts'))]
    periods = [p for p in periods if p] or [p for p in [_d(tender.get('contractPeriod'))] + [_d(lot.get('contractPeriod')) for lot in lots] if p]
    if not periods:
        return None
    first = periods[0]
    start, end, extent = _day(first.get('startDate')), _day(first.get('endDate')), _day(first.get('maxExtentDate'))
    months = _months_between(start, end) if start and end else None
    if not months:
        try:
            days = float(first.get('durationInDays'))
            months = round(days / 30.44) if 0 < days < 20000 else None
        except (TypeError, ValueError):
            months = None
    renewal = next((_s(_d(lot.get('renewal')).get('description')) for lot in lots if _s(_d(lot.get('renewal')).get('description'))), '')
    has_renewal = any(lot.get('hasRenewal') is True for lot in lots) or bool(renewal)
    if not (months or start or end):
        return None
    keys = {(_day(p.get('startDate')), _day(p.get('endDate')), _s(p.get('durationInDays'))) for p in periods}
    parts = [_span(months)] if months else []
    if extent and end and extent > end:
        more = _months_between(end, extent)
        parts.append(f'can run to {extent[:4]}' if not more else f'plus up to {_span(more)} of extensions')
    elif has_renewal:
        parts.append('extension options')
    return {'start': start, 'end': end, 'max_end': extent if extent and extent != end else '', 'months': months, 'renewal': renewal[:400],
            'has_renewal': has_renewal, 'varies_by_lot': len(keys) > 1, 'label': ', '.join(parts) or (f'to {end}' if end else '')}


def _deadlines(rel: dict) -> list[dict]:
    tender, planning = _d(rel.get('tender')), _d(rel.get('planning'))
    out = []

    def add(key, label, value, note=''):
        at = _when(value)
        if at:
            timed = 'T' in _s(value) and (at.hour, at.minute) not in ((0, 0), (23, 59))
            out.append({'key': key, 'label': label, 'date': at.date().isoformat(), 'time': at.strftime('%H:%M') if timed else '', 'note': note[:300]})

    for m in _l(planning.get('milestones')):
        m = _d(m)
        if _s(m.get('type')) == 'engagement':
            add('engagement', 'Market engagement closes', m.get('dueDate'), _s(m.get('description')))
    add('enquiries', 'Questions to the buyer by', _d(tender.get('enquiryPeriod')).get('endDate'))
    add('submission', 'Tenders due', _d(tender.get('tenderPeriod')).get('endDate'))
    add('notice_expected', 'Tender notice expected', _d(tender.get('communication')).get('futureNoticeDate'))
    award = _d(tender.get('awardPeriod'))
    add('award', 'Award decision expected', award.get('endDate') or award.get('startDate'))
    due = next((d for d in out if d['key'] == 'submission'), None)
    seen, unique = set(), []
    for item in sorted(out, key=lambda d: d['date']):
        if item['key'] == 'award' and due and item['date'] <= due['date']:
            continue  # some portals copy the tender deadline into the award period: that is not a decision date
        if item['key'] not in seen:
            seen.add(item['key'])
            unique.append(item)
    return unique


def _weight(criterion: dict) -> float | None:
    for n in _l(criterion.get('numbers')):
        n = _d(n)
        if _s(n.get('weight')).lower().startswith('percentage') or not n.get('weight'):
            try:
                value = float(n.get('number'))
            except (TypeError, ValueError):
                continue
            if 0 < value <= 100:
                return value
    m = re.fullmatch(r'(\d{1,3}(?:\.\d+)?)\s*%?', _s(criterion.get('description')))
    if m and 0 < float(m.group(1)) <= 100:
        return float(m.group(1))
    return None


def _split_from_name(name: str) -> list[tuple[str, float]] | None:
    """'Quality / Price - 60/40' states the split in the criterion's own name."""
    m = re.search(r'(quality|technical|price|cost|commercial)\s*(?:/|and|&|:)\s*(quality|technical|price|cost|commercial)\D{0,12}(\d{1,3})\s*%?\s*[/:]\s*(\d{1,3})', name, re.I)
    if not m or int(m.group(3)) + int(m.group(4)) != 100:
        return None
    return [(m.group(1).capitalize(), float(m.group(3))), (m.group(2).capitalize(), float(m.group(4)))]


def _num(value: float) -> str:
    return f'{value:.0f}' if abs(value - round(value)) < 0.05 else f'{value:.1f}'


def _criteria(rel: dict) -> dict | None:
    tender = _d(rel.get('tender'))
    lots = [_d(lot) for lot in _l(tender.get('lots'))]
    per_lot = []
    for lot in lots:
        items = []
        for c in _l(_d(lot.get('awardCriteria')).get('criteria')):
            c = _d(c)
            kind = _s(c.get('type')).lower()
            name = _s(c.get('name')) or kind.capitalize()
            weight = _weight(c)
            if not (name or weight):
                continue
            detail = _s(c.get('description'))
            items.append({'type': kind if kind in ('quality', 'price', 'cost') else 'other', 'name': name[:120], 'weight': weight,
                          'detail': '' if re.fullmatch(r'\d{1,3}(?:\.\d+)?\s*%?', detail) else detail[:300]})
        if items:
            per_lot.append({'lot': _s(lot.get('id')), 'title': _s(lot.get('title'))[:140], 'items': items})
    if not per_lot:
        return None

    def split(items: list[dict]) -> list[dict] | None:
        if len(items) == 1:
            named = _split_from_name(items[0]['name'])
            if named:
                return [{'label': label, 'weight': weight} for label, weight in named]
        weighted = [i for i in items if i['weight'] is not None]
        if not weighted or len(weighted) != len(items):
            return None
        total = sum(i['weight'] for i in weighted)
        if not 99 <= total <= 101:
            return None
        quality = sum(i['weight'] for i in weighted if i['type'] in ('quality', 'other'))
        price = sum(i['weight'] for i in weighted if i['type'] in ('price', 'cost'))
        return [{'label': 'Quality', 'weight': quality}, {'label': 'Price', 'weight': price}] if quality and price else None

    splits = [split(lot['items']) for lot in per_lot]
    first = splits[0]
    same = all(s == first for s in splits)
    summary = ''
    if first and same:
        summary = ' / '.join(f"{s['label']} {_num(s['weight'])}%" for s in first)
    elif any(splits):
        summary = 'Weightings differ by lot'
    return {'split': first if first and same else None, 'summary': summary, 'same_for_all_lots': same, 'lots': per_lot[:12], 'lot_count': len(per_lot)}


def _procedure(rel: dict) -> dict:
    tender = _d(rel.get('tender'))
    lots = [_d(lot) for lot in _l(tender.get('lots'))]
    method = _s(tender.get('procurementMethod')).lower()
    techniques = _d(tender.get('techniques'))
    framework = _d(techniques.get('frameworkAgreement'))
    suit = [_d(tender.get('suitability'))] + [_d(lot.get('suitability')) for lot in lots]
    out: dict[str, Any] = {'method': method, 'method_label': METHOD.get(method, ''), 'details': _s(tender.get('procurementMethodDetails'))[:160],
                           'category': _s(tender.get('mainProcurementCategory')).lower()}
    if isinstance(tender.get('aboveThreshold'), bool):
        out['above_threshold'] = tender['aboveThreshold']
    if techniques.get('hasFrameworkAgreement') is True or framework:
        out['framework'] = True
        try:
            places = float(framework.get('maximumParticipants'))
            if 1 <= places <= 500:  # some portals publish an overflow number where no limit was set
                out['framework_places'] = int(places)
        except (TypeError, ValueError):
            pass
    if any(s.get('sme') is True for s in suit):
        out['sme_suitable'] = True
    if any(s.get('vcse') is True for s in suit):
        out['vcse_suitable'] = True
    try:
        most = int(float(_d(tender.get('lotDetails')).get('maximumLotsBidPerSupplier')))
        if 0 < most < 100:
            out['max_lots_per_supplier'] = most
    except (TypeError, ValueError):
        pass
    reserved = _l(_d(tender.get('otherRequirements')).get('reservedParticipation'))
    if reserved:
        out['reserved'] = [_s(r) for r in reserved if _s(r)][:3]
    return {k: v for k, v in out.items() if v not in ('', None, [])}


def _requirements(rel: dict) -> list[str]:
    """Conditions of participation the notice spells out (many only say 'see the documents')."""
    tender = _d(rel.get('tender'))
    found = []
    for c in _l(_d(tender.get('selectionCriteria')).get('criteria')):
        text = _s(_d(c).get('description'))
        if len(text) > 20:
            found.append(text[:400])
    return found[:5]


def _lots(rel: dict) -> list[dict]:
    out = []
    for lot in _l(_d(rel.get('tender')).get('lots')):
        lot = _d(lot)
        title = _s(lot.get('title'))
        if not title:
            continue
        amount = _amount(_d(lot.get('value')).get('amount'))
        out.append({'id': _s(lot.get('id')), 'title': clip(title, 160), 'description': clip(lot.get('description'), 300), 'value': amount,
                    'value_label': money(amount)})
    return out if len(out) > 1 else []


def _documents(rel: dict) -> list[dict]:
    groups = [_l(_d(rel.get('tender')).get('documents')), _l(_d(rel.get('planning')).get('documents'))] + [_l(_d(a).get('documents')) for a in _l(rel.get('awards'))]
    out, seen = [], set()
    for group in groups:
        for doc in group:
            doc = _d(doc)
            url = _url(doc.get('url'))
            if not url or url in seen:
                continue
            seen.add(url)
            kind = _s(doc.get('documentType'))
            out.append({'type': kind, 'label': DOCUMENT.get(kind, '') or _s(doc.get('title'))[:90] or 'Document', 'title': _s(doc.get('title'))[:140],
                        'url': url, 'published': _day(doc.get('datePublished'))})
    return out[:8]


def _cpv(rel: dict) -> list[dict]:
    tender = _d(rel.get('tender'))
    found = [_d(tender.get('classification'))]
    for holder in _l(tender.get('items')) + [i for a in _l(rel.get('awards')) for i in _l(_d(a).get('items'))]:
        holder = _d(holder)
        found.append(_d(holder.get('classification')))
        found.extend(_d(c) for c in _l(holder.get('additionalClassifications')))
    out, seen = [], set()
    for c in found:
        code = _s(c.get('id'))
        if code and code not in seen and _s(c.get('scheme')).upper() in ('CPV', ''):
            seen.add(code)
            out.append({'id': code, 'description': _s(c.get('description'))[:120]})
    return out[:8]


def _places(rel: dict) -> list[str]:
    tender = _d(rel.get('tender'))
    found: list[str] = []
    for holder in _l(tender.get('items')) + [i for a in _l(rel.get('awards')) for i in _l(_d(a).get('items'))]:
        for address in _l(_d(holder).get('deliveryAddresses')):
            label = region_label(_d(address).get('region'))
            if label and label not in found:
                found.append(label)
    return found[:6]


def _bids(rel: dict) -> dict | None:
    stats = [_d(s) for s in _l(_d(rel.get('bids')).get('statistics'))]

    def values(measure):
        out = []
        for s in stats:
            if _s(s.get('measure')) == measure:
                try:
                    out.append(float(s.get('value')))
                except (TypeError, ValueError):
                    pass
        return out

    counts = [int(v) for v in values('bids') if 0 < v < 1000]
    if not counts:
        return None
    low, high = values('lowestValidBidValue'), values('highestValidBidValue')
    low = [v for v in low if v >= PLACEHOLDER_BELOW]
    high = [v for v in high if v >= PLACEHOLDER_BELOW]
    if len(counts) == 1:
        label = f'{counts[0]} bid{"s" if counts[0] != 1 else ""} received'
    elif min(counts) == max(counts):
        label = f'{counts[0]} bid{"s" if counts[0] != 1 else ""} on each of {len(counts)} lots'
    else:
        label = f'{min(counts)} to {max(counts)} bids per lot across {len(counts)} lots'
    out = {'lots': len(counts), 'fewest': min(counts), 'most': max(counts), 'label': label}
    if low and high and len(low) == 1 and len(high) == 1 and high[0] >= low[0]:
        out['bid_range'] = {'low': low[0], 'high': high[0], 'label': f'Valid bids ranged from {money(low[0])} to {money(high[0])}'}
    return out


def _suppliers(rel: dict) -> list[dict]:
    scale = {}
    for p in _l(rel.get('parties')):
        p = _d(p)
        size = _s(_d(p.get('details')).get('scale')).lower()
        if size:
            scale[_s(p.get('id'))] = scale[_s(p.get('name')).casefold()] = size
    out, seen = [], set()
    for a in _l(rel.get('awards')):
        a = _d(a)
        if _s(a.get('status')) in ('unsuccessful', 'cancelled'):
            continue
        for s in _l(a.get('suppliers')):
            s = _d(s)
            name = _s(s.get('name'))
            if name and name.casefold() not in seen:
                seen.add(name.casefold())
                out.append({'name': name[:140], 'size': scale.get(_s(s.get('id'))) or scale.get(name.casefold()) or ''})
    return out[:12]


def stage_of(rel: dict) -> str:
    tags = {_s(t).lower() for t in _l(rel.get('tag'))}
    tender = _d(rel.get('tender'))
    if rel.get('awards') or rel.get('contracts') or tags & {'award', 'contract', 'awardupdate', 'contractupdate'}:
        if any(_s(_d(a).get('status')) != 'pending' for a in _l(rel.get('awards'))) or rel.get('contracts'):
            return 'award'
    if _s(tender.get('status')).lower() in ('planning', 'planned') or tags & {'planning', 'planningupdate'}:
        return 'planning'
    return 'tender' if tender else 'award' if rel.get('awards') else 'planning'


def facts(raw: dict, *, source_url: str = '', source: str = '') -> dict:
    """Everything this one notice states, in the shape the brief shows. Absent keys mean the notice does not say."""
    rel = _release(raw or {})
    tender = _d(rel.get('tender'))
    stage = stage_of(rel)
    description = _s(tender.get('description')) or _s(rel.get('description')) or next((_s(_d(a).get('description')) for a in _l(rel.get('awards')) if _s(_d(a).get('description'))), '')
    out = {
        'stage': stage, 'title': _s(tender.get('title')) or next((_s(_d(a).get('title')) for a in _l(rel.get('awards')) if _s(_d(a).get('title'))), ''),
        'description': clip(description, 1200), 'reference': _s(tender.get('id'))[:80] or _s(rel.get('ocid'))[:80],
        'buyer': _buyer(rel), 'value': _value(rel, stage), 'term': _term(rel, stage), 'deadlines': _deadlines(rel) if stage != 'award' else [],
        'procedure': _procedure(rel), 'criteria': _criteria(rel) if stage != 'planning' or tender.get('lots') else None,
        'requirements': _requirements(rel), 'lots': _lots(rel), 'portal': _url(tender.get('submissionMethodDetails')) if stage != 'award' else '',
        'documents': _documents(rel), 'cpv': _cpv(rel), 'places': _places(rel), 'bids': _bids(rel), 'suppliers': _suppliers(rel) if stage == 'award' else [],
        'source_url': source_url, 'source': source,
    }
    return {k: v for k, v in out.items() if v not in (None, '', [], {})}


def for_revisions(db: Session, revision_ids: list[int]) -> dict[int, dict]:
    """Facts for many stored notices. Parsed once per process: the cache is keyed by the notice's own content hash, so a
    different database, or a revision id reused by one, can never be served another notice's facts."""
    ids = [r for r in dict.fromkeys(revision_ids) if r]
    found: dict[int, dict] = {}
    for start in range(0, len(ids), 400):
        chunk = ids[start:start + 400]
        hashes = dict(db.execute(select(SourceRevision.id, SourceRevision.content_hash).where(SourceRevision.id.in_(chunk))).all())
        wanted = [r for r in chunk if r in hashes and (r, hashes[r]) not in _CACHE]
        if wanted:
            for rid, raw, url, key in db.execute(select(SourceRevision.id, SourceRevision.raw, SourceRevision.source_url, SourceRevision.source_key)
                                                 .where(SourceRevision.id.in_(wanted))):
                if len(_CACHE) >= _CACHE_MAX:
                    _CACHE.clear()
                _CACHE[(rid, hashes[rid])] = facts(raw or {}, source_url=url or '', source=key or '')
        found.update({r: _CACHE[(r, hashes[r])] for r in chunk if (r, hashes.get(r)) in _CACHE})
    return {r: found.get(r, {}) for r in ids}


def cited(db: Session, records: list[list]) -> list[list[dict]]:
    """For each record's evidence, the facts of the stored notices it cites, in the order cited (the first four). A notice is read
    only where the evidence names that notice's own record key: evidence drawn from elsewhere (an inferred signal, a company
    filing, a hand-entered note) carries ids that are not notice ids, and must never borrow another notice's facts."""
    pairs = [[(e['source_revision_id'], e.get('record_key') or '') for e in evidence or []
              if isinstance(e, dict) and isinstance(e.get('source_revision_id'), int) and e['source_revision_id'] > 0][:4] for evidence in records]
    ids = list(dict.fromkeys(r for p in pairs for r, _ in p))
    keys: dict[int, str] = {}
    for start in range(0, len(ids), 400):
        keys.update(dict(db.execute(select(SourceRevision.id, SourceRevision.record_key).where(SourceRevision.id.in_(ids[start:start + 400]))).all()))
    known = for_revisions(db, [r for p in pairs for r, k in p if k and keys.get(r) == k])
    return [[known[r] for r, k in p if k and keys.get(r) == k and known.get(r)] for p in pairs]


def for_revision(db: Session, revision_id: int | None) -> dict:
    """The facts of one stored notice."""
    return for_revisions(db, [revision_id]).get(revision_id, {}) if revision_id else {}


def headline(f: dict, today: date | None = None) -> dict:
    """The few facts a list row can carry: value, the next dated step, place, lots."""
    today = today or date.today()
    upcoming = [d for d in f.get('deadlines') or [] if d['date'] >= today.isoformat() and d['key'] in ('engagement', 'submission', 'notice_expected')]
    nxt = upcoming[0] if upcoming else None
    buyer = f.get('buyer') or {}
    places = f.get('places') or []
    where = place(buyer) or (places[0] if len(places) == 1 else '')
    out = {'value': (f.get('value') or {}).get('label') or '', 'value_amount': (f.get('value') or {}).get('amount'),
           'value_kind': (f.get('value') or {}).get('kind') or '',
           'deadline': {'key': nxt['key'], 'label': nxt['label'], 'date': nxt['date'], 'days': (date.fromisoformat(nxt['date']) - today).days} if nxt else None,
           'place': where,
           'lots': len(f.get('lots') or []), 'scoring': (f.get('criteria') or {}).get('summary') or '',
           'term': (f.get('term') or {}).get('label') or ''}
    return {k: v for k, v in out.items() if v not in (None, '', 0)}
