from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.main import create_app
from app.security import LocalOnlyGuard


def guarded(remote=False):
    async def ok(request):
        return PlainTextResponse("ok")
    app = Starlette(routes=[Route("/x", ok, methods=["GET", "POST"])])
    return LocalOnlyGuard(app, allowed_hosts={"127.0.0.1", "localhost", "testserver"}, allowed_origins={"http://127.0.0.1:3000"}, allow_remote_clients=remote)


def test_dns_rebinding_host_is_refused():
    c = TestClient(guarded())
    assert c.get("/x").status_code == 200
    assert c.get("/x", headers={"host": "attacker.example"}).status_code == 400
    assert c.get("/x", headers={"host": "127.0.0.1:8001"}).status_code == 200


def test_cross_site_writes_are_refused_but_local_ones_work():
    c = TestClient(guarded())
    assert c.post("/x", headers={"origin": "https://evil.example"}).status_code == 403
    assert c.post("/x", headers={"origin": "http://127.0.0.1:3000"}).status_code == 200
    assert c.post("/x").status_code == 200  # local tools send no Origin
    assert c.get("/x", headers={"origin": "https://evil.example"}).status_code == 200  # reads are protected by CORS and the Host check


def test_remote_clients_are_refused_unless_explicitly_allowed():
    remote = TestClient(guarded(), client=("192.168.1.20", 5000))
    assert remote.get("/x").status_code == 403
    assert TestClient(guarded(remote=True), client=("192.168.1.20", 5000)).get("/x").status_code == 200
    assert TestClient(guarded(), client=("127.0.0.1", 5000)).get("/x").status_code == 200


def test_the_real_app_refuses_a_cross_site_draft_approval():
    c = TestClient(create_app())
    assert c.post("/api/si/drafts/1/approve", headers={"origin": "https://evil.example"}).status_code == 403
    assert c.get("/api/si/today", headers={"host": "rebind.attacker.example"}).status_code == 400
