# SalesIntel Data Model

This document defines the practical MVP data model and the direction for a later PostgreSQL-backed implementation. SQLite is acceptable for local MVP, but table design should avoid patterns that make PostgreSQL migration painful.

## Data Model Principles

- Store source attribution for imported and connector-sourced records.
- Keep raw source metadata separate from normalized business entities.
- Use stable IDs and timestamps on every important table.
- Avoid storing secrets in the database.
- Treat internal commercial data as sensitive.
- Keep AI outputs structured and schema-validated.
- Preserve enough evidence for users to understand why SalesIntel recommended an action.
- Label enriched fields as `known`, `inferred`, `estimated`, `unknown`,
  `user_provided`, or `system_calculated` instead of visually hiding missing
  data or presenting estimates as facts.

## Core Entities

### Account

Represents an organization that may buy from Mitie Fire & Security or already has a relationship.

Suggested fields:

- `id`
- `name`
- `sector`
- `region`
- `account_owner`
- `relationship_status`
- `created_at`
- `updated_at`

### Buyer

Represents a purchasing organization or public authority. In many cases this may overlap with Account, but the distinction is useful when tender sources name authorities differently from internal CRM records.

Suggested fields:

- `id`
- `name`
- `sector`
- `buyer_type`
- `parent_organization`
- `website`
- `source_confidence`
- `created_at`
- `updated_at`

### Buyer Contact

Represents a named stakeholder only where collection and use are permitted.

Suggested fields:

- `id`
- `buyer_id`
- `name`
- `role_title`
- `email`
- `phone`
- `source_id`
- `consent_basis`
- `created_at`
- `updated_at`

Personal data requirements should be reviewed before this becomes a scaled feature.

### Opportunity

Represents a sales pipeline opportunity.

Suggested fields:

- `id`
- `account_id`
- `name`
- `description`
- `stage`
- `estimated_value_gbp`
- `probability`
- `weighted_value_gbp`
- `expected_close_date`
- `close_quarter`
- `owner`
- `risk_level`
- `source_id`
- `created_at`
- `updated_at`

### AI Enrichment Run

Represents one AI-first enrichment attempt. A run may start from a rough user
query, an imported market signal, or an existing opportunity record. It stores
operational metadata so SalesIntel can explain what happened and whether internet
search was used.

Implemented fields:

- `id`
- `run_type`
- `status`
- `user_query`
- `opportunity_id`
- `started_at`
- `finished_at`
- `model_used`
- `search_performed`
- `sources_checked`
- `records_created`
- `records_updated`
- `error_message`

### Field Intelligence

Stores field-level provenance for AI-populated or system-calculated values. This
is the main mechanism for avoiding blank commercial records without fabricating
certainty. For example, contract value may be `estimated`, buyer name may be
`known`, incumbent supplier may be `unknown`, and margin may require
`needs_user_confirmation`.

Standing-start AI opportunity research now requires OpenAI to return each core
opportunity field as a strict nested object with `value`, `value_type`,
`confidence_score`, `rationale`, and `source_urls`. The backend validates that
shape with Pydantic before writing records. Values marked `unknown` must carry
zero confidence; database-compatible numeric values are normalised by the backend
before they reach `Opportunity`, `FinanceForecast`, or `FieldIntelligence`.

Implemented fields:

- `id`
- `entity_type`
- `entity_id`
- `field_name`
- `field_value`
- `value_type`
- `confidence_score`
- `rationale`
- `source_urls`
- `source_titles`
- `recommended_next_step`
- `needs_user_confirmation`
- `created_at`
- `updated_at`

Allowed `value_type` values:

- `known`
- `inferred`
- `estimated`
- `unknown`
- `user_provided`
- `system_calculated`

### Opportunity Enrichment

Stores the narrative and analytical intelligence pack for a specific
opportunity, linked back to the enrichment run that created it.

Implemented fields:

- `id`
- `opportunity_id`
- `enrichment_run_id`
- `buyer_summary`
- `opportunity_summary`
- `likely_scope`
- `estimated_contract_value_rationale`
- `likely_buyer_drivers`
- `compliance_drivers`
- `competitor_assessment`
- `commercial_assessment`
- `mobilisation_assessment`
- `self_delivery_assessment`
- `finance_assessment`
- `executive_recommendation`
- `unknowns`
- `recommended_next_steps`
- `overall_confidence`
- `created_at`

### Tender Notice

Represents an external tender or market signal.

Suggested fields:

- `id`
- `source_id`
- `buyer_id`
- `title`
- `description`
- `published_date`
- `deadline`
- `estimated_value_gbp`
- `url`
- `procurement_reference`
- `status`
- `raw_payload_hash`
- `created_at`
- `updated_at`

### Tender Signal

Represents SalesIntel's normalized interpretation of a tender notice.

Suggested fields:

- `id`
- `tender_notice_id`
- `signal_strength`
- `fit_score`
- `matched_account_id`
- `matched_opportunity_id`
- `summary`
- `recommended_action`
- `confidence`
- `created_at`
- `updated_at`

### Competitor

Represents a competitor organization.

Suggested fields:

- `id`
- `name`
- `known_strengths`
- `known_weaknesses`
- `sector_focus`
- `created_at`
- `updated_at`

### Competitor Signal

Represents a source-attributed competitor observation.

Suggested fields:

