# Optional NHS ERIC 2025/26 import

This is an **opt-in, local CSV import**, not a continuously updated feed. It uses
NHS England's published site-level ERIC 2025/26 v2 file to create observations
about general estates backlog. This is not fire or security-specific evidence,
does not establish a compliance failure or supplier underperformance, and is not
the value of a sales opportunity. ERIC is an annual return for England, not a
real-time or UK-wide account of maintenance.

1. Open the [NHS England ERIC 2025/26 publication](https://digital.nhs.uk/data-and-information/publications/statistical/estates-returns-information-collection/summary-page-and-dataset-for-eric-2025-26)
   and download **ERIC - 2025/26 - Site data**, v2. Record the time you downloaded it.
2. From the repository root, preview the file (substitute the local path and
   actual download time, including its timezone):

   ```bash
   .venv/bin/python backend/scripts/import_eric_2025_26.py /path/to/eric-site-data-v2.csv --retrieved-at 2026-10-28T12:00:00+00:00
   ```

3. After inspecting the preview and confirming the configured backend database,
   append `--apply` to import. It processes batches of 500 using MiSi's evidence
   import, so retrying the same input does not duplicate observations. A failed
   later batch does not roll back earlier completed batches.

The script accepts only the exact published v2 file with SHA-256
`50a6286f05a7e3bd06e1849120d85392c17c25a4a17eaa4ae2779403cc3fd931`.
It skips sites with no positive recorded backlog and does not turn unavailable
values into zero. The imported observation retains the site and trust IDs,
publication date and reporting-period end. Check NHS England's [data-quality
guidance and updated publication](https://digital.nhs.uk/data-and-information/publications/statistical/estates-returns-information-collection/summary-page-and-dataset-for-eric-2025-26)
before using a finding; estimates and definitions may be revised. A changed
file needs a reviewed adapter update rather than bypassing the hash check.

Contains information from NHS England, licenced under the current version of
the Open Government Licence. See NHS England's [terms and conditions](https://digital.nhs.uk/about-nhs-digital/terms-and-conditions),
including its direction to refresh cached content every 24 hours. This importer
does not refresh or reconcile changes automatically; an operator must check the
source and updates before reuse. There is no implied NHS England endorsement.
