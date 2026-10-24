# MiSi Product Specification

MiSi, Mitie Sales Intelligence, is a live commercial command centre for Mitie Fire & Security. It combines sales pipeline, tender market data, buyer intelligence, competitor intelligence, self-delivery intelligence, finance forecasting, and OpenAI-powered analysis.

The product exists to help senior leadership answer:

> Where is the opportunity, what should we pursue, what is it worth, what is the risk, and what action is needed now?

Every executive-facing insight should ultimately answer a simpler operational question:

> So what should we do next?

## Product Goals

- Give leadership a current view of commercial opportunity and risk.
- Combine internal and external signals into one decision surface.
- Improve bid/no-bid discipline.
- Expose hidden risks in delivery capacity, competitor position, buyer timing, and forecast quality.
- Turn analysis into accountable next actions.
- Keep sensitive commercial data protected.
- Use OpenAI for structured decision support, not opaque prose.

## Primary Users

### Executive Leadership

Needs a concise view of value, risk, forecast movement, strategic opportunities, and action ownership.

### Sales Leadership

Needs opportunity prioritization, pipeline quality, tender timing, competitor context, and pursuit recommendations.

### Bid / Commercial Teams

Need bid/no-bid evidence, tender summaries, buyer context, competitor position, and deadlines.

### Finance Leadership

Needs weighted pipeline, forecast assumptions, LE1/finance views, risk-adjusted value, and movement explanations.

### Operational / Self-Delivery Leads

Need visibility of whether Mitie can self-deliver the work, where mobilisation risk exists, and where subcontractor dependency may affect margin or service quality.

## Product Modules

### 1. Executive Command Summary

Purpose: provide the top-level answer for leadership in one screen.

Should include:

- Total open opportunity.
- Weighted pipeline.
- High-priority opportunities.
- Forecast movement and variance.
- Tender signals requiring action.
- High-risk pursuits.
- Open executive actions.
- AI-generated recommendations in structured form.

Example question answered:

- "Which three opportunities need leadership intervention this week?"

Required output:

- Summary.
- Evidence.
- Risk.
- Recommended action.
- Owner role.
- Deadline.

### 2. Market Radar

Purpose: identify external market movements that may create sales opportunity or risk.

Should include:

- Public tender trends.
- Sector activity.
- Buyer procurement patterns.
- Regulatory or compliance signals relevant to Fire & Security.
- Local authority, healthcare, commercial property, industrial, and transport market signals.

Market Radar must distinguish:

- Observed source facts.
- MiSi inference.
- AI-generated interpretation.

### 3. Tender Intelligence

Purpose: turn tender market data into actionable pursuit intelligence.

Should include:

- Tender notices.
- Source attribution.
- Buyer organization.
- Published date.
- Deadline.
- Estimated value when available.
- Fit to Mitie Fire & Security.
- Incumbent or competitor clues.
- Bid/no-bid recommendation link.

Rules:

- No scraping that violates site terms.
- Source attribution is mandatory.
- Connectors must preserve source URL, retrieval timestamp, and connector name.

### 4. Bid / No-Bid Engine

Purpose: support disciplined pursuit decisions.

Inputs:

- Estimated contract value.
- Margin expectation.
- Strategic fit.
- Sector fit.
- Delivery capability.
- Self-delivery availability.
- Deadline feasibility.
- Buyer relationship.
- Incumbent competitor risk.
- Tender requirements.
- Internal pursuit capacity.

Outputs:

- Recommendation: `bid`, `no_bid`, or `review_required`.
- Confidence.
- Top reasons.
- Blocking risks.
- Required next action.
- Decision owner.

The engine should combine deterministic rules with AI-assisted interpretation. AI may summarize and classify evidence, but core thresholds should remain visible and testable.

### 5. Competitor Intelligence

Purpose: help users understand incumbent position, competitor pressure, and likely differentiation strategy.

Should include:

- Competitor organizations.
- Known incumbent relationships.
- Sector strengths.
- Pricing or margin pressure signals.
- Recent wins/losses where known.
- Evidence date and source.
- Confidence level.

Competitor data should be treated as time-sensitive. Old intelligence should decay or be flagged.

### 6. Buyer Intelligence

Purpose: build a useful view of buyer organizations and stakeholder context.

Should include:

- Buyer organization profile.
- Sector.
- Sites or regions.
- Procurement cycle.
- Existing Mitie relationship.
- Known contacts where permitted.
- Tender history.
- Opportunity history.
- Decision timing signals.

Personal data handling must be reviewed before storing named contacts at scale.

### 7. Sales Pipeline Forecast

Purpose: turn pipeline data into a leadership-ready forecast.

Should include:

- Open pipeline.
- Weighted pipeline.
- Stage distribution.
- Expected close period.
- Movement since last import.
- Probability by stage.
- Slippage risk.
- High-value changes.
- Forecast assumptions.

Forecast views should show both raw and risk-adjusted values.

### 8. Self-Delivery Intelligence

Purpose: connect commercial opportunity to operational delivery reality.

Should include:

- Delivery capability fit.
- Geographic coverage.
- Certifications or compliance requirements.
- Mobilisation risk.
- Subcontractor dependency.
- Capacity constraints.
- Margin implications.

Every major bid/no-bid recommendation should consider self-delivery capability.

### 9. LE1 / Finance Forecasting

Purpose: support finance-aligned commercial forecasting.

Should include:

- Forecast value by period.
- Weighted opportunity contribution.
- Risk-adjusted scenario views.
- Commit, best case, and upside views.
- Variance against target.
- Explanation of material movement.

The exact LE1 calculation logic and terminology should be validated with finance stakeholders before becoming authoritative.

### 10. Executive Action Centre

Purpose: turn insight into tracked action.

Should include:

- Action title.
- Recommended owner role.
- Assigned user once auth exists.
- Priority.
- Due date.
- Linked opportunity, tender, buyer, or forecast item.
- Supporting evidence.
- Status.
- Decision history.

An insight without a next action is incomplete for MiSi.

## AI Product Requirements

AI output must be structured JSON. It should not be vague prose returned directly to the frontend.

Required fields for executive-facing AI insights:

- `summary`
- `recommended_action`
- `risk_level`
- `confidence`
- `evidence`
- `commercial_impact`
- `decision_deadline` where applicable
- `owner_role` where applicable

AI should be used for:

- Summarizing tenders.
- Extracting requirements from source text where permitted.
- Classifying opportunity fit.
- Explaining forecast movement.
- Drafting bid/no-bid reasoning.
- Highlighting risks and missing evidence.
- Recommending next actions.

AI should not be used as the only authority for:

- Final bid/no-bid decision.
- Financial forecast approval.
- Customer commitments.
- Contractual interpretation.
- Source connector permissions.

## Data Sensitivity

MiSi will handle internal commercial data, future opportunity values, buyer intelligence, competitor intelligence, and finance forecasts. This data must be treated as sensitive even in prototype form.

Prototype sample data must remain synthetic.

## Success Measures

- Leadership can identify priority opportunities in under two minutes.
- Every high-value opportunity has visible risk and next action.
- Tender signals are source-attributed and deduplicated.
- Bid/no-bid recommendations include evidence and blockers.
- Forecast movement is explainable.
- OpenAI use is secure, backend-only, and auditable.

