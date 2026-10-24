# Living Intelligence workspace

Start the new synthetic workspace with `pnpm dev:living`. See [startup, demonstrations and deployment boundaries](docs/living/README.md). The original workspace remains at `/classic`.

# MiSi - Mitie Sales Intelligence

MiSi is a secure sales intelligence command centre for Mitie Fire & Security. It is designed to combine internal pipeline data, self-delivery data, public tender signals, buyer intelligence, competitor intelligence, OpenAI-powered opportunity analysis, finance forecasting, and executive reporting.

Phase 0 establishes the repository, local development workflow, backend boundary, frontend shell, and extension points. The backend now includes early rule-based intelligence, LE1-style forecasting, and a backend-only OpenAI analysis integration.

## Repository Structure

```text
.
├── frontend/      # Next.js, TypeScript, Tailwind app
├── backend/       # Python FastAPI service
├── docs/          # Architecture and product notes
├── sample_data/   # Synthetic local MVP samples and blank import template
├── scripts/       # Local development helpers
├── .env.example   # Placeholder-only configuration
└── README.md
```

## Prerequisites

- Node.js 20+ with pnpm
- Python 3.11+

## Configuration

Copy the placeholder environment file before running locally:

```bash
cp .env.example .env
```

Do not commit real secrets. The frontend only uses `NEXT_PUBLIC_*` variables. OpenAI credentials are read by the backend only.

Local data is not protected by authentication yet. Use synthetic data for demos, or explicitly approved real data only in a controlled local environment. Be deliberate about what you send for AI analysis: OpenAI calls are backend-only, but opportunity details included in an analysis request are sent to the configured OpenAI API.

## One-Time Local Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e "backend[dev]"
pnpm install
```

After setup, choose either empty real-data mode or synthetic demo mode. Do not run the demo seed if you want a clean real-data workspace.

## Start Backend

```bash
. .venv/bin/activate
uvicorn app.main:app --app-dir backend --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## Start Frontend

```bash
pnpm --dir frontend dev
```

