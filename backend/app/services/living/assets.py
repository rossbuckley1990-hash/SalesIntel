"""Versioned, source-bound commercial assets. No model call or invented facts."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CompetitorProfile, ExecutiveAction
from app.models.living import Asset, Scenario, Snapshot
from app.schemas.living import AssetRequest
from app.services.finance_summary import build_finance_forecast_summary
from app.services.living.audit import change, commit_event, record
from app.services.living.workspace import opportunity_detail, portfolio, snapshot_diff

TITLES = {
    "dossier": "Opportunity intelligence dossier",
    "bid_decision": "Bid decision pack",
    "pursuit_plan": "Sales pursuit plan",
    "battlecard": "Competitor battlecard",
    "self_delivery": "Self delivery capture business case",
    "forecast": "LE1 forecast and scenario pack",
    "leadership": "Executive leadership briefing",
    "tender": "Tender response starter pack",
}


def gbp(value) -> str:
    return "Unknown" if value is None else f"£{Decimal(str(value)):,.2f}"


def section(title, paragraphs=None, columns=None, rows=None) -> dict:
    return {
        "title": title,
        "paragraphs": paragraphs or [],
        "columns": columns or [],
        "rows": rows or [],
    }


def build_content(db: Session, request: AssetRequest) -> dict:
    detail = (
        opportunity_detail(db, request.opportunity_id)
        if request.opportunity_id
        else None
    )
    if request.kind not in {"leadership", "forecast"} and detail is None:
        raise HTTPException(422, "Select an opportunity for this asset.")
    scenario = db.get(Scenario, request.scenario_id) if request.scenario_id else None
    if request.scenario_id and scenario is None:
        raise HTTPException(404, "Scenario not found")
    if (
        scenario
        and request.opportunity_id
        and scenario.opportunity_id != request.opportunity_id
    ):
        raise HTTPException(422, "The scenario belongs to another opportunity.")
    if request.kind == "self_delivery" and not scenario:
        raise HTTPException(
            422,
            "Save a scenario with explicit delivery cost assumptions before generating a business case.",
        )
    if request.kind == "tender" and not detail["requirements"]:
        raise HTTPException(
            422, "Add source-referenced tender requirements before creating this pack."
        )
    sections = []
    finance = build_finance_forecast_summary(db).model_dump(mode="json")
    snapshots = list(db.scalars(select(Snapshot).order_by(Snapshot.id.desc()).limit(2)))
    movements = snapshot_diff(
        snapshots[1] if len(snapshots) > 1 else None,
        snapshots[0] if snapshots else None,
    )
    records = portfolio(db)
    sources = []
    if detail:
        o, q, f = detail["opportunity"], detail["qualification"], detail["financials"]
        enrichment = detail["enrichment"] or {}
        sources.append(
            {
                "reference": f"opportunity:{o['id']}",
                "title": o["name"],
                "timestamp": o["updated_at"],
                "type": o["source_type"],
            }
        )
        sections.append(
            section(
                "Decision context",
                [
                    f"{o['buyer_name']} — {o['name']}. {q['recommendation']}. Current stage: {o['stage']}; accountable owner: {o['owner']}; submission date: {o['submission_deadline'] or 'unconfirmed'}.",
                    "This pack is structured from saved records and disclosed rules. It is a draft for human review, not an approval or evidence of realised value.",
                ],
            )
        )
        sections.append(
            section(
                "Commercial position",
                columns=["Measure", "Recorded value", "Basis"],
                rows=[
                    [
                        "Annual revenue",
                        gbp(f["estimated_annual_revenue"]),
                        "Estimate unless source says otherwise",
                    ],
                    [
                        "Contract total value",
                        gbp(f["estimated_total_contract_value"]),
                        "Whole contract; not annual revenue",
                    ],
                    [
                        "Annual gross margin",
                        gbp(f["estimated_gross_margin"]),
                        "Recorded annual estimate",
                    ],
                    [
                        "Weighted contract value",
                        gbp(f["weighted_contract_value"]),
                        "Contract total × recorded probability",
                    ],
                    [
                        "Margin",
                        (
                            "Unknown"
                            if f["margin_percentage"] is None
                            else f"{f['margin_percentage']}%"
                        ),
                        "Recorded assumption",
                    ],
                    [
                        "Probability",
                        (
                            "Unknown"
                            if f["probability"] is None
                            else f"{f['probability'] * 100:g}%"
                        ),
                        "Commercial judgement",
                    ],
                ],
            )
        )
        if request.kind == "dossier":
            sections += [
                section(
                    "Buyer and procurement context",
                    [
                        enrichment.get("buyer_summary")
                        or "No buyer research is recorded.",
                        "Procurement drivers: "
                        + "; ".join(
                            enrichment.get("likely_buyer_drivers")
                            or ["Not yet established"]
                        ),
                    ],
                ),
                section(
                    "Scope and delivery fit",
                    [
                        enrichment.get("likely_scope") or o["name"],
                        enrichment.get("self_delivery_assessment")
                        or f"Recorded fit is {o['self_delivery_fit']}; operational evidence is required.",
                    ],
                ),
                section(
                    "Competitor and incumbent assessment",
                    [
                        enrichment.get("competitor_assessment")
                        or "No source-attributed incumbent or competitor assessment is available."
                    ],
                ),
                section(
                    "Recommended pursuit strategy",
                    [
                        q["recommendation"],
                        "Validate scope and buyer requirements, resolve delivery evidence gaps, then conduct a recorded bid review. This is a rule-based next step, not a verified win strategy.",
                    ],
                ),
            ]
        if request.kind == "bid_decision":
            sections += [
                section(
                    "Qualification scorecard",
                    [q["method"], f"Current score: {q['score']} out of 100."],
                    ["Criterion", "Result", "Evidence basis"],
                    [
                        [c["label"], "Met" if c["passed"] else "Review", c["basis"]]
                        for c in q["criteria"]
                    ],
                ),
                section(
                    "Resource and mobilisation review",
                    [
                        enrichment.get("mobilisation_assessment")
                        or "Mobilisation constraints are unconfirmed.",
                        "Bid resource requirements and contractual risk must be reviewed by the accountable owner. No resource approval is implied.",
                    ],
                ),
                section(
                    "Recorded decisions",
                    [
                        "Local reviews are unauthenticated. Enterprise approval requires Entra ID and backend roles."
                    ],
                    ["Choice", "Reviewer", "Reason", "Recorded"],
                    [
                        [d["choice"], d["reviewer"], d["rationale"], d["created_at"]]
                        for d in detail["decisions"]
                    ],
                ),
            ]
        if request.kind == "pursuit_plan":
            sections += [
                section(
                    "Proposed win themes",
                    [
                        "Hypothesis: a single accountable maintenance and reporting plan could address fragmented delivery. Validate this against buyer feedback before using it in a bid.",
                        "Differentiate only through evidenced coverage, service performance and a costed mobilisation plan.",
                    ],
                ),
                section(
                    "Account entry and buyer questions",
                    [
                        "Confirm who owns technical evaluation, procurement and budget approval; no personal contacts have been inferred.",
                        "Which asset categories, response times and evidence outputs determine success?",
                        "What drove the procurement timetable, and what would prevent mobilisation?",
                    ],
                ),
                section(
                    "Technical milestones",
                    [
                        "Obtain the priced asset register before margin sign-off.",
                        "Confirm regional engineering capacity and required accreditations before delivery commitment.",
                        "Review the draft response with the bid owner before the recorded submission date.",
                    ],
                ),
            ]
        if request.kind == "battlecard":
            candidates = [
                c
                for c in db.scalars(select(CompetitorProfile))
                if o["sector"] in c.sectors
            ]
            sections.append(
                section(
                    "Recorded sector profiles",
                    [
                        "Sector overlap is not evidence of participation in this pursuit. Incumbent identity remains unknown unless explicitly sourced."
                    ],
                    [
                        "Profile",
                        "Recorded strengths",
                        "Recorded limitations",
                        "Response",
                    ],
                    [
                        [
                            c.name,
                            "; ".join(c.strengths),
                            "; ".join(c.weaknesses),
                            c.counter_strategy,
                        ]
                        for c in candidates
                    ],
                )
            )
            if not candidates:
                sections.append(
                    section(
                        "Evidence required",
                        [
                            "No sector-matched competitor profile is recorded. Ask the buyer about incumbent performance and verify permitted public sources before naming competitors."
                        ],
                    )
                )
        if request.kind == "self_delivery":
            result = scenario.result
            sections += [
                section(
                    "Capture hypothesis",
                    [
                        f"Modelled annual gross margin moves from {gbp(result['baseline']['gross_margin'])} to {gbp(result['proposed']['gross_margin'])}; difference {gbp(result['delta_gross_margin'])}.",
                        f"Expected contribution after bid and mobilisation assumptions changes by {gbp(result['delta_expected_contribution'])}. This is potential value, not savings achieved.",
                        result["formula"],
                    ],
                ),
                section(
                    "Delivery assumptions",
                    [scenario.assumptions["assumption_note"]],
                    ["Input", "Assumption"],
                    [
                        [k.replace("_", " "), str(v)]
                        for k, v in scenario.assumptions.items()
                        if k != "assumption_note"
                    ],
                ),
                section(
                    "Sensitivity to internal delivery cost",
                    columns=[
                        "Internal cost ratio",
                        "Annual margin",
                        "Expected contribution",
                    ],
                    rows=[
                        [
                            f"{Decimal(v['inhouse_cost_ratio']) * 100}%",
                            gbp(v["gross_margin"]),
                            gbp(v["expected_contribution"]),
                        ]
                        for v in result["sensitivity"]
                    ],
                ),
                section(
                    "Transition requirements",
                    result["warnings"]
                    + [
                        "Confirm addressable subcontract expenditure, engineering coverage, accreditation evidence, site access and transition responsibilities with Operations."
                    ],
                ),
            ]
        if request.kind == "tender":
            sections += [
                section(
                    "Source referenced requirements matrix",
                    [
                        "Requirements below are explicitly captured source extracts. Unassessed items and gaps are not compliance claims."
                    ],
                    ["Requirement", "Source", "Status", "Evidence", "Owner"],
                    [
                        [
                            r["requirement"],
                            r["source_reference"],
                            r["compliance"],
                            r["evidence"] or "Missing",
                            r["owner"],
                        ]
                        for r in detail["requirements"]
                    ],
                ),
                section(
                    "Response and clarification plan",
                    [
                        "For each gap, obtain the source clause, define the clarification question and assign technical input to the named owner.",
                        "Confirm requirement interpretation with the buyer and submit only reviewed compliance evidence.",
                    ],
                ),
            ]
        sections.append(
            section(
                "Risks and unresolved questions",
                q["risks"]
                + [
                    "Evidence required: " + gap
                    for gap in (enrichment.get("unknowns") or q["gaps"])
                ]
                or [
                    "No risks captured by these rules. This does not establish absence of risk."
                ],
            )
        )
        sections.append(
            section(
                "Live pursuit actions at generation",
                columns=["Action ID", "Action", "Owner", "Due", "Status"],
                rows=[
                    [
                        str(a["id"]),
                        a["recommended_action"],
                        a["owner"],
                        a["due_date"] or "Unscheduled",
                        a["status"],
                    ]
                    for a in detail["actions"]
                ],
            )
        )
        sections.append(
            section(
                "Evidence and assumptions",
                columns=["Field", "Value", "Type and confidence", "Source"],
                rows=[
                    [
                        e["field_name"].replace("_", " "),
                        (
                            "Unknown"
                            if e["field_value"] is None
                            else str(e["field_value"])
                        ),
                        f"{e['value_type']} · {e['confidence_score'] * 100:g}%"
                        + (" · stale" if e["stale"] else ""),
                        "; ".join(e["source_titles"] + e["source_urls"]) or "No source",
                    ]
                    for e in detail["evidence"]
                ],
            )
        )
        for e in detail["evidence"]:
            sources.append(
                {
                    "reference": f"field:{e['id']}",
                    "title": e["field_name"],
                    "timestamp": e["updated_at"],
                    "type": e["value_type"],
                    "urls": e["source_urls"],
                    "rationale": e["rationale"],
                }
            )
    if request.kind in {"leadership", "forecast"}:
        sections += [
            section(
                "Executive financial position",
                [
                    f"FY {finance['financial_year']} recorded secured revenue is {gbp(finance['secured_revenue'])}. Weighted open revenue is {gbp(finance['open_weighted_revenue'])}; after recorded risk adjustments it is {gbp(finance['risk_adjusted_revenue'])}.",
                    f"The existing LE1 service returns {gbp(finance['forecast_to_financial_year_end'])} revenue and {gbp(finance['forecast_margin_to_financial_year_end'])} margin. These are forecast measures, not realised cash. Finance must approve the definitions before operational use.",
                ],
            ),
            section(
                "Movement between accepted snapshots",
                [movements["message"]],
                ["Opportunity", "Field", "Previous", "Current"],
                [
                    [m["name"], m["field"], str(m["before"]), str(m["after"])]
                    for m in movements["changes"]
                ],
            ),
            section(
                "Monthly forecast",
                columns=["Month", "Revenue", "Margin"],
                rows=[
                    [r["month"], gbp(r["value"]), gbp(m["value"])]
                    for r, m in zip(
                        finance["monthly_revenue"],
                        finance["monthly_margin"],
                        strict=True,
                    )
                ],
            ),
            section(
                "Decisions and ownership",
                columns=["Opportunity", "Owner", "Recorded risk", "Next step"],
                rows=[
                    [
                        o["buyer_name"] + " — " + o["name"],
                        o["owner"],
                        o["risk_rating"],
                        o["recommended_action"],
                    ]
                    for o in records
                    if o["stage"].lower() not in {"won", "lost", "qualified out"}
                ],
            ),
            section(
                "Validation warnings",
                [
                    w["message"] if "message" in w else str(w)
                    for w in finance["margin_warnings"]
                ]
                + [
                    "Current public-market connectors are fixtures; no live source refresh is claimed.",
                    "A local reviewer identity is not an authenticated enterprise approval.",
                ],
            ),
        ]
        sources += [
            {
                "reference": f"opportunity:{o['id']}",
                "title": o["name"],
                "timestamp": o["updated_at"],
                "type": o["source_type"],
            }
            for o in records
        ]
    if request.notes:
        sections.append(
            section(
                "Reviewer working notes",
                [
                    request.notes,
                    "These user-provided notes are not independently verified facts.",
                ],
            )
        )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "sections": sections,
        "sources": sources,
        "detail": detail,
        "finance": finance,
        "movements": movements,
        "portfolio": records,
        "scenario": record(scenario) if scenario else None,
        "notes": request.notes,
        "source_ids": [s["reference"] for s in sources],
    }


def create_asset(db: Session, request: AssetRequest) -> Asset:
    content = build_content(db, request)
    key = f"{request.kind}:{request.opportunity_id or 'portfolio'}"
    version = (
        db.scalar(select(func.max(Asset.version)).where(Asset.series_key == key)) or 0
    ) + 1
    name = (
        content["detail"]["opportunity"]["buyer_name"]
        if content["detail"]
        else "Commercial portfolio"
    )
    asset = Asset(
        opportunity_id=request.opportunity_id,
        kind=request.kind,
        series_key=key,
        title=f"{name} {TITLES[request.kind]}",
        version=version,
        review_status="draft",
        content=content,
    )
    db.add(asset)
    commit_event(
        db,
        f"Generate {TITLES[request.kind]}",
        "Local author",
        [change(db, asset)],
        "Immutable content snapshot; review status is recorded separately.",
    )
    return asset
