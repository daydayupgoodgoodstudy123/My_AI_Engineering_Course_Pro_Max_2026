"""Combine feedback sources while retaining every owned action target."""
from __future__ import annotations
from collections.abc import AsyncIterable,AsyncIterator
from dataclasses import asdict
from datetime import date
import json
from .actions import Signal,Action,combine,valid_signal,promote
class MergeBook:
    """Correct supplied incremental merge. Same recurrence policy as actions.merge."""
    def __init__(self):self.groups={}
    def feed(self,signal:Signal)->Signal:
        valid_signal(signal);key=signal.fingerprint
        self.groups[key]=combine(self.groups[key],signal) if key in self.groups else signal
        return self.groups[key]
class ActionGate:
    """Correct supplied once-per-complete-action identity, not once per observation.
    It owns notification state; candidates need not reimplement key deduplication.
    """
    def __init__(self):self.sent=set()
    def claim(self,action:Action)->bool:
        key=(action.fingerprint,action.track,action.destination)
        if key in self.sent:return False
        self.sent.add(key);return True

def packet(action:Action)->str:
    """Correct private NDJSON: complete immutable action snapshot plus newline."""
    return json.dumps(asdict(action),ensure_ascii=False)+'\n'

async def ratchet(source:AsyncIterable[Signal],today:date,threshold:int)->AsyncIterator[str]:
    """Use supplied MergeBook, ActionGate and packet. After each observation, compare
    the MERGED severity*frequency to inclusive threshold. At/above it materialize all
    track/target actions from that merged snapshot, retaining its full source provenance.
    Yield newly claimed actions in impact order before reading another signal. Keep
    monitoring other fingerprints after promotion; later same-target evidence updates
    merge state but does not rewrite an already-emitted snapshot. Newly added impacts
    are independent actions. Closing at any row cannot pull future evidence.
    """
    raise NotImplementedError
    yield ''
