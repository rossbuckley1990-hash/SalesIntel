"""Test-wide settings. In-process tests run research jobs explicitly (jobs.drain), so the API's inline worker
thread must not start and poll a database it does not own. Tests that need it (a real API process) set it themselves."""
import os

os.environ.setdefault("RESEARCH_WORKER", "off")
