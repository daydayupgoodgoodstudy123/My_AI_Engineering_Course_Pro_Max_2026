"""Risk ranking and the next unresolved assumption."""
from __future__ import annotations
from .model import Assumption, risk_score

def evidence_status(item: Assumption) -> str:
    """Supporting evidence means supported, rejecting evidence means rejected;
    absent or inconclusive evidence leaves the assumption open.
    """
    if item.evidence and item.evidence.verdict in ('supports','rejects'):
        return 'supported'
    return 'open'

def next_experiment(items: list[Assumption]) -> str | None:
    """Select only open assumptions. Highest score wins, then smallest id.
    Rejected assumptions require reframing or stopping, not another build premise.
    """
    opened = [item for item in items if evidence_status(item) != 'supported']
    return max(opened, key=risk_score).id if opened else None

def ranked_rows(items: list[Assumption]) -> list[dict]:
    """Return score-descending/id-ascending rows, with consecutive one-based ranks.
    IDs are unique. No caller objects are changed. Ranking applies to every status.
    """
    keys = {item.id: (-risk_score(item), item.id) for item in items}
    rows = []
    for item in items:
        rank = 1 + sum(other < keys[item.id] for other in keys.values())
        rows.append({'id':item.id,'score':-keys[item.id][0],'status':evidence_status(item),'rank':rank})
    return sorted(rows, key=lambda row: row['rank'])

def map_decision(items: list[Assumption]) -> dict:
    """Present the map and its evidence decision: rejected claims reframe-or-stop,
    supported claims bounded-build, and open claims experiment. An empty map is valid.
    """
    actions = {'supported':'bounded-build','rejected':'reframe-or-stop','open':'experiment'}
    rows = ranked_rows(items)
    return {'rows':rows,'actions':{row['id']:actions[row['status']] for row in rows},'next':next_experiment(items)}
