"""Local-only request guard.

SalesIntel has no sign-in, so it must only ever answer this machine. Three checks:
- the Host header must name a local host, which defeats DNS rebinding (an attacker's
  domain pointing at 127.0.0.1 would otherwise be able to read every record);
- the client must be on the loopback interface, unless remote access is explicitly
  enabled, which is only acceptable once authentication exists;
- a state-changing request that carries an Origin header must come from an allowed
  origin. Browsers send "simple" cross-site POSTs without a CORS preflight, so CORS
  alone does not stop another website from approving drafts or completing tasks.
"""
from __future__ import annotations

import ipaddress

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
TEST_CLIENT = "testclient"  # Starlette's TestClient


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host == TEST_CLIENT:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


class LocalOnlyGuard:
    def __init__(self, app: ASGIApp, *, allowed_hosts: set[str], allowed_origins: set[str], allow_remote_clients: bool = False) -> None:
        self.app = app
        self.allowed_hosts = {h.lower() for h in allowed_hosts}
        self.allowed_origins = {o.rstrip("/").lower() for o in allowed_origins}
        self.allow_remote_clients = allow_remote_clients

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        host = headers.get("host", "").lower()
        hostname = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
        if hostname not in self.allowed_hosts:
            await JSONResponse({"detail": "Host not allowed. SalesIntel only answers this machine."}, status_code=400)(scope, receive, send)
            return
        client = (scope.get("client") or (None, None))[0]
        if not self.allow_remote_clients and not _is_loopback(client):
            await JSONResponse({"detail": "Remote access is disabled. SalesIntel has no sign-in yet."}, status_code=403)(scope, receive, send)
            return
        origin = headers.get("origin")
        if scope.get("method", "GET").upper() not in SAFE_METHODS and origin and origin.rstrip("/").lower() not in self.allowed_origins:
            await JSONResponse({"detail": "Cross-site request refused."}, status_code=403)(scope, receive, send)
            return
        await self.app(scope, receive, send)
