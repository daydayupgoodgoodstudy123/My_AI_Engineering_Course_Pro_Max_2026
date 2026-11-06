"""SQLite snapshot of prompt records, stable bucket assignments and typed observations."""
import sqlite3
from .contracts import PromptTemplate,Assignment,Snapshot,validate_snapshot,observation_json,observation_from_json
class RolloutStore:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS prompts(seq INTEGER PRIMARY KEY,name TEXT,version TEXT,body TEXT,model TEXT,max_tokens INTEGER);
        CREATE TABLE IF NOT EXISTS assignments(seq INTEGER PRIMARY KEY,user TEXT,experiment TEXT,bucket INTEGER);
        CREATE TABLE IF NOT EXISTS observations(seq INTEGER PRIMARY KEY,record TEXT);
        """)
    def close(self):self.db.close()
    def save_snapshot(self,snapshot):
        """Replace a local complete snapshot in one transaction, preserving input order.

        Persist prompt text/version/model, stable (user,experiment) buckets and
        every request/paid observation independently. A bucket is the persistent
        assignment; changing traffic_pct may change selection, never this bucket.
        Observed usage/role/cost do not derive from served safety replacement text.
        Correct strict codecs/primitive validation are supplied.
        """
        raise NotImplementedError
    def load_snapshot(self):
        """Round-trip all original typed facts in order, including served and shadow."""
        raise NotImplementedError
