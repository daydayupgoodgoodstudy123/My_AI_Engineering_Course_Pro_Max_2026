"""Review triggers are not permission to delete a control."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date,timedelta
from .actions import Action
@dataclass(frozen=True)
class Evidence:
    control_id:str
    track:str
    verified:bool=False
    full_window_observed:bool=False
    replacement_id:str=''
    replacement_verified:bool=False
    replacement_covers:bool=False
    retirement_approved:bool=False
@dataclass(frozen=True)
class Review:
    window_days:int
    last_recurrence:str|None
    blocked_legitimate:int
    prevented_harm:int
    architecture_changed:bool
    evidence:Evidence
@dataclass(frozen=True)
class Verdict:
    status:str
    reasons:tuple[str,...]

def evidence_flags(control:Action,evidence:Evidence)->tuple[bool,bool,bool]:
    """Correct supplied evidence qualification, not a second claim/receipt matching lab.
    Return complete-window, verified-covering-replacement, explicit-retirement-approval.
    Matching control id/track and verified evidence are required for all three.
    """
    valid=evidence.control_id==control.id and evidence.track==control.track and evidence.verified
    return (valid and evidence.full_window_observed,valid and bool(evidence.replacement_id) and evidence.replacement_verified and evidence.replacement_covers,valid and evidence.retirement_approved)

def assess(control:Action,today:date,review:Review)->Verdict:
    """Valid positive window, nonnegative counts and recurrence<=today. Ordered review
    reasons: architecture, replacement, no-recorded-recurrence, obstruction, due.
    Replacement means qualified evidence helper says verified and covering. Quiet means
    last_recurrence absent or strictly BEFORE today-window_days (start boundary included
    in the window), and the control has existed >=window_days. Obstruction is blocked
    legitimate > prevented harm. Due means today>=review_on, inclusive. Any reason
    requests review. Retire only with qualified explicit approval AND either verified
    replacement or quiet elapsed window with complete observed-window evidence. Mere
    architecture change, old age or counts never retire alone. No reasons ->keep.
    """
    complete,replacement,approved=evidence_flags(control,review.evidence)
    elapsed=(today-date.fromisoformat(control.promoted_on)).days>=review.window_days
    start=today-timedelta(days=review.window_days)
    quiet=elapsed and (review.last_recurrence is None or date.fromisoformat(review.last_recurrence)<start)
    reasons=[]
    if review.architecture_changed:reasons.append('architecture')
    if replacement:reasons.append('replacement')
    if quiet:reasons.append('no-recorded-recurrence')
    if review.blocked_legitimate>review.prevented_harm:reasons.append('obstruction')
    if today>=date.fromisoformat(control.review_on):reasons.append('due')
    retire=approved and (replacement or (quiet and complete))
    return Verdict('retire' if retire else ('review' if reasons else 'keep'),tuple(reasons))
