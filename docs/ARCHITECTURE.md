# MiSi Architecture

MiSi is a browser-based commercial command centre backed by a secure API service. The frontend renders decision workflows and visual summaries. The backend owns data access, ingestion, source connectors, OpenAI calls, scoring, forecasting, audit records, and sensitive configuration.

The primary architecture rule is simple: the browser is a presentation and interaction surface, not a trust boundary for secrets or internal commercial logic.

## Runtime Responsibilities

### Frontend: `frontend/`

The frontend is a Next.js TypeScript application. It should:

- Render the Executive Command Summary and functional modules.
- Call only MiSi backend API endpoints.
- Hold no OpenAI API keys, tender credentials, database credentials, or internal service secrets.
- Display structured backend responses, including confidence, source attribution, risk, and recommended next action.
- Provide filters, navigation, tables, dashboards, and workflows for senior leadership and sales users.
- Treat all AI output as reviewed decision support, not final authority.

The frontend may store browser-local UI preferences such as selected tabs, table density, or dismissed non-sensitive prompts. It must not store sensitive commercial data in local storage unless a future security review explicitly approves it.

### Backend: `backend/`

The backend is a Python FastAPI service. It should:

- Authenticate and authorize users once auth is added.
- Read and write application data.
- Own all ingestion and normalization logic.
- Own all tender source connector execution.
- Own all OpenAI calls and API-key handling.
- Validate AI outputs against structured JSON schemas.
- Persist source attribution and audit metadata.
- Produce decision-ready insight payloads for the frontend.
- Keep business rules testable and separated from route handlers.

The backend is the only place where sensitive credentials are read from environment variables or secret managers.

### Database

SQLite is acceptable for the local MVP because it keeps development simple and avoids infrastructure overhead. The data layer should still be written with a future PostgreSQL move in mind:

- Keep SQLAlchemy session setup isolated in `backend/app/db/`.
- Let `DATABASE_URL` control the database connection.
- Keep `sqlite:///./misi.db` as the default local demo database.
- Use the `psycopg` driver for PostgreSQL URLs.
- Avoid SQLite-specific behavior in business logic.
- Prefer typed models and migrations when the schema becomes non-trivial.
- Use stable IDs, timestamps, and normalized tables.
- Store source attribution with imported records from day one.

PostgreSQL should become the default for the internal pilot or earlier if concurrency, access control, reporting, or audit requirements exceed local SQLite comfort.

The current MVP can create tables against SQLite or PostgreSQL through SQLAlchemy metadata. For real pilot data, this should be replaced by Alembic migrations with staging verification, backup/restore tests, and a review of commercial money fields for exact numeric precision.

## Current Phase 0 Components

```text
frontend/
  Next.js dashboard shell
  Browser-safe environment variables
  Fixture-backed command centre view

backend/
  FastAPI application
  /health endpoint
  Settings loader
  SQLite-ready SQLAlchemy engine factory
  Backend-only OpenAI structured analysis wrapper
  Backend-only OpenAI internet research via Responses API web_search
  CSV/XLSX tracker upload
  Controlled mock source connector framework and source-run history

docs/
  Product, architecture, data model, security, roadmap

sample_data/
  Synthetic CSV examples only
```

## Target Logical Architecture

```text
User browser
  |
  | HTTPS
  v
Next.js frontend
  |
  | Authenticated API calls
  v
FastAPI backend
  |-- Application services
  |-- Ingestion jobs
  |-- Tender connector jobs
  |-- OpenAI analysis service
  |-- Forecasting service
  |-- Audit/event service
  |
  v
SQLite local MVP / PostgreSQL production
```

External data sources connect to backend jobs only. OpenAI is called from backend services only. The frontend receives already-shaped JSON objects that the UI can render.

## Data Flow

### Internal Pipeline Import

1. User uploads CSV/XLSX or an approved internal export arrives through a controlled integration.
2. Backend stores the raw file metadata and source details.
3. Backend validates columns, types, required fields, and duplicate keys.
4. Backend normalizes rows into accounts, opportunities, stages, values, dates, and ownership fields.
5. Backend records import errors without partially hiding them.
6. Frontend shows import status, validation errors, and updated dashboard metrics.

### Tender Source Connector

1. Scheduled backend job runs an approved connector.
2. Connector respects site terms, rate limits, robots guidance where relevant, and licensed API restrictions.
3. Connector stores source URL, source name, published date, retrieval timestamp, and query parameters.
4. Backend deduplicates tender notices and links them to buyers/accounts where possible.
5. Backend exposes tender signal summaries to the frontend.

No scraping that violates site terms is allowed. If a source requires an API key, license, login, or commercial permission, the connector must make that requirement explicit.

