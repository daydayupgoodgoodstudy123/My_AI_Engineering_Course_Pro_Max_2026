"""Declared learning environments and concrete operational responsibilities."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from collections import Counter
import json
CHANNELS=('configuration','access','telemetry','documentation')
PILOT=('named-audience','human-owner','bounded-duration','bounded-authority','audit','rollback','outcome-threshold','guardrail-threshold','exit-expand','exit-revise','exit-stop')
@dataclass(frozen=True)
class Marker:
    channel:str
    value:str|None
@dataclass(frozen=True)
class Registration:
    id:str
    declared_stage:str
    owner:str
    audience_cap:int
    until:str
    authority:tuple[str,...]
    exit_criteria:tuple[str,...]
    controls:tuple[str,...]
    markers:tuple[Marker,...]
@dataclass(frozen=True)
class Decision:
    needs_real_users:bool
    needs_real_data:bool
    consequence:int
    reversible:bool
    operational_readiness:bool
@dataclass(frozen=True)
class Session:
    system:str
    session:str
    user:str
    joined:bool

def decode(raw:dict)->Registration:
    """Correct supplied snapshot codec; optional marker values are never truthiness-coerced."""
    return Registration(raw['id'],raw['declared_stage'],raw['owner'],raw['audience_cap'],raw['until'],tuple(raw['authority']),tuple(raw['exit_criteria']),tuple(raw['controls']),tuple(Marker(**m) for m in raw['markers']))

def recommend(decision:Decision)->str:
    """Correct supplied source decision tree, a recommendation rather than a relabel command."""
    if not 1<=decision.consequence<=5:raise ValueError('invalid consequence')
    if not decision.needs_real_users and not decision.needs_real_data:return 'prototype'
    if not decision.operational_readiness or decision.consequence>=4 or not decision.reversible:return 'pilot'
    return 'production'

def required_controls(stage:str)->tuple[str,...]:
    """Return this stage's ordered control contract. Pilot includes the complete
    PILOT list; production is ongoing responsibility, not a higher polish score.
    """
    controls={'prototype':('isolated-inputs','discardable','learning-question'),
        'pilot':PILOT,
        'production':('slo','on-call','incident-owner','security-privacy','cost-capacity','rollback','recovery','monitoring','retirement')}
    if stage not in controls:raise ValueError('unknown stage')
    return controls[stage]

def _missing(stage:str,present:tuple[str,...])->tuple[str,...]:
    return tuple(c for c in required_controls(stage) if c not in present)

def _effective_stage(record:Registration,recommended:str)->str:
    """A changed recommendation does not silently modify the registered declaration."""
    return record.declared_stage

def plan(record:Registration,decision:Decision)->dict:
    """Keep declared_stage intact, show recommended_stage separately and report the
    missing controls of the declared environment in contract order (required minus
    present). A readiness failure never silently turns a production declaration into
    pilot. Changes to stage require an explicit registration update elsewhere.
    """
    choice=recommend(decision);stage=_effective_stage(record,choice)
    return {'declared_stage':stage,'recommended_stage':choice,'missing_controls':_missing(stage,record.controls)}

def audiences(events:list[Session])->list[tuple[str,int]]:
    """After every join/leave, return (event.system,current distinct active users).
    Session ids are scoped per system. Joining an existing session replaces its user
    (same user refresh is idempotent); leaving an absent session does nothing. A user
    with two live sessions stays active until the last leaves. Preserve input events.
    Count active users, not past unique users or active sessions, efficiently.
    """
    sessions={};users={};out=[]
    for e in events:
        book=sessions.setdefault(e.system,{});counts=users.setdefault(e.system,Counter())
        if e.session in book:
            old=book.pop(e.session);counts[old]-=1
            if not counts[old]:del counts[old]
        if e.joined:book[e.session]=e.user;counts[e.user]+=1
        out.append((e.system,len(counts)))
    return out
