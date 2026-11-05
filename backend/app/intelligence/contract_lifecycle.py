"""Conservative extraction from one published OCDS release.

Published contract status is the issuer's field, not independent evidence of
current delivery. Ambiguous relationships and dates remain unknown.
"""
from __future__ import annotations
import re

from app.intelligence.contract_terms import BASIS_LABELS, award_term, framework_stage

_MAINTENANCE = re.compile(r'\b(maintenan\w*|servic(?:e|es|ing)|inspect(?:ion|ions|ing)?|planned preventative|preventive maintenance)\b', re.I)
_INSTALL = re.compile(r'\b(install\w*|replace\w*|supply\s*(?:and|&)\s*install|upgrade\w*)\b', re.I)


def contract_lifecycle(raw: dict, award_id: str | None) -> dict:
    result = {'classification': 'unknown', 'scope': 'unknown', 'status': 'unknown',
              'published_contract_status': None, 'start_date': None, 'end_date': None,
              'estimated_end_date': None, 'end_basis': 'none', 'latest_end_date': None, 'latest_end_basis': None,
              'extension_note': None, 'contract_id': None, 'evidence_paths': [], 'limitations': []}
    if not isinstance(raw, dict) or not award_id:
        result['limitations'].append('No unambiguous award identifier is available.')
        return result
    awards = raw.get('awards') if isinstance(raw.get('awards'), list) else []
    matches = [(i, a) for i, a in enumerate(awards) if isinstance(a, dict) and str(a.get('id')) == str(award_id)]
    if len(matches) != 1:
        result['limitations'].append('The award identifier does not identify exactly one award in this source.')
        return result
    index, award = matches[0]
    result['status'] = 'award_published'
    result['evidence_paths'].append(f'awards[{index}]')
    tender = raw.get('tender') if isinstance(raw.get('tender'), dict) else {}
    stage, stage_path = framework_stage(raw)
    if stage == 'conflicting_framework_flags':
        result['classification'] = stage
        result['limitations'].append('Source has conflicting first- and second-stage framework markers; review source.')
    elif stage:
        result['classification'] = stage
        result['evidence_paths'].append(stage_path)
    # Explicit source scope text is a discovery hint, not independently proven capability.
    scope_parts = [tender.get('title'), tender.get('description'), award.get('title'), award.get('description')]
    for item in award.get('items', []) if isinstance(award.get('items'), list) else []:
        if isinstance(item, dict):
            classification = item.get('classification') if isinstance(item.get('classification'), dict) else {}
            scope_parts.extend([item.get('description'), classification.get('description')])
            for classification in item.get('additionalClassifications', []) if isinstance(item.get('additionalClassifications'), list) else []:
                if isinstance(classification, dict): scope_parts.append(classification.get('description'))
    text = ' '.join(x for x in scope_parts if isinstance(x, str))
    maintenance, install = bool(_MAINTENANCE.search(text)), bool(_INSTALL.search(text))
    result['scope'] = 'mixed_or_ambiguous' if maintenance and install else 'maintenance_mentioned' if maintenance else 'installation_or_replacement' if install else 'unknown'
    result['limitations'].append('Scope is determined from published wording, not proof of actual service delivery.')
    contracts = raw.get('contracts') if isinstance(raw.get('contracts'), list) else []
    matched = [(i,c) for i,c in enumerate(contracts) if isinstance(c, dict) and str(c.get('awardID', '')) == str(award_id)]
    if len(matched) > 1:
        result['limitations'].append('Multiple contract records match this award; no single term is selected.')
        return result
    contract = None
    if matched:
        ci, contract = matched[0]
        result['status'] = 'contract_details_published'
        result['contract_id'] = str(contract.get('id')) if contract.get('id') is not None else None
        result['published_contract_status'] = contract.get('status') if isinstance(contract.get('status'), str) else None
        result['evidence_paths'].append(f'contracts[{ci}]')
    else:
        result['limitations'].append('No matching contract details have been found in this release.')
    term = award_term(raw, award, contract)
    if term['end_basis'] == 'award_contract_period':
        result['evidence_paths'].append(f'awards[{index}].contractPeriod')
        result['status'] = 'contract_details_published' if contract else 'award_period_published'
    result.update(start_date=term['start'] or None, end_date=term['end'] or None, estimated_end_date=term['estimated_end'] or None,
                  end_basis=term['end_basis'], latest_end_date=term['latest_end'] or None, latest_end_basis=term['latest_end_basis'] or None,
                  extension_note=term['extension_note'] or None)
    if term['end_estimated']:
        result['limitations'].append(f"The end date is an estimate from the {BASIS_LABELS[term['end_basis']]}, not a published end date.")
    if term['conflict']:
        result['limitations'].append('The source gives conflicting contract dates; check the original notice.')
    # A contract's period and OCDS active status do not prove continued delivery,
    # extensions, or that all related notices are present.
    result['limitations'].append('Published status and dates do not independently establish current delivery or extensions.')
    result['limitations'].append('Framework stages are based only on explicit OCDS fields; an appointment is not a call-off or supplier revenue.')
    return result
