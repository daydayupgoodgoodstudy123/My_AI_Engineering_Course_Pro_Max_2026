"""Complete schema, per-run atomic snapshot, ordered rows and exact metadata codecs."""
from pathlib import Path
from decimal import Decimal
from fractions import Fraction
import sqlite3
def encode_fraction(value):return str(value.numerator),str(value.denominator)
def decode_fraction(numerator,denominator):return Fraction(int(numerator),int(denominator))
class Database:
    def __init__(self,path):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS proposals(run TEXT, ordinal INTEGER, uid TEXT, agent TEXT, kind TEXT, answer TEXT, self_n TEXT,self_d TEXT, PRIMARY KEY(run,ordinal))')
        self.db.execute('CREATE TABLE IF NOT EXISTS probes(run TEXT, ordinal INTEGER, proposal_uid TEXT,probe_uid TEXT,confidence_n TEXT,confidence_d TEXT,evaluator TEXT,assessment TEXT,PRIMARY KEY(run,ordinal))')
        self.db.commit()
    def replace(self,run,proposal_rows,probe_rows):
        with self.db:
            self.db.execute('DELETE FROM proposals WHERE run=?',(run,));self.db.execute('DELETE FROM probes WHERE run=?',(run,))
            self.db.executemany('INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?)',((run,*row)for row in proposal_rows))
            self.db.executemany('INSERT INTO probes VALUES(?,?,?,?,?,?,?,?)',((run,*row)for row in probe_rows))
    def rows(self,run):
        proposals=tuple(self.db.execute('SELECT ordinal,uid,agent,kind,answer,self_n,self_d FROM proposals WHERE run=? ORDER BY ordinal',(run,)))
        probes=tuple(self.db.execute('SELECT ordinal,proposal_uid,probe_uid,confidence_n,confidence_d,evaluator,assessment FROM probes WHERE run=? ORDER BY ordinal',(run,)))
        return proposals,probes
    def close(self):self.db.close()
