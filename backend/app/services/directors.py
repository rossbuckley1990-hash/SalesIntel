"""The directors of a small firm, from Companies House, for who to call about a lead (agreed 17 November 2026).

At a small owner-managed company a director usually decides on fire and security; at a larger one the board rarely does,
and the facilities or site manager is the person to ask for. So SalesIntel names directors only when the company is active,
files small-company accounts and has at most four active directors, and keeps only each director's first name, surname,
role and appointment date. A company is found by its number, never by a similar name alone: a number that research gives
must belong to a company whose registered name matches the lead's; a number the rep chooses is taken as theirs.
Companies House publishes no phone number or email address for anyone, so this names a person, never a way in.
Works the same for a company in any sector.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

import httpx

from app.ingestion import companies_house as ch

TRANSPORT: httpx.BaseTransport | None = None  # tests set a mock transport, so no test reaches the network
MAX_DIRECTORS = 4
SMALL = {'micro-entity': 'micro-entity', 'small': 'small-company', 'total-exemption-full': 'small-company',
         'total-exemption-small': 'small-company', 'audited-abridged': 'abridged small-company', 'unaudited-abridged': 'abridged small-company'}
LARGER = {'full': 'full', 'group': 'group', 'medium': 'medium-sized company', 'partial-exemption': 'medium-sized company',
          'audit-exemption-subsidiary': 'subsidiary', 'filing-exemption-subsidiary': 'subsidiary'}
NOT_SET_UP = 'The Companies House lookup is not set up yet: add a free Companies House API key as COMPANIES_HOUSE_API_KEY.'
ASK_INSTEAD = 'ask for the facilities or site manager rather than a director'
TITLES = {'mr', 'mrs', 'ms', 'miss', 'mx', 'dr', 'sir', 'dame', 'lord', 'lady', 'prof', 'professor', 'rev', 'revd', 'reverend'}
SUFFIX = re.compile(r'\b(?:limited|ltd|plc|llp|lp|cic|the|and|co|company)\b')


def number(text: Any) -> str:
    """A Companies House company number, if that is what the text is (spaces ignored), else ''."""
    found = re.sub(r'\s+', '', str(text or '')).upper()
    return found if ch.COMPANY_NUMBER.fullmatch(found) else ''


def _cap(part: str) -> str:
    part = part[:1].upper() + part[1:].lower()
    return 'Mc' + part[2:3].upper() + part[3:] if part.startswith('Mc') and len(part) > 2 else part


def _case(word: str) -> str:
    """'O'NEILL-MCDONALD' as 'O'Neill-McDonald'."""
    return '-'.join("'".join(_cap(p) for p in part.split("'")) for part in word.split('-'))


def person_name(register_name: str) -> str:
    """The register's 'SMITH, Jane Mary' as 'Jane Smith': first forename and surname only, as the person is addressed."""
    surname, comma, forenames = register_name.partition(',')
    if not comma:
        return ' '.join(_case(w) for w in register_name.split())
    first = next((w.strip('.') for w in forenames.split(',')[0].split() if w.strip('.').casefold() not in TITLES), '')
    return ' '.join(x for x in (_case(first), ' '.join(_case(w) for w in surname.split())) if x)


def _words(name: str) -> set[str]:
    text = re.sub(r"[’'`]", '', name.casefold().replace('&', ' and '))
    return set(SUFFIX.sub(' ', re.sub(r'[^a-z0-9]+', ' ', text)).split())


def same_company(registered: str, lead: str) -> bool:
    """Whether a registered name is the lead's name, give or take 'Limited' and the like. Either may add words to the
    other ('DHL Supply Chain UK' and 'DHL SUPPLY CHAIN LIMITED'); a name in brackets counts as another name for the lead."""
    reg = _words(registered)
    names = [re.sub(r'\(.*?\)', ' ', lead), *re.findall(r'\((.*?)\)', lead)]
    return bool(reg) and any((w := _words(n)) and (reg <= w or w <= reg) for n in names)


def _settings():
    from app.config import get_settings
    return get_settings()


def _replay() -> httpx.BaseTransport | None:
    """In demo and test with replayed research, the replayed companies, so nothing reaches the network."""
    settings = _settings()
    if settings.research_provider == 'replay' and settings.app_env in {'demo', 'test'}:
        from app.services.research_replay import companies_transport
        return companies_transport()
    return None


def _key() -> str | None:
    key = _settings().companies_house_api_key
    return key if key and key.strip() else ('replay' if _replay() is not None else None)


