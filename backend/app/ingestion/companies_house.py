"""Bounded Companies House company-profile retrieval.

The authenticated public API is optional.  A company number must be supplied;
name similarity never establishes identity.  Profiles do not prove capability,
contract delivery or ownership.  Market signals collect no officers or personal
data.  The one exception is `fetch_directors`, for who to call about a lead
(agreed 17 November 2026): the active directors of one company, name, role and
appointment date only, and only where `app.services.directors` judges the firm
small enough that a director decides.
"""
from __future__ import annotations

from datetime import UTC, datetime
import json
import re

import httpx

API_BASE = "https://api.company-information.service.gov.uk"
MAX_BYTES = 1_000_000
COMPANY_NUMBER = re.compile(r"^(?:[0-9]{8}|[A-Z]{2}[0-9]{6})$")


class CompaniesHouseError(Exception):
    """Safe error without request headers, credentials, or upstream body."""


def fetch_company_profile(company_number: str, *, api_key: str | None, client: httpx.Client | None = None) -> dict:
    """Fetch one explicit company number. Caller schedules retries after 429/errors.

    Follows no redirects (so credentials cannot be sent to a different host), caps
    response size, and returns only selected organisation-level fields.
    """
    number = company_number.strip().upper()
    if not COMPANY_NUMBER.fullmatch(number):
        raise ValueError("Invalid Companies House company number")
    if not api_key or not api_key.strip():
        raise CompaniesHouseError("Companies House API key is not configured")
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(25, connect=10), follow_redirects=False)
    try:
        try:
            with client.stream("GET", f"{API_BASE}/company/{number}", auth=(api_key, ""),
                               headers={"Accept": "application/json", "User-Agent": "SalesIntel market intelligence/1.0"},
                               follow_redirects=False) as response:
                if response.status_code == 429:
                    raise CompaniesHouseError("Companies House rate limit reached; retry later")
                if response.status_code != 200:
                    raise CompaniesHouseError(f"Companies House returned HTTP {response.status_code}")
                parts, size = [], 0
                for part in response.iter_bytes():
                    size += len(part)
                    if size > MAX_BYTES:
                        raise CompaniesHouseError("Companies House response exceeds size limit")
                    parts.append(part)
            payload = json.loads(b"".join(parts))
        except (httpx.HTTPError, ValueError) as exc:
            raise CompaniesHouseError("Companies House request or response failed") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("company_number"), str) or payload["company_number"].upper() != number:
            raise CompaniesHouseError("Companies House returned a mismatched company profile")
        name = payload.get("company_name")
        if not isinstance(name, str) or not name.strip():
            raise CompaniesHouseError("Companies House returned a profile without a company name")
        fields = ("company_number", "company_name", "company_status", "date_of_creation", "date_of_cessation", "type", "sic_codes", "previous_company_names")
        profile = {key: payload[key] for key in fields if key in payload}
        profile["accounts_overdue"] = (payload.get("accounts") or {}).get("overdue") is True
        profile["confirmation_overdue"] = (payload.get("confirmation_statement") or {}).get("overdue") is True
        profile["has_insolvency_history"] = payload.get("has_insolvency_history") is True
        # Registered offices can be residential; region/locality is sufficient here.
        address = payload.get("registered_office_address")
        if isinstance(address, dict):
            profile["registered_office_address"] = {k: address[k] for k in ("locality", "region", "country") if k in address}
        return {"source_key": "companies_house", "release_id": number,
                "source_url": f"https://find-and-update.company-information.service.gov.uk/company/{number}",
                "retrieved_at": datetime.now(UTC), "raw": profile}
    finally:
        if owned:
            client.close()


DIRECTOR_ROLES = {"director": "Director", "llp-designated-member": "Designated member", "llp-member": "Member"}


