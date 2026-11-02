# UK fire and security market network

MiSi stores public procurement releases as versioned source records and extracts supplier identities and published award assertions. It now collects Find a Tender and Contracts Finder incrementally, and Public Contracts Scotland monthly OCDS award packages. A separate worker backfills Contracts Finder and Scotland within an explicit daily request budget. These are **periodically refreshed sources**, not a complete or real-time UK market. The geographic and historical windows actually collected are visible through `/api/market-network/summary` and the operational checkpoint lanes.

Sector classification distinguishes a clear sector-specific title from an ambiguous broad project. Both can be retained, but ambiguous records are not used as qualified market suggestions. This is a conservative discovery filter, not proof of capability, maintenance, a buying need or delivery. Published award status is a source field and does not establish current delivery. Framework ceilings, lot values and award values must not be treated as supplier revenue or added without checking duplication. Legal entities link across notices only by matching published GB-COH numbers; a number in a notice is not independently verified by the registry. Unresolved identities are kept separate, so supplier identity counts can include duplicates.

Source revisions retain a content hash, publication and retrieval dates, last observed and supersession times. Notice contact-point fields are removed before storing structured content. The hash is over that minimised, normalised representation, not the publisher's original bytes; for Scotland the unstable package-position prefix is removed from the stored release ID. A partial unique index prevents two current revisions of a source record. The sector filter is applied to existing records dynamically, so earlier broad matches remain reviewable rather than silently disappearing. Procurement histories may have multiple releases for one OCID and should not be counted as independent contracts. A source's last successful check may be a historical backfill; it is not proof the live window is fully current. The latest-record publication-to-retrieval delay can also reflect historical backfill, not source-wide latency.

## Recorded public corporate evidence

`backend/reference_data/companies_house_reviewed_psc.json` is a manually transcribed selection from cached public Companies House significant-control pages, read on 28 October 2026. Pages were cached between approximately one week and four months earlier. The source revisions contain the selected structured transcription and its hash, not the original full page. Assertions are labelled as reported filings: they may be stale, are not independently verified by Companies House, and do not establish the complete ownership chain. This dataset is not automated registry monitoring.

The optional authenticated Companies House company-profile and corporate-control clients use exact company numbers and minimise personal information. Set `COMPANIES_HOUSE_API_KEY` securely in the worker environment; never commit it. Without a key these clients cannot run live. The key is a Companies House **REST API key**, not a streaming key; the optional corporate PSC import is not a streaming implementation or automatic scheduler:

```sh
PYTHONPATH=backend .venv/bin/python backend/scripts/market_company_profiles.py 06005074 03304503 00524469 02703471
PYTHONPATH=backend .venv/bin/python backend/scripts/market_company_control.py 03304503 00524469 08737754 03210833
```

For a fresh database only, the selected manually reviewed material can be imported with:

```sh
PYTHONPATH=backend .venv/bin/python backend/scripts/import_reviewed_psc.py backend/reference_data/companies_house_reviewed_psc.json
```

