# Procurement source operations

The source collectors below extend the existing Find a Tender collector. They do not by themselves establish current incumbency, eligibility, an open requirement or a unique contract count. A publication and its later versions may create multiple award observations. Classifier matches must be reviewed; no national coverage is implied.

## Contracts Finder

Official source: [OCDS Search API](https://www.contractsfinder.service.gov.uk/apidocumentation/Notices/1/GET-Published-Notice-OCDS-Search), OGL v3, filtered by publication/update date. The collector uses the source's release package, a fixed window and validated pagination cursor. Each page commits data and cursor atomically. Current polling uses `contracts_finder`; historical checkpoint names are independent per year (`contracts_finder_backfill_YYYY`). All these checkpoints share one source lease and rate-limit state, preventing concurrent API calls from the same database. After a 403 the documented five-minute cooldown is persisted across restarts; no more requests are sent before it expires. Multiple pages within a batch are spaced at least five seconds apart.

With the same `DATABASE_URL` as the application, repeat one bounded batch until `year_complete` becomes true:

```sh
PYTHONPATH=backend .venv/bin/python backend/scripts/market_sources_backfill.py contracts-finder --year 2021 --max-pages 2
```

An existing partially completed checkpoint keeps its original fixed window until completion, even if a later invocation requests a longer end date. Then the next invocation continues from the watermark with a five-minute overlap. Backfills and periodic collection are asynchronous and do not guarantee historical completeness or automatic correction of records deleted from the publisher.

## Public Contracts Scotland

Official source: [PCS OCDS API](https://api.publiccontractsscotland.gov.uk/v1). Its published API returns an entire month and notice type rather than cursor pages. The integration processes one month atomically; a failure reruns that month, and repeated unchanged releases do not produce new revisions. Notice type 3 is an award notice; other types are opt-in and must be processed separately. This captures the source's historic publication regime and does not imply all Scottish procurements are included. The payload and request are bounded, redirects are not followed, and contact-point fields are omitted before storage.

```sh
PYTHONPATH=backend .venv/bin/python backend/scripts/market_sources_backfill.py scotland --year 2024 --month 1 --notice-type 3 --system-curl
```

`--system-curl` uses `/usr/bin/curl` with the operating system's standard TLS checks, no shell, no redirect following, and fixed official host. It addresses the observed difference between macOS's trusted certificate store and the current Python CA bundle. Without it, the default httpx TLS verifier is used. Neither mode bypasses certificate verification. The source can be polled on the current month, but the complete month is downloaded each time, so choose a conservative schedule. If a monthly package exceeds 8 MB or 5,000 releases the collector fails safely rather than pretending coverage is complete.

## Source gaps

The Welsh Government's [OCDS guide](https://www.sell2wales.gov.wales/helpandresources/ocds/dataaccessinfo) links to a Sell2Wales API, but the linked API returned HTTP 502 in this environment during validation; no working integration is claimed. The Northern Ireland Department of Finance identifies [eTendersNI](https://www.finance-ni.gov.uk/topics/etendersni) as the procurement portal. A permitted, documented public structured endpoint has not been established here, so no undocumented endpoint or restricted access is used. Find a Tender and Contracts Finder can contain some devolved notices, but are not complete substitutes for these feeds.

## Supervised historical backfill

For a bounded, resumable process covering completed calendar years, use:

```sh
PYTHONPATH=backend .venv/bin/python backend/scripts/market_backfill_watch.py --from-year 2021 --to-year 2025 --interval 60 --daily-budget 96 --system-curl
```

The worker alternates one Contracts Finder page and one Scottish award month and type (3 or 103), subject to source leases, a minimum 30-second pacing interval and a persisted combined UTC daily request budget. It derives pending work from the existing year/month checkpoints after restart. It does not refetch successfully completed historical months automatically; the separate current-month monitor serves freshness. A Scottish month with three failed attempts is left as a failed work item and listed in the final `completed_with_failures` output; an operator may retry it using the single-month command above. Completion means those configured source windows were processed, not that all notices were correctly identified or that the wider UK market is fully covered. Run under a process supervisor which restarts on failure but does not continuously restart successful completion.
