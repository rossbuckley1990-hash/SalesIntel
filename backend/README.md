# SalesIntel Backend

FastAPI backend skeleton for SalesIntel, SalesIntel.

## Responsibilities

- Serve SalesIntel API endpoints.
- Load environment-based configuration.
- Own database access.
- Own future source connectors and intelligence services.
- Keep browser code away from secrets.

OpenAI analysis is integrated through backend-only services. `OPENAI_API_KEY` is optional for startup and is only required when an OpenAI-backed analysis endpoint is called.

Tracker uploads are accepted only as CSV/XLSX files and are size-limited by `MAX_UPLOAD_BYTES` (5MB by default). For real-data runs, use only source data you are allowed to process in this unauthenticated local environment.

## Setup

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e "backend[dev]"
```

## Run

```bash
uvicorn app.main:app --app-dir backend --reload --port 8000
```

Endpoints:

- `GET /health`
- `GET /api/version`
- `GET /api/opportunities`
- `GET /api/opportunities/{id}`
- `GET /api/market-signals`
- `GET /api/buyers`
- `GET /api/buyers/{id}`
- `GET /api/competitors`
- `GET /api/executive-actions`
- `GET /api/finance-forecast`
- `GET /api/finance-forecast/summary`
- `GET /api/dashboard`
- `POST /api/refresh-market-data`
- `GET /api/source-runs`
- `POST /api/upload-tracker`
- `POST /api/intelligence/opportunity-analysis`
- `POST /api/intelligence/analyse-opportunity/{opportunity_id}`
- `POST /api/intelligence/generate-executive-summary`
- `POST /api/intelligence/internet-research`
- `POST /api/intelligence/research-opportunity`
- `GET /api/enrichment/runs`
- `GET /api/enrichment/runs/{run_id}`
- `GET /api/enrichment/opportunities/{opportunity_id}`
- `GET /api/enrichment/field-intelligence?entity_type=opportunity&entity_id=1`

Useful list filters include `sector`, `region`, `stage`, `risk_rating`, `owner`, and `search` where relevant to the resource.

## Database

The local MVP uses SQLite by default:

```bash
DATABASE_URL=sqlite:///./misi.db
```

Relative SQLite paths are resolved from the repository root so seeding and running the backend use the same local database.

`DATABASE_URL` controls the active database. PostgreSQL can be used by setting:

```bash
DATABASE_URL=postgresql://misi_user:change-me@db-host:5432/misi
```

The backend normalizes bare `postgresql://` and `postgres://` URLs to SQLAlchemy's `postgresql+psycopg` driver. SQLite-only connection arguments are applied only to SQLite; PostgreSQL uses SQLAlchemy's normal connection pooling with pre-ping enabled for stale connection handling.

For internal pilot or production, add Alembic migrations before loading real data. Treat `python backend/scripts/migrate.py` as a local/demo table creation helper, not a production migration runner.

Create or update local tables:

```bash
python backend/scripts/migrate.py
```

Reset local SQLite to empty tables with no demo data:

```bash
./scripts/reset-empty-db.sh
```

The empty reset script refuses non-SQLite databases unless `MISI_ALLOW_DESTRUCTIVE_RESET=true` is set.

Insert synthetic sample records:

```bash
./scripts/seed-demo.sh
```

The seed data is fictional and includes realistic UK Fire & Security scenarios across retail, healthcare, education, police, local authority, government, logistics, utilities, housing, transport, commercial property, and facilities management.

`POST /api/refresh-market-data` currently runs controlled placeholder source connectors. It is useful for connector framework testing, not live tender gathering, until approved real source integrations are added.

## Internet Intelligence

### Public research provider

Discover's universal research, saved-lead contact research and virtual-sensor site research can use either OpenAI (the default) or Anthropic. Configure the backend environment, then restart the API:

```bash
# Default: OpenAI Responses API with web search
RESEARCH_PROVIDER=openai
OPENAI_API_KEY=your-backend-key
OPENAI_MODEL=gpt-6.1-terra

# Alternative: Anthropic Messages API with web search enabled on the account
# RESEARCH_PROVIDER=anthropic
# ANTHROPIC_API_KEY=your-backend-key
# ANTHROPIC_MODEL=claude-sonnet-4-6
```

Keep keys on the backend, never in `NEXT_PUBLIC_*` settings. Specify a model available to the chosen account that supports web search and structured outputs. A missing key, unsupported model or disabled tool fails the run instead of switching providers silently. Anthropic's web search with citations and strict JSON outputs are incompatible in a single request, so SalesIntel uses a bounded search request followed by a separate structured extraction request. This may affect latency, results and API charges. SalesIntel only accepts source links returned in an actual completed web-search result, and those links and model-extracted claims still need independent review. The Anthropic integration is tested with simulated vendor responses; it has not been tested here against a live Anthropic account. Other legacy analysis endpoints still use OpenAI and `OPENAI_MODEL`.

`POST /api/intelligence/internet-research` uses the backend OpenAI client and the Responses API `web_search` tool to research public web information for Market Radar, tender intelligence, competitor intelligence, buyer intelligence, opportunity intelligence, pipeline forecast context and self-delivery signals.

The endpoint requires `OPENAI_API_KEY` and defaults to `gpt-6.1-terra`. Set `OPENAI_MODEL` to another model available to your API project that supports the Responses API web search tool if needed. An existing `OPENAI_MODEL` in `.env` overrides the default; restart the backend after changing it. The endpoint returns structured JSON and source URLs for review. It does not persist findings automatically; importing findings into SalesIntel records should be a reviewed workflow.

## AI Enrichment Data

SalesIntel includes a durable enrichment data model for AI-first opportunity records:

- `enrichment_runs` records each enrichment attempt, model used, search status,
  sources checked and import/update counts.
- `field_intelligence` stores field-level value status, confidence, rationale and
  source URLs for known, inferred, estimated, unknown, user-provided and
  system-calculated values.
- `opportunity_enrichments` stores the commercial intelligence pack linked to an
  opportunity and enrichment run.

Read endpoints under `/api/enrichment/*` expose these records for future premium
frontend enrichment views. Creation will remain controlled by backend enrichment
services so raw AI output is validated before it enters the database.

`POST /api/intelligence/research-opportunity` is the standing-start AI workflow.
It accepts a rough query, runs public internet research, converts the evidence
into a structured commercial opportunity pack, creates or updates an opportunity,
stores field-level value status and confidence, and records unknown fields with a
reason and next step.

The OpenAI conversion step uses a strict nested JSON schema. Every core
opportunity field is returned as `{ value, value_type, confidence_score,
rationale, source_urls }`, where `value_type` is one of `known`, `inferred`,
`estimated`, or `unknown`. Unknown AI fields must validate with confidence `0`;
numeric fields such as revenue, margin, probability and strategic fit are
normalised before being written to the database.

## Tests

```bash
python -m pytest backend/tests
```
