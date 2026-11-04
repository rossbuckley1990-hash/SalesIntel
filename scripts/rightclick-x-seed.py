"""Seed one approved public OpenAPI contract in the isolated local runtime."""
import json
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

token = Path(sys.argv[1]).read_text().strip()
body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
    "name": "context_learn", "arguments": {"source": "https://www.planning.data.gov.uk/openapi.json"}}}).encode()
request = Request("http://127.0.0.1:8787/mcp", data=body, headers={
    "Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json",
    "MCP-Protocol-Version": "2025-06-18"}, method="POST")
for attempt in range(20):
    try:
        with urlopen(request, timeout=30) as response:
            data = json.load(response)
        if data.get("error") or data.get("result", {}).get("isError"):
            raise RuntimeError("The approved contract could not be learned.")
        content = data.get("result", {}).get("structuredContent", {})
        learned = [entry for group in content.get("results", []) for entry in group.get("learned", [])]
        if not any(entry.get("provider") == "openapi:planning-data-gov-uk-api" for entry in learned):
            raise RuntimeError("The approved contract was not returned.")
        print("Approved public source ready.")
        break
    except (OSError, URLError):
        if attempt == 19:
            print("Source discovery is unavailable; MiSi can continue without it.", file=sys.stderr)
            break
        time.sleep(0.25)
    except (ValueError, RuntimeError):
        print("The approved public source could not load; MiSi can continue without it.", file=sys.stderr)
        break
