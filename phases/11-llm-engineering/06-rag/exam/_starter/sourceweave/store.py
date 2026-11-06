"""Transactional SQLite persistence of one complete corpus/vector snapshot."""
import sqlite3
from .models import Document, Chunk, Snapshot, validate_snapshot
from .codec import pack_vector, unpack_vector, generation_rows

class SnapshotStore:
    def __init__(self,path):
        self._db = sqlite3.connect(path)
        self._db.executescript("""CREATE TABLE IF NOT EXISTS meta(generation INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS documents(pos INTEGER PRIMARY KEY, id TEXT UNIQUE, name TEXT, text TEXT, generation INTEGER);
        CREATE TABLE IF NOT EXISTS terms(pos INTEGER PRIMARY KEY, term TEXT, idf BLOB, generation INTEGER);
        CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, source TEXT, ordinal INTEGER, start INTEGER, end INTEGER, text TEXT, vector BLOB, generation INTEGER);""")
    def close(self):
        self._db.close()
    def save(self,snapshot):
        """Replace the complete validated snapshot in one SQLite transaction.

        Exact raw source text/UTF8 byte spans, ordered coordinates, binary64
        IDF/vectors and generation belong together. A write failure retains
        the previous snapshot. Repeated text or names do not merge identities.
        """
        raise NotImplementedError
    def load(self):
        """Return saved Snapshot or None for an empty store; never refit text."""
        raise NotImplementedError