def _get(client: httpx.Client, path: str, api_key: str, params: dict | None = None) -> dict:
    """One bounded GET: no redirects, capped size, and errors that carry no credentials or upstream body."""
    try:
        with client.stream("GET", f"{API_BASE}{path}", params=params, auth=(api_key, ""), follow_redirects=False,
                           headers={"Accept": "application/json", "User-Agent": "SalesIntel market intelligence/1.0"}) as response:
            if response.status_code == 429:
                raise CompaniesHouseError("Companies House is busy; try again in a few minutes.")
            if response.status_code == 404:
                raise CompaniesHouseError("Companies House has no company with that number.")
            if response.status_code != 200:
                raise CompaniesHouseError(f"Companies House returned HTTP {response.status_code}.")
            parts, size = [], 0
            for part in response.iter_bytes():
                size += len(part)
                if size > MAX_BYTES:
                    raise CompaniesHouseError("Companies House sent more than expected.")
                parts.append(part)
        payload = json.loads(b"".join(parts))
    except (httpx.HTTPError, ValueError) as exc:
        raise CompaniesHouseError("Companies House did not answer.") from exc
    if not isinstance(payload, dict):
        raise CompaniesHouseError("Companies House sent an unexpected answer.")
    return payload


def _client(client: httpx.Client | None, transport: httpx.BaseTransport | None) -> httpx.Client:
    return client or httpx.Client(timeout=httpx.Timeout(15, connect=8), follow_redirects=False, transport=transport)


def search_companies(query: str, *, api_key: str | None, client: httpx.Client | None = None,
                     transport: httpx.BaseTransport | None = None, limit: int = 5) -> list[dict]:
    """Companies whose registered name matches a search, for a person to choose from. A match is never taken as the
    organisation on its own. Only the town of the registered office is kept: a small firm's office can be a home."""
    query = " ".join(str(query or "").split())[:160]
    if not query:
        raise ValueError("Give a company name to search for")
    if not api_key or not api_key.strip():
        raise CompaniesHouseError("Companies House API key is not configured")
    owned = client is None
    client = _client(client, transport)
    try:
        payload = _get(client, "/search/companies", api_key, {"q": query, "items_per_page": limit})
    finally:
        if owned:
            client.close()
    out = []
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        number = str(item.get("company_number") or "").strip().upper()
        name = str(item.get("title") or "").strip()
        if COMPANY_NUMBER.fullmatch(number) and name:
            address = item.get("address") if isinstance(item.get("address"), dict) else {}
            out.append({"company_number": number, "name": name[:255], "status": str(item.get("company_status") or "")[:40],
                        "town": str(address.get("locality") or "")[:80], "created": str(item.get("date_of_creation") or "")[:10]})
    return out[:limit]


def fetch_directors(company_number: str, *, api_key: str | None, client: httpx.Client | None = None,
                    transport: httpx.BaseTransport | None = None) -> dict:
    """One company's profile facts that say how big it is, and its active directors: name, role and appointment date only.

    Never kept: date of birth, nationality, country of residence, occupation or any address. Secretaries, corporate
    directors and nominees are left out; so is anyone who has resigned."""
    number = company_number.strip().upper()
    if not COMPANY_NUMBER.fullmatch(number):
        raise ValueError("Invalid Companies House company number")
    if not api_key or not api_key.strip():
        raise CompaniesHouseError("Companies House API key is not configured")
    owned = client is None
    client = _client(client, transport)
    try:
        profile = _get(client, f"/company/{number}", api_key)
        if str(profile.get("company_number") or "").upper() != number or not str(profile.get("company_name") or "").strip():
            raise CompaniesHouseError("Companies House returned a mismatched company profile")
        officers = _get(client, f"/company/{number}/officers", api_key, {"items_per_page": 100})
    finally:
        if owned:
            client.close()
    directors = []
    for item in officers.get("items") or []:
        if not isinstance(item, dict) or item.get("resigned_on") or item.get("officer_role") not in DIRECTOR_ROLES:
            continue
        name = str(item.get("name") or "").strip()
        if name:
            directors.append({"register_name": name[:200], "role": DIRECTOR_ROLES[item["officer_role"]],
                              "appointed_on": str(item.get("appointed_on") or "")[:10]})
    listed = len(officers.get("items") or [])
    total = officers.get("total_results")
    accounts = profile.get("accounts") if isinstance(profile.get("accounts"), dict) else {}
    last = accounts.get("last_accounts") if isinstance(accounts.get("last_accounts"), dict) else {}
    return {"company_number": number, "company_name": str(profile["company_name"]).strip()[:255],
            "status": str(profile.get("company_status") or "")[:40], "type": str(profile.get("type") or "")[:60],
            "accounts_type": str(last.get("type") or "")[:60], "directors": directors,
            "complete": not (isinstance(total, int) and total > listed),
            "source_url": f"https://find-and-update.company-information.service.gov.uk/company/{number}/officers"}


