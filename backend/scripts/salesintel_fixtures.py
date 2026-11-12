"""Load clearly synthetic SalesIntel records into an isolated test database.

Used by the browser tests. It refuses to run unless APP_ENV is demo, so it can never
write fictional records into a real workspace.
"""
from datetime import UTC, datetime, timedelta
import os
import sys

from app.db import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.models.prospect import Prospect

if os.environ.get("APP_ENV") != "demo":
    sys.exit("salesintel_fixtures.py only runs with APP_ENV=demo")

now = datetime.now(UTC)
Base.metadata.create_all(engine)
NOTICE = "https://www.contractsfinder.service.gov.uk/Notice/example-synthetic-0001"
with SessionLocal() as db:
    if db.query(MarketOpportunity).count():
        sys.exit(0)
    def opportunity(key, customer, title, supplier, days, value=None):
        item = MarketOpportunity(dedup_key=key, first_seen=now, last_evaluated=now)
        db.add(item)
        db.flush()
        result = {"kind": "possible_renewal_window", "fit_reason": "title names both the system and the service", "unknowns": [], "category": "pre_tender", "category_label": "Pre-tender opportunity", "customer": customer, "title": title, "supplier": supplier,
                  "timing": (now + timedelta(days=days)).date().isoformat(), "timing_basis": "published award contract period", "end_estimated": False, "latest_end": None,
                  "nation": "England", "fit": "core", "value": value or {"type": "unknown", "published_total": None, "estimated_annualised": None, "framework_ceiling": None, "basis": "No value is published.", "scope_note": ""},
                  "priority": {"tier": 1, "reasons": ["Core fit"]}, "counter_evidence": [], "next_actions": ["Investigate the buyer's plans."], "next_action": "Investigate the buyer's plans.",
                  "extension": "", "link": {"confidence": "exact", "records": 1, "sources": ["Contracts Finder"]},
                  "brief": {"why_it_matters": "Title names both the system and the service.", "missing_information": ["Procurement route."], "contract_lifecycle": "", "procurement_route": ""},
                  "evidence": [{"source_revision_id": 1, "source_url": NOTICE, "source": "Contracts Finder", "record_key": "example-synthetic-0001", "published_at": "2023-04-01"}]}
        version = MarketOpportunityRevision(opportunity_id=item.id, fingerprint="synthetic", result=result, created_at=now)
        db.add(version)
        db.flush()
        item.current_revision_id = version.id
    opportunity("synthetic:1", "EXAMPLE HOUSING TRUST LIMITED", "Fire alarm servicing and maintenance across 14 sheltered schemes", "Sample Fire Services Ltd", 150,
                value={"type": "estimated_annualised", "published_total": 312000, "estimated_annualised": 104000, "framework_ceiling": None,
                       "basis": "Published award value divided by the published term of 3.0 years.", "scope_note": ""})
    opportunity("synthetic:2", "Sample Borough Council", "CCTV maintenance for town centre cameras", None, 220)
    db.add(Prospect(dedup_key="example housing trust", name="Example Housing Trust", status="new", created_at=now, updated_at=now, data={
        "website": "https://www.example-housing.example", "sector": "Housing", "location": "Leeds, England", "company_number": "", "size": "",
        "headline": "Building a new extra-care scheme due to open in 2027.", "summary": "Synthetic test record.",
        "signals": [{"type": "new_site", "title": "New extra-care scheme announced", "detail": "Synthetic.", "date": "2026-09", "basis": "stated", "direction": "supports",
                     "source_url": "https://news.example/example-housing-scheme"}],
        "timing_clues": [], "incumbent": {"name": "", "detail": "", "basis": "unknown", "source_url": ""}, "competitors": [],
        "people": [{"name": "Robin Sample", "role": "Head of Assets", "influence": "decision_maker", "why": "Leads the scheme",
                    "source_url": "https://news.example/example-housing-scheme", "quote": "said Robin Sample, Head of Assets"}],
        "contact_routes": [], "approach": {"angle": "", "opening_line": "", "offer": "", "questions": []}, "services": ["fire_alarm"], "unknowns": []}))
    db.commit()
print("SalesIntel synthetic fixtures loaded")
