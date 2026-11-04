"""Contracts Finder public OCDS release packages (Open Government Licence v3).

https://www.contractsfinder.service.gov.uk/apidocumentation/Notices/1/GET-Published-Notice-OCDS-Search
One bounded request at a time. Source URLs are constructed from validated IDs.
"""
from __future__ import annotations
import json
import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, quote, urlsplit
import httpx
from app.ingestion.find_a_tender import MAX_RESPONSE_BYTES

API_URL = 'https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search'
CURSOR = re.compile(r'^[A-Za-z0-9=]{1,300}$')
UUID = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
OCID = re.compile(r'^ocds-b5fd17-[0-9a-fA-F-]{36}$')
RELEASE_ID = re.compile(r'^([0-9a-fA-F-]{36})-[0-9]{1,20}$')
SAFE_RELEASE_ID = re.compile(r'^[A-Za-z0-9_-]{1,240}$')


def _next_cursor(links):
    url = links.get('next') if isinstance(links, dict) else None
    if not url:
        return None
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != 'www.contractsfinder.service.gov.uk' or parsed.path != '/Published/Notices/OCDS/Search':
        raise ValueError('Unexpected Contracts Finder pagination URL')
    values = parse_qs(parsed.query).get('cursor', [])
    if len(values) != 1 or not CURSOR.fullmatch(values[0]):
        raise ValueError('Invalid Contracts Finder cursor')
    return values[0]


def fetch_page(*, updated_from: datetime, updated_to: datetime, cursor: str | None = None, client=None):
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(25, connect=10), follow_redirects=False,
                                   headers={'User-Agent': 'SalesIntel public-market-monitor/1.0', 'Accept': 'application/json'})
    try:
        params = {'limit': 100, 'publishedFrom': updated_from.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%S'),
                  'publishedTo': updated_to.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%S')}
        if cursor:
            if not CURSOR.fullmatch(cursor):
                raise ValueError('Invalid stored Contracts Finder cursor')
            params['cursor'] = cursor
        with client.stream('GET', API_URL, params=params, follow_redirects=False) as response:
            response.raise_for_status()
            parts, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise ValueError('Contracts Finder page exceeded response size limit')
                parts.append(chunk)
        payload = json.loads(b''.join(parts))
        if not isinstance(payload, dict) or not isinstance(payload.get('releases'), list) or len(payload['releases']) > 100:
            raise ValueError('Invalid Contracts Finder release package')
        next_cursor = _next_cursor(payload.get('links'))
        if next_cursor and next_cursor == cursor:
            raise ValueError('Contracts Finder returned a repeated cursor')
        return payload['releases'], next_cursor
    finally:
        if owned:
            client.close()


def record_for_release(release: dict, retrieved_at: datetime) -> dict | None:
    if not isinstance(release, dict):
        return None
    release_id, ocid = release.get('id'), release.get('ocid')
    if not isinstance(release_id, str) or not SAFE_RELEASE_ID.fullmatch(release_id) or not isinstance(ocid, str) or not OCID.fullmatch(ocid):
        return None
    match = RELEASE_ID.fullmatch(release_id)
    source_url = (f'https://www.contractsfinder.service.gov.uk/Notice/{match.group(1)}'
                  if match and UUID.fullmatch(match.group(1))
                  else f'https://www.contractsfinder.service.gov.uk/Published/OCDS/Release/{quote(release_id, safe="")}')
    try:
        published = datetime.fromisoformat(str(release['date']).replace('Z', '+00:00'))
        if published.tzinfo is None:
            return None
    except (ValueError, KeyError, TypeError):
        return None
    def redact(value):
        if isinstance(value, dict):
            return {k: redact(v) for k, v in value.items() if k not in ('contactPoint', 'contactPoints', 'person', 'persons')}
        if isinstance(value, list):
            return [redact(v) for v in value]
        return value
    return {'source_key': 'contracts_finder', 'release_id': release_id, 'ocid': ocid,
            'source_url': source_url,
            'published_at': published.astimezone(UTC), 'retrieved_at': retrieved_at, 'raw': redact(release)}
