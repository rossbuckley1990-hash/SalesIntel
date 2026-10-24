# MiSi Living Intelligence — local delivery

A working local commercial workspace built on the existing Next.js/FastAPI application. The default Today view leads into source-aware discovery, the BREAKOUT-derived Intelligence Field, evidence review, transparent qualification, local decisions, actions, assets and a commercial outcome ledger. The original capabilities remain under `/classic`; their former dashboard shell is split into fourteen feature modules.

## Start the synthetic workspace

From the repository root, with Python 3.11+ and pnpm 10 available:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
pnpm install --frozen-lockfile
bash scripts/living-dev.sh
```

Open **http://127.0.0.1:3000**. API documentation is at **http://127.0.0.1:8001/docs**. Ctrl+C stops the owned processes. If dependencies already exist, only the last command is needed.

The script binds to loopback, explicitly selects `.runtime/living-demo.db`, disables the OpenAI key for this process and labels all demo records as synthetic. It does not read or modify the original `misi.db` or edit `.env`. No cloud deployment, model call or external market feed is part of this demo. Eight invented accounts contain attributable fixture evidence, gaps, actions, forecasts and two real accepted snapshots. Rerunning startup preserves this separate demo database and applies additive migrations.

For a production-build preview, stop development first and run:

```sh
MISI_FRONTEND_MODE=production bash scripts/living-dev.sh
```

This builds the frontend with the explicit local API URL and serves the compiled application on the same loopback address. It is still a local synthetic demo, not an authorised deployment.

## Four repeatable demonstrations

**A — Question to dossier.** Discover → enter “Find fire and security maintenance opportunities at universities in Yorkshire” → Explore intelligence → Assemble in the field. Select Alderwick University. Open the full workspace, inspect Evidence and its missing capacity field, then Decision. Record a rationale, named reviewer, responsible owner and date. Build pursuit pack. Open the saved version in Asset Studio and download PDF, editable Word or Excel. Reopen the page: the decision, action, asset and outcome link persist.

**B — Find missing margin.** Self-Delivery → select an account → change baseline/proposed share and disclosed cost assumptions. Compare baseline/proposed gross margin, contribution after bid/mobilisation, payment-delay proxy, sensitivity and April–March allocation. Use Explore in 3D for live geometry. Save the scenario explicitly, then Build business case. The source opportunity remains unchanged. Download editable Word or Excel; the workbook contains editable inputs and calculation formulas.

**C — Executive review.** Today shows financial bases, three dated open actions and differences between actual accepted snapshots. Asset Studio → Leadership briefing → Build asset. Review financial meaning, movement, monthly forecast, ownership and the source register; download PDF. Finance → Change ledger lets a reviewer inspect saved states and explicitly accept another snapshot.

**D — At-risk deal.** Intelligence Field → Westhaven Health Partnership → Reveal risk. Inspect missing engineering evidence or switch to Accessible data view. My Work → Create action with the linked opportunity, owner, date and consequence. Add prerequisite actions where needed. Continue an action to update status; completion requires an evidence reference, and unresolved prerequisites prevent closure. Outcomes separately records identified, investigating, approved, won and realised value. Realisation requires an explicit actual amount and verification evidence.

## Operating details

- **Cmd/Ctrl+K:** search saved records, open workspaces or submit a commercial question. Discovery is transparent local matching, not an unconfigured external AI search. “Five biggest at risk this quarter” applies a five-record limit, recorded risk and the current calendar quarter's submission dates. Quarter scope and matching basis are disclosed.
- **Imports:** CSV/XLSX, mapping, row preview, duplicates, explicit review and atomic commit. A stale or expired preview is rejected. Unspecified update fields are preserved. Missing annual revenue remains unknown even when TCV is supplied. Calculated annual gross margin uses supplied annual revenue × margin percentage. Values above 100% are rejected, not clamped.
- **Evidence:** source type, URL where present, capture date, rationale, confidence, staleness and local review. Acknowledgement never turns an estimate into a known fact.
- **Tender sources:** paste authorised document text and identify its document/page/clause. Exact lines containing must/shall/required/mandatory can be extracted, reviewed, excluded and captured with line references. Manual exact-clause capture is also supported. This is not comprehensive PDF/OCR or legal interpretation; original-source review remains necessary.
- **Eight saved asset formats:** dossier, bid/no-bid pack, pursuit plan, battlecard, self-delivery business case, LE1 forecast pack, leadership briefing and tender starter. Source-bound sections, immutable content versions, notes, review status and PDF/DOCX/XLSX exports. Pursuit actions remain editable in My Work; generated versions capture their state at generation.
- **Undo:** the header exposes the latest persisted change. Undo checks that records still match the audited after-state and reverses linked changes atomically. It refuses to overwrite newer work. Spatial undo is separate and never writes business data.
- **Outages:** source/API failures are visible and retryable. No missing values or failed integrations are replaced with invented facts. Existing authorised OpenAI/manual-assist research remains in the classic workspace.

## Finance contract

Scenario money uses Decimal, saved monetary columns use Numeric(20,2), and inputs reject nonfinite, negative or excessive values. The frozen legacy Float schema is preserved; no bulk conversion of confidential data was attempted.

For revenue `R`, share `s`, internal cost ratio `i`, subcontract ratio `c`, probability `p`, bid spend `b`, and incremental proposed mobilisation `m`:

- Internal cost = `R × s × i`; subcontract cost = `R × (1 − s) × c`.
- Annual gross margin = `R − internal cost − subcontract cost`.
- Baseline expected contribution = `p × baseline GM − b`.
- Proposed expected contribution = `p × (proposed GM − m) − b`.
- Working-capital proxy = annual delivery cost × payment delay / 365. This is not a cash-flow forecast.

At £1m annual revenue, 40%→70% share, 62%/84% cost ratios, 60% probability, £12k bid and £18k mobilisation: GM £248k→£314k, expected contribution £136.8k→£165.6k, contribution improvement £28.8k. Monthly penny allocation conserves the annual amount over twelve service months, then filters the requested April–March year. It deliberately does not equate annual revenue, TCV, weighted pipeline, secured work or realised cash. Existing LE1 calculation service is reused and its business definitions still require Finance sign-off.

## Architecture and migrations

Frontend business modules live in `frontend/src/features/workspace`; shared rendering and data-to-scene conversion in `features/field`; preserved functionality in `features/classic`. React displays backend results and never calculates authoritative finance totals. `/api/living` uses typed Pydantic contracts and focused services under `backend/app/services/living`.

Alembic revisions: `0001_legacy` freezes original tables; `0002_living` adds snapshots, reviews, decisions, scenarios, immutable asset versions, outcomes, requirements, audit events and import previews; `0003_action_details` adds durable completion references and validated action prerequisites. New databases migrate to head. For an existing database, first make and verify a backup, compare its actual schema to revision 0001, then **only if identical** stamp 0001 and upgrade. Do not run the legacy CREATE revision over populated tables. This adoption procedure has not been executed against the original database or a production PostgreSQL instance.

See [BREAKOUT traceability](BREAKOUT_PORT.md), [implementation audit](IMPLEMENTATION.md), [verification evidence](VERIFICATION.md), and the existing [enterprise plan](../ENTERPRISE_DEPLOYMENT.md).

## Enterprise deployment gates

This delivery is a local synthetic-data implementation. Reviewer names are unauthenticated review records. `/api/living` refuses production mode until identity is supplied; this does not retrofit authentication onto the legacy routes. Do not expose either server publicly.

Remaining authorised rollout work: Entra ID, backend roles and tenant isolation, trusted actor identities, approved model/data egress, live connector contracts and credentials, Finance-approved LE1 definitions, PostgreSQL migration/restore and concurrency tests, durable asset storage/retention, immutable audit controls, managed secrets, monitoring, security review and deployment approval. Local audit undo is designed for one workspace and is not a multi-user concurrency guarantee. Source collections and queries are bounded for the local demo, not load-tested enterprise scale. No successful production integration, authentication or 60 FPS hardware certification is claimed.
