"""Bounded Companies House company-profile retrieval.

The authenticated public API is optional.  A company number must be supplied;
name similarity never establishes identity.  Profiles do not prove capability,
contract delivery or ownership.  No officers or personal data are collected.
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
                               headers={"Accept": "application/json", "User-Agent": "MiSi market intelligence/1.0"},
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
                     auth=(api_key,''),headers={'Accept':'application/json','User-Agent':'MiSi market intelligence/1.0'},
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
