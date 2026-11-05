"""Does the Shadow Radar find organisations that later buy fire or security work, compared with simpler methods?

Three arms judged on the same decision dates, each seeing only what was published by that date:
- shadow: organisations with an indicated or corroborated Shadow Radar hypothesis;
- renewal: organisations with a known fire or security contract ending within the horizon;
- keyword: organisations whose recent published text merely mentions building or fire words.

Outcome: the organisation publishes a fire or security procurement (a core, bundled or framework
contract, or an early market notice) after the decision date and within the horizon, having not
done so in the 90 days before it. Organisations already buying are not "hidden" opportunities.

This is an entity-level test: a hit means the organisation bought something relevant, not that
the radar's specific hypothesis was right. It says nothing about win rates.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import sqrt
import re
from statistics import median

from app.intelligence import shadow_radar
from app.intelligence.signal_inference import council_key

KEYWORDS = re.compile(r'\b(?:new build|construction|refurbish\w*|fire|security|alarm|cctv)\b', re.I)
RECENT_ACTIVE_DAYS = 90


def _wilson(hits: int, n: int) -> list[float] | None:
    if not n:
        return None
    p, z = hits / n, 1.96
    centre, spread = (p + z * z / (2 * n)) / (1 + z * z / n), z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - spread), 3), round(min(1.0, centre + spread), 3)]


def outcomes(contracts: list[dict], observations: list[dict]) -> dict[str, list[date]]:
    """Dates on which each organisation published fire or security procurement."""
    out: dict[str, list[date]] = {}
    for c in contracts:
        if c['fit'] in ('core', 'bundled', 'framework') and c.get('published'):
            out.setdefault(council_key(c['buyer']), []).append(c['published'])
    for o in observations:
        if o['signal_type'] == 'market_engagement' and o.get('buyer'):
            out.setdefault(council_key(o['buyer']), []).append(o['available_on'])
    return out


def arms(observations: list[dict], contracts: list[dict], as_of: date, horizon: int) -> dict[str, dict[str, date]]:
    """Each arm's flagged organisations at `as_of`, with the date of the evidence that flagged them. No later record is read."""
    visible = [o for o in observations if o['available_on'] <= as_of and o['signal_type'] != 'market_engagement']  # outcomes are never inputs
    shadow = {}
    for a in shadow_radar.evaluate(visible, as_of):
        if a['state'] in ('indicated', 'corroborated'):
            shadow[a['entity_key']] = min(shadow.get(a['entity_key'], as_of), date.fromisoformat(a['first_published_on']))
    renewal = {}
    for c in contracts:
        if c['fit'] in ('core', 'bundled', 'framework') and c.get('published') and c['published'] <= as_of and c.get('end') and as_of < c['end'] <= as_of + timedelta(days=horizon):
            renewal[council_key(c['buyer'])] = c['published']
    keyword = {}
    for o in visible:
        if o['available_on'] >= as_of - timedelta(days=365) and o.get('buyer') and KEYWORDS.search(o['statement']):
            key = council_key(o['buyer'])
            keyword[key] = min(keyword.get(key, as_of), o['available_on'])
    return {'shadow': shadow, 'renewal': renewal, 'keyword': keyword}


def evaluate(observations: list[dict], contracts: list[dict], decision_dates: list[date], horizon: int, data_end: date) -> dict:
    events = outcomes(contracts, observations)
    report = {'horizon_days': horizon, 'decision_dates': [str(d) for d in decision_dates], 'data_end': str(data_end), 'arms': {}, 'by_sensor': {}}
    totals = {name: {'flagged': 0, 'hits': 0, 'lead_days': [], 'outcomes': 0} for name in ('shadow', 'renewal', 'keyword')}
    sensor_totals: dict[str, dict] = {}
    universe_outcomes = 0
    for d in decision_dates:
        end = min(d + timedelta(days=horizon), data_end)
        fresh = {k for k, days in events.items() if any(d < x <= end for x in days) and not any(d - timedelta(days=RECENT_ACTIVE_DAYS) <= x <= d for x in days)}
        universe_outcomes += len(fresh)
        flagged = arms(observations, contracts, d, horizon)
        for name, entities in flagged.items():
            active = {k for k, days in events.items() if any(d - timedelta(days=RECENT_ACTIVE_DAYS) <= x <= d for x in days)}
            candidates = {k: v for k, v in entities.items() if k not in active}  # already buying: not a hidden opportunity
            hits = [k for k in candidates if k in fresh]
            t = totals[name]
            t['flagged'] += len(candidates)
            t['hits'] += len(hits)
            t['outcomes'] += len(fresh)
            t['lead_days'] += [min(x for x in events[k] if d < x <= end).toordinal() - candidates[k].toordinal() for k in hits]
        for a in shadow_radar.evaluate([o for o in observations if o['available_on'] <= d and o['signal_type'] != 'market_engagement'], d):
            if a['state'] not in ('indicated', 'corroborated'):
                continue
            s = sensor_totals.setdefault(a['sensor'], {'flagged': 0, 'hits': 0, 'corroborated': 0})
            s['flagged'] += 1
            s['hits'] += int(a['entity_key'] in fresh)
            s['corroborated'] += int(a['independent_sources'] >= 2)
    for name, t in totals.items():
        report['arms'][name] = {'flagged': t['flagged'], 'hits': t['hits'], 'false_positives': t['flagged'] - t['hits'],
                                'precision': round(t['hits'] / t['flagged'], 3) if t['flagged'] else None, 'precision_95': _wilson(t['hits'], t['flagged']),
                                'coverage_of_outcomes': round(t['hits'] / t['outcomes'], 3) if t['outcomes'] else None,
                                'median_days_from_first_evidence_to_outcome': median(t['lead_days']) if t['lead_days'] else None}
    report['by_sensor'] = {k: {**v, 'precision': round(v['hits'] / v['flagged'], 3) if v['flagged'] else None, 'precision_95': _wilson(v['hits'], v['flagged'])}
                           for k, v in sensor_totals.items()}
    report['outcomes_in_window'] = universe_outcomes
    return report
