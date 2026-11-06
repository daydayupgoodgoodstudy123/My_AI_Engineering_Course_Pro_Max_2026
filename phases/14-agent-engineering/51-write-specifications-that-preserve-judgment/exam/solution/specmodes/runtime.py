"""A private NDJSON policy gate for controlled action attempts."""
from __future__ import annotations
from dataclasses import dataclass
from collections.abc import AsyncIterable,AsyncIterator,Callable
import json
from .model import Decision,mode,canonical_limit

@dataclass(frozen=True)
class Attempt:
    decision_id: str
    sources_completed: int = 0
    elapsed_s: float = 0.0
    retries: int = 0
    dependency: str = ''
    interface: str = ''

def context(attempt: Attempt) -> dict:
    """Supplied upstream snapshot of completed work and current proposed choices.
    Counts/elapsed are valid nonnegative cumulative measurements, not new source work.
    """
    return {'sources':attempt.sources_completed,'elapsed':attempt.elapsed_s,'retries':attempt.retries,
            'dependency':attempt.dependency,'interface':attempt.interface}

def packet(event: str,decision_id: str,reasons: list[str]) -> str:
    """Supplied private NDJSON framing, not an external RPC/protocol standard."""
    return json.dumps({'event':event,'decision':decision_id,'reasons':reasons},ensure_ascii=False)+'\n'

async def enforce_stream(decisions: list[Decision],source: AsyncIterable[Attempt],apply: Callable[[Attempt],None]) -> AsyncIterator[str]:
    """Inputs have unique ids, valid modes/boundaries, known attempt decision ids.
    A locked attempt yields checkpoint with its rationale, then stops before apply,
    even if budgets also expired. For nonlocked attempts enforce every bounded limit
    globally: a measured count/time >= its limit blocks the next action. Collect all
    violated decision ids in declared order. Also enforce the current bounded
    decision's allowed dependency/interface list, with its id as reason on violation.
    Any violation yields one stop packet then returns without apply or future pull.
    Otherwise apply exactly once before yielding continue with no reasons. Delegated
    choices need no checkpoint but still obey global budgets. Closing at a yield must
    not prefetch. No actual tool/network effects occur unless the injected fake does.
    """
    by_id={d.id:d for d in decisions}
    async for attempt in source:
        current=by_id[attempt.decision_id]
        if mode(current.mode)=='locked':
            yield packet('checkpoint',current.id,[current.rationale])
            return
        values=context(attempt);reasons=[]
        for d in decisions:
            if mode(d.mode)!='bounded':continue
            b=d.boundary
            if b.kind=='limit' and values[b.metric]>=canonical_limit(b):reasons.append(d.id)
            elif d.id==current.id and b.kind=='allowed' and values[b.metric] not in b.values:reasons.append(d.id)
        if reasons:
            yield packet('stop',current.id,reasons)
            return
        apply(attempt)
        yield packet('continue',current.id,[])
