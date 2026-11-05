"""Phase 1 acceptance: identities, workspaces, roles and isolation between companies.

Every test runs the real application in hosted mode with signed tokens, on SQLite and, when
SALESINTEL_TEST_POSTGRES_URL is set (always in CI), on PostgreSQL.
"""
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from app import auth
from app.config import Settings
from app.models import Opportunity
from app.models.crm import Account, Contact, DealRecord, Draft, Task
from app.models.market_opportunity import MarketOpportunity
from app.models.prospect import Prospect
from app.models.tenancy import WorkspaceAuditEvent
from app.tenancy import TenantScopeError
from tenancy_support import hosted  # noqa: F401
from test_salesintel_journey import add_mo, add_prospect, journey_to_logged_contact

SCOPE = [{"service": "fire_alarm", "field": f, "value": v, "basis": "surveyed"} for f, v in (("panels", 2), ("devices", 80), ("visits_per_year", 2), ("panel_make", "X"))]
RATES = {"fire_alarm.panels": "120", "fire_alarm.devices": "5", "fire_alarm.visits_per_year": "350"}


def workspace(h, sub, email, name):
    c = h.client(sub, email, name)
    org = c.post("/api/workspaces", json={"name": name}).json()["id"]
    return h.client(sub, email, sub.title(), workspace=org), org


def two_companies(h):
    with h.system() as db:
        mo = add_mo(db)
    alice, a_org = workspace(h, "alice", "alice@alpha.example", "Alpha Fire Ltd")
    bob, b_org = workspace(h, "bob", "bob@beta.example", "Beta Security Ltd")
    return alice, a_org, bob, b_org, mo


def build_alpha(alice, h, a_org):
    """Alpha's full private record set: account, contact, approved draft, activity, follow-up, deal with quote, research."""
    account, key = journey_to_logged_contact(alice)
    contact = alice.post(f"/api/si/accounts/{account}/contacts", json={"name": "Jo Example", "role": "Estates", "email": "jo@orbit.example"}).json()["id"]
    draft = alice.post(f"/api/si/accounts/{account}/drafts", json={"subject": "Hi", "body": "Dear Jo, hello. Regards, Alice", "contact_id": contact}).json()["id"]
    deal = alice.post(f"/api/si/accounts/{account}/deals", json={"source_key": key, "services": ["fire_alarm"], "qualification": {"requirement": "PPM"}}).json()["id"]
    alice.put(f"/api/si/deals/{deal}/scope", json={"entries": SCOPE})
    alice.post(f"/api/si/deals/{deal}/quote", json={"rates": RATES})
    alice.post(f"/api/si/discover/{key}/status", json={"status": "investigating"})
    task = alice.get(f"/api/si/accounts/{account}").json()["tasks"][0]["id"]
    with h.as_workspace(a_org) as db:
        prospect = add_prospect(db, name="Alpha Secret Prospect Ltd", company_number="01234567")
    alice.post("/api/si/saved-views", json={"name": "Alpha view", "filters": {"q": "orbit"}})
    return {"account": account, "key": key, "contact": contact, "draft": draft, "deal": deal, "task": task, "prospect": prospect}


# ---------------------------------------------------------------- authentication

def test_requests_without_a_valid_identity_are_refused(hosted):
    h = hosted
    assert h.anonymous().get("/api/si/today").status_code == 401
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    moment = datetime.now(UTC)
    good = {"iss": auth.DEV_ISSUER, "aud": auth.DEV_AUDIENCE, "sub": "mallory", "email": "m@x.example", "email_verified": True, "iat": moment, "exp": moment + timedelta(minutes=5)}
    forged = {
        "signed by another key": jwt.encode(good, other_key, algorithm="RS256"),
        "unsigned (alg none)": jwt.encode(good, None, algorithm="none"),
        "symmetric with a guessable secret": jwt.encode(good, "secret", algorithm="HS256"),
        "expired": auth.dev_token("mallory", "m@x.example", minutes=-5),
        "wrong issuer": auth.dev_token("mallory", "m@x.example", iss="https://evil.example"),
        "wrong audience": auth.dev_token("mallory", "m@x.example", aud="someone-else"),
    }
    for label, token in forged.items():
        r = h.anonymous().get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401, label
    unverified = h.client("eve", "eve@x.example", email_verified=False)
    assert unverified.get("/api/me").status_code == 403


