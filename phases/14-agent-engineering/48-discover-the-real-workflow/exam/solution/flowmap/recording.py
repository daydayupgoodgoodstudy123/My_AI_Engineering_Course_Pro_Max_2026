"""Turn a deterministic recording event stream into observed workflow steps."""
from __future__ import annotations
import csv,io
from dataclasses import dataclass
from collections.abc import AsyncIterator
@dataclass(frozen=True)
class Event:
    at:int
    actor:str
    action:str

def _row(*fields)->str:
    """Correct supplied CSV row serializer, one record ending in newline."""
    out=io.StringIO();csv.writer(out,lineterminator="\n").writerow(fields);return out.getvalue()

async def segment(events:AsyncIterator[Event],idle_ms:int=10)->AsyncIterator[str]:
    """Yield CSV header step,actor,start,end,wait_ms,events and one row per segment.
    Event timestamps are nondecreasing integer milliseconds; preserve equal-time input
    order. Start a new segment on actor change OR gap>idle_ms. Only an idle gap counts
    as the new segment's wait_ms, even when actor also changes; otherwise wait is0.
    End is the last event time, not the next event or wall clock. Emit a closed segment
    immediately after seeing its boundary event; emit the last segment on end-of-stream.
    An empty recording emits only the header. idle_ms must be nonnegative.
    """
    if idle_ms<0:raise ValueError("idle_ms must be nonnegative")
    yield _row("step","actor","start","end","wait_ms","events")
    current=None;index=0
    async for e in events:
        if current is None:
            current=[e.actor,e.at,e.at,0,1];continue
        gap=e.at-current[2]
        if e.actor!=current[0] or gap>idle_ms:
            index+=1;yield _row(index,*current)
            current=[e.actor,e.at,e.at,gap if gap>idle_ms else 0,1]
        else:current[2]=e.at;current[4]+=1
    if current is not None:yield _row(index+1,*current)
