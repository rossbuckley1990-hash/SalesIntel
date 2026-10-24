from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from openpyxl import load_workbook
import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base, create_database_engine, get_db
from app.main import create_app
from app.models import Opportunity
from app.schemas.living import ScenarioInput
from app.services.living.demo import seed_living_demo
from app.services.living.finance import allocate, calculate_scenario


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "demo")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        seed_living_demo(db)
    app = create_app()

    def override():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        c.sessions = sessions
        yield c
    engine.dispose()
    get_settings.cache_clear()


def scenario_input(**changes):
    return {
        "annual_revenue": "1000000.00",
        "baseline_share": ".4",
        "proposed_share": ".7",
        "inhouse_cost_ratio": ".62",
        "subcontract_cost_ratio": ".84",
        "probability": ".6",
        "bid_cost": "12000",
        "mobilisation_cost": "18000",
        "payment_delay_days": 30,
        "start_month": "2026-10",
        "financial_year_start": 2026,
        "assumption_note": "Explicit hypothetical delivery assumptions for testing.",
        "source_references": ["opportunity:1"],
        **changes,
    }


def test_decimal_calculation_and_financial_year():
    result = calculate_scenario(ScenarioInput(**scenario_input()))
    assert result["baseline"]["gross_margin"] == "248000.00"
    assert result["proposed"]["gross_margin"] == "314000.00"
    assert result["baseline"]["expected_contribution"] == "136800.00"
    assert result["proposed"]["expected_contribution"] == "165600.00"
    assert result["delta_expected_contribution"] == "28800.00"
    assert result["monthly"][0]["month"] == "2026-04"
    assert result["monthly"][-1]["month"] == "2027-03"
    assert Decimal(result["financial_year_revenue"]) == Decimal(
        "499999.98"
    )  # 6 of 12 penny-allocated months
    assert sum(allocate(Decimal("1000000.00"), 12)) == Decimal("1000000.00")
    assert result["sensitivity"][0]["gross_margin"] == "349000.00"


@pytest.mark.parametrize(
    "change",
    [
        {"probability": "1.01"},
        {"annual_revenue": "NaN"},
        {"inhouse_cost_ratio": "Infinity"},
        {"bid_cost": "-1"},
        {"start_month": "2026-13"},
        {"annual_revenue": "0.001"},
    ],
)
def test_invalid_financial_assumptions_rejected(client, change):
    assert (
        client.post(
            "/api/living/scenarios/calculate", json=scenario_input(**change)
        ).status_code
        == 422
    )


def test_zero_and_year_boundaries():
    zero = calculate_scenario(
        ScenarioInput(
            **scenario_input(annual_revenue="0", probability="0", bid_cost="100")
        )
    )
    assert zero["proposed"]["gross_margin"] == "0.00"
    assert zero["proposed"]["expected_contribution"] == "-100.00"
    march = calculate_scenario(ScenarioInput(**scenario_input(start_month="2027-03")))
    assert sum(Decimal(m["revenue"]) > 0 for m in march["monthly"]) == 1
    april = calculate_scenario(ScenarioInput(**scenario_input(start_month="2027-04")))
    assert april["financial_year_revenue"] == "0.00"