### OpenAI Opportunity Analysis

1. Frontend requests analysis for an opportunity, account, buyer, tender, or portfolio view.
2. Backend collects the minimum necessary context from trusted application data.
3. Backend calls OpenAI with a constrained prompt and a required JSON schema.
4. Backend validates the JSON response.
5. Backend stores prompt metadata, model, output, confidence, source IDs, and user-visible recommendation.
6. Frontend displays the structured result and asks "so what should we do next?"

AI outputs must be structured JSON, not vague prose. Narrative text can be rendered from structured fields, but the persisted insight should remain machine-checkable.

### OpenAI Internet Intelligence

MiSi can use the backend OpenAI integration to run public web research through the Responses API `web_search` tool. This is query-driven research for market radar, tender intelligence, buyer intelligence, competitor intelligence, opportunity context, pipeline assumptions and self-delivery signals.

Important boundaries:

- The browser never receives OpenAI credentials.
- Web research is backend-only.
- Results must include source URLs, limitations and recommended next actions.
- Web research does not replace approved source connectors or internal source-of-truth systems.
- Internet findings should be reviewed before they are imported into opportunities, buyer profiles, competitor profiles or forecasts.

Example insight shape:

```json
{
  "insight_type": "opportunity_priority",
  "summary": "High-value renewal with timing risk.",
  "recommended_action": "Confirm incumbent contract end date and schedule bid/no-bid review.",
  "commercial_value_gbp": 420000,
  "risk_level": "medium",
  "confidence": "medium",
  "evidence": [
    {
      "source_type": "pipeline_import",
      "source_id": "pipeline-row-123",
      "claim": "Opportunity is in qualified stage with 62 percent probability."
    }
  ],
  "next_action_owner_role": "Sales lead",
  "decision_deadline": "2026-07-15"
}
```

## Module Architecture

### Executive Command Summary

Aggregates the most important commercial facts across pipeline, tender signals, forecast, risks, and executive actions. This module should be backed by a single backend summary endpoint rather than many frontend-side calculations.

### Market Radar

Tracks macro and local market signals relevant to Fire & Security. It should distinguish observed source facts from AI interpretations.

### Tender Intelligence

Normalizes public opportunity signals, maps them to buyers and accounts, stores source attribution, and supports bid timing decisions.

### Bid / No-Bid Engine

Combines fit, value, capacity, deadline, incumbent risk, margin expectation, self-delivery capability, and strategic importance. It should return structured recommendations with explicit reasons and blockers.

### Competitor Intelligence

Tracks incumbent suppliers, competitor positioning, known strengths, pricing pressure signals, and win/loss context. Data should be source-attributed and date-stamped because competitor information decays quickly.

### Buyer Intelligence

Tracks buyer organizations, stakeholders, procurement cycles, existing relationships, contract history, and decision signals.

### Sales Pipeline Forecast

Calculates current pipeline, weighted value, stage movement, probability, close-quarter view, and leadership exceptions.

### Self-Delivery Intelligence

Maps opportunity demand against Mitie Fire & Security delivery capability, coverage, certifications, mobilisation risk, and subcontractor dependency.

### LE1 / Finance Forecasting

Connects pipeline and delivery assumptions to finance forecast views. Exact LE1 definitions and finance terminology should be validated with finance stakeholders before calculations become authoritative.

### Executive Action Centre

Turns insights into tracked actions with owner, due date, priority, decision status, and link back to supporting evidence.

## API Design Principles

- API responses should be typed and stable.
- Backend endpoints should return structured decision objects, not UI-specific blobs.
- Every generated insight should include `recommended_action`, `risk_level`, `confidence`, and `evidence`.
- Errors should be explicit and actionable.
- Imported data should be traceable to source file, row, connector, URL, or API response.
- Expensive analysis should run as jobs once the product grows beyond synchronous MVP calls.

## Suggested Backend Package Shape

```text
backend/app/
  api/routes/          # HTTP endpoints
  core/                # settings, security, logging
  db/                  # engine, sessions, models, migrations later
  ingestion/           # CSV/XLSX import workflows
  tenders/connectors/  # approved public/source connectors
  services/            # OpenAI, forecasting, scoring, summaries
  schemas/             # Pydantic request/response models
  jobs/                # scheduled/background work later
```

## Operational Principles

- Treat internal commercial data as sensitive by default.
- Record who imported, changed, or generated important records once auth exists.
- Do not hide connector or AI uncertainty.
- Make the "next action" field mandatory for executive-facing insights.
- Prefer deterministic scoring rules for core business logic and use AI to explain, classify, summarize, and recommend within guardrails.
- Keep sample data synthetic.
- Build thin vertical slices that can be validated end to end.
