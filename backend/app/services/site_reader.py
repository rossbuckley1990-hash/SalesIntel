"""Read an organisation's own website for the business contact details it publishes.

Only the organisation's own site, and only pages its robots.txt allows. The reader gives an honest name, sends no cookies,
never logs in and runs no scripts. A site that asks automated readers to stop (a challenge page, 401, 403, 429 or 503) is
not read any further: there is no way round that, on purpose. Every detail kept is on a page this reader fetched, word for
word, with the words around it and the day it was read. A name is attached only when a person research already named appears
in those words. The reader never builds or guesses an address.
"""
from __future__ import annotations

import re
import time
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

AGENT = 'SalesIntelContactReader'
USER_AGENT = f'{AGENT}/1.0 (reads the business contact details an organisation publishes; obeys robots.txt)'
MAX_PAGES, MAX_BYTES, MAX_ROUTES, BUDGET_SECONDS = 5, 1_500_000, 8, 25.0
SCRIPT_BUILT_WORDS = 30  # fewer visible words than this on every page: the site is built by scripts the reader does not run
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
TRANSPORT: httpx.BaseTransport | None = None  # tests set a mock transport, so no test reaches the network
STOP_STATUS = {401, 403, 429, 503}
CHALLENGE = re.compile(r'just a moment|attention required|verify you are (?:a )?human|are you a robot|captcha|access denied|checking your browser', re.I)
PAGE_WORDS = re.compile(r'contact|about|team|people|leadership|management|who-we-are|meet', re.I)
FALLBACKS = ('/contact', '/contact-us')
EMAIL = re.compile(r'(?<![\w.%+-])[A-Z0-9._%+-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)*\.[A-Z]{2,}', re.I)
PHONE = re.compile(r'(?<![\d+])(?:\+44\s?(?:\(0\)\s?)?|0)\d[\d\s().-]{7,14}\d(?!\d)')
# Addresses that are not a way in for a sales conversation: data protection, recruitment, press, investors, accounts.
NOT_FOR_SALES = re.compile(r'^(?:privacy|dpo|gdpr|data\.?protection|careers?|jobs?|recruit\w*|hr|people\.?team|press|media|pr|news|investors?|ir|'
                           r'accounts?|invoices?|payables?|finance|unsubscribe|noreply|no-reply|donotreply|webmaster|abuse)$', re.I)
