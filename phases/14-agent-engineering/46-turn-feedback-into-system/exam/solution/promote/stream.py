"""Online recurrence with a bounded evidence window; SSE is this exercise's view."""
from __future__ import annotations
import json
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from .controls import Correction, normalize_cause

@dataclass(frozen=True)
class Observation:
    at: int
    cause: str
    consequence: str

class Window:
    """Correct supplied window helper. Times are nondecreasing integer ticks. A record
    lives on (now-width, now], so an observation at now-width has expired. Identity is
    normalize_cause; counts and severity are computed independently per cause.
    """
    def __init__(self,width:int):
        if width<=0: raise ValueError("width must be positive")
        self.width=width
        self.rows={}
    def add(self,event:Observation)->tuple[str,int,bool]:
        key=normalize_cause(event.cause)
        rows=self.rows.setdefault(key,deque())
        while rows and rows[0].at<=event.at-self.width:
            rows.popleft()
        rows.append(event)
        return key,len(rows),any(e.consequence=="severe" for e in rows)

def _line(key:str,count:int,at:int)->str:
    return "event: promoted\ndata: "+json.dumps({"cause":key,"count":count,"at":at},ensure_ascii=False)+"\n\n"

async def promoted(events:AsyncIterator[Observation],width:int=10,threshold:int=2)->AsyncIterator[str]:
    """Use Window to promote each cause once: severe immediately, otherwise at threshold
    observations inside the window. Keep reading other causes after a promotion. Output
    the supplied SSE line immediately after the triggering observation; no future pull
    while that event is being consumed. Time comes solely from event.at. A cause promoted
    in this view stays promoted even if its old evidence later expires.
    """
    if threshold<1: raise ValueError("threshold must be positive")
    window=Window(width)
    emitted=set()
    async for event in events:
        key,count,severe=window.add(event)
        if key not in emitted and (severe or count>=threshold):
            emitted.add(key)
            yield _line(key,count,event.at)
