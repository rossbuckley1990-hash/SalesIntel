# Public false-alarm sensor pilot

This local pilot searches London Fire Brigade incident records for repeated
automatic fire-alarm attendances at non-residential UPRNs. It compares each
site with other observed sites of the same reported property type over the same
post-policy period. The list is sorted by attendance count, not likelihood of
purchase or commercial value. It is a research aid, not a calibrated model.

### Candidate inspection context

The optional inspection link uses a London Fire Brigade [public inspection and audit workbook](https://www.data.gov.uk/dataset/1d299ca4-a431-4068-80fa-57af4b502762/regulatory-fire-safety-inspections-and-audits1) and the already imported NHS site references. After obtaining the published workbook, run `python backend/scripts/import_lfb_inspections.py /path/to/workbook.xlsx` with `DATABASE_URL` set to the intended database. The import checks its format, processes the local file and records its filename and SHA-256. For this local pilot, the workbook downloaded was the February 2026 publication, not a live feed. A hash identifies the file, not its authenticity.

A candidate link requires the same full postcode and the exact historical hospital name in the inspection address; ambiguous matches are excluded. The inspection dataset does not provide a matching UPRN, so the linked visit may concern a different building or block. An outcome is historical and may have been remedied or superseded. Do not infer current non-compliance, equipment faults, incumbent performance, or buying intent. A missing match is not evidence that no inspection occurred. The dataset is not refreshed automatically.

The source only records attended incidents. Zero-attendance sites are absent,
and site size, hours, alarm exposure, call-handling policy, occupier and service
provider are not known. Exact-location qualifiers reduce but do not eliminate
location ambiguity. The 29 October 2024 policy transition is excluded from the
analysis. A UPRN can be shared by multiple organisations or site descriptions.
Neither attendance nor an ERIC match proves a fault, poor maintenance,
non-compliance, current occupancy or a buying requirement. Verify all sources,
contact roles and the site before engagement.

## Open the prepared local pilot

Run `pnpm dev:sensor`, open `http://127.0.0.1:3100`, then choose **Discover →
Repeated fire-alarm attendances**. This command uses the separate
`.runtime/false-alarm-pilot-v2.db` and ports 8002/3100. It does not modify the
main SalesIntel database. Override the database path with `MISI_PILOT_DB`; override
ports with `MISI_PILOT_API_PORT` and `MISI_PILOT_FRONTEND_PORT`. The backend
reads `OPENAI_API_KEY` and `OPENAI_MODEL` from the existing local configuration
for the optional web research action. Research sends selected public property
context to the configured model and searches the web. It does not contact anyone
or automatically create a pipeline record. This local app is unauthenticated and
must not be exposed publicly.

## Build or refresh a local snapshot

To build a new local database from scratch, set `DATABASE_URL` to its absolute
SQLite path and run the import scripts. Run these commands from the repo root:

```bash
export DATABASE_URL="sqlite:///$PWD/.runtime/false-alarm-pilot-v2.db"
.venv/bin/python backend/scripts/import_lfb_incidents.py --download --apply
```

The fixed official download is streamed to a temporary file; preview first by
omitting `--apply`. A successful apply atomically replaces the incident snapshot;
an unchanged file is skipped. The published workbook, extraction and optional
local-file import are described in [LFB_IMPORT.md](../backend/LFB_IMPORT.md).
The dataset's public page describes monthly updates, while its metadata says
quarterly; inspect the actual source date and coverage. There is no scheduler.

Download the **2025/26 ERIC site data v2 CSV** from the [NHS England publication](https://digital.nhs.uk/data-and-information/publications/statistical/estates-returns-information-collection/summary-page-and-dataset-for-eric-2025-26),
then preview and import its site references:

```bash
.venv/bin/python backend/scripts/import_eric_site_references.py /path/to/eric-site-data-v2.csv
.venv/bin/python backend/scripts/import_eric_site_references.py /path/to/eric-site-data-v2.csv --apply
```

Only exact numeric identifiers are used: scientific notation in the published
file may have rounded away identifying digits. All same-UPRN matches are kept
as historical references. This import is pinned to the exact published v2 file;
it does not automatically refresh or reconcile changes. NHS England asks users
to refresh cached content every 24 hours; consult the [NHS terms](https://digital.nhs.uk/about-nhs-digital/terms-and-conditions)
and the current publication before reuse. Contains information from NHS England,
licenced under the current version of the Open Government Licence. LFB data is
provided under the Open Government Licence v2; see its [dataset page](https://data.london.gov.uk/dataset/london-fire-brigade-incident-records-em8xy).

This is a London-only, single-sensor pilot. Other UK sources, entity-resolution
validation, outcome feedback, historical backtesting and automated refresh
remain necessary before making claims about predictive accuracy or UK-wide
coverage.
