from app.intelligence.contract_lifecycle import contract_lifecycle


def test_replacement_is_not_maintenance_and_status_not_asserted_active():
    raw={'tender':{'title':'Replacement of Roland Levinsky Fire Alarm'}, 'awards':[{'id':'1','status':'active'}],
         'contracts':[{'id':'1','awardID':'1','status':'active','period':{'startDate':'2026-08-01','endDate':'2027-07-31'}}]}
    result=contract_lifecycle(raw,'1')
    assert result['scope']=='installation_or_replacement'
    assert result['status']=='contract_details_published'
    assert result['published_contract_status']=='active'
    assert result['end_date']=='2027-07-31'
    assert result['classification']=='unknown'
    assert 'extensions' in ' '.join(result['limitations'])


def test_missing_or_ambiguous_award_and_contract_does_not_invent_dates():
    raw={'tender':{'title':'Fire alarm maintenance'},'awards':[{'id':'1'}],
         'contracts':[{'id':'a','awardID':'1','period':{'endDate':'2027-01-01'}}, {'id':'b','awardID':'1'}]}
    result=contract_lifecycle(raw,'1')
    assert result['scope']=='maintenance_mentioned' and result['end_date'] is None
    assert result['status']=='award_published'
    assert contract_lifecycle(raw,'9')['status']=='unknown'


def test_framework_first_stage_and_second_stage_are_distinct():
    base={'tender': {'techniques': {'hasFrameworkAgreement': True}}, 'awards':[{'id':'a','status':'active'}]}
    first=contract_lifecycle(base,'a')
    assert first['classification']=='framework_first_stage'
    assert first['status']=='award_published' and first['contract_id'] is None
    second=contract_lifecycle({'tender':{},'awards':[{'id':'a'}], 'relatedProcesses':[{'relationship':['framework'],'identifier':'ocds-example'}],
                               'contracts':[{'id':'c','awardID':'a'}]},'a')
    assert second['classification']=='framework_second_stage' and second['status']=='contract_details_published'
    conflicting=contract_lifecycle({**base,'relatedProcesses':[{'relationship':['framework']}]},'a')
    assert conflicting['classification']=='conflicting_framework_flags'