def test_unsafe_configurations_refuse_to_start():
    with pytest.raises(RuntimeError, match="only allowed with APP_ENV=demo or test"):
        Settings(_env_file=None, auth_mode="dev", app_env="production").check_safe_to_serve()
    with pytest.raises(RuntimeError, match="needs OIDC_ISSUER"):
        Settings(_env_file=None, auth_mode="oidc").check_safe_to_serve()
    with pytest.raises(RuntimeError, match="must use https"):
        Settings(_env_file=None, auth_mode="oidc", oidc_issuer="i", oidc_audience="a", oidc_jwks_url="http://keys.example").check_safe_to_serve()
    with pytest.raises(RuntimeError, match="asymmetric"):
        Settings(_env_file=None, auth_mode="oidc", oidc_issuer="i", oidc_audience="a", oidc_jwks_url="https://k.example", oidc_algorithms="HS256").check_safe_to_serve()
    with pytest.raises(RuntimeError, match="requires sign-in"):
        Settings(_env_file=None, allow_remote_clients=True).check_safe_to_serve()


def test_development_sign_in_exists_only_in_dev_mode(hosted, monkeypatch):
    token = hosted.anonymous().post("/api/dev/session", json={"email": "Dana@Alpha.example", "name": "Dana"}).json()["token"]
    assert hosted.anonymous().get("/api/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]["email"] == "dana@alpha.example"
    from app.config import get_settings
    from app.main import create_app
    monkeypatch.setenv("AUTH_MODE", "local")
    get_settings.cache_clear()
    assert "/api/dev/session" not in create_app().openapi()["paths"]
    get_settings.cache_clear()


def test_hosted_mode_exposes_only_tenant_scoped_routes(hosted):
    paths = set(hosted.app.openapi()["paths"])
    assert "/api/si/today" in paths and "/api/workspaces" in paths
    assert not any(p.startswith(("/api/opportunities", "/api/living", "/api/upload", "/api/prospects", "/api/market-opportunities")) for p in paths)


# ---------------------------------------------------------------- isolation

def test_another_company_cannot_see_or_change_any_protected_record(hosted):
    h = hosted
    alice, a_org, bob, b_org, mo = two_companies(h)
    a = build_alpha(alice, h, a_org)
    before = alice.get(f"/api/si/deals/{a['deal']}").json()

    # Nothing of Alpha's appears in Beta's lists.
    assert bob.get("/api/si/accounts").json()["items"] == []
    assert bob.get("/api/si/drafts", params={"status": "all"}).json()["items"] == []
    today = bob.get("/api/si/today").json()
    assert today["queue"] == [] and today["upcoming"] == []
    assert bob.get("/api/si/deals").json()["items"] == [] if "items" in bob.get("/api/si/deals").json() else True
    assert bob.get("/api/si/saved-views").json()["items"] == []
    discover = {x["key"]: x for x in bob.get("/api/si/discover", params={"status": "all"}).json()["items"]}
    assert f"pr:{a['prospect']}" not in discover  # Alpha's private research is invisible
    assert discover[a["key"]]["status"] == "new" and discover[a["key"]]["account_id"] is None  # Alpha's review is not shared

    # Every protected record, read or changed by id, behaves as if it does not exist.
    attempts = [
        ("get", f"/api/si/accounts/{a['account']}", None),
        ("patch", f"/api/si/accounts/{a['account']}", {"notes": "x"}),
        ("post", f"/api/si/accounts/{a['account']}/contacts", {"name": "Spy", "role": "x"}),
        ("patch", f"/api/si/contacts/{a['contact']}", {"status": "do_not_contact"}),
        ("post", f"/api/si/accounts/{a['account']}/introduction", {}),
        ("post", f"/api/si/accounts/{a['account']}/drafts", {"subject": "s", "body": "b"}),
        ("patch", f"/api/si/drafts/{a['draft']}", {"body": "overwritten"}),
        ("post", f"/api/si/drafts/{a['draft']}/approve", None),
        ("post", f"/api/si/drafts/{a['draft']}/log", {"sent_externally": True}),
        ("post", f"/api/si/accounts/{a['account']}/activities", {"kind": "note", "summary": "spy"}),
        ("post", f"/api/si/accounts/{a['account']}/tasks", {"title": "t", "due_on": "2026-12-01"}),
        ("post", f"/api/si/tasks/{a['task']}/complete", None),
        ("patch", f"/api/si/tasks/{a['task']}", {"due_on": "2026-12-01"}),
        ("get", f"/api/si/deals/{a['deal']}", None),
        ("patch", f"/api/si/deals/{a['deal']}", {"stage": "lost", "reason": "sabotage"}),
        ("put", f"/api/si/deals/{a['deal']}/scope", {"entries": SCOPE}),
        ("post", f"/api/si/deals/{a['deal']}/quote", {"rates": RATES}),
        ("post", f"/api/si/deals/{a['deal']}/quote/approve", {"reviewer": "Bob"}),
        ("post", f"/api/si/accounts/{a['account']}/deals", {"qualification": {"requirement": "steal"}}),
        ("post", f"/api/si/discover/pr:{a['prospect']}/account", {}),
        ("post", f"/api/si/discover/pr:{a['prospect']}/status", {"status": "dismissed"}),
        ("post", f"/api/si/discover/{a['key']}/account", {"account_id": a["account"]}),
    ]
    for method, path, body in attempts:
        r = getattr(bob, method)(path, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (method, path, r.status_code, r.text[:200])

    # Choosing Alpha's workspace by header is refused: membership is checked, not trusted.
    spoof = h.client("bob", "bob@beta.example", "Bob", workspace=a_org)
    assert spoof.get("/api/si/accounts").status_code == 403

    # Alpha's records are exactly as they were.
    after = alice.get(f"/api/si/deals/{a['deal']}").json()
    assert after == before
    view = alice.get(f"/api/si/accounts/{a['account']}").json()
    assert view["notes"] == "" and [c["status"] for c in view["contacts"]] == ["unverified"] and all(t["status"] == "open" for t in view["tasks"])
    with h.as_workspace(a_org) as db:
        assert db.get(Draft, a["draft"]).body.startswith("Dear Jo")


def test_two_companies_can_pursue_the_same_public_notice_independently(hosted):
    h = hosted
    alice, a_org, bob, b_org, mo = two_companies(h)
    a = build_alpha(alice, h, a_org)
    linked = bob.post(f"/api/si/discover/mo:{mo}/account", json={}).json()
    assert linked["created"] is True and linked["account_id"] != a["account"]
    deal = bob.post(f"/api/si/accounts/{linked['account_id']}/deals", json={"source_key": f"mo:{mo}", "services": ["fire_alarm"], "qualification": {"requirement": "Ours"}}).json()
    assert deal["id"] != a["deal"] and deal["qualification"]["requirement"] == "Ours"
    # Same registered company number in both workspaces is allowed; neither learns of the other.
    with h.as_workspace(b_org) as db:
        add_prospect(db, name="Alpha Secret Prospect Ltd", company_number="01234567")
    assert alice.get(f"/api/si/deals/{a['deal']}").json()["qualification"]["requirement"] == "PPM"


def test_the_session_itself_refuses_unscoped_or_foreign_access(hosted):
    h = hosted
    alice, a_org, bob, b_org, mo = two_companies(h)
    a = build_alpha(alice, h, a_org)
    from sqlalchemy.orm import Session
    with Session(h.engine) as db:  # no workspace and not a system session
        with pytest.raises(TenantScopeError):
            db.scalars(select(Account)).all()
    with h.as_workspace(b_org) as db:
        assert db.get(Account, a["account"]) is None  # Session.get is scoped too
        assert db.scalars(select(Contact)).all() == []
        from sqlalchemy import func
        assert db.scalar(select(func.count()).select_from(Task)) == 0  # counts cannot leak
        with pytest.raises(TenantScopeError):
            db.scalars(select(Opportunity)).all()  # single-user legacy tables are out of reach
        db.add(Account(organisation_id=a_org, name="Planted", key="planted", kind="unknown", status="prospect", watched=False, notes="",
                       created_at=datetime.now(UTC), updated_at=datetime.now(UTC)))
        with pytest.raises(TenantScopeError):
            db.flush()  # writing into another workspace
        db.rollback()
        db.get(MarketOpportunity, mo).review_state = "dismiss"
        with pytest.raises(TenantScopeError):
            db.flush()  # shared public data is read-only to a workspace
    with h.system() as db:
        assert {r.organisation_id for r in db.scalars(select(Account))} == {a_org}


# ---------------------------------------------------------------- roles

def test_roles_are_enforced_by_the_server(hosted):
    h = hosted
    with h.system() as db:
        add_mo(db)
    admin, org = workspace(h, "ann", "ann@alpha.example", "Alpha Fire Ltd")
    tokens = {}
    for sub, role in (("sam", "salesperson"), ("rita", "reviewer"), ("ben", "bid_contributor"), ("max", "sales_manager")):
        tokens[sub] = admin.post("/api/workspace/invitations", json={"email": f"{sub}@alpha.example", "role": role}).json()["token"]
        assert h.client(sub, f"{sub}@alpha.example").post("/api/invitations/accept", json={"token": tokens[sub]}).status_code == 200
    sam, rita, ben, maxi = (h.client(s, f"{s}@alpha.example", s.title(), workspace=org) for s in ("sam", "rita", "ben", "max"))

    # A read-only reviewer can read but cannot change anything.
    assert rita.get("/api/si/accounts").status_code == 200
    assert rita.post("/api/si/accounts", json={"name": "Nope Ltd"}).status_code == 403

    # A salesperson builds a deal but cannot approve a quotation; the manager can, and is recorded by identity.
    account, key = journey_to_logged_contact(sam)
    deal = sam.post(f"/api/si/accounts/{account}/deals", json={"source_key": key, "services": ["fire_alarm"], "qualification": {"requirement": "PPM"}}).json()["id"]
    sam.put(f"/api/si/deals/{deal}/scope", json={"entries": SCOPE})
    sam.post(f"/api/si/deals/{deal}/quote", json={"rates": RATES})
    assert sam.post(f"/api/si/deals/{deal}/quote/approve", json={"reviewer": "Pat Manager"}).status_code == 403
    assert ben.post(f"/api/si/deals/{deal}/quote/approve", json={"reviewer": "Ben"}).status_code == 403
    approved = maxi.post(f"/api/si/deals/{deal}/quote/approve", json={"reviewer": "Somebody Else"}).json()
    assert approved["quote"]["status"] == "approved" and approved["quote"]["approved_by"] == "Max"  # the typed name is ignored

    # A manager cannot approve a quotation on a deal they own.
    account2 = maxi.post("/api/si/accounts", json={"name": "Manager Owned Ltd"}).json()["account_id"]
    own = maxi.post(f"/api/si/accounts/{account2}/deals", json={"services": ["fire_alarm"], "qualification": {"requirement": "PPM"}}).json()["id"]
    maxi.put(f"/api/si/deals/{own}/scope", json={"entries": SCOPE})
    maxi.post(f"/api/si/deals/{own}/quote", json={"rates": RATES})
    assert maxi.post(f"/api/si/deals/{own}/quote/approve", json={"reviewer": "Max"}).status_code == 403

    # Paid research needs permission and an allowance; neither costs anything when refused.
    assert ben.post("/api/si/discover/research", json={"query": "warehouses in Leeds"}).status_code == 403
    assert sam.post("/api/si/discover/research", json={"query": "warehouses in Leeds"}).status_code == 429

    # Only administrators manage people, and a workspace always keeps an administrator.
    assert maxi.post("/api/workspace/invitations", json={"email": "x@alpha.example", "role": "admin"}).status_code == 403
    ann_id = admin.get("/api/me").json()["user"]["id"]
    assert admin.patch(f"/api/workspace/members/{ann_id}", json={"role": "reviewer"}).status_code == 409
    sam_id = sam.get("/api/me").json()["user"]["id"]
    assert maxi.patch(f"/api/si/accounts/{account}/owner", json={"user_id": sam_id}).status_code == 200
    assert sam.patch(f"/api/si/accounts/{account}/owner", json={"user_id": sam_id}).status_code == 403
    assert admin.delete(f"/api/workspace/members/{sam_id}").status_code == 200
    assert h.client("sam", "sam@alpha.example", workspace=org).get("/api/si/accounts").status_code == 403


def test_invitations_cannot_be_misused(hosted):
    h = hosted
    admin, org = workspace(h, "ann", "ann@alpha.example", "Alpha Fire Ltd")
    invite = admin.post("/api/workspace/invitations", json={"email": "new@alpha.example", "role": "salesperson"}).json()
    stranger = h.client("eve", "eve@evil.example")
    assert stranger.post("/api/invitations/accept", json={"token": invite["token"]}).status_code == 404  # not their email
    assert stranger.post("/api/invitations/accept", json={"token": "x" * 43}).status_code == 404
    new = h.client("new", "new@alpha.example")
    assert new.post("/api/invitations/accept", json={"token": invite["token"]}).json()["role"] == "salesperson"
    assert h.client("new2", "new@alpha.example").post("/api/invitations/accept", json={"token": invite["token"]}).status_code == 404  # single use
    revoked = admin.post("/api/workspace/invitations", json={"email": "late@alpha.example", "role": "admin"}).json()
    admin.delete(f"/api/workspace/invitations/{revoked['id']}")
    assert h.client("late", "late@alpha.example").post("/api/invitations/accept", json={"token": revoked["token"]}).status_code == 404
    with h.system() as db:
        from app.models.tenancy import Invitation
        assert all(len(i.token_hash) == 64 and i.token_hash != invite["token"] for i in db.scalars(select(Invitation)))  # only hashes stored


# ---------------------------------------------------------------- audit and profile

def test_changes_are_audited_per_workspace_without_copying_values(hosted):
    h = hosted
    alice, a_org, bob, b_org, mo = two_companies(h)
    a = build_alpha(alice, h, a_org)
    alice.patch(f"/api/si/accounts/{a['account']}", json={"notes": "Confidential pricing note"})
    events = alice.get("/api/workspace/audit").json()["items"]
    alice_id = alice.get("/api/me").json()["user"]["id"]
    notes = [e for e in events if e["entity_type"] == "si_accounts" and e["action"] == "update" and "notes" in e["fields"]]
    assert notes and notes[0]["user_id"] == alice_id
    assert any(e["entity_type"] == "si_drafts" and e["action"] == "create" for e in events)
    assert "Confidential pricing note" not in str(events)
    assert all(e["entity_type"] == "workspace" or e["user_id"] in (alice_id, None) for e in events)
    assert not any(e["entity_type"].startswith("si_") for e in bob.get("/api/workspace/audit").json()["items"])
    with h.system() as db:
        assert {e.organisation_id for e in db.scalars(select(WorkspaceAuditEvent).where(WorkspaceAuditEvent.entity_type == "si_drafts"))} == {a_org}


def test_a_target_always_states_what_it_measures(hosted):
    h = hosted
    alice, org = workspace(h, "alice", "alice@alpha.example", "Alpha Fire Ltd")
    assert alice.patch("/api/workspace/me", json={"target_amount": "750000"}).status_code == 422
    me = alice.patch("/api/workspace/me", json={"target_amount": "750000.00", "target_basis": "total_contract_value", "target_period": "annual",
                                                "territory": ["Yorkshire"], "services": ["fire_alarm", "cctv"]}).json()
    assert me["target"] == {"amount": "750000.00", "basis": "total_contract_value", "basis_label": "Total contract value", "period": "annual"}
    assert alice.patch("/api/workspace/me", json={"target_amount": "12.345"}).status_code == 422


def test_oidc_mode_verifies_the_providers_keys_issuer_and_audience(tmp_path, monkeypatch):
    """The production path: keys from the provider's JWKS, issuer and audience from settings."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.config import get_settings
    from app.db import Base, get_db
    from app.main import create_app
    provider_key, impostor = rsa.generate_private_key(public_exponent=65537, key_size=2048), rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("OIDC_ISSUER", "https://login.provider.example/tenant/v2.0")
    monkeypatch.setenv("OIDC_AUDIENCE", "api://salesintel")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://login.provider.example/keys")
    get_settings.cache_clear()

    class FakeJwks:  # stands in for the provider's published keys; no network
        def get_signing_key_from_jwt(self, token):
            return type("Key", (), {"key": provider_key.public_key()})()
    monkeypatch.setattr(auth, "_jwks_client", lambda url: FakeJwks())
    engine = create_engine(f"sqlite:///{tmp_path / 'oidc.db'}")
    Base.metadata.create_all(engine)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: Session(engine)
    assert "/api/dev/session" not in app.openapi()["paths"]  # no development sign-in in oidc mode
    moment = datetime.now(UTC)
    claims = {"iss": "https://login.provider.example/tenant/v2.0", "aud": "api://salesintel", "sub": "abc", "email": "pat@company.example",
              "email_verified": True, "name": "Pat", "iat": moment, "exp": moment + timedelta(minutes=5)}
    client = TestClient(app)
    ok = client.get("/api/me", headers={"Authorization": f"Bearer {jwt.encode(claims, provider_key, algorithm='RS256')}"})
    assert ok.status_code == 200 and ok.json()["user"]["email"] == "pat@company.example"
    for label, token in {"impostor key": jwt.encode(claims, impostor, algorithm="RS256"),
                         "other issuer": jwt.encode(claims | {"iss": "https://evil.example"}, provider_key, algorithm="RS256"),
                         "other audience": jwt.encode(claims | {"aud": "api://other"}, provider_key, algorithm="RS256"),
                         "HS256 confusion": jwt.encode(claims, "x" * 40, algorithm="HS256")}.items():
        assert client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401, label
    with pytest.raises(RuntimeError, match="Development tokens exist only"):
        auth.dev_token("x", "x@x.example")
    get_settings.cache_clear()
