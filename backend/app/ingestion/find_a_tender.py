"""Bounded Find a Tender OCDS harvesting. Notices are historical context, not leads.

Source: https://www.find-tender.service.gov.uk/Developer/Documentation
Notice data is published under the Open Government Licence.
"""
from datetime import UTC, datetime
import re
from urllib.parse import parse_qs, urlsplit

import httpx

from app.schemas.evidence_observation import EvidenceObservationInput

API_URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
MAX_RESPONSE_BYTES = 8_000_000
_MAINTENANCE = re.compile(r"\b(maintenan\w*|servic\w*|inspect\w*|repair\w*|testing|test\s+and\s+inspect\w*)\b", re.I)
_SYSTEM = re.compile(r"\b(fire\s+(?:and\s+security|alarm\w*|detect\w*|safety|protect\w*|suppression|equipment|extinguisher\w*|door\w*|systems?)|(?:fire|security)\s*(?:&|and)\s*(?:fire|security)|(?:physical\s+)?security\s+(?:systems?|alarms?|equipment)|cctv|intruder\s+alarms?|burglar\s+alarms?|access\s+control)\b", re.I)
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,31}:[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CURSOR = re.compile(r"^[A-Za-z0-9=]{1,300}$")
_NOTICE_ID = re.compile(r"^[0-9]{1,12}-[0-9]{4}$")


def _word(value, max_length=255):
    return ' '.join(str(value or '').split())[:max_length]


def _buyer(release):
    buyer = release.get('buyer') or {}
    if not isinstance(buyer, dict):
        return None
    for party in release.get('parties') or []:
        if not isinstance(party, dict) or party.get('id') != buyer.get('id'):
            continue
        ident = party.get('identifier') or {}
        if not isinstance(ident, dict):
            continue
        scheme, value = _word(ident.get('scheme')), _word(ident.get('id'))
        org_id = f'{scheme}:{value}'
        name = _word(buyer.get('name') or party.get('name'))
        if not _IDENTIFIER.fullmatch(org_id) or not name:
            return None
        address = party.get('address') or {}
        if not isinstance(address, dict):
            address = {}
        locality = _word(address.get('locality'), 100)
        postcode = _word(address.get('postalCode'), 20)
        return org_id, name, ', '.join(part for part in (locality, postcode) if part)
    return None


def parse_release(release, retrieved_at, keywords=None):
    """Only record explicitly published notice facts; never infer performance or intent."""
    if not isinstance(release, dict):
        return None
    tags = release.get('tag') or []
    if not isinstance(tags, list) or not any(str(tag).lower() in {'award', 'awardupdate', 'contract', 'contractupdate'} for tag in tags):
        return None
    tender = release.get('tender') or {}
    if not isinstance(tender, dict):
        return None
    title = _word(tender.get('title'), 500)
    description = _word(tender.get('description'), 8000)
    text = f'{title} {description}'
    if keywords:
        if not any(keyword.casefold() in text.casefold() for keyword in keywords):
            return None
    elif not ((_SYSTEM.search(title) and _MAINTENANCE.search(text)) or
              any(_SYSTEM.search(part) and _MAINTENANCE.search(part)
                  for part in re.split(r'[.!?;\n]', str(tender.get('description') or '')))):
        return None
    buyer = _buyer(release)
    notice_id, ocid = _word(release.get('id')), _word(release.get('ocid'))
    if not buyer or not _NOTICE_ID.fullmatch(notice_id) or not ocid or not title:
        return None
    try:
        published = datetime.fromisoformat(str(release['date']).replace('Z', '+00:00')).date()
    except (ValueError, KeyError, TypeError):
        return None
    org_id, name, location = buyer
    stages = ', '.join(_word(tag, 30) for tag in tags if isinstance(tag, str))
    statement = f'Find a Tender published a {stages} notice titled "{title}" on {published.isoformat()}.'
    if location:
        statement += f' The published buyer address gives {location}; this is not necessarily the service site.'
    statement += ' The notice is historical procurement context; it does not establish present demand, non-compliance, or supplier underperformance.'
    return EvidenceObservationInput(
        organisation_id=org_id, organisation_name=name, site='Unknown', category='other' if keywords else 'maintenance',
        observed_statement=statement, source_title='Find a Tender: ' + title[:239],
        source_reference=f'{ocid} / {notice_id}'[:512],
        source_url=f'https://www.find-tender.service.gov.uk/Notice/{notice_id}',
        published_at=published, observed_at=published, retrieved_at=retrieved_at,
    )


def _next_cursor(links):
    next_url = (links or {}).get('next') if isinstance(links, dict) else None
    if not next_url:
        return None
    parsed = urlsplit(next_url)
    if parsed.scheme != 'https' or parsed.netloc != 'www.find-tender.service.gov.uk' or parsed.path != '/api/1.0/ocdsReleasePackages':
        raise ValueError('Unexpected pagination URL from Find a Tender')
    values = parse_qs(parsed.query).get('cursor', [])
    if len(values) != 1 or not _CURSOR.fullmatch(values[0]):
        raise ValueError('Invalid pagination cursor from Find a Tender')
    return values[0]


def fetch_batch(*, updated_from, updated_to, cursor=None, max_pages=2, keywords=None, client=None):
    """Fetch first, then import atomically. Window is fixed across cursor pages."""
    now = datetime.now(UTC)
    observations = []
    scanned = pages = 0
    next_cursor = cursor
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(25, connect=10), follow_redirects=False,
                                   headers={'User-Agent': 'SalesIntel public-data research/1.0', 'Accept': 'application/json'})
    try:
        for _ in range(max_pages):
            params = {'limit': 100, 'updatedFrom': updated_from.strftime('%Y-%m-%dT%H:%M:%S'),
                      'updatedTo': updated_to.strftime('%Y-%m-%dT%H:%M:%S')}
            if next_cursor:
                params['cursor'] = next_cursor
            with client.stream('GET', API_URL, params=params) as response:
                response.raise_for_status()
                parts = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise ValueError('Find a Tender page exceeded the response size limit')
                    parts.append(chunk)
            import json
            payload = json.loads(b''.join(parts))
            releases = payload.get('releases')
            if not isinstance(releases, list) or len(releases) > 100:
                raise ValueError('Invalid Find a Tender release package')
            scanned += len(releases)
            pages += 1
            observations.extend(obs for item in releases if (obs := parse_release(item, now, keywords)) is not None)
            new_cursor = _next_cursor(payload.get('links'))
            if new_cursor and new_cursor == next_cursor:
                raise ValueError('Find a Tender returned a repeated pagination cursor')
            next_cursor = new_cursor
            if not next_cursor:
                break
        return observations, scanned, pages, next_cursor
    finally:
        if owned:
            client.close()
