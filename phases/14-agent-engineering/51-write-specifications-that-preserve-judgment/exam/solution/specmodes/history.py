"""JSON Lines is a physical, contiguous revision journal, not a timestamp sort."""
from __future__ import annotations
from dataclasses import dataclass,asdict,replace
from pathlib import Path
import json
from .model import Decision,Boundary,mode,decode_boundary,decode_decision

@dataclass(frozen=True)
class Revision:
    number: int
    operation: str
    decision_id: str
    decision: Decision | None = None
    new_mode: str | None = None
    boundary: Boundary | None = None
    rationale: str | None = None

def read_events(path: Path) -> list[dict]:
    """Supplied physical-line decoder; Unicode separators inside JSON strings stay data. Missing file is an empty journal."""
    if not path.exists():return []
    with path.open(encoding='utf-8') as file:
        return [json.loads(line) for line in file]

def append_json(path: Path, event: dict) -> None:
    """Supplied single-writer JSONL framing. Text newlines remain inside JSON."""
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')

class DecisionJournal:
    def __init__(self,path: str | Path):self.path=Path(path)
    def append(self,event: Revision) -> None:
        """Append exactly the next positive revision; reject gaps/duplicates before
        writing. Events have valid schema: added supplies a new Decision, mode updates
        new_mode, boundary updates boundary (including None). Other ids already exist.
        rationale=None means keep the previous rationale; explicit '' replaces it.
        Raw rationale, boundary units/list order, mode and question text are preserved.
        """
        events=read_events(self.path)
        if type(event.number) is not int or event.number!=len(events)+1:
            raise ValueError('revision must be next contiguous number')
        append_json(self.path,asdict(event))
    def at(self,revision: int | None = None) -> tuple[Decision,...]:
        """Replay physical events through the specified revision inclusive (None=all,
        zero=empty); reject an out-of-range revision. Preserve initial add order.
        Changes affect only their target id; mode changes retain the old boundary,
        boundary changes retain the old mode, and optional rationale semantics apply
        to either update. Return independent typed immutable decisions.
        """
        events=read_events(self.path)
        last=len(events) if revision is None else revision
        if type(last) is not int or not 0<=last<=len(events):raise ValueError('revision out of range')
        decisions={}
        for event in events[:last]:
            key=event['decision_id']
            if event['operation']=='added':decisions[key]=decode_decision(event['decision'])
            else:
                current=decisions[key]
                changes={}
                if event['operation']=='mode':changes['mode']=event['new_mode']
                else:changes['boundary']=decode_boundary(event['boundary'])
                if event['rationale'] is not None:changes['rationale']=event['rationale']
                decisions[key]=replace(current,**changes)
        return tuple(decisions.values())