def fetch_corporate_control_snapshot(company_number: str, *, api_key: str | None, client: httpx.Client | None = None,
                                     max_pages: int = 5) -> dict:
    """Retrieve a bounded, paginated PSC list, retaining UK corporate controllers only.

    This omits individuals and corporate entities lacking a UK company number or
    a clear UK registry declaration. Incomplete pagination fails closed rather
    than presenting a partial snapshot as a complete current register.
    """
    number = company_number.strip().upper()
    if not COMPANY_NUMBER.fullmatch(number):
        raise ValueError('Invalid Companies House company number')
    if not api_key or not api_key.strip():
        raise CompaniesHouseError('Companies House API key is not configured')
    if not 1 <= max_pages <= 5:
        raise ValueError('max_pages must be between 1 and 5')
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(25, connect=10), follow_redirects=False)
    try:
        profile = fetch_company_profile(number, api_key=api_key, client=client)
        controllers=[]
        for page in range(max_pages):
            try:
                with client.stream('GET', f'{API_BASE}/company/{number}/persons-with-significant-control',
                     params={'items_per_page':100,'start_index':page*100,'register_view':'false'},
                     auth=(api_key,''),headers={'Accept':'application/json','User-Agent':'SalesIntel market intelligence/1.0'},
                     follow_redirects=False) as response:
                    if response.status_code == 429:
                        raise CompaniesHouseError('Companies House rate limit reached; retry later')
                    if response.status_code != 200:
                        raise CompaniesHouseError(f'Companies House returned HTTP {response.status_code}')
                    parts=[]; size=0
                    for chunk in response.iter_bytes():
                        size+=len(chunk)
                        if size>MAX_BYTES: raise CompaniesHouseError('Companies House response exceeds size limit')
                        parts.append(chunk)
                payload=json.loads(b''.join(parts))
            except (httpx.HTTPError,ValueError) as exc:
                raise CompaniesHouseError('Companies House request or response failed') from exc
            items=payload.get('items') if isinstance(payload,dict) else None
            if not isinstance(items,list) or len(items)>100:
                raise CompaniesHouseError('Invalid Companies House PSC list')
            for item in items:
                if not isinstance(item,dict) or item.get('kind')!='corporate-entity-person-with-significant-control':
                    continue
                ident=item.get('identification') if isinstance(item.get('identification'),dict) else {}
                place=str(ident.get('place_registered') or '').lower()
                reg=str(ident.get('registration_number') or '').strip().upper()
                if not COMPANY_NUMBER.fullmatch(reg) or not any(x in place for x in ('companies house','england and wales','scotland','northern ireland')):
                    continue
                name=item.get('name'); nature=item.get('natures_of_control')
                if not isinstance(name,str) or not name.strip() or not isinstance(nature,list) or not nature or not all(isinstance(v,str) for v in nature):
                    continue
                controllers.append({'company_number':reg,'company_name':name.strip(),'notified_on':item.get('notified_on'),
                                    'ceased_on':item.get('ceased_on'),'nature_of_control':nature})
            total=payload.get('total_results')
            if isinstance(total,int) and total > page*100 and not items:
                raise CompaniesHouseError('Companies House PSC pagination ended before total results')
            if isinstance(total,int) and total <= page*100+len(items) or (not isinstance(total,int) and len(items)<100):
                return {'company_number':number,'company_name':profile['raw']['company_name'],
                        'source_url':f'https://find-and-update.company-information.service.gov.uk/company/{number}/persons-with-significant-control',
                        'retrieved_at':datetime.now(UTC).isoformat(),'controllers':controllers}
        raise CompaniesHouseError('Companies House PSC list exceeds the configured page limit')
    finally:
        if owned: client.close()
