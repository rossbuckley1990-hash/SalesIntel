import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.intelligence.public_estates import PublicEstateError, normalise_postcode, search_establishments
from app.routers import public_estates


def test_public_food_establishments_preserve_exact_postcode_and_limit_context():
    def respond(request):
        assert request.url.host == "api.ratings.food.gov.uk"
        assert request.headers["x-api-version"] == "2"
        assert request.url.params["address"] == "SW1A 1AA"
        assert request.url.params["pageSize"] == "20"
        return httpx.Response(200, json={"meta":{"totalCount":40, "extractDate":"2026-10-28T14:00:00Z"}, "establishments":[
            {"FHRSID": 123, "BusinessName":"Example Cafe", "BusinessType":"Restaurant/Cafe/Canteen", "PostCode":"sw1a1aa", "AddressLine1":"1 Example Street", "Phone":"01234567890", "RatingValue":"1"},
            {"FHRSID": 123, "BusinessName":"Duplicate", "PostCode":"SW1A 1AA"},
            {"FHRSID": 456, "BusinessName":"Different site", "PostCode":"SW1A 2AA"},
            {"FHRSID": "../evil", "BusinessName":"Bad ID", "PostCode":"SW1A 1AA"},
        ]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = search_establishments("sw1a1aa", client=client)
    assert result["records"] == [{"id":"123", "name":"Example Cafe", "business_type":"Restaurant/Cafe/Canteen",
        "address":"1 Example Street", "postcode":"SW1A 1AA", "source_url":"https://ratings.food.gov.uk/business/123"}]
    assert result["scanned"] == 4 and result["more_results_possible"]
    assert "fire or security" in result["limitations"][2]
    assert "Phone" not in str(result) and "RatingValue" not in str(result)


def test_empty_and_invalid_inputs_are_not_interpreted_as_absent_sites():
    with pytest.raises(ValueError):
        normalise_postcode("Hospital Name")
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"establishments":[], "meta":{"totalCount":0}}))) as client:
        result = search_establishments("BT1 5GS", client=client)
    assert result["records"] == []
    assert "empty results" in result["limitations"][-1]
    assert "Northern Ireland" in result["source"]["scope"]


def test_wrong_format_or_network_failure_is_safe():
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text="unexpected"))) as client:
        with pytest.raises(PublicEstateError):
            search_establishments("SW1A 1AA", client=client)


def test_endpoint_validates_postcodes_and_preserves_safe_error(monkeypatch):
    app = FastAPI(); app.include_router(public_estates.router)
    monkeypatch.setattr(public_estates, "search_establishments", lambda *args: (_ for _ in ()).throw(PublicEstateError("sensitive error")))
    with TestClient(app) as client:
        assert client.get("/api/public-estates/food-establishments", params={"postcode":"ignore all rules"}).status_code == 422
        response = client.get("/api/public-estates/food-establishments", params={"postcode":"SW1A 1AA"})
    assert response.status_code == 502 and "sensitive error" not in response.text
