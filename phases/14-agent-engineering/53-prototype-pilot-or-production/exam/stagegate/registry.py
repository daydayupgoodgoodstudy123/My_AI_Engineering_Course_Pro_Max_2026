"""Persist declarations, not recomputed stage recommendations."""
from __future__ import annotations
from dataclasses import asdict
import json,sqlite3
from .stages import Registration,decode
class Registry:
    """Single-writer SQLite complete registration snapshots keyed by opaque system id.
    Retain original deadline, audience cap, authority/exit/control tuple order and every
    independent technical marker. put replaces only its id; get returns an independent
    Registration after reopen, or KeyError. Supplied decode restores exact field types.
    """
    def __init__(self,path:str):
        self.db=sqlite3.connect(path);self.db.execute('CREATE TABLE IF NOT EXISTS registry(id TEXT PRIMARY KEY,payload TEXT)');self.db.commit()
    def put(self,record:Registration)->None:
        """Save its declaration exactly; never infer a new stage from readiness or markers."""
        raise NotImplementedError
    def get(self,id:str)->Registration:
        """Reconstruct the complete independent typed snapshot, including all four channels."""
        raise NotImplementedError
    def close(self):self.db.close()
