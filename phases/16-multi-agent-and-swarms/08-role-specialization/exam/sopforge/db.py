"""GIVEN complete SQLite transaction, typed payload codec and physical row ordering."""
from contextlib import contextmanager
import sqlite3
from .codec import encode,decode
@contextmanager
def database(path):
    db=sqlite3.connect(path)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS records(seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, entity TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, UNIQUE(kind,entity,revision))')
        with db:yield db
    finally:db.close()
def clear(db):db.execute('DELETE FROM records')
def write_record(db,kind,entity,revision,value):db.execute('INSERT INTO records(kind,entity,revision,payload) VALUES (?,?,?,?)',(kind,entity,revision,encode(value)))
def read_records(db):return tuple((kind,entity,revision,decode(payload))for kind,entity,revision,payload in db.execute('SELECT kind,entity,revision,payload FROM records ORDER BY seq'))