- `id`
- `competitor_id`
- `account_id`
- `buyer_id`
- `opportunity_id`
- `signal_type`
- `summary`
- `source_id`
- `observed_at`
- `confidence`
- `created_at`
- `updated_at`

### Self-Delivery Capability

Represents Mitie capability relevant to fulfilling an opportunity.

Suggested fields:

- `id`
- `service_line`
- `region`
- `capability`
- `certification`
- `capacity_status`
- `notes`
- `updated_at`

### Opportunity Delivery Fit

Links an opportunity to self-delivery capability and delivery risk.

Suggested fields:

- `id`
- `opportunity_id`
- `self_delivery_capability_id`
- `fit_level`
- `mobilisation_risk`
- `subcontractor_dependency`
- `margin_impact`
- `recommended_action`
- `created_at`
- `updated_at`

### Finance Forecast

Represents forecast snapshots and scenario values.

Suggested fields:

- `id`
- `forecast_period`
- `scenario`
- `target_value_gbp`
- `pipeline_value_gbp`
- `weighted_value_gbp`
- `commit_value_gbp`
- `best_case_value_gbp`
- `upside_value_gbp`
- `created_by`
- `created_at`

### Forecast Contribution

Links opportunities to forecast snapshots.

Suggested fields:

- `id`
- `finance_forecast_id`
- `opportunity_id`
- `contribution_value_gbp`
- `weighting_method`
- `risk_adjustment`
- `notes`

### Bid Decision

Represents bid/no-bid analysis.

Suggested fields:

- `id`
- `opportunity_id`
- `tender_notice_id`
- `recommendation`
- `confidence`
- `estimated_value_gbp`
- `strategic_fit`
- `delivery_fit`
- `deadline_feasibility`
- `competitor_risk`
- `margin_risk`
- `top_reasons_json`
- `blockers_json`
- `recommended_action`
- `decision_status`
- `decided_by`
- `decided_at`
- `created_at`
- `updated_at`

### Executive Action

Represents a tracked action generated from an insight, forecast issue, tender signal, or leadership decision.

Suggested fields:

- `id`
- `title`
- `description`
- `owner_role`
- `assigned_user_id`
- `priority`
- `status`
- `due_date`
- `linked_entity_type`
- `linked_entity_id`
- `source_insight_id`
- `created_at`
- `updated_at`

## Source Attribution

Source attribution is mandatory for connector-sourced and imported records.

### Source

Suggested fields:

- `id`
- `source_type`
- `source_name`
- `source_url`
- `source_attribution`
- `connector_name`
- `retrieved_at`
- `uploaded_by`
- `original_filename`
- `license_or_terms_note`
- `content_hash`
- `created_at`

### Source Evidence

Links a claim or insight to specific evidence.

Suggested fields:

- `id`
- `source_id`
- `entity_type`
- `entity_id`
- `claim`
- `source_excerpt`
- `confidence`
- `created_at`

Do not store large copyrighted source text unless the source terms allow it. Store short excerpts or structured references where appropriate.

## AI Output Tables

### AI Analysis

Stores schema-validated AI outputs.

Suggested fields:

- `id`
- `analysis_type`
- `model`
- `input_entity_type`
- `input_entity_id`
- `prompt_version`
- `output_json`
- `summary`
- `recommended_action`
- `risk_level`
- `confidence`
- `created_by`
- `created_at`

The `output_json` field must validate against an analysis-specific schema before persistence.

### AI Evidence Link

Links AI analysis to source evidence and application entities.

Suggested fields:

- `id`
- `ai_analysis_id`
- `source_evidence_id`
- `entity_type`
- `entity_id`

## Relationships

```text
Account 1--many Opportunity
Buyer 1--many TenderNotice
TenderNotice 1--many TenderSignal
Opportunity 1--many BidDecision
Opportunity many--many FinanceForecast through ForecastContribution
Opportunity many--many SelfDeliveryCapability through OpportunityDeliveryFit
Competitor 1--many CompetitorSignal
Source 1--many SourceEvidence
AIAnalysis many--many SourceEvidence through AIEvidenceLink
AIAnalysis 1--many ExecutiveAction
```

## JSON Fields

JSON fields are acceptable for early MVP flexibility, especially in SQLite, but they should be used deliberately:

- Good use: AI output payload, top reasons, blockers, connector raw metadata.
- Avoid: core searchable fields such as account name, stage, value, deadline, risk level, and status.

When PostgreSQL is adopted, JSON fields that remain important can move to `jsonb`.

## Migration Guidance

Start simple in SQLite, but prepare for PostgreSQL:

- Use SQLAlchemy models rather than raw ad hoc SQL scattered through services.
- Keep `DATABASE_URL` as the single database selection mechanism.
- Keep SQLite as the local default and use PostgreSQL for staging, pilot, and production.
- Add Alembic before real internal data is loaded or the schema grows materially.
- Use UTC timestamps.
- Avoid relying on SQLite-only date behavior.
- Keep enum values stable and documented.
- Add indexes for common filters: account, buyer, deadline, forecast period, status, risk level, and source ID.
- Convert authoritative finance and contract value fields to `Numeric`/`Decimal` during the production PostgreSQL migration. The MVP uses Python floats for speed of prototyping, which is not ideal for final finance-grade precision.
- Prefer PostgreSQL `jsonb` for AI outputs and connector metadata that remain important and queryable.
- Validate the migration in staging with seeded data, tracker upload, source refresh, dashboard aggregation, AI analysis storage, LE1 forecast, and executive report export before pilot use.
