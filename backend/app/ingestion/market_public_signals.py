"""Open public sources of indirect signals, read within each publisher's limits.

The Regulator of Social Housing publishes judgements through the GOV.UK search and
content APIs. The Gazette publishes insolvency notices as an Atom feed and asks for
ten seconds between requests. Both carry the Open Government Licence.
A refused request is reported, never worked around.
"""
from __future__ import annotations
from datetime import date, timedelta
import html
import re
import time
from xml.etree import ElementTree

import httpx

GOV_SEARCH = 'https://www.gov.uk/api/search.json'
GOV_CONTENT = 'https://www.gov.uk/api/content'
GAZETTE_FEED = 'https://www.thegazette.co.uk/insolvency/data.feed'
GOV_PAUSE = 0.5
GAZETTE_PAUSE = 10
_ATOM = {'a': 'http://www.w3.org/2005/Atom'}
_TAGS = re.compile(r'<[^>]+>')
_GRADE = re.compile(r'\bC([1-4])\b')
_FIRE_PROBLEM = re.compile(r'\bfire\b.*\b(?:overdue|outstanding|remedial|breach\w*|fail\w*|not\s+completed)\b|\b(?:overdue|outstanding|remedial|breach\w*|fail\w*)\b.*\bfire\b', re.I)
_COMPANY_NUMBER = re.compile(r'\b(?:company\s+(?:number|no\.?|registration\s+number)|registered\s+number)[:\s]*([0-9]{8}|[A-Z]{2}[0-9]{6})\b', re.I)


def client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=True, headers={'User-Agent': 'MiSi public-market-monitor/1.0', 'Accept': 'application/json, application/atom+xml'})


def _plain(value) -> str:
    return ' '.join(html.unescape(_TAGS.sub(' ', str(value or ''))).split())


def judgement_links(http, *, count: int = 1000) -> list[dict]:
    """Landlord judgement pages, newest first."""
    response = http.get(GOV_SEARCH, params={'filter_organisations': 'regulator-of-social-housing', 'filter_content_store_document_type': 'decision', 'count': count,
                                            'order': '-public_timestamp', 'fields': 'title,link,public_timestamp'})
    response.raise_for_status()
    return [x for x in response.json()['results'] if x.get('link', '').startswith('/government/publications/')]


def read_judgement(http, link: str, *, pause: float = GOV_PAUSE, sleep=time.sleep) -> dict | None:
    """The current judgement's grade and fire safety sentences, or None without one."""
    page = http.get(GOV_CONTENT + link)
    page.raise_for_status()
    details = page.json().get('details', {})
    attachment = next((x for x in details.get('attachments', []) if 'udgement' in str(x.get('title')) and str(x.get('url', '')).startswith('/government/')), None)
    if attachment is None:
        return None
    sleep(pause)
    body = http.get(GOV_CONTENT + attachment['url'])
    body.raise_for_status()
    text = _plain(body.json().get('details', {}).get('body'))
    return {'title': attachment['title'], 'url': 'https://www.gov.uk' + attachment['url'], 'grades': sorted({int(x) for x in _GRADE.findall(text)}),
            'fire_sentences': [x.strip()[:400] for x in re.split(r'(?<=[.!?])\s+', text) if _FIRE_PROBLEM.search(x)][:8]}


def parse_gazette(body: bytes) -> list[dict]:
    """Corporate insolvency entries from one feed page."""
    found = []
    for entry in ElementTree.fromstring(body).findall('a:entry', _ATOM):
        title = entry.findtext('a:title', '', _ATOM).strip()
        link = next((x.get('href') for x in entry.findall('a:link', _ATOM) if not x.get('rel')), None)
        summary = _plain(entry.findtext('a:content', '', _ATOM) or entry.findtext('a:summary', '', _ATOM))
        number = _COMPANY_NUMBER.search(summary)
        found.append({'title': title, 'url': link, 'published': (entry.findtext('a:published', '', _ATOM) or entry.findtext('a:updated', '', _ATOM))[:10],
                      'summary': summary[:400], 'company_number': number.group(1) if number else None})
    return found


def gazette_notices(http, first: date, last: date, *, text: str = '', max_pages: int = 12, sleep=time.sleep) -> list[dict]:
    """Notices published in a window, with the crawl delay the publisher asks for."""
    notices, params = [], {'start-publish-date': first.isoformat(), 'end-publish-date': last.isoformat(), 'results-page-size': 100}
    if text:
        params['text'] = text
    for page in range(1, max_pages + 1):
        response = http.get(GAZETTE_FEED, params={**params, 'results-page': page})
        response.raise_for_status()
        rows = parse_gazette(response.content)
        notices += rows
        sleep(GAZETTE_PAUSE)
        if len(rows) < 100:
            break
    return notices


def gazette_window(today: date, *, days: int = 3) -> tuple[date, date]:
    return today - timedelta(days=days), today
