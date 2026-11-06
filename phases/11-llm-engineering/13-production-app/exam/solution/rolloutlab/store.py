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
        validate_snapshot(snapshot)
        with self.db:
            for table in ("prompts","assignments","observations"):self.db.execute("DELETE FROM "+table)
            self.db.executemany("INSERT INTO prompts(name,version,body,model,max_tokens) VALUES(?,?,?,?,?)",[(p.name,p.version,p.template,p.model,p.max_output_tokens) for p in snapshot.prompts])
            self.db.executemany("INSERT INTO assignments(user,experiment,bucket) VALUES(?,?,?)",[(a.user,a.experiment_id,a.bucket) for a in snapshot.assignments])
            self.db.executemany("INSERT INTO observations(record) VALUES(?)",[(observation_json(row),) for row in snapshot.observations])
    def load_snapshot(self):
        """Round-trip all original typed facts in order, including served and shadow."""
        prompts=tuple(PromptTemplate(*r) for r in self.db.execute("SELECT name,version,body,model,max_tokens FROM prompts ORDER BY seq"))
        assignments=tuple(Assignment(*r) for r in self.db.execute("SELECT user,experiment,bucket FROM assignments ORDER BY seq"))
        observations=tuple(observation_from_json(r[0]) for r in self.db.execute("SELECT record FROM observations ORDER BY seq"))
        return Snapshot(prompts,assignments,observations)
