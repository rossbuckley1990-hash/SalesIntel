"""Public Contracts Scotland's documented monthly OCDS API.

https://api.publiccontractsscotland.gov.uk/v1
System curl is an optional platform TLS transport, useful where the Python CA
store differs from the operating system store. It does not disable TLS checks.
"""
from __future__ import annotations
import calendar
import json
import re
import subprocess
from datetime import UTC, datetime
import httpx

API_URL = 'https://api.publiccontractsscotland.gov.uk/v1/Notices'
MAX_BYTES = 8_000_000
NOTICE_TYPES = frozenset((1,2,3,4,5,6,7,12,13,14,15,20,21,22,23,24,25,101,102,103))
NOTICE_ID = re.compile(r'^[A-Z]{3}[0-9]{1,12}$')
RELEASE_ID = re.compile(r'^rls-[0-9]+-([A-Z]{3}[0-9]{1,12})$')
OCID = re.compile(r'^ocds-r6ebe6-[0-9]{1,20}$')


def _params(year: int, month: int, notice_type: int) -> dict:
    if not (2019 <= year <= 2100 and 1 <= month <= 12 and notice_type in NOTICE_TYPES):
        raise ValueError('Invalid Scottish notice month or type')
    return {'dateFrom':f'{month:02d}-{year:04d}', 'noticeType':str(notice_type), 'outputType':'0'}


def fetch_month(year: int, month: int, notice_type: int, *, client=None, system_curl=False) -> list:
    params = _params(year,month,notice_type)
    if system_curl:
        # No shell, no redirects, bounded runtime and bytes, trusted TLS as configured by system curl.
        url = f'{API_URL}?dateFrom={params["dateFrom"]}&noticeType={params["noticeType"]}&outputType=0'
        try:
            result = subprocess.run(['/usr/bin/curl','--silent','--show-error','--fail','--max-time','45',
                                     '--max-filesize',str(MAX_BYTES),url],capture_output=True,timeout=50,check=True)
        except (OSError,subprocess.SubprocessError) as exc:
            raise RuntimeError('Public Contracts Scotland request failed') from exc
        body=result.stdout
        if len(body) > MAX_BYTES:
            raise ValueError('Public Contracts Scotland response exceeded size limit')
    else:
        owned=client is None
        client=client or httpx.Client(timeout=httpx.Timeout(45,connect=10),follow_redirects=False,
                                     headers={'User-Agent':'MiSi public-market-monitor/1.0','Accept':'application/json'})
        try:
            with client.stream('GET',API_URL,params=params,follow_redirects=False) as response:
                response.raise_for_status()
                parts=[]; size=0
                for part in response.iter_bytes():
                    size += len(part)
                    if size > MAX_BYTES: raise ValueError('Public Contracts Scotland response exceeded size limit')
                    parts.append(part)
            body=b''.join(parts)
        finally:
            if owned: client.close()
    payload=json.loads(body)
    # A month with no notices yet is a full package that omits the releases key.
    if isinstance(payload,dict) and 'releases' not in payload and payload.get('publisher') and payload.get('publishedDate'):
        return []
    if not isinstance(payload,dict) or not isinstance(payload.get('releases'),list) or len(payload['releases']) > 5000:
        raise ValueError('Invalid Public Contracts Scotland release package')
    return payload['releases']


def record_for_release(release: dict, retrieved_at: datetime) -> dict | None:
    if not isinstance(release,dict): return None
    id_,ocid=release.get('id'),release.get('ocid')
    match=RELEASE_ID.fullmatch(id_) if isinstance(id_,str) else None
    if not match or not isinstance(ocid,str) or not OCID.fullmatch(ocid): return None
    notice_id=match.group(1)
    if not NOTICE_ID.fullmatch(notice_id): return None
    try:
        published=datetime.fromisoformat(str(release['date']).replace('Z','+00:00'))
        if published.tzinfo is None: return None
    except (ValueError,KeyError,TypeError): return None
    def redact(value):
        if isinstance(value,dict): return {k:redact(v) for k,v in value.items() if k not in ('contactPoint','contactPoints','person','persons')}
        if isinstance(value,list): return [redact(v) for v in value]
        return value
    raw=redact(release)
    # Publisher's rls-<index>-... prefix is position in this monthly package and
    # can shift; preserve a stable canonical notice ID for revision comparison.
    raw['id']=notice_id
    return {'source_key':'public_contracts_scotland','release_id':notice_id,'ocid':ocid,
            'source_url':f'https://www.publiccontractsscotland.gov.uk/search/show/search_view.aspx?ID={notice_id}',
            'published_at':published.astimezone(UTC),'retrieved_at':retrieved_at,'raw':raw}
