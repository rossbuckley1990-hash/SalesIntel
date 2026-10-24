"""Explicit synthetic fixture. Never call against an existing commercial database."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    BuyerProfile,
    CompetitorProfile,
    EnrichmentRun,
    ExecutiveAction,
    FieldIntelligence,
    FinanceForecast,
    Opportunity,
    OpportunityEnrichment,
)
from app.models.living import Outcome, Requirement, Snapshot
from app.services.living.workspace import snapshot_payload


def seed_living_demo(db: Session) -> bool:
    if db.scalar(select(func.count()).select_from(Opportunity)):
        return False
    today = date.today()
    month = f"{today.year}-{today.month:02d}"
    # Every organisation, person, value, source and requirement is invented for demonstration.
    rows = [
        (
            "Alderwick University",
            "Integrated campus fire & security",
            "Education",
            "Yorkshire",
            "Proposal",
            "Alex Morgan",
            620000,
            1860000,
            24,
            0.65,
            "High",
            "Amber",
            12,
        ),
        (
            "Pennine Technical University",
            "Life-safety maintenance renewal",
            "Education",
            "Yorkshire",
            "Qualification",
            "Jamie Reed",
            390000,
            1170000,
            29,
            0.40,
            "High",
            "Green",
            24,
        ),
        (
            "Westhaven Health Partnership",
            "Critical-estate compliance programme",
            "Healthcare",
            "Midlands",
            "Negotiation",
            "Sam Taylor",
            980000,
            3920000,
            21,
            0.75,
            "Medium",
            "Red",
            5,
        ),
        (
            "Northline Logistics",
            "National CCTV & access control",
            "Logistics",
            "National",
            "Proposal",
            "Alex Morgan",
            840000,
            2520000,
            32,
            0.55,
            "High",
            "Amber",
            18,
        ),
        (
            "Harbour City Estates",
            "Passive fire inspection & remedials",
            "Property",
            "London",
            "Qualification",
            "Casey Blake",
            470000,
            1410000,
            27,
            0.35,
            "Medium",
            "Red",
            9,
        ),
        (
            "Civic Care Alliance",
            "Fire alarm planned maintenance",
            "Healthcare",
            "Yorkshire",
            "Won",
            "Jamie Reed",
            360000,
            1080000,
            28,
            1,
            "High",
            "Green",
            40,
        ),
        (
            "Meridian Data Park",
            "Suppression & specialist detection",
            "Technology",
            "Midlands",
            "Discovery",
            "Sam Taylor",
            720000,
            2160000,
            33,
            0.25,
            "Unknown",
            "Amber",
            35,
        ),
        (
            "Calder Retail Collective",
            "Emergency lighting service programme",
            "Retail",
            "Yorkshire",
            "Proposal",
            "Casey Blake",
            280000,
            840000,
            30,
            0.60,
            "High",
            "Green",
            15,
        ),
    ]
    for i, (
        buyer,
        name,
        sector,
        region,
        stage,
        owner,
        annual,
        total,
        margin,
        probability,
        fit,
        risk,
        days,
    ) in enumerate(rows, 1):
        action_text = (
            "Confirm engineering capacity and review the scope with the account owner"
            if fit != "Unknown"
            else "Obtain the specialist accreditation and coverage evidence"
        )
        o = Opportunity(
            name=name,
            buyer_name=buyer,
            sector=sector,
            region=region,
            source_type="Synthetic demonstration",
            stage=stage,
            owner=owner,
            estimated_annual_revenue=annual,
            estimated_total_contract_value=total,
            estimated_gross_margin=annual * margin / 100,
            margin_percentage=margin,
            probability=probability,
            weighted_value=total * probability,
            submission_deadline=today + timedelta(days=days),
            forecast_start_month=month,
            self_delivery_fit=fit,
            risk_rating=risk,
            strategic_fit_score=80 if fit == "High" else 55,
            bid_no_bid_recommendation="Watch" if risk == "Red" else "Pursue",
            recommended_action=action_text,
        )
        db.add(o)
        db.flush()
        db.add(
            BuyerProfile(
                buyer_name=buyer,
                sector=sector,
                region=region,
                estate_size=f"{8 + i * 3} sites (synthetic)",
                procurement_drivers=[
                    "Consolidate planned maintenance and evidence reporting",
                    "Reduce reactive call-outs and compliance backlog",
                ],
                pain_points=[
                    "Fragmented subcontractor coverage",
                    "Incomplete asset registers",
                ],
                decision_criteria=[
                    "Verified engineering coverage",
                    "Transparent whole-life cost",
                    "Mobilisation assurance",
                ],
                relationship_status="Qualification",
                next_best_action="Validate estate scope and procurement timetable with the buyer.",
            )
        )
        run = EnrichmentRun(
            run_type="synthetic_fixture",
            status="completed",
            user_query=f"Synthetic Fire & Security opportunity {i}",
            opportunity_id=o.id,
            model_used="fixture-v1",
            search_performed=False,
            sources_checked=[
                {
                    "title": f"Synthetic estate brief {i}",
                    "reference": f"fixture:living-v1/{i}",
                }
            ],
            records_created=1,
            finished_at=datetime.now(UTC),
        )
        db.add(run)
        db.flush()
        for field_name, value, value_type, confidence, rationale in [
            (
                "buyer_name",
                buyer,
                "known",
                1,
                "Identity is specified in the synthetic estate brief; not a real organisation.",
            ),
            (
                "estimated_annual_revenue",
                annual,
                "estimated",
                0.65,
                "Synthetic annual planning estimate; validate against priced scope.",
            ),
            (
                "estimated_total_contract_value",
                total,
                "estimated",
                0.6,
                "Synthetic whole-contract estimate; separate from annual revenue.",
            ),
            (
                "estimated_gross_margin",
                annual * margin / 100,
                "system_calculated",
                0.65,
                "Annual revenue multiplied by the recorded margin percentage.",
            ),
            (
                "margin_percentage",
                margin,
                "estimated",
                0.55,
                "Synthetic margin hypothesis pending a costed delivery plan.",
            ),
            (
                "probability",
                probability,
                "estimated",
                0.5,
                "Commercial judgement, not a statistical probability forecast.",
            ),
            (
                "self_delivery_fit",
                fit if fit != "Unknown" else None,
                "inferred" if fit != "Unknown" else "unknown",
                0.6 if fit != "Unknown" else 0,
                "Indicative scope fit; no assertion of actual Mitie capacity or accreditation.",
            ),
            (
                "engineering_capacity",
                None,
                "unknown",
                0,
                "No confirmed engineering capacity allocation is recorded.",
            ),
            (
                "incumbent",
                None,
                "unknown",
                0,
                "No source identifies the incumbent. Do not infer a supplier.",
            ),
            (
                "submission_deadline",
                o.submission_deadline.isoformat(),
                "known",
                1,
                "Deadline explicitly supplied by the synthetic tender fixture.",
            ),
        ]:
            db.add(
                FieldIntelligence(
                    entity_type="opportunity",
                    entity_id=o.id,
                    field_name=field_name,
                    field_value=value,
                    value_type=value_type,
                    confidence_score=confidence,
                    rationale=rationale,
                    source_titles=[f"Synthetic estate brief {i} · fixture v1"],
                    source_urls=[],
                    recommended_next_step="Validate against an approved source before real commercial use.",
                    needs_user_confirmation=value_type != "known",
                )
            )
        db.add(
            OpportunityEnrichment(
                opportunity_id=o.id,
                enrichment_run_id=run.id,
                buyer_summary=f"{buyer} is an invented {sector.lower()} account in {region}. The fixture describes {8 + i * 3} sites with fragmented service coverage.",
                opportunity_summary=f"{name} is a synthetic pursuit to consolidate planned service, reactive support and compliance evidence.",
                likely_scope="Asset survey; planned preventive maintenance; reactive support; compliance reporting",
                estimated_contract_value_rationale="Planning figures supplied by synthetic fixture v1, not a market valuation.",
                likely_buyer_drivers=[
                    "Reliable compliance evidence",
                    "Fewer supplier hand-offs",
                    "Predictable annual cost",
                ],
                compliance_drivers=[
                    "Confirm applicable statutory and contractual obligations from tender documents"
                ],
                competitor_assessment="Incumbent and competitor identities are unknown. Do not name or attribute claims without evidence.",
                commercial_assessment="Validate asset volumes, call-out assumptions, exclusions and indexation before pricing.",
                mobilisation_assessment="Engineering allocation, site access and asset data transfer remain unconfirmed.",
                self_delivery_assessment="Potential fit requires regional capacity and accreditation validation.",
                finance_assessment="Annual revenue and margin are synthetic estimates. No actual realised revenue is recorded.",
                executive_recommendation="Investigate evidence gaps and assign an owner before bid commitment.",
                unknowns=[
                    "Confirmed engineering capacity",
                    "Incumbent identity",
                    "Priced asset register",
                    "Agreed mobilisation plan",
                ],
                recommended_next_steps=[
                    action_text,
                    "Request the asset register and contract specification",
                    "Validate the annual cost model with Finance",
                ],
                overall_confidence=0.6,
            )
        )
        a = ExecutiveAction(
            priority="high" if risk == "Red" else "medium",
            category="Evidence review",
            owner=owner,
            due_date=today + timedelta(days=min(days - 2, 7)),
            related_opportunity_id=o.id,
            commercial_value=annual * margin / 100,
            reason=f"{risk} recorded risk; capacity remains unconfirmed before the submission deadline.",
            recommended_action=action_text,
            status="open",
        )
        db.add(a)
        db.flush()
        db.add(
            Outcome(
                opportunity_id=o.id,
                action_id=a.id,
                stage="won" if stage == "Won" else "investigating",
                expected_impact=Decimal(str(annual * margin / 100)),
                owner=owner,
                due_date=a.due_date,
                confidence="estimated",
                assumptions="Potential annual gross margin from synthetic revenue × margin; not realised value.",
                completion_evidence=(
                    "Synthetic award fixture v1 records a won contract; no payment evidence."
                    if stage == "Won"
                    else ""
                ),
                verified_by="Synthetic fixture" if stage == "Won" else "",
            )
        )
        remaining = 12 - ((today.month - 4) % 12)
        fy_revenue = annual * remaining / 12
        db.add(
            FinanceForecast(
                opportunity_id=o.id,
                forecast_category=(
                    "Committed"
                    if stage == "Won"
                    else "At risk" if risk == "Red" else "Likely"
                ),
                start_month=month,
                revenue_to_year_end=fy_revenue,
                estimated_margin=fy_revenue * margin / 100,
                margin_percentage=margin,
                probability_weighting=probability,
                risk_adjustment=0.15 if risk == "Red" else 0.05,
                notes="Synthetic annual value prorated to March; approved finance definition remains pending.",
            )
        )
        if i == 1:
            for text, ref in [
                (
                    "Provide a mobilisation plan covering site access and asset verification",
                    "Synthetic tender schedule section 2.1",
                ),
                (
                    "Submit evidence of engineering coverage and applicable accreditations",
                    "Synthetic tender schedule section 3.2",
                ),
                (
                    "Describe service reporting and escalation responsibilities",
                    "Synthetic tender schedule section 4.1",
                ),
            ]:
                db.add(
                    Requirement(
                        opportunity_id=o.id,
                        requirement=text,
                        source_reference=ref,
                        compliance="gap",
                        owner=owner,
                    )
                )
    db.add(
        CompetitorProfile(
            name="Northstar Compliance Services (fictional)",
            sectors=["Education", "Healthcare"],
            strengths=["Synthetic competitor fixture: regional service coverage"],
            weaknesses=["No independently verified weaknesses"],
            pricing_behaviour="Unknown; do not infer pricing",
            threat_level="Unknown",
            counter_strategy="Ask the buyer about evidenced service gaps; differentiate on the verified delivery plan.",
        )
    )
    db.commit()
    # Two real captured states in the fixture build, not invented historical timestamps.
    db.add(
        Snapshot(
            label="Synthetic baseline · fixture revision 1",
            reviewer="Demo fixture generator",
            payload=snapshot_payload(db),
        )
    )
    db.commit()
    o = db.get(Opportunity, 1)
    o.stage = "Negotiation"
    o.margin_percentage = 26
    o.estimated_gross_margin = o.estimated_annual_revenue * 0.26
    for field in db.scalars(
        select(FieldIntelligence).where(
            FieldIntelligence.entity_id == o.id,
            FieldIntelligence.entity_type == "opportunity",
        )
    ):
        if field.field_name == "margin_percentage":
            field.field_value = 26
        if field.field_name == "estimated_gross_margin":
            field.field_value = o.estimated_gross_margin
    forecast = db.scalar(
        select(FinanceForecast).where(FinanceForecast.opportunity_id == o.id)
    )
    forecast.margin_percentage = 26
    forecast.estimated_margin = forecast.revenue_to_year_end * 0.26
    db.get(Opportunity, 3).forecast_start_month = (
        f"{today.year + (today.month == 12)}-{today.month % 12 + 1:02d}"
    )
    db.commit()
    db.add(
        Snapshot(
            label="Synthetic review · fixture revision 2",
            reviewer="Demo fixture generator",
            payload=snapshot_payload(db),
        )
    )
    db.commit()
    return True
