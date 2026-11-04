import json
from types import SimpleNamespace

from app.config import Settings
from app.intelligence import public_contacts
from app.schemas.public_contacts import PublicContactRequest


def _item(**updates):
    item = {"name": "Alex Smith", "role": "Estates manager", "kind": "email",
            "value": "alex@example.org", "source_url": "https://example.org/team",
            "source_title": "Team", "source_date": "", 
            "evidence_quote": "Alex Smith, Estates manager: alex@example.org"}
    item.update(updates)
    return item


def _research(monkeypatch, items, *, sources=None, performed=True, request=None):
    action = SimpleNamespace(type="search" if performed else "open_page", queries=["example"],
                             sources=[SimpleNamespace(url=x) for x in (sources or ["https://example.org/team"])])
    response = SimpleNamespace(output_text=json.dumps({"contacts": items}),
                               output=[SimpleNamespace(type="web_search_call", action=action)])
    monkeypatch.setattr(public_contacts, "get_research_client", lambda settings: object())
    monkeypatch.setattr(public_contacts, "_call", lambda *args, **kwargs: response)
    return public_contacts.research_public_contacts(
        request or PublicContactRequest(organisation="Example"), Settings(openai_api_key=None))


def test_accepts_public_contact_with_search_provenance_and_literal_quote(monkeypatch):
    result = _research(monkeypatch, [_item()])
    assert result.contacts[0].value == "alex@example.org"
    assert "not independently verified" in result.limitations[0]


def test_rejects_invented_source_and_unsourced_value_and_wrong_name(monkeypatch):
    result = _research(monkeypatch, [
        _item(source_url="https://example.org/invented"),
        _item(value="guessed@example.org"),
        _item(name="Someone Else"),
    ])
    assert result.contacts == []
    assert "3 candidate" in result.limitations[1]


def test_rejects_results_without_actual_web_search(monkeypatch):
    result = _research(monkeypatch, [_item()], performed=False)
    assert result.contacts == []


def test_does_not_attach_an_unsourced_current_role_to_an_old_contact(monkeypatch):
    result = _research(monkeypatch, [_item(role="Director", evidence_quote="Alex Smith, Estates manager: alex@example.org")])
    assert result.contacts[0].role == ""


def test_requested_name_cannot_be_swapped_and_general_route_is_allowed(monkeypatch):
    request = PublicContactRequest(organisation="Example", contact_name="Jane Doe")
    result = _research(monkeypatch, [_item(), _item(name="", role="", kind="phone", value="020 1234 5678",
        evidence_quote="Main switchboard: 020 1234 5678")], request=request)
    assert len(result.contacts) == 1
    assert result.contacts[0].name == ""
    assert result.contacts[0].kind == "phone"
