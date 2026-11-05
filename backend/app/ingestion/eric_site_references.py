"""Extract exact, unambiguous-looking identifiers from the published ERIC file."""
import csv
import io
import re

from app.ingestion.eric_2025_26 import SOURCE_URL, validate_official_file


def parse_site_references(data: bytes) -> list[dict[str, str]]:
    validate_official_file(data)
    reader = csv.reader(io.StringIO(data.decode("cp1252"), newline=""))
    try:
        codes, names = next(reader), next(reader)
        fields = {key: names.index(key) for key in (
            "Trust Code", "Trust Name", "EFM Site Id", "Site Name", "Post Code", "UPRN"
        )}
    except (StopIteration, ValueError) as exc:
        raise ValueError("Unexpected ERIC site headers") from exc
    if len(codes) != len(names):
        raise ValueError("Unexpected ERIC header lengths")
    records = []
    for row in reader:
        if len(row) != len(names):
            raise ValueError("Unexpected ERIC row length")
        trust, name, site_id, site, postcode, uprn = (row[fields[key]].strip() for key in fields)
        # Scientific notation in the published file may be rounded; it cannot
        # safely identify a property. Exclude it rather than inventing digits.
        if not re.fullmatch(r"[1-9][0-9]{0,19}", uprn):
            continue
        if not re.fullmatch(r"[A-Za-z0-9]+", trust) or not re.fullmatch(r"[A-Za-z0-9]+", site_id) or not name or not site:
            continue
        records.append({"source_record_id": f"eric-2025-26:{site_id}", "uprn": uprn,
                        "organisation_id": f"nhs-ods:{trust}", "organisation_name": name,
                        "site_name": site, "postcode": postcode, "source_url": SOURCE_URL,
                        "source_period": "2025/26"})
    return records
