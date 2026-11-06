"""The ratchet record: a versioned control snapshot with ownership and review date."""
from __future__ import annotations
import json
import sqlite3
from dataclasses import asdict, dataclass
from .controls import Control

@dataclass(frozen=True)
class Record:
    control: Control
    owner: str
    review_date: str

class ControlStore:
    """SQLite snapshots keyed by fingerprint. save replaces that control's entire
    snapshot, not an increment; it keeps its first slot in the listing. Empty owner
    and free-form review date are preserved here: human policy checking is upstream.
    """
    def __init__(self,path:str):
        self.db=sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS controls(seq INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT UNIQUE, payload TEXT)")
        self.db.commit()
    def save(self,record:Record)->None:
        """Persist all record fields; replacing a snapshot must not add recurrence."""
        payload=json.dumps(asdict(record),ensure_ascii=False)
        with self.db:
            self.db.execute("INSERT INTO controls(fingerprint,payload) VALUES(?,?) ON CONFLICT(fingerprint) DO UPDATE SET payload=excluded.payload",(record.control.fingerprint,payload))
    def records(self,target:str|None=None)->list[Record]:
        """First-seen control slots, optionally filtered by target, across reopen."""
        result=[]
        for (payload,) in self.db.execute("SELECT payload FROM controls ORDER BY seq"):
            raw=json.loads(payload)
            record=Record(Control(**raw["control"]),raw["owner"],raw["review_date"])
            if target is None or record.control.target==target:
                result.append(record)
        return result
    def close(self)->None:
        self.db.close()