Check [Companies House authentication](https://developer.company-information.service.gov.uk/authentication), terms and rate limits before use. API clients were tested with mock responses; live authenticated access was not verified without a key.

## Suggestions and quality

The market suggestion engine is deterministic, not AI-driven. It now runs as the [UK Renewal Radar](RENEWAL_RADAR.md), which reads all stored records together and keeps one canonical contract row per contract. It proposes reviewable, source-linked published procurement signals and possible renewal windows only when its conservative rules are met. A suggestion is a hypothesis or published signal, not proof of an unadvertised need, current supplier, bid intention, or conversion probability. Review decisions express user preference and do not establish market truth. Suggestion versions and withdrawn states are retained. Existing users can prepare a public-research brief and choose whether to start a model-backed investigation; no model call is automatic. The company view can also connect a supplier award to a reported control filing when both name the exact company number, with both source links and dates. The two sources establish different reported facts; this connection neither independently corroborates either fact nor attributes the supplier's award to its controller. General cross-source reasoning and calibrated pursuit prediction are not implemented.

A small manually reviewed, non-representative benchmark is in `backend/reference_data/market_relevance_sample.json`. Evaluate the records actually present in the configured database with:

```sh
PYTHONPATH=backend .venv/bin/python backend/scripts/evaluate_market_relevance.py
```

It reports missing records, accepted precision, recall and ambiguous decisions for this small convenience sample, not an industry-wide accuracy claim.

## Local operation on macOS

Apply the Alembic migrations in a versioned deployment. The existing local pilot was created before Alembic; its new tables were created additively. Do not blindly stamp or replace an unversioned database. Back it up and evaluate its schema before migration.

The user-level LaunchAgents are generated from the actual checkout and SQLite path without embedding API keys:

```sh
PYTHONPATH=backend .venv/bin/python backend/scripts/generate_market_launch_agents.py --database-path '.runtime/false-alarm-pilot-v2.db'
```

Five generated agents are used on this Mac: `com.misi.market.find.a.tender`, `com.misi.market.contracts.finder`, `com.misi.market.public.contracts.scotland`, `com.misi.market.renewal.radar`, and `com.misi.market.backfill`. The source and radar agents use `RunAtLoad` and `KeepAlive`; the backfill agent restarts on failure and exits when its configured work completes. They run after this macOS user logs in, not while the computer is shut down or asleep. Periods of downtime are caught up via saved windows/checkpoints where source availability permits.

Inspect status and logs:

```sh
launchctl print gui/$(id -u)/com.misi.market.find.a.tender
launchctl print gui/$(id -u)/com.misi.market.contracts.finder
launchctl print gui/$(id -u)/com.misi.market.public.contracts.scotland
launchctl print gui/$(id -u)/com.misi.market.backfill
tail -f .runtime/market-find-a-tender.log .runtime/market-contracts-finder.log .runtime/market-public-contracts-scotland.log .runtime/market-backfill.log
```

To stop a particular job for the current login, use `launchctl bootout gui/$(id -u)/LABEL` with one of the exact labels above. To start it again use `launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/LABEL.plist"`. Removing its plist is required to prevent future login starts; do so only if you intend to uninstall it. Logs are local files and should be rotated by the operator.

The backfill worker is configured for 2021–2025, one source request per cycle and at most 96 combined requests per UTC day. It shares source leases with live workers. A completed or failed window is recorded; failures after the configured attempts need operator review. This job can take many days. Starting a job is not evidence that a complete five-year history has been collected.

For an individual bounded run:

```sh
PYTHONPATH=backend .venv/bin/python backend/scripts/market_monitor.py --source find-a-tender --max-pages 2
PYTHONPATH=backend .venv/bin/python backend/scripts/market_monitor.py --source contracts-finder --max-pages 1
PYTHONPATH=backend .venv/bin/python backend/scripts/market_monitor.py --source public-contracts-scotland
PYTHONPATH=backend .venv/bin/python backend/scripts/market_backfill_watch.py --from-year 2021 --to-year 2025 --interval 60 --daily-budget 96 --system-curl
```

The Scotland source uses the system `curl` TLS trust store here because this Python environment cannot validate the source certificate; verification is not disabled, redirects are not followed, and requests are bounded. Each source has a database lease and checkpoint; file locks add same-host protection. HTTP retry delays are persisted so process restart cannot bypass them. A deterministic suggestion refresh runs after successful batches without network or model calls. Multi-host inference locking is not implemented.

## Recovery, backup and always-on hosting

For SQLite, make a consistent backup with the SQLite backup API rather than copying a live database file:

```sh
.venv/bin/python -c "import sqlite3; s=sqlite3.connect('.runtime/false-alarm-pilot-v2.db'); d=sqlite3.connect('.runtime/market-backup.db'); s.backup(d); d.close(); s.close()"
```

Stop writers before restoring a verified backup to the selected database path; retain the existing database until the restore has been checked. For PostgreSQL, use the deployment's tested backup and restore procedures. Keep backups outside the checkout and protect them as business data.

An always-on host is required to collect while the Mac is off. `ops/systemd/` contains **untested examples**, not an installed deployment. Adapt the paths, unprivileged account, environment file, database, migration and network policy before enabling them. The example source service uses a conservative daily interval; adjust individual source units within source limits. A multi-host deployment needs a shared transactional database and a shared inference lock; the single-host SQLite/file-lock arrangement is not a distributed system.

## Source gaps and operations

Find a Tender, Contracts Finder and Public Contracts Scotland have each returned genuine structured public records. Scotland's live source now reads pipeline, contract and award notices for the current month, and the previous month for a week after rollover; its historical backfill covers award notices only. Sell2Wales returned HTTP 502 during validation, and a permitted documented structured eTendersNI API was not established. Neither is claimed as operational. Other notice types, corporate news, accreditation and private-sector sources remain unconnected. See [MARKET_PROCUREMENT_SOURCES.md](MARKET_PROCUREMENT_SOURCES.md) for collection details and limitations. Follow source terms, rate limits and reuse restrictions; do not bypass access controls.

Failures are recorded in source state with a safe category, not the untrusted body. Resume a failed checkpoint by fixing the source problem and restarting its worker; do not reset or stamp data to force progress. An inaccessible or oversized monthly package needs operator investigation. The system does not yet provide a full dead-letter queue, verified current-contract model, complete framework/call-off reconciliation, automated corporate change tracking, or cross-source evidence corroboration.