Open [http://localhost:3000](http://localhost:3000).

The frontend reads backend data from `NEXT_PUBLIC_API_BASE_URL`, defaulting to
`http://localhost:8000` when the variable is not set. Only `NEXT_PUBLIC_*`
values are exposed to browser code; do not put OpenAI keys or backend secrets in
frontend environment variables.

## Run Both Apps

After installing dependencies for both apps:

```bash
./scripts/dev.sh
```

The backend runs on [http://localhost:8000](http://localhost:8000) and the frontend runs on [http://localhost:3000](http://localhost:3000).

## Real Data Mode: Empty Database

Use this when you want MiSi to start from scratch with no seeded opportunities, market signals, buyer profiles, competitor profiles, actions, or forecasts.

```bash
./scripts/reset-empty-db.sh
```

The reset script drops and recreates local SQLite tables, then inserts no sample data. It refuses to reset a non-SQLite database unless `MISI_ALLOW_DESTRUCTIVE_RESET=true` is set.

Start the apps:

```bash
./scripts/dev.sh
```

Open [http://localhost:3000](http://localhost:3000). The dashboard should show zero pipeline and empty-state guidance.

To load real opportunity data, use a CSV/XLSX tracker export you are allowed to process:

```bash
curl -F "file=@/absolute/path/to/your-tracker.csv" http://localhost:8000/api/upload-tracker
```

Use `sample_data/real_tracker_template.csv` as a header-only template. Do not place real tracker files in `sample_data/` or commit them to Git.

Once records are imported:

1. Open an opportunity from the table.
2. Click **Run AI Analysis** to generate structured opportunity intelligence.
3. Use **Market Radar > Internet Intelligence Scan** to run source-attributed public web research for market, tender, buyer, competitor, opportunity, pipeline and self-delivery questions.
4. Generate **Leadership Briefing** after enough real records exist to make the summary meaningful.
5. Treat AI output as decision support; validate it against source systems before commercial use.

Important real-data boundary: `POST /api/refresh-market-data` currently runs controlled placeholder connectors. Do not use that endpoint as a live public tender feed until an approved real connector or API feed has been wired in.

## Internet Intelligence

MiSi can run backend-owned internet research through OpenAI's Responses API with the hosted `web_search` tool. This powers the **Internet Intelligence Scan** in Market Radar.

It can be used for:

- competitor intelligence
- buyer intelligence
- tender and market radar research
- opportunity context
- pipeline forecast assumptions
- self-delivery capture signals

Requirements:

- `OPENAI_API_KEY` must be set in `.env`.
- `OPENAI_MODEL=gpt-5.5` is recommended for the web-search workflow.
- The backend must be restarted after changing `.env`.

The scan returns structured JSON with findings, source URLs, risk warnings, limitations and next best actions. It does not scrape private systems, bypass site terms, or automatically import internet findings into source-of-truth pipeline records.

MiSi now also has an AI enrichment data layer for turning incomplete opportunity
signals into reviewed commercial records. Enrichment runs, opportunity
intelligence packs and field-by-field confidence metadata are stored separately
from the core opportunity so inferred or estimated values can be useful without
being misrepresented as confirmed facts.

The AI-first standing-start endpoint is `POST /api/intelligence/research-opportunity`.
It can take a rough phrase such as `University of Leeds fire and security tender`,
research public sources, create or update an opportunity, and store known,
inferred, estimated and unknown field values with confidence, rationale, source
URLs and recommended next steps.

The AI conversion contract is intentionally strict: OpenAI must return nested
field-level JSON, not prose. The backend validates the response, rejects invalid
or overconfident unknowns, and normalises numeric commercial values before they
enter the SQLite database.

## ChatGPT Plus Assist Mode

ChatGPT Plus does not include OpenAI API quota. For local demos where the API
project has no credits, MiSi includes a manual **ChatGPT Plus Assist** workflow
inside the AI Research Workspace:

1. Enter a buyer, tender, market or sector phrase.
2. Click **Use ChatGPT Plus Assist**.
3. Copy the MiSi-generated structured research prompt.
4. Paste it into ChatGPT Plus and ask for JSON only.
5. Paste the JSON result back into MiSi.
6. MiSi validates the JSON, labels known/inferred/estimated/unknown fields, and
   saves the opportunity intelligence pack.

This mode does not automate ChatGPT, scrape a browser session, or bypass API
billing. It is a human-in-the-loop bridge for local testing when API quota is
not available. The production path remains backend-owned OpenAI API usage.

## Seed Demo Data

Reset and seed the local SQLite demo database with synthetic MiSi data:

```bash
./scripts/seed-demo.sh
```

This script uses `backend/scripts/seed.py --reset` and works without `OPENAI_API_KEY`. The seeded data is fictional and is safe for local demonstration.

## Database Configuration

`DATABASE_URL` controls the backend database connection. SQLite remains the default for local demos:

```bash
DATABASE_URL=sqlite:///./misi.db
```

Relative SQLite paths are resolved from the repository root so the backend, seed script, and smoke tests use the same local file.

For a PostgreSQL staging or production environment, provide a PostgreSQL URL:

```bash
DATABASE_URL=postgresql://misi_user:change-me@db-host:5432/misi
```

The backend uses SQLAlchemy with the `psycopg` driver and also accepts the common `postgres://` URL alias. Before real internal data is moved to PostgreSQL, add proper Alembic migrations, run them in staging, test backup/restore, and review commercial money fields for `Numeric`/`Decimal` precision.

## Synthetic Demo Flow

1. Start backend:

```bash
. .venv/bin/activate
uvicorn app.main:app --app-dir backend --reload --port 8000
```

2. Seed database in a second terminal:

```bash
./scripts/seed-demo.sh
```

3. Start frontend in another terminal:

```bash
pnpm --dir frontend dev
```

4. Open MiSi dashboard at [http://localhost:3000](http://localhost:3000).
5. Filter opportunities by sector, region, stage, risk rating, owner, or search.
6. Open an opportunity detail view from the opportunity table.
7. Run AI analysis only if `OPENAI_API_KEY` is configured in `.env`; without it, the backend returns a clear configuration error and the seeded demo still works.
8. Generate the leadership briefing from the Executive Command view only if `OPENAI_API_KEY` is configured.
9. View the LE1 Finance view to check secured work, weighted open opportunities, risk-adjusted forecast, and April-to-March revenue and margin.
10. Export the executive report from the Executive Command view as downloadable JSON or printable HTML.

## Stakeholder Review Path

For an MD / FD / GSD / Bid / Commercial review, use this route:

1. Executive Command: read the KPI tiles, Leadership Control This Week lanes, Executive Command Summary and priority opportunities.
2. Priority Opportunity Control: filter to a sector or owner, open an opportunity, and review value, margin, probability, risk, bid/no-bid and recommended action.
3. LE1 Finance: review secured WON work separately from open weighted revenue, then check risk-adjusted forecast and FD review warnings.
4. Self-Delivery: review value captured, value at risk, route candidates and third-party leakage controls.
5. Executive Actions: confirm owner, due date, commercial value and reason for the highest priority actions.
6. Export Executive Report: generate JSON and printable HTML for the review pack.

## Prototype Boundaries

- Authentication, role-based access and audit logging are documented but not implemented. See `docs/ENTERPRISE_DEPLOYMENT.md` for the Entra ID, RBAC, audit, PostgreSQL and secure deployment plan.
- SQLite is the default local database; PostgreSQL is supported by `DATABASE_URL` but production migration, backups and monitoring are not yet built.
- Public tender connectors use controlled sample/mock data unless a safe approved source is connected.
- Buyer and competitor records are seeded demo intelligence, not live CRM or market data.
- AI analysis and leadership briefing require `OPENAI_API_KEY` on the backend. Without it, MiSi still runs with seeded data, rule-based scoring, LE1 finance and report export.
- Do not use local demo output as an authoritative commercial forecast without validation against source systems.

## Smoke Test

With the backend running, run:

```bash
./scripts/smoke.sh
```

The smoke test checks health, version, dashboard, opportunities, market signals, executive actions, LE1 finance summary, and executive report endpoints. To point it at another backend URL, use:

```bash
API_BASE_URL=http://localhost:8000 ./scripts/smoke.sh
```

## Tests And Checks

```bash
./scripts/check.sh
```

This runs backend tests, frontend type checks, and frontend unit tests.

Individual commands:

```bash
. .venv/bin/activate
python -m pytest backend/tests
pnpm --dir frontend typecheck
pnpm --dir frontend test
```

## Tracker Upload Format

MiSi can import internal opportunity tracker files through:

```bash
curl -F "file=@sample_data/tracker_upload_sample.csv" http://localhost:8000/api/upload-tracker
```

Accepted formats are `.csv` and `.xlsx`. The upload mapper is tolerant of common tracker headings, but every file must include columns for:

- `opportunity name` or similar, such as `Opportunity`, `Project Name`, `Title`
- `buyer/client` or similar, such as `Buyer`, `Client`, `Customer Name`

Optional columns include `sector`, `region`, `stage/status`, `owner`, `estimated revenue`, `estimated margin`, `margin %`, `probability`, `deadline`, `forecast start month`, `discipline`, `comments`, and `source`.

The backend validates the filename extension, upload content type, and file size before parsing. The default upload limit is 5MB and can be changed with `MAX_UPLOAD_BYTES` for controlled local testing. Missing optional fields are defaulted for the local MVP. Invalid numbers or dates skip only the affected row and are returned as validation errors.

## Current Phase 0 Scope

- FastAPI health endpoint
- SQLite-ready database configuration, structured to support a later PostgreSQL move
- Optional OpenAI key configuration with backend-only structured analysis
- Backend OpenAI web-search internet intelligence scan
- CSV/XLSX tracker upload for opportunity-style rows
- Source connector framework with controlled mock public-market signals and source-run history
- Next.js dashboard shell connected to backend dashboard, opportunity, market signal, executive action, and finance forecast endpoints
- Synthetic sample data only
