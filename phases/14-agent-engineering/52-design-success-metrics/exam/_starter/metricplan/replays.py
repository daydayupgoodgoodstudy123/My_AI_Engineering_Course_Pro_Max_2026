"""Raw replay records keep measurement selection separate from source preservation."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
import sqlite3,json
@dataclass(frozen=True)
class Replay:
    id:str
    incident:str
    elapsed_ms:int
    correct:bool
    writes:int
    at:str
    population:str
    included:bool=True

def instant(text:str)->str:
    """Correct supplied aware-time key, uniform UTC microseconds, original text untouched."""
    value=datetime.fromisoformat(text[:-1]+'+00:00' if text.endswith('Z') else text)
    if value.tzinfo is None:raise ValueError('replay timestamp needs timezone')
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds')
class ReplayStore:
    """SQLite keyed by opaque replay id. put replaces only that id's full snapshot.
    get reconstructs Replay exactly, including raw time, integer milliseconds, booleans,
    population and excluded records. Missing get raises KeyError, also after reopen.
    """
    def __init__(self,path:str):
        self.db=sqlite3.connect(path);self.db.execute('CREATE TABLE IF NOT EXISTS replay(id TEXT PRIMARY KEY,population TEXT,instant TEXT,payload TEXT)');self.db.commit()
    def put(self,replay:Replay)->None:
        """Persist every source record, not merely those included in an outcome denominator."""
        raise NotImplementedError
    def get(self,id:str)->Replay:
        """Restore this exact typed record or raise KeyError."""
        raise NotImplementedError
    def recent(self,population:str,n:int)->list[Replay]:
        """Latest n records of this exact population, selected by instant then id.
        Return the selected records oldest-first (id ascending for tied instants).
        n=0 gives []; n<0 raises ValueError. Included/excluded both remain evidence.
        """
        raise NotImplementedError
    def close(self):self.db.close()
