"""Workflow snapshots retain every piece of evidence in observation order."""
from __future__ import annotations
import json,sqlite3
from dataclasses import asdict
from .audit import Step,Evidence
class WorkflowStore:
    """SQLite keyed by opaque workflow id. save replaces only that workflow's complete
    snapshot. Input step/evidence order and all values round-trip; audit decides whether
    those orders are valid. Loading an absent id raises KeyError, including after reopen.
    """
    def __init__(self,path:str):
        self.db=sqlite3.connect(path);self.db.execute("CREATE TABLE IF NOT EXISTS workflows(id TEXT PRIMARY KEY,payload TEXT)");self.db.commit()
    def save(self,id:str,steps:list[Step])->None:
        """Replace this workflow snapshot without altering another workflow."""
        data=json.dumps([asdict(s) for s in steps],ensure_ascii=False)
        with self.db:self.db.execute("INSERT INTO workflows VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",(id,data))
    def load(self,id:str)->list[Step]:
        """Restore Step and Evidence objects, not raw dictionaries or sorted evidence."""
        row=self.db.execute("SELECT payload FROM workflows WHERE id=?",(id,)).fetchone()
        if row is None:raise KeyError(id)
        result=[]
        for raw in json.loads(row[0]):
            raw["evidence"]=tuple(Evidence(**e) for e in raw["evidence"]);result.append(Step(**raw))
        return result
    def close(self):self.db.close()
