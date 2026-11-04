"""Bounded acquisition of Find a Tender OCDS releases for market monitoring.

Official documentation: https://www.find-tender.service.gov.uk/apidocumentation/1.0/GET-ocdsReleasePackages
The feed is open under the Open Government Licence. This local sector filter is
only a discovery aid; inclusion is not proof that a supplier provides a service.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import httpx
from app.ingestion.find_a_tender import API_URL, MAX_RESPONSE_BYTES, _next_cursor

NOTICE_ID = re.compile(r'^[0-9]{1,12}-[0-9]{4}$')
OCID = re.compile(r'^ocds-[A-Za-z0-9-]{4,240}$')
SECTOR = re.compile(
    r'\b(?:fire\s+(?:alarms?|detection|protection|safety|suppression|extinguishers?|doors?|stopping|dampers?|systems?|equipment|risk\s+assessments?)|'
    r'(?:fire\s*(?:and|&)\s*security|security\s*(?:and|&)\s*fire)|'
    r'(?:electronic\s+)?security\s+(?:systems?|alarms?|maintenance|equipment)|'
    r'cctv|intruder\s+alarms?|access\s+control|sprinklers?|water\s+mist|smoke\s+control|'
    r'compartmentation|emergency\s+lighting|voice\s+alarms?)\b', re.I)

SPECIFIC_CPV = {'31625100', '31625200', '31625300', '35111500', '35120000',
                '35125300', '45312100', '45312200', '45343000', '50413200',
                '50610000', '79711000', '42961100', '38431200', '32235000'}
GENERIC_PROJECT = re.compile(r'\b(?:general (?:building|construction|electrical)|construction of|'
                             r'new build|building works|minor works|electrical works|video wall|'
                             r'fire (?:engine|appliance|tender vehicle)|fire brigade vehicles?)\b', re.I)


def classify_release(release: dict) -> dict:
    """Classify sector evidence without equating a keyword with a qualified lead.

    Ambiguous notices are retained for review, but are not reliable evidence of
    a supplier's capability or a maintenance need. A CPV code by itself is not
    conclusive because notices frequently contain broad or unrelated lots.
    """
    tender = release.get('tender') if isinstance(release, dict) else None
    tender = tender if isinstance(tender, dict) else {}
    title = tender.get('title') if isinstance(tender.get('title'), str) else ''
    description = tender.get('description') if isinstance(tender.get('description'), str) else ''
    chunks = [description]
    codes = set()
    def add_code(classification):
        if isinstance(classification, dict) and str(classification.get('scheme', '')).upper() == 'CPV':
            code = str(classification.get('id', '')).split('-')[0]
            if code in SPECIFIC_CPV:
                codes.add(code)
    add_code(tender.get('classification'))
    for classification in tender.get('additionalClassifications') if isinstance(tender.get('additionalClassifications'), list) else []:
        add_code(classification)
    for item in tender.get('items') if isinstance(tender.get('items'), list) else []:
        if isinstance(item, dict):
            chunks.append(item.get('description') if isinstance(item.get('description'), str) else '')
            add_code(item.get('classification'))
            for classification in item.get('additionalClassifications') if isinstance(item.get('additionalClassifications'), list) else []:
                add_code(classification)
    title_match = bool(SECTOR.search(title[:10000]))
    body_match = bool(SECTOR.search(' '.join(chunks)[:30000]))
    generic_title = bool(GENERIC_PROJECT.search(title[:10000]))
    if title_match and not generic_title:
        return {'level': 'relevant', 'reason': 'Sector terminology in the procurement title', 'cpv': sorted(codes)}
    if body_match or codes:
        return {'level': 'ambiguous', 'reason': 'Sector terms or codes appear outside a clear sector-specific title; review scope and lots', 'cpv': sorted(codes)}
    return {'level': 'excluded', 'reason': 'No recognised fire or security system terms or specific classifications', 'cpv': []}


def relevant_release(release: dict) -> bool:
    """Identify explicit sector language without equating it with an award."""
    return classify_release(release)['level'] != 'excluded'


def record_for_release(release: dict, retrieved_at: datetime) -> dict | None:
    if not isinstance(release, dict):
        return None
    release_id, ocid = release.get('id'), release.get('ocid')
    if not isinstance(release_id, str) or not NOTICE_ID.fullmatch(release_id):
        return None
    if not isinstance(ocid, str) or not OCID.fullmatch(ocid):
        return None
    try:
        published = datetime.fromisoformat(str(release['date']).replace('Z', '+00:00'))
        if published.tzinfo is None:
            return None
    except (ValueError, KeyError, TypeError):
        return None
    # Remove contact details and named individuals before persistent storage.
    # Names of organisations, parties and procurement evidence remain intact.
    def redact(value):
        if isinstance(value, dict):
            return {k: redact(v) for k, v in value.items() if k not in ('contactPoint', 'persones', 'persons')}
        if isinstance(value, list):
            return [redact(v) for v in value]
        return value
    return {'source_key': 'find_a_tender', 'release_id': release_id, 'ocid': ocid,
            'source_url': f'https://www.find-tender.service.gov.uk/Notice/{release_id}',
            'published_at': published.astimezone(UTC), 'retrieved_at': retrieved_at, 'raw': redact(release)}


def fetch_page(*, updated_from: datetime, updated_to: datetime, cursor: str | None = None, client=None):
    """One fixed-window API page. Reject off-domain pagination and oversized pages."""
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(25, connect=10), follow_redirects=False,
                                   headers={'User-Agent': 'SalesIntel public-market-monitor/1.0', 'Accept': 'application/json'})
    try:
        params = {'limit': 100, 'updatedFrom': updated_from.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%S'),
                  'updatedTo': updated_to.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%S')}
        if cursor:
            if not re.fullmatch(r'[A-Za-z0-9=]{1,300}', cursor):
                raise ValueError('Invalid stored pagination cursor')
            params['cursor'] = cursor
        with client.stream('GET', API_URL, params=params) as response:
            response.raise_for_status()
            size = 0
            parts = []
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise ValueError('Find a Tender page exceeded the response size limit')
                parts.append(chunk)
        payload = json.loads(b''.join(parts))
        if not isinstance(payload, dict) or not isinstance(payload.get('releases'), list) or len(payload['releases']) > 100:
            raise ValueError('Invalid Find a Tender release package')
        next_cursor = _next_cursor(payload.get('links'))
        if next_cursor and next_cursor == cursor:
            raise ValueError('Find a Tender returned a repeated pagination cursor')
        return payload['releases'], next_cursor
    finally:
        if owned:
            client.close()
