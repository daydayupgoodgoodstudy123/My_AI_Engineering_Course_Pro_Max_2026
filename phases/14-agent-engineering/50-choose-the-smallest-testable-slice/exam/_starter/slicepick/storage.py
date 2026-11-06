"""One JSON decision snapshot. Correct atomic file replacement is supplied."""
from __future__ import annotations
import json,os
from pathlib import Path
from dataclasses import asdict
from .model import Slice,Candidate,StopRule,Snapshot

def atomic_json(path: Path, value) -> None:
    """Supplied single-writer replace helper; no concurrent-writer guarantee."""
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)

class DecisionStore:
    def __init__(self,path: str | Path):self.path=Path(path)
    def save(self,snapshot: Snapshot) -> None:
        """Validate selected_id names an actual candidate id before any write.
        Replace the snapshot without changing raw proof strings/order/duplicates,
        stop-rule text, bool type or selected_score float bits. No score recalculation.
        """
        raise NotImplementedError
    def load(self) -> Snapshot:
        """Reopen as typed independent dataclasses with tuple-valued collections."""
        raise NotImplementedError
