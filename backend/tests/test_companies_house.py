import base64
import httpx
import pytest
from app.ingestion.companies_house import CompaniesHouseError, fetch_company_profile


def test_profile_is_exact_and_excludes_personal_fields():
    def handler(request):
        assert request.url.host == 'api.company-information.service.gov.uk'
        assert request.url.path == '/company/01234567'
        assert request.headers['authorization'] == 'Basic ' + base64.b64encode(b'secret:').decode()
        return httpx.Response(200, json={'company_number':'01234567','company_name':'Example Ltd', 'company_status':'active', 'sic_codes':['80200'], 'officers':['private'], 'unknown':'ignored'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        record = fetch_company_profile('01234567', api_key='secret', client=client)
    assert record['raw'] == {'company_number':'01234567', 'company_name':'Example Ltd', 'company_status':'active', 'sic_codes':['80200'], 'accounts_overdue':False, 'confirmation_overdue':False, 'has_insolvency_history':False}
    assert record['source_url'].endswith('/01234567')


def test_unavailable_rate_limited_redirect_and_mismatch_are_safe():
    with pytest.raises(CompaniesHouseError, match='not configured'):
        fetch_company_profile('01234567', api_key=None)
    with pytest.raises(ValueError):
        fetch_company_profile('../secret', api_key='secret')
    for status in (429, 302, 401):
        with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, headers={'location':'https://attacker.example'}))) as client:
            with pytest.raises(CompaniesHouseError) as exc:
                fetch_company_profile('01234567', api_key='secret', client=client)
            assert 'secret' not in str(exc.value)
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'company_number':'87654321','company_name':'Wrong'}))) as client:
        with pytest.raises(CompaniesHouseError, match='mismatched'):
            fetch_company_profile('01234567', api_key='secret', client=client)


def test_psc_fetch_keeps_only_identifiable_uk_corporate_controllers():
    from app.ingestion.companies_house import fetch_corporate_control_snapshot
    def handler(request):
        if request.url.path.endswith('/persons-with-significant-control'):
            return httpx.Response(200,json={'total_results':3,'items':[
                {'kind':'corporate-entity-person-with-significant-control','name':'UK Company','identification':{'registration_number':'12345678','place_registered':'Companies House'},'notified_on':'2020-01-01','natures_of_control':['ownership-of-shares-75-to-100-percent']},
                {'kind':'individual-person-with-significant-control','name':'Private Person','date_of_birth':{'year':1980}},
                {'kind':'corporate-entity-person-with-significant-control','name':'Foreign','identification':{'registration_number':'87654321','place_registered':'Foreign Registry'},'natures_of_control':['control']} ]})
        return httpx.Response(200,json={'company_number':'01234567','company_name':'Subject Limited'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=fetch_corporate_control_snapshot('01234567',api_key='secret',client=client)
    assert result['company_name']=='Subject Limited'
    assert [item['company_name'] for item in result['controllers']]==['UK Company']
    assert 'Private Person' not in str(result)


def test_psc_incomplete_pagination_does_not_claim_complete():
    from app.ingestion.companies_house import fetch_corporate_control_snapshot
    def handler(request):
        if request.url.path.endswith('/persons-with-significant-control'):
            return httpx.Response(200,json={'total_results':100,'items':[]})
        return httpx.Response(200,json={'company_number':'01234567','company_name':'Subject Limited'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CompaniesHouseError,match='pagination'):
            fetch_corporate_control_snapshot('01234567',api_key='secret',client=client)
