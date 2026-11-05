"""Bounded, attributed UK public food-premises context.

The food register says nothing about fire or security maintenance or a buying
requirement. Postcode matches may identify multiple distinct premises.
"""
from datetime import UTC, datetime
import json
import re

import httpx


FSA_ENDPOINT = "https://api.ratings.food.gov.uk/Establishments"
FSA_RECORD = "https://ratings.food.gov.uk/business/"
SOURCE_URL = "https://api.ratings.food.gov.uk/help"
MAX_BYTES = 524_288
MAX_LIMIT = 10
PAGE_SIZE = 20
_POSTCODE = re.compile(r"(?:[A-Z]{1,2}[0-9][A-Z0-9]?[0-9][A-Z]{2}|GIR0AA)")


class PublicEstateError(RuntimeError):
    """A public source could not return a usable result."""


def normalise_postcode(value: str) -> str:
    compact = re.sub(r"\s+", "", value.upper())
    if not _POSTCODE.fullmatch(compact):
        raise ValueError("Enter a full UK postcode.")
    return compact[:-3] + " " + compact[-3:]


def _clean(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join("".join(c if c.isprintable() else " " for c in value).split())[:limit]


def search_establishments(postcode: str, limit: int = 10, *, client: httpx.Client | None = None) -> dict:
    postcode = normalise_postcode(postcode)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError("Select between one and ten records.")
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(15, connect=5), follow_redirects=False,
                                   headers={"x-api-version": "2", "Accept": "application/json"})
    try:
        with client.stream("GET", FSA_ENDPOINT, params={"address": postcode, "pageNumber": 1, "pageSize": PAGE_SIZE},
                           headers={"x-api-version": "2", "Accept": "application/json"}) as response:
            response.raise_for_status()
            if "application/json" not in response.headers.get("content-type", "").lower():
                raise PublicEstateError("The public source returned an unsupported format.")
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise PublicEstateError("The public source response exceeded the size limit.")
                chunks.append(chunk)
        data = json.loads(b"".join(chunks))
        if not isinstance(data, dict) or not isinstance(data.get("establishments"), list) or len(data["establishments"]) > PAGE_SIZE:
            raise PublicEstateError("The public source returned an invalid response.")
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        raw_total = meta.get("totalCount")
        total = raw_total if isinstance(raw_total, int) and not isinstance(raw_total, bool) and raw_total >= 0 else None
        records = []
        seen = set()
        for item in data["establishments"]:
            if not isinstance(item, dict):
                continue
            try:
                site_postcode = normalise_postcode(_clean(item.get("PostCode"), 20))
            except ValueError:
                continue
            if site_postcode != postcode:
                continue
            identifier = str(item.get("FHRSID", ""))
            if not identifier.isascii() or not identifier.isdigit() or len(identifier) > 18 or identifier in seen:
                continue
            name, kind = _clean(item.get("BusinessName"), 255), _clean(item.get("BusinessType"), 120)
            if not name:
                continue
            seen.add(identifier)
            address = ", ".join(filter(None, (_clean(item.get(f"AddressLine{i}"), 100) for i in range(1, 5))))[:300]
            records.append({"id": identifier, "name": name, "business_type": kind, "address": address,
                            "postcode": site_postcode, "source_url": FSA_RECORD + identifier})
        clipped = len(records) > limit
        records = records[:limit]
        extract = _clean(meta.get("extractDate"), 50)
        try:
            datetime.fromisoformat(extract.replace("Z", "+00:00"))
        except ValueError:
            extract = ""
        return {"postcode": postcode, "records": records, "retrieved_at": datetime.now(UTC).isoformat(),
                "source": {"title": "Food Standards Agency food establishment register", "url": SOURCE_URL,
                           "scope": "England, Scotland, Wales and Northern Ireland", "source_extracted_at": extract},
                "scanned": len(data["establishments"]), "total_source_matches": total,
                "more_results_possible": clipped or total is None or total > len(data["establishments"]),
                "limitations": ["This register concerns food establishments, not all premises; records may be incomplete or stale.",
                                "A postcode can contain multiple sites; independently confirm the exact premises, current occupier and decision maker.",
                                "Food registration and inspection data do not establish fire or security conditions, maintenance gaps or purchasing intent.",
                                "Only the first source page was checked; empty results do not show that a site or business is absent."]}
    except (httpx.HTTPError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise PublicEstateError("The public food establishment source is unavailable or invalid.") from exc
    finally:
        if owned:
            client.close()
