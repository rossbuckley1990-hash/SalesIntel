from app.ingestion.market_find_tender import classify_release, relevant_release


def case(title, description='', cpv=None):
    tender = {'title': title, 'description': description}
    if cpv:
        tender['classification'] = {'scheme': 'CPV', 'id': cpv}
    return {'tender': tender}


def test_sector_specific_scope_and_installation_are_distinct_from_maintenance():
    for title in ('Fire alarm maintenance across schools', 'Replacement of Roland Levinsky Fire Alarm',
                  'CCTV and access control maintenance', 'Fire door inspection'):
        assert classify_release(case(title))['level'] == 'relevant'
    # Relevance does not imply a maintenance contract; lifecycle handles this separately.


def test_generic_works_are_review_only_when_fire_or_security_is_collateral():
    for title, description in [
        ('General building works', 'Electrical upgrades with fire alarm changes.'),
        ('Video wall', 'A new CCTV screen wall for the control room.'),
        ('Minor works and maintenance', 'Some lots include fire doors and general construction.'),
        ('Electrical works', 'Lighting replacement and fire alarm installation.'),
    ]:
        record = case(title, description)
        assert classify_release(record)['level'] == 'ambiguous'
        assert relevant_release(record)


def test_fire_brigade_vehicles_and_unrelated_electrical_work_not_sector_contracts():
    for title in ('Fire engine appliance purchase', 'New fire station construction', 'Electrical switchboard repair', 'Video wall procurement'):
        assert classify_release(case(title))['level'] == 'excluded'


def test_specific_cpv_on_its_own_requires_scope_review():
    assert classify_release(case('Various site works', cpv='31625200'))['level'] == 'ambiguous'
    assert classify_release(case('Fire alarm service', cpv='31625200'))['cpv'] == ['31625200']