def test_question_evidence_decision_asset_outcome_journey(client):
    result = client.post(
        "/api/living/discover",
        json={"query": "Find universities in Yorkshire for fire maintenance"},
    )
    assert result.status_code == 200
    assert set(result.json()["matches"]) == {1, 2}
    detail = client.get("/api/living/opportunities/1").json()
    assert detail["evidence"] and detail["qualification"]["criteria"]
    unknown = next(f for f in detail["evidence"] if f["value_type"] == "unknown")
    reviewed = client.post(
        f"/api/living/evidence/{unknown['id']}/reviews",
        json={
            "disposition": "acknowledged",
            "reviewer": "Test owner",
            "note": "Capacity evidence is still required before commitment.",
        },
    )
    assert reviewed.status_code == 200
    assert (
        next(
            f
            for f in client.get("/api/living/opportunities/1").json()["evidence"]
            if f["id"] == unknown["id"]
        )["value_type"]
        == "unknown"
    )
    decision = client.post(
        "/api/living/opportunities/1/decisions",
        json={
            "choice": "pursue",
            "rationale": "Pursue subject to a verified regional engineering plan.",
            "reviewer": "Test owner",
            "owner": "Bid team",
            "due_date": "2026-11-01",
            "action": "Obtain the regional engineering capacity evidence",
        },
    )
    assert decision.status_code == 200
    assert decision.json()["outcome"]["stage"] == "approved"
    asset = client.post(
        "/api/living/assets", json={"kind": "dossier", "opportunity_id": 1}
    ).json()
    assert asset["version"] == 1 and asset["review_status"] == "draft"
    assert "Alderwick" in asset["title"]
    assert len(asset["content"]["sources"]) >= 10
    assert str(decision.json()["action"]["id"]) in str(asset["content"]["sections"])
    assert (
        client.get(f"/api/living/assets/{asset['id']}").json()["content"]
        == asset["content"]
    )
    revised = client.post(
        "/api/living/assets",
        json={
            "kind": "dossier",
            "opportunity_id": 1,
            "notes": "Review capacity with the regional team.",
        },
    ).json()
    assert revised["version"] == 2
    assert (
        client.get(f"/api/living/assets/{asset['id']}").json()["content"]["notes"] == ""
    )
    outcome_payload = {
        "stage": "realised",
        "owner": "Finance owner",
        "expected_impact": "1000",
        "actual_value": "420",
        "assumptions": "Measured contribution for an explicitly defined completed period.",
        "completion_evidence": "Test invoice and approved margin reconciliation reference 42.",
        "verified_by": "Finance reviewer",
    }
    assert (
        client.put(
            "/api/living/opportunities/1/outcome", json=outcome_payload
        ).status_code
        == 200
    )
    outcome = next(
        o
        for o in client.get("/api/living/workspace").json()["outcomes"]
        if o["opportunity_id"] == 1
    )
    assert outcome["actual_value"] == "420.00"


def test_unknown_draft_not_zero_and_no_irrelevant_match(client):
    assert (
        client.post(
            "/api/living/discover", json={"query": "Quantum orchard Zzyzx Antarctica"}
        ).json()["matches"]
        == []
    )
    created = client.post(
        "/api/living/discover",
        json={
            "query": "Investigate a new fire maintenance programme",
            "create_draft": True,
            "owner": "Sales owner",
        },
    ).json()
    oid = created["matches"][0]
    detail = client.get(f"/api/living/opportunities/{oid}").json()
    assert all(value is None for value in detail["financials"].values())
    pulse = client.get("/api/living/workspace").json()["pulse"]
    assert pulse["weighted_contract_value"]["unknown"] == 1


def test_scenario_is_persisted_without_changing_source(client):
    before = client.get("/api/opportunities/1").json()
    result = client.post(
        "/api/living/scenarios",
        json={
            "opportunity_id": 1,
            "name": "Delivery model",
            "owner": "Finance",
            "inputs": scenario_input(),
        },
    )
    assert result.status_code == 200
    saved = result.json()
    assert saved["result"] == calculate_scenario(ScenarioInput(**saved["assumptions"]))
    assert client.get("/api/opportunities/1").json() == before
    assert client.get("/api/living/scenarios").json()[0]["id"] == saved["id"]
    mismatch = client.post(
        "/api/living/assets",
        json={"kind": "self_delivery", "opportunity_id": 2, "scenario_id": saved["id"]},
    )
    assert mismatch.status_code == 422


