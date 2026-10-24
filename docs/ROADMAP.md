# MiSi Roadmap

The roadmap is split into four stages: prototype, MVP, internal pilot, and scalable webapp. Each stage should produce a usable decision surface, not just technical plumbing.

## Stage 1: Prototype

Goal: prove the command centre concept with synthetic or carefully approved sample data.

Primary outcomes:

- Executive dashboard shell.
- Backend health endpoint.
- Clear frontend/backend separation.
- Backend-only OpenAI integration seam.
- Synthetic pipeline and tender examples.
- Product, architecture, data model, security, and roadmap docs.

Functional scope:

- Static Executive Command Summary shell.
- Static opportunity priority table.
- Static forecast panel.
- Static tender signal feed.
- Planned ingestion and connector interfaces.

Technical scope:

- Next.js frontend.
- FastAPI backend.
- SQLite-ready configuration.
- Local development scripts.
- Basic tests.

Exit criteria:

- Frontend runs locally.
- Backend runs locally.
- Health endpoint works.
- No secrets committed.
- Stakeholders can review the intended product direction.

## Stage 2: MVP

Goal: ingest real controlled data sources and generate useful structured insights for a small trusted user group.

Primary outcomes:

- CSV/XLSX pipeline ingestion.
- SQLite-backed persistence.
- Tender source connector proof of concept for approved sources.
- Basic opportunity scoring.
- Structured OpenAI analysis JSON.
- Bid/no-bid recommendation prototype.
- Executive actions created from insights.

Functional scope:

- Upload pipeline data.
- Validate imports and show errors.
- Normalize accounts and opportunities.
- Display pipeline forecast.
- Display tender notices with source attribution.
- Generate AI summaries for selected opportunities or tenders.
- Show recommended next action for each insight.
- Track basic executive action status.

Technical scope:

- SQLAlchemy models.
- Alembic migration setup once schema stabilizes.
- Pydantic API schemas.
- OpenAI JSON-schema validation.
- Import job status model.
- Connector source attribution model.
- Basic backend test coverage for ingestion, health, and analysis validation.

Exit criteria:

- A user can import a controlled pipeline file and see updated dashboard data.
- Tender signals include source attribution.
- AI outputs validate as structured JSON.
- Every insight has a recommended next action.
- No OpenAI key is exposed to frontend code.

## Stage 3: Internal Pilot

Goal: make MiSi useful and safe for internal Mitie Fire & Security leadership workflows.

Primary outcomes:

- Authentication and role-based access.
- PostgreSQL decision made or migration completed.
- Audit logging.
- More complete bid/no-bid engine.
- Competitor and buyer intelligence workflows.
- Finance forecast views aligned with stakeholder definitions.
- Self-delivery risk inputs.

Functional scope:

- Executive Command Summary backed by live internal data.
- Market Radar from approved sources.
- Tender Intelligence with deduplication and matching.
- Bid/no-bid workflow with decision status.
- Competitor signal management.
- Buyer profile pages.
- Sales Pipeline Forecast with movement explanations.
- Self-Delivery Intelligence linked to opportunities.
- LE1 / finance forecast view validated with finance stakeholders.
- Executive Action Centre with owners and due dates.

Technical scope:

- Auth provider integration.
- Role-based API permissions.
- Audit event table.
- Scheduled connector runs.
- Background jobs for ingestion and AI analysis.
- Data retention policy implementation.
- Monitoring for connector failures and AI validation failures.

Exit criteria:

- Pilot users can use MiSi for weekly leadership review.
- Sensitive data access is role-controlled.
- Material decisions are auditable.
- Forecast and action outputs are trusted enough for internal review.
- Known data quality issues are visible rather than hidden.

## Stage 4: Scalable Webapp

Goal: operate MiSi as a reliable, secure, scalable web application.

Primary outcomes:

- Production hosting.
- PostgreSQL as primary database.
- Managed backups.
- Robust ingestion pipeline.
- Connector monitoring.
- Scalable AI analysis jobs.
- Rich reporting and exports.
- Strong operational security.

Functional scope:

- Multi-user command centre.
- Saved views and filters.
- Scheduled executive reports.
- Alerting for high-priority opportunities and tender deadlines.
- Mature competitor and buyer intelligence.
- Finance forecast scenario comparison.
- Action workflow analytics.
- Data quality dashboard.

Technical scope:

- Production deployment pipeline.
- Managed secret store.
- PostgreSQL migrations and backups.
- Queue or job runner for long-running work.
- Observability: logs, metrics, traces where appropriate.
- Rate limits and connector backoff.
- Dependency and vulnerability scanning.
- Disaster recovery plan.

Exit criteria:

- Application is reliable under expected user and data volume.
- Backups and restore processes are tested.
- Security controls are reviewed.
- Performance is acceptable for executive dashboard workflows.
- Product has a clear ownership and support model.

## Cross-Stage Workstreams

### Data Quality

- Define required fields for each import.
- Track missing values.
- Track duplicate and merged records.
- Show stale data warnings.

### AI Governance

- Version prompts.
- Require JSON schemas.
- Store model and timestamp.
- Link outputs to evidence.
- Track validation failures.
- Keep final decisions human-owned.

### Source Governance

- Approve sources before connector implementation.
- Record terms or license notes.
- Store source attribution.
- Avoid prohibited scraping.

### Security

- Keep secrets out of Git and browser code.
- Add auth before internal pilot.
- Add audit logs before leadership workflow adoption.
- Review personal data handling before storing named contacts at scale.

## Suggested Next Build Sequence

1. Add SQLAlchemy models for accounts, opportunities, sources, tender notices, AI analyses, and executive actions.
2. Build CSV pipeline ingestion with validation and import status.
3. Replace frontend fixtures with backend dashboard summary endpoint.
4. Add structured OpenAI opportunity analysis endpoint.
5. Add source-attributed tender connector proof of concept for an approved source.
6. Add bid/no-bid scoring rules and structured recommendation output.
7. Add authentication and audit logging before internal pilot data is used.

