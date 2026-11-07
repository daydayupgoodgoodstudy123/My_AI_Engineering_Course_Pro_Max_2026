"""Complete transaction and table resources, not epistemic row modeling."""
from pathlib import Path
import sqlite3
class SnapshotDB:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(self.path)
        self.db.executescript('CREATE TABLE IF NOT EXISTS header(singleton INTEGER PRIMARY KEY,value TEXT);CREATE TABLE IF NOT EXISTS observations(ord INTEGER PRIMARY KEY,uid TEXT,key TEXT,value TEXT,turn TEXT,ordinal TEXT,kind TEXT);CREATE TABLE IF NOT EXISTS beliefs(ord INTEGER PRIMARY KEY,uid TEXT,key TEXT,value TEXT,turn TEXT,ordinal TEXT,source TEXT);')
    def replace(self,header,observations,beliefs):
        with self.db:
            self.db.execute('DELETE FROM header');self.db.execute('DELETE FROM observations');self.db.execute('DELETE FROM beliefs');self.db.execute('INSERT INTO header VALUES(1,?)',(header,));self.db.executemany('INSERT INTO observations VALUES(?,?,?,?,?,?,?)',observations);self.db.executemany('INSERT INTO beliefs VALUES(?,?,?,?,?,?,?)',beliefs)
    def read(self):return self.db.execute('SELECT value FROM header WHERE singleton=1').fetchone()[0],self.db.execute('SELECT * FROM observations ORDER BY ord').fetchall(),self.db.execute('SELECT * FROM beliefs ORDER BY ord').fetchall()
    def close(self):self.db.close()
