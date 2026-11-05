# London Fire Brigade incident data import

The optional importer retrieves the public [London Fire Brigade incident dataset](https://data.london.gov.uk/dataset/london-fire-brigade-incident-records-em8xy) under the Open Government Licence v2. Its facts concern **attendances**, not all alarm activations. `AFA` means an automatic fire alarm attendance, not a verified apparatus fault or a failure by a supplier. The dataset covers London only.

From the repository root, preview the current official workbook without changing the database:

```bash
.venv/bin/python backend/scripts/import_lfb_incidents.py --download
```

To download and atomically replace the current LFB snapshot in the backend's configured database, add `--apply`:

```bash
.venv/bin/python backend/scripts/import_lfb_incidents.py --download --apply
```

The downloader uses the fixed HTTPS London Datastore URL, refuses redirects and limits the download to 200 MiB. It keeps the workbook only in a temporary directory. The run records its retrieval and import times, source, acquisition method and file SHA-256. There is **no scheduled refresh**. The datastore currently describes monthly updates in its text and quarterly in its metadata; check the publication for updates rather than assuming either cadence.

Alternatively, download the workbook from the official dataset page and pass the local file path. Add `--retrieved-at 2026-10-28T12:00:00Z` using the actual download time if known. Local files are labelled as user-supplied and their SHA-256 does not independently establish their origin.

Only non-residential incidents with a positive UPRN are retained. All incident types and the original `AddressQualifier` are preserved; downstream matching must filter qualifiers explicitly. A UPRN is a location identifier, not proof of the current occupier, account owner or maintenance provider. Rows with dwelling, missing, redacted or invalid UPRNs are excluded. Incident date ranges are ranges **among retained records**, not proof that all dates or properties are covered. Comparable-site analysis must account for missing exposure, location uncertainty, reporting/attendance policy and time coverage.

Applying a new workbook replaces the incident snapshot in one transaction. A failure rolls back the replacement; importing the same latest file again does nothing. The importer keeps run metadata but does not retain the raw workbook or reconcile source revisions automatically. File provenance, service status and date coverage should be checked before using results.