def _transport() -> httpx.BaseTransport | None:
    return TRANSPORT or _replay()


class LookupFailed(Exception):
    """A search could not be made, with a message the rep can act on. `unavailable` when Companies House or the key is."""

    def __init__(self, message: str, unavailable: bool = True):
        super().__init__(message)
        self.unavailable = unavailable


def search(query: str, *, client: httpx.Client | None = None) -> list[dict]:
    """Companies matching a name, for the rep to choose from."""
    key = _key()
    if not key:
        raise LookupFailed(NOT_SET_UP)
    try:
        found = ch.search_companies(query, api_key=key, client=client, transport=_transport())
    except ValueError as exc:
        raise LookupFailed('Give the company name or its Companies House number.', unavailable=False) from exc
    except ch.CompaniesHouseError as exc:
        raise LookupFailed(str(exc)) from exc
    if not found:
        raise LookupFailed(f'Companies House has no company called “{query.strip()[:80]}”. Try its registered name or its company number.', unavailable=False)
    return found


def _why_not(found: dict, lead: str, chosen: bool) -> str:
    """Why the directors are not shown, or '' when they are."""
    count = len(found['directors'])
    kind = found['accounts_type']
    if not chosen and not same_company(found['company_name'], lead):
        return 'That number belongs to a company of another name, so SalesIntel did not use it. Choose the right company to see its directors.'
    if found['status'] != 'active':
        return f"Companies House lists it as {found['status'].replace('-', ' ') or 'not active'}, so its directors are not shown."
    if 'plc' in found['type'] or found['type'].startswith('public'):
        return f'It is a public limited company: {ASK_INSTEAD}.'
    if kind == 'dormant':
        return 'It files dormant-company accounts, so it is not trading; its directors are not shown.'
    if kind not in SMALL:
        if kind in LARGER:
            return f"It files {LARGER[kind]} accounts, so it is not a small firm: at a company this size, {ASK_INSTEAD}."
        return 'It has not yet filed accounts that show its size, so its directors are not shown.'
    if not found['complete'] or count > MAX_DIRECTORS:
        return f"It has {count if found['complete'] else 'many'} active directors: with a board that size, {ASK_INSTEAD}."
    if not count:
        return 'No active director is listed.'
    return ''


def read(company_number: str, lead: str, today: date, *, chosen: bool = False, client: httpx.Client | None = None) -> dict:
    """Companies House's record of one company, as it bears on who to call: the directors of a small firm, or why not.
    `stopped` says why nothing could be read; `unavailable` when trying again later may work."""
    num = number(company_number)
    base = {'company_number': num or str(company_number or '')[:20], 'read_on': today.isoformat(), 'chosen': chosen}
    if not num:
        return {**base, 'stopped': 'That is not a Companies House company number: it has eight characters, such as 01234567 or SC123456.'}
    key = _key()
    if not key:
        return {**base, 'stopped': NOT_SET_UP, 'unavailable': True}
    try:
        found = ch.fetch_directors(num, api_key=key, client=client, transport=_transport())
    except ch.CompaniesHouseError as exc:
        return {**base, 'stopped': str(exc), 'unavailable': 'no company' not in str(exc)}
    why = _why_not(found, lead, chosen)
    sole = len(found['directors']) == 1
    directors = [] if why else [{'name': person_name(d['register_name']), 'role': 'Sole director' if sole and d['role'] == 'Director' else d['role'],
                                 'appointed_on': d['appointed_on']} for d in found['directors']]
    return {**base, 'company_name': found['company_name'], 'status': found['status'], 'accounts_type': found['accounts_type'],
            'source_url': found['source_url'], 'shown': not why, 'why': why, 'mismatch': why.startswith('That number belongs'),
            'directors': directors}


def _long(day: str) -> str:
    try:
        d = date.fromisoformat((day or '')[:10])
    except ValueError:
        return day or ''
    return f"{d.day} {d:%B %Y}"


def note(reg: dict | None) -> str:
    """One sentence on what Companies House gave, for the rep and for the research model to report honestly."""
    if not reg:
        return ''
    if reg.get('stopped'):
        return reg['stopped']
    head = f"Companies House, read by SalesIntel on {_long(reg['read_on'])}: {reg['company_name']} ({reg['company_number']})"
    if reg.get('shown'):
        n = len(reg['directors'])
        return f"{head} files {SMALL.get(reg['accounts_type'], 'small-company')} accounts and has {n} active director{'' if n == 1 else 's'}."
    return f"{head}. {reg['why']}"
