"""Owned control history over a correctly supplied physical CSV codec."""
from __future__ import annotations
from pathlib import Path
from dataclasses import asdict,fields
import csv,json
from .actions import Action
HEADER=('revision',)+tuple(f.name for f in fields(Action))

def read_rows(path:Path)->list[tuple[int,Action]]:
    """Correct supplied physical CSV reader. Preserve raw CR/LF, U+2028/U+0085,
    quoting and every field; restore integer priority and tuple sources. Missing is
    empty. Row order is physical history, with no grouping, sorting or deduplication.
    This codec does not choose a new revision number or select artifact history.
    """
    if not path.exists():return []
    result=[]
    with path.open(encoding='utf-8',newline='') as f:
        for raw in csv.DictReader(f):
            revision=int(raw.pop('revision'));raw['priority']=int(raw['priority']);raw['sources']=tuple(json.loads(raw['sources']));result.append((revision,Action(**raw)))
    return result

def append_row(path:Path,revision:int,action:Action)->None:
    """Correct supplied append-only physical CSV writer for one chosen revision.
    Use real CSV/newline handling and an initial header, including an existing empty
    file. It appends exactly the given row; the caller owns revision/history policy.
    """
    path.parent.mkdir(parents=True,exist_ok=True);new=not path.exists() or path.stat().st_size==0
    row=asdict(action);row['sources']=json.dumps(action.sources,ensure_ascii=False)
    with path.open('a',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=HEADER,lineterminator='\n')
        if new:writer.writeheader()
        writer.writerow(dict(revision=revision,**row))

class Ledger:
    """Single-writer complete Action revision history. Use supplied CSV codec unchanged.
    Every append is a new review record, even an identical Action or the same artifact
    on another product/workbench track. Revisions are contiguous one-based positions
    across the entire ledger, not per id/artifact/track or per Ledger instance.
    Read current file history on each call so another reopened handle is visible.
    """
    def __init__(self,path:str|Path):self.path=Path(path)
    def append(self,action:Action)->None:
        """Choose the next global physical revision and append, without coalescing history."""
        raise NotImplementedError
    def entries(self)->list[tuple[int,Action]]:
        """Return every stored revision in physical order, including duplicate Actions."""
        raise NotImplementedError
    def history(self,artifact:str)->list[tuple[int,Action]]:
        """All exact artifact matches in physical revision order, across ids and tracks.
        Keep original global revision numbers and repeated Actions, never current-only.
        """
        raise NotImplementedError
