"""Test-wide settings. In-process tests run research jobs explicitly (jobs.drain), so the API's inline worker
thread must not start and poll a database it does not own. Tests that need it (a real API process) set it themselves."""
import os

os.environ.setdefault("RESEARCH_WORKER", "off")

import httpx
import pytest


@pytest.fixture(autouse=True)
def _no_site_reading_over_the_network(monkeypatch):
    """The website reader never reaches the network in tests: every site answers 404 unless a test gives it pages."""
    from app.services import site_reader
    monkeypatch.setattr(site_reader, "TRANSPORT", httpx.MockTransport(lambda request: httpx.Response(404)))