@pytest.mark.parametrize(
    "kind",
    [
        "dossier",
        "bid_decision",
        "pursuit_plan",
        "battlecard",
        "forecast",
        "leadership",
        "tender",
    ],
)
def test_all_asset_types_and_exports_contain_recorded_data(client, kind):
    result = client.post(
        "/api/living/assets",
        json={
            "kind": kind,
            "opportunity_id": 1 if kind not in {"forecast", "leadership"} else None,
        },
    )
    assert result.status_code == 200
    asset = result.json()
    assert len(asset["content"]["sections"]) >= 4
    pdf = client.get(f"/api/living/assets/{asset['id']}/export/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    docx = client.get(f"/api/living/assets/{asset['id']}/export/docx")
    with ZipFile(BytesIO(docx.content)) as archive:
        document = archive.read("word/document.xml").decode()
        assert "Alderwick" in document and "Source register" in document
    xlsx = client.get(f"/api/living/assets/{asset['id']}/export/xlsx")
    workbook = load_workbook(BytesIO(xlsx.content))
    assert (
        workbook["Summary"]["B7"].value
        == asset["content"]["finance"]["forecast_to_financial_year_end"]
    )
    assert workbook["Monthly forecast"]["B14"].value == "=SUM(B2:B13)"
    assert workbook["Sources"].max_row > 1


def test_business_case_and_missing_evidence_gates(client):
    assert (
        client.post(
            "/api/living/assets", json={"kind": "self_delivery", "opportunity_id": 1}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/living/assets", json={"kind": "tender", "opportunity_id": 2}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/living/opportunities/2/requirements",
            json={
                "requirement": "Must hold a verified accreditation",
                "source_reference": "Tender schedule section 2",
                "compliance": "evidenced",
            },
        ).status_code
        == 422
    )
    scenario = client.post(
        "/api/living/scenarios",
        json={
            "opportunity_id": 1,
            "name": "Capture model",
            "owner": "Finance",
            "inputs": scenario_input(),
        },
    ).json()
    asset = client.post(
        "/api/living/assets",
        json={
            "kind": "self_delivery",
            "opportunity_id": 1,
            "scenario_id": scenario["id"],
        },
    ).json()
    assert "£66,000.00" in str(asset["content"]["sections"])
    workbook = load_workbook(
        BytesIO(client.get(f"/api/living/assets/{asset['id']}/export/xlsx").content)
    )
    assert workbook["Scenario inputs"]["B2"].value == 1000000
    assert workbook["Scenario model"]["D3"].value == "=C3-B3"


def test_realised_value_requires_evidence_and_never_implicit(client):
    payload = {
        "stage": "realised",
        "owner": "Finance",
        "assumptions": "Potential estimate only",
    }
    assert (
        client.put("/api/living/opportunities/1/outcome", json=payload).status_code
        == 422
    )
    payload.update(stage="investigating", actual_value="100")
    assert (
        client.put("/api/living/opportunities/1/outcome", json=payload).status_code
        == 422
    )
    payload.pop("actual_value")
    payload["stage"] = "approved"
    assert (
        client.put("/api/living/opportunities/2/outcome", json=payload).status_code
        == 422
    )


def test_completion_requires_evidence_and_detects_stale_status(client):
    payload = {
        "owner": "Sales owner",
        "due_date": "2026-11-01",
        "status": "completed",
        "action": "Review capacity",
        "completion_evidence": "",
        "expected_status": "open",
    }
    assert client.patch("/api/living/actions/1", json=payload).status_code == 422
    payload["completion_evidence"] = "Regional capacity review document 123"
    assert client.patch("/api/living/actions/1", json=payload).status_code == 200
    assert client.patch("/api/living/actions/1", json=payload).status_code == 409


def test_snapshot_diff_is_between_saved_states(client):
    workspace = client.get("/api/living/workspace").json()
    assert len(workspace["changes"]["changes"]) >= 3
    assert workspace["changes"]["previous"]["captured_at"]
    assert workspace["changes"]["current"]["captured_at"]
    assert (
        client.post(
            "/api/living/snapshots",
            json={"label": "Unchanged current state", "reviewer": "Test reviewer"},
        ).status_code
        == 200
    )
    assert client.get("/api/living/workspace").json()["changes"]["changes"] == []


def test_undo_is_atomic_with_linked_decision_action_outcome(client):
    before = client.get("/api/living/workspace").json()
    decision = client.post(
        "/api/living/opportunities/1/decisions",
        json={
            "choice": "investigate",
            "rationale": "Check engineering coverage first",
            "reviewer": "Test owner",
            "owner": "Test team",
            "due_date": "2026-11-01",
            "action": "Validate coverage before commitment",
        },
    ).json()
    assert (
        client.post(f"/api/living/audit/{decision['event_id']}/undo").status_code == 200
    )
    after = client.get("/api/living/workspace").json()
    assert before["actions"] == after["actions"]
    assert before["outcomes"] == after["outcomes"]
    assert client.get("/api/living/opportunities/1").json()["decisions"] == []
    assert (
        client.post(f"/api/living/audit/{decision['event_id']}/undo").status_code == 409
    )


def test_undo_refuses_intervening_source_edits(client):
    result = client.post(
        "/api/living/actions",
        json={
            "opportunity_id": 1,
            "owner": "Sales",
            "due_date": "2026-11-01",
            "action": "Validate buyer scope",
            "reason": "Tender deadline approaching",
        },
    ).json()
    eid = client.get("/api/living/workspace").json()["last_event"]["id"]
    from app.models import ExecutiveAction

    with client.sessions() as db:
        db.get(ExecutiveAction, result["id"]).owner = "Another editor"
        db.commit()
    assert client.post(f"/api/living/audit/{eid}/undo").status_code == 409


def test_import_preview_mapping_commit_deduplication_and_undo(client):
    csv = b"Project,Business,Annual revenue\nNew fire service,Example fictional estate,125000\n"
    before = len(client.get("/api/opportunities").json())
    preview = client.post(
        "/api/living/imports/preview",
        files={"file": ("test.csv", csv, "text/csv")},
        data={"mapping": '{"Business":"buyer_name"}'},
    ).json()
    assert preview["can_commit"] and preview["rows"][0]["operation"] == "create"
    assert len(client.get("/api/opportunities").json()) == before
    committed = client.post(f"/api/living/imports/{preview['id']}/commit")
    assert committed.status_code == 200
    assert len(client.get("/api/opportunities").json()) == before + 1
    assert client.post(f"/api/living/imports/{preview['id']}/commit").status_code == 409
    assert (
        client.post(
            f"/api/living/audit/{committed.json()['event_id']}/undo"
        ).status_code
        == 200
    )
    assert len(client.get("/api/opportunities").json()) == before
    duplicate = client.post(
        "/api/living/imports/preview",
        files={
            "file": (
                "duplicate.csv",
                csv + b"New fire service,Example fictional estate,125000\n",
                "text/csv",
            )
        },
        data={"mapping": '{"Business":"buyer_name"}'},
    ).json()
    assert not duplicate["can_commit"] and duplicate["errors"]


def test_import_detects_stale_preview_and_rejects_nonfinite_values(client):
    csv = (
        b"Opportunity,Buyer,Annual revenue\nImported service,Fictional estate,125000\n"
    )
    preview = client.post(
        "/api/living/imports/preview", files={"file": ("test.csv", csv, "text/csv")}
    ).json()
    with client.sessions() as db:
        db.get(Opportunity, 1).owner = "Intervening editor"
        db.commit()
    assert client.post(f"/api/living/imports/{preview['id']}/commit").status_code == 409
    invalid = client.post(
        "/api/living/imports/preview",
        files={
            "file": (
                "invalid.csv",
                b"Opportunity,Buyer,Annual revenue\nService,Fictional,NaN\n",
                "text/csv",
            )
        },
    ).json()
    assert not invalid["can_commit"]


def test_export_formula_injection_is_inert(client):
    created = client.post(
        "/api/living/discover",
        json={
            "query": "Investigate a fictional service",
            "buyer": '=HYPERLINK("https://example.invalid","click")',
            "create_draft": True,
        },
    ).json()
    asset = client.post(
        "/api/living/assets",
        json={"kind": "dossier", "opportunity_id": created["matches"][0]},
    ).json()
    wb = load_workbook(
        BytesIO(client.get(f"/api/living/assets/{asset['id']}/export/xlsx").content)
    )
    assert wb["Summary"]["B2"].data_type == "s"


def test_migrations_fresh_database_and_idempotency(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    database = tmp_path / "migrated.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    engine = create_database_engine(f"sqlite:///{database}")
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables) | {
        "alembic_version"
    }
    with sessionmaker(bind=engine)() as db:
        assert seed_living_demo(db)
    command.downgrade(config, "0001_legacy")
    assert "opportunities" in inspect(engine).get_table_names()
    assert "living_assets" not in inspect(engine).get_table_names()
    engine.dispose()
    get_settings.cache_clear()


def test_action_prerequisites_completion_and_reversible_evidence(client):
    payload = {
        "opportunity_id": 1,
        "owner": "Action owner",
        "due_date": "2026-11-01",
        "action": "Price the validated capacity",
        "reason": "Required for bid margin validation",
        "depends_on": [1],
    }
    response = client.post("/api/living/actions", json=payload)
    assert response.status_code == 200
    action_id = response.json()["id"]
    update = {
        "owner": "Action owner",
        "due_date": "2026-11-01",
        "action": payload["action"],
        "status": "completed",
        "expected_status": "open",
        "completion_evidence": "Synthetic evidence CAP-42 reviewed.",
    }
    assert (
        client.patch(f"/api/living/actions/{action_id}", json=update).status_code == 422
    )
    assert (
        client.patch(
            "/api/living/actions/1",
            json={**update, "status": "open", "depends_on": [action_id]},
        ).status_code
        == 422
    )
    assert client.patch("/api/living/actions/1", json=update).status_code == 200
    assert (
        client.patch(f"/api/living/actions/{action_id}", json=update).status_code == 200
    )
    actions = client.get("/api/living/opportunities/1").json()["actions"]
    saved = next(a for a in actions if a["id"] == action_id)
    assert saved["depends_on"] == [1] and saved["blocked_by"] == []
    assert saved["completion_evidence"] == update["completion_evidence"]
    event = client.get("/api/living/workspace").json()["last_event"]
    assert client.post(f"/api/living/audit/{event['id']}/undo").status_code == 200
    saved = next(
        a
        for a in client.get("/api/living/opportunities/1").json()["actions"]
        if a["id"] == action_id
    )
    assert saved["status"] == "open" and saved["completion_evidence"] == ""


def test_source_extraction_requires_review_and_keeps_exact_lines(client):
    source = "Introduction\nSupplier shall inspect the alarm panel monthly.\nPersonnel must present current accreditation evidence.\nOptional site visit."
    result = client.post(
        "/api/living/requirements/extract",
        json={"text": source, "source_reference": "Synthetic tender.pdf page 4"},
    ).json()
    assert len(result["requirements"]) == 2
    assert result["requirements"][0]["requirement"] == source.splitlines()[1]
    assert result["requirements"][0]["source_reference"].endswith("line 2")
    before = client.get("/api/living/opportunities/1").json()["requirements"]
    assert len(before) == 3
    saved = client.post(
        "/api/living/opportunities/1/requirements/capture",
        json={"requirements": result["requirements"]},
    )
    assert saved.status_code == 200 and all(
        r["compliance"] == "unassessed" for r in saved.json()
    )
    event = client.get("/api/living/workspace").json()["last_event"]
    assert client.post(f"/api/living/audit/{event['id']}/undo").status_code == 200
    assert client.get("/api/living/opportunities/1").json()["requirements"] == before


def test_local_workspace_rejects_production_without_identity(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    assert client.get("/api/living/workspace").status_code == 503


def test_import_preserves_missing_annual_basis_and_updates_only_supplied_fields(client):
    csv = b"Opportunity,Buyer,Revenue,Probability\nContract only,Fictional estate,900000,60%\n"
    preview = client.post(
        "/api/living/imports/preview", files={"file": ("contract.csv", csv, "text/csv")}
    ).json()
    assert preview["can_commit"]
    assert client.post(f"/api/living/imports/{preview['id']}/commit").status_code == 200
    item = next(
        o
        for o in client.get("/api/living/workspace").json()["opportunities"]
        if o["name"] == "Contract only"
    )
    assert item["financials"]["estimated_total_contract_value"] == 900000
    assert item["financials"]["estimated_annual_revenue"] is None
    assert item["financials"]["estimated_gross_margin"] is None
    bad = client.post(
        "/api/living/imports/preview",
        files={"file": ("bad.csv", csv.replace(b"60%", b"120%"), "text/csv")},
    ).json()
    assert not bad["can_commit"]
    change_csv = b"Opportunity,Buyer,Owner\nContract only,Fictional estate,New owner\n"
    updated = client.post(
        "/api/living/imports/preview",
        files={"file": ("owner.csv", change_csv, "text/csv")},
    ).json()
    assert client.post(f"/api/living/imports/{updated['id']}/commit").status_code == 200
    detail = client.get(f"/api/living/opportunities/{item['id']}").json()
    assert detail["opportunity"]["owner"] == "New owner"
    assert detail["financials"]["estimated_total_contract_value"] == 900000
    assert detail["financials"]["estimated_annual_revenue"] is None


def test_xlsx_preview_and_annual_margin_basis(client):
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.append(["Opportunity", "Buyer", "Annual revenue", "Revenue", "Margin %"])
    sheet.append(
        ["Workbook annual basis", "Fictional workbook estate", 100000, 300000, 25]
    )
    stream = BytesIO()
    book.save(stream)
    preview = client.post(
        "/api/living/imports/preview",
        files={
            "file": (
                "source.xlsx",
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    ).json()
    assert preview["can_commit"]
    assert preview["rows"][0]["values"]["estimated_gross_margin"] == 25000
    assert (
        preview["rows"][0]["provenance"]["estimated_gross_margin"]
        == "system_calculated"
    )
    assert client.post(f"/api/living/imports/{preview['id']}/commit").status_code == 200
    row = next(
        o
        for o in client.get("/api/living/workspace").json()["opportunities"]
        if o["name"] == "Workbook annual basis"
    )
    assert row["financials"]["estimated_annual_revenue"] == 100000
    assert row["financials"]["estimated_total_contract_value"] == 300000
    assert row["financials"]["estimated_gross_margin"] == 25000


def test_pdf_exports_long_tender_rows_without_layout_failure(client):
    requirement = (
        "The supplier must provide current competence evidence for every assigned engineer. "
        * 45
    )[:3950]
    assert (
        client.post(
            "/api/living/opportunities/1/requirements",
            json={
                "requirement": requirement,
                "source_reference": "Synthetic specification clause 6 page 10",
                "owner": "Test owner",
            },
        ).status_code
        == 200
    )
    asset = client.post(
        "/api/living/assets", json={"kind": "tender", "opportunity_id": 1}
    ).json()
    result = client.get(f"/api/living/assets/{asset['id']}/export/pdf")
    assert result.status_code == 200 and result.content.startswith(b"%PDF-")