SKIP_TAGS = {'script', 'style', 'noscript', 'template', 'svg'}
BLOCK_TAGS = {'p', 'div', 'li', 'br', 'tr', 'td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'section', 'article', 'footer', 'header', 'address', 'dd', 'dt'}


class _Stop(Exception):
    """The site asked automated readers to stop, or could not be reached."""


class _Page(HTMLParser):
    """The visible words of a page, its title, and its links with their words."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.title = ''
        self._skip = 0
        self._title = False
        self._link: list | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag == 'title':
            self._title = True
        elif tag == 'a':
            self._link = [dict(attrs).get('href') or '', []]
        if tag in BLOCK_TAGS:
            self.parts.append(' \n ')

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag == 'title':
            self._title = False
        elif tag == 'a' and self._link is not None:
            self.links.append((self._link[0], ' '.join(self._link[1]).strip()))
            self._link = None
        if tag in BLOCK_TAGS:
            self.parts.append(' \n ')

    def handle_data(self, data: str) -> None:
        if self._title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)
            if self._link is not None:
                self._link[1].append(data)

    def text(self) -> str:
        return re.sub(r'[ \t\r\f\v ]+', ' ', re.sub(r'\s*\n\s*', ' \n ', ''.join(self.parts))).strip()


def root(website: str) -> tuple[str, str] | None:
    """The site's first page and its own domain (without www), or None when the address is not a website."""
    text = (website or '').strip()
    if not text:
        return None
    if not re.match(r'^https?://', text, re.I):
        if re.match(r'^[a-z][a-z0-9+.-]*:', text, re.I) and not re.match(r'^[\w.-]+:\d+(?:/|$)', text):
            return None  # mailto:, ftp: and the like are not websites
        text = 'https://' + text
    parts = urlparse(text)
    host = (parts.hostname or '').lower()
    if (parts.scheme not in ('http', 'https') or '@' in parts.netloc or '.' not in host or host.replace('.', '').isdigit() or host == 'localhost'):
        return None
    return f"{parts.scheme}://{host}{parts.path or '/'}", host.removeprefix('www.')


def own(host: str, base: str) -> bool:
    """Whether a host belongs to the organisation's own domain: the same domain, a part of it, or the domain it is part of."""
    host = (host or '').lower().removeprefix('www.')
    return bool(host) and (host == base or host.endswith('.' + base) or base.endswith('.' + host))


def digits(value: str) -> str:
    """A UK number as its national digits (+44 (0)1757 450000 and 01757 450000 are the same number)."""
    found = re.sub(r'\D', '', value or '')
    if found.startswith('44'):
        found = found[2:]
        found = found if found.startswith('0') else '0' + found
    return found


def _same(route: dict) -> tuple[str, str]:
    """One contact detail however it is written: an address in any case, a number with or without +44."""
    return route['kind'], route['value'].casefold() if route['kind'] == 'email' else digits(route['value'])


def _phone_ok(value: str) -> bool:
    found = digits(value)
    return found.startswith('0') and len(found) in (10, 11) and found[1] in '123578'


def _quote(text: str, at: int, length: int) -> str:
    start, end = max(0, at - 160), min(len(text), at + length + 160)
    words = re.sub(r'\s+', ' ', text[start:end]).strip()
    return ('… ' if start else '') + words + (' …' if end < len(text) else '')


def _name_in(quote: str, names: list[str]) -> str:
    low = quote.casefold()
    return next((n for n in names if n and len(n) > 3 and n.casefold() in low), '')


def extract(html: str, url: str, base: str, names: list[str], read_on: str) -> tuple[_Page, list[dict]]:
    """The email addresses and phone numbers a page shows, each with the words around it. Nothing is built or guessed."""
    page = _Page()
    try:
        page.feed(html)
        page.close()
    except Exception:  # a page too broken to read gives nothing, never a guess
        return page, []
    text = page.text()
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def keep(kind: str, value: str, at: int, words: str = '') -> None:
        value = value.strip().rstrip('.')
        key = (kind, value.casefold() if kind == 'email' else digits(value))
        if key in seen or len(found) >= MAX_ROUTES:
            return
        if kind == 'email':
            local, _, domain = value.partition('@')
            if not own(domain, base) or NOT_FOR_SALES.match(local):
                return
        elif not _phone_ok(value) or re.search(r'fax\W{0,4}$', text[max(0, at - 12):at], re.I):
            return
        seen.add(key)
        quote = _quote(text, at, len(value)) if at >= 0 else re.sub(r'\s+', ' ', words).strip() or value  # only in a link: the link's own words
        found.append({'kind': kind, 'value': value, 'label': page.title.strip()[:120], 'source_url': url, 'quote': quote[:400],
                      'name': _name_in(quote, names), 'read_on': read_on})

    for m in EMAIL.finditer(text):
        keep('email', m.group(0), m.start())
    for m in PHONE.finditer(text):
        keep('phone', m.group(0), m.start())
    for href, words in page.links:  # an address only in a link: kept with the link's own words
        low = href.strip().lower()
        if low.startswith('mailto:'):
            value = href.strip()[7:].split('?')[0]
            if EMAIL.fullmatch(value):
                keep('email', value, text.find(value), words)
        elif low.startswith('tel:'):
            shown = PHONE.search(words or '')
            value = shown.group(0) if shown else href.strip()[4:]
            keep('phone', value, text.find(value), words)
    return page, found


def _get(client: httpx.Client, url: str, base: str, deadline: float) -> tuple[str, str]:
    """One page of the site, following redirects only within it. Raises _Stop when the site asks readers to stop."""
    for _ in range(5):
        if time.monotonic() > deadline:
            raise TimeoutError('time budget spent')
        with client.stream('GET', url) as response:
            if response.status_code in STOP_STATUS or 'cf-mitigated' in response.headers:
                raise _Stop(f'{urlparse(url).hostname} asked automated readers to stop (HTTP {response.status_code}), so it was not read.')
            if response.is_redirect:
                target = urljoin(url, response.headers.get('location') or '')
                if not own(urlparse(target).hostname or '', base):
                    raise ValueError('redirects off the site')
                url = target
                continue
            if response.status_code != 200 or 'html' not in (response.headers.get('content-type') or 'text/html').lower():
                raise ValueError(f'HTTP {response.status_code}')
            body = b''
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    break
            html = body[:MAX_BYTES].decode(response.encoding or 'utf-8', errors='replace')
            title = re.search(r'<title[^>]*>(.*?)</title>', html[:20000], re.I | re.S)
            if title and CHALLENGE.search(title.group(1)):
                raise _Stop(f'{urlparse(url).hostname} showed a check for automated readers, so it was not read.')
            return url, html
    raise ValueError('too many redirects')


def _robots(client: httpx.Client, first: str, base: str) -> RobotFileParser:
    """The site's robots.txt (redirects followed within the site). Missing means every page may be read; an error means none."""
    parts = urlparse(first)
    robots = RobotFileParser()
    url = f'{parts.scheme}://{parts.hostname}/robots.txt'
    try:
        for _ in range(5):
            response = client.get(url)
            target = urljoin(url, response.headers.get('location') or '') if response.is_redirect else ''
            if not target or not own(urlparse(target).hostname or '', base):
                break
            url = target
    except httpx.HTTPError as exc:
        raise _Stop(f'{parts.hostname} could not be reached.') from exc
    if response.status_code in STOP_STATUS:
        raise _Stop(f'{parts.hostname} asked automated readers to stop (HTTP {response.status_code}), so it was not read.')
    if response.status_code >= 500:
        raise _Stop(f'{parts.hostname} could not say which pages may be read (HTTP {response.status_code}), so it was not read.')
    robots.parse(response.text.splitlines() if response.status_code == 200 else [])
    return robots


def _replay() -> httpx.BaseTransport | None:
    """In demo and test with replayed research, the replayed organisations' own pages, so nothing reaches the network."""
    from app.config import get_settings
    settings = get_settings()
    if settings.research_provider == 'replay' and settings.app_env in {'demo', 'test'}:
        from app.services.research_replay import site_transport
        return site_transport()
    return None


def read(website: str, names: list[str], today: date, *, client: httpx.Client | None = None) -> dict:
    """Read up to five of an organisation's own pages (its first page, then contact, about and team pages it links to)."""
    start = root(website)
    out = {'website': website, 'read_on': today.isoformat(), 'pages': [], 'routes': [], 'stopped': ''}
    if start is None:
        return {**out, 'stopped': 'No website address to read.'}
    first, base = start
    deadline = time.monotonic() + BUDGET_SECONDS
    owned = client is None
    client = client or httpx.Client(timeout=TIMEOUT, follow_redirects=False, transport=TRANSPORT or _replay(),
                                    headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml'})
    names = [n.strip() for n in names if n and n.strip()]
    try:
        robots = _robots(client, first, base)
        queue, done = [first], set()
        while queue and len(out['pages']) < MAX_PAGES and time.monotonic() < deadline:
            url = queue.pop(0)
            if url in done:
                continue
            done.add(url)
            if not robots.can_fetch(AGENT, url):
                out.setdefault('not_allowed', []).append(url)
                continue
            try:
                final, html = _get(client, url, base, deadline)
            except (ValueError, TimeoutError, httpx.HTTPError):
                if url == first:  # no first page: try the usual contact pages instead
                    queue += [urljoin(first, f) for f in FALLBACKS]
                continue
            done.add(final)
            page, routes = extract(html, final, base, names, out['read_on'])
            out['pages'].append({'url': final, 'title': page.title.strip()[:160], 'words': len(page.text().split())})
            have = {_same(r) for r in out['routes']}
            out['routes'] += [r for r in routes if _same(r) not in have][:MAX_ROUTES - len(out['routes'])]
            if url == first:  # pages it links to that a person would open for contact details, contact pages first
                links = []
                for href, words in page.links:
                    target = urljoin(final, href.split('#')[0])
                    parts = urlparse(target)
                    if parts.scheme in ('http', 'https') and own(parts.hostname or '', base) and (PAGE_WORDS.search(parts.path) or PAGE_WORDS.search(words)):
                        links.append(target.split('?')[0])
                links = sorted(dict.fromkeys(links), key=lambda u: (not re.search(r'contact', u, re.I), len(u)))
                if not any(re.search(r'contact', u, re.I) for u in links):
                    links += [urljoin(final, f) for f in FALLBACKS]
                queue += links
    except _Stop as stop:
        out['stopped'] = str(stop)
    finally:
        if owned:
            client.close()
    if not out['stopped'] and out['pages'] and not out['routes'] and all(p['words'] < SCRIPT_BUILT_WORDS for p in out['pages']):
        out['stopped'] = (f"{urlparse(first).hostname} builds its pages with scripts, which SalesIntel’s reader does not run, so it found no words "
                          'to read. Open the site yourself, or ask the research chat to read it.')
    return out
