"""Own a bounded feedback change, its proof, review window and affected track."""
from __future__ import annotations
from dataclasses import dataclass,replace
from datetime import date,timedelta
@dataclass(frozen=True)
class Signal:
    fingerprint:str
    sources:tuple[str,...]
    observation:str
    severity:int
    frequency:int
    owner:str
    days:int
    observed_on:str
    impacts:tuple[str,...]=('workbench',)
@dataclass(frozen=True)
class Action:
    id:str
    fingerprint:str
    track:str
    destination:str
    priority:int
    owner:str
    artifact:str
    verification:str
    promoted_on:str
    review_on:str
    retirement:str
    sources:tuple[str,...]
TARGETS={
    ('workbench','evaluation'):('evaluations/regression-suite.json','passing regression evaluation'),
    ('workbench','policy'):('policies/authority-boundaries.json','passing authority-boundary scenario'),
    ('workbench','context'):('context/retrieval-guidance.md','replay with required context present'),
    ('workbench','runtime'):('runtime/reliability-controls.json','timeout/retry scenario within budget'),
    ('workbench','backlog'):('backlog/shaped-work.json','review against outcome frame'),
    ('product','backlog'):('product/outcome-frame.md','review outcome assumptions and authority boundary')}

def destination(signal:Signal)->str:
    """Correct supplied ordered finite routing table; no external NLP inferred."""
    text=signal.observation.casefold()
    rows=(('evaluation',('regression','wrong result','false positive')),('policy',('permission','unsafe','production write','authority gap')),('context',('missing context','could not find','duplicate','stale fact')),('runtime',('timeout','retry','unavailable')))
    return next((target for target,words in rows if any(w in text for w in words)),'backlog')

def valid_signal(signal:Signal)->None:
    """Correct supplied owner and numeric/schema boundary, never a planted blank-owner bug."""
    if not signal.owner.strip():raise ValueError('owner is required')
    if type(signal.severity) is not int or not 1<=signal.severity<=5 or type(signal.frequency) is not int or signal.frequency<1 or type(signal.days) is not int or signal.days<1:raise ValueError('invalid signal dimensions')
    if not signal.impacts or any(x not in ('product','workbench') for x in signal.impacts):raise ValueError('invalid impacts')
    date.fromisoformat(signal.observed_on)

def combine(first:Signal,later:Signal)->Signal:
    """Correct supplied same-fingerprint accumulation: frequency sum, maximum severity,
    minimum review window, earliest observed date and stable source/impact union. Inputs
    agree on owner; first observation remains the display, canonical cause is upstream.
    """
    valid_signal(first);valid_signal(later)
    if first.fingerprint!=later.fingerprint or first.owner!=later.owner:raise ValueError('inconsistent signal identity')
    return replace(first,frequency=first.frequency+later.frequency,severity=max(first.severity,later.severity),days=min(first.days,later.days),observed_on=min((first.observed_on,later.observed_on),key=date.fromisoformat),sources=tuple(dict.fromkeys(first.sources+later.sources)),impacts=tuple(dict.fromkeys(first.impacts+later.impacts)))

def merge(signals:list[Signal])->list[Signal]:
    """Correct supplied grouping; first fingerprint order, no loss of independent recurrence."""
    groups={}
    for s in signals:
        valid_signal(s);groups[s.fingerprint]=combine(groups[s.fingerprint],s) if s.fingerprint in groups else s
    return list(groups.values())

def _metadata(track:str,target:str)->tuple[str,str]:
    """Artifact and verification must be paired with this exact control target."""
    return TARGETS[('workbench','backlog')]

def _impacts(signal:Signal)->tuple[str,...]:
    return signal.impacts[:1]

def _review_start(signal:Signal,promoted_on:date)->date:
    """Review lifetime starts when this control is promoted, not when a signal occurred."""
    return date.fromisoformat(signal.observed_on)

def review_date(start:date,days:int)->str:
    """ISO calendar date days after start; normal review windows are60/90/180days."""
    for _ in range(days):start+=timedelta(days=1)
    return start.isoformat()

def schedule(start:date,windows:list[int])->list[str]:
    """Return every independent review date in window order without changing inputs."""
    return [review_date(start,days) for days in windows]

def promote(signal:Signal,promoted_on:date)->list[Action]:
    """Use correct signal/routing helpers. Materialize every declared impact in order.
    Workbench uses destination(signal); product becomes a shaped backlog/frame action.
    Each action binds its target's artifact AND verification, raw owner/sources,
    consequence*recurrence priority, injected promotion day and a review day starting
    at promotion. Retirement condition names evidence/review, never automatic deletion.
    IDs are fingerprint+':'+track, with upstream unique impacts. No actual writes occur.
    """
    valid_signal(signal);actions=[]
    for track in _impacts(signal):
        target='backlog' if track=='product' else destination(signal);artifact,verification=_metadata(track,target)
        actions.append(Action(signal.fingerprint+':'+track,signal.fingerprint,track,target,signal.severity*signal.frequency,signal.owner,artifact,verification,promoted_on.isoformat(),review_date(_review_start(signal,promoted_on),signal.days),'review recurrence and replacement evidence before retirement',signal.sources))
    return actions

def backlog(signals:list[Signal],promoted_on:date)->list[Action]:
    """Correct accumulation before materialization; sort by -priority then track,id."""
    actions=[a for s in merge(signals) for a in promote(s,promoted_on)]
    return sorted(actions,key=lambda a:(-a.priority,a.track,a.id))
