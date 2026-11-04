"""Contracts Finder notice search (Open Government Licence v3).

https://www.contractsfinder.service.gov.uk/apidocumentation/Notices/1/POST-Published-Notice-Search
The endpoint has no working pagination, so a truncated date window is split in
half and asked again. Results are bounded by an explicit request budget.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
import html
import re
import time
import httpx

API_URL = 'https://www.contractsfinder.service.gov.uk/api/rest/2/search_notices/json'
NOTICE_URL = 'https://www.contractsfinder.service.gov.uk/Notice/'
PAGE_SIZE = 500
MIN_WINDOW_DAYS = 7
DESCRIPTION_LIMIT = 4000
UUID = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')


@dataclass
class Budget:
    requests_left: int
    requests_made: int = 0
    truncated_hits: int = 0
    waits: int = 0
    exhausted: bool = False


def _text(value, limit=500):
    return ' '.join(html.unescape(value).split())[:limit] if isinstance(value, str) else ''


def _day(value):
    try:
        return date.fromisoformat(value[:10]) if isinstance(value, str) else None
    except ValueError:
        return None


def _suppliers(value):
    names = [_text(x, 200) for x in value.split(',')] if isinstance(value, str) else []
    return list(dict.fromkeys(x for x in names if x))


def normalise(item: dict) -> dict | None:
    """Reduce one search result to the published fields a lead needs."""
    notice_id = item.get('id') if isinstance(item, dict) else None
    title, buyer = _text(item.get('title')), _text(item.get('organisationName'), 250) if isinstance(item, dict) else ''
    if not isinstance(notice_id, str) or not UUID.fullmatch(notice_id) or not title or not buyer:
        return None
    value = item.get('awardedValue')
    published = _day(item.get('publishedDate'))
    return {'id': notice_id, 'url': NOTICE_URL + notice_id, 'title': title, 'buyer': buyer,
            'description': _text(item.get('description'), DESCRIPTION_LIMIT),
            'type': _text(item.get('noticeType'), 40), 'status': _text(item.get('noticeStatus'), 40),
            'published': published.isoformat() if published else None,
            'start': (_day(item.get('start')) or '') and _day(item.get('start')).isoformat(),
            'end': (_day(item.get('end')) or '') and _day(item.get('end')).isoformat(),
            'approach': (_day(item.get('approachMarketDate')) or '') and _day(item.get('approachMarketDate')).isoformat(),
            'value': float(value) if isinstance(value, (int, float)) and value > 0 else None,
            'suppliers': _suppliers(item.get('awardedSupplier')),
            'cpv': sorted(set(str(item.get('cpvCodes') or '').split())),
            'region': _text(item.get('regionText') or item.get('region'), 120), 'postcode': _text(item.get('postcode'), 12)}


def _search(client, criteria: dict, start: date, end: date) -> dict:
    body = {'searchCriteria': {**criteria, 'publishedFrom': start.isoformat(), 'publishedTo': end.isoformat()}, 'size': PAGE_SIZE}
    response = client.post(API_URL, json=body)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get('noticeList'), list):
        raise ValueError('Invalid Contracts Finder search response')
    return payload


def collect(client, criteria: dict, start: date, end: date, budget: Budget, *, pause: float = 1.5, sleep=time.sleep) -> list[dict]:
    """Return normalised notices for a date range, splitting truncated windows."""
    found, pending = [], [(start, end)]
    while pending:
        if budget.requests_left <= 0:
            budget.exhausted = True
            return found
        first, last = pending.pop()
        budget.requests_left -= 1
        budget.requests_made += 1
        payload = _search(client, criteria, first, last)
        sleep(pause)
        rows, hits = payload['noticeList'], payload.get('hitCount') or 0
        if len(rows) < hits and (last - first).days >= MIN_WINDOW_DAYS:
            middle = first + (last - first) // 2
            pending += [(middle + timedelta(days=1), last), (first, middle)]
            continue
        budget.truncated_hits += max(0, hits - len(rows))
        found += [notice for row in rows if isinstance(row, dict) and (notice := normalise(row.get('item')))]
    return found


def client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(90, connect=10), follow_redirects=False,
                        headers={'User-Agent': 'SalesIntel public-market-monitor/1.0', 'Accept': 'application/json'})
