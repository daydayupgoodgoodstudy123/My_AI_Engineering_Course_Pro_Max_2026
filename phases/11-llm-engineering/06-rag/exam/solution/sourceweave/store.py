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
        validate_snapshot(snapshot)
        with self._db:
            for table in ("meta","documents","terms","chunks"):
                self._db.execute("DELETE FROM "+table)
            self._db.execute("INSERT INTO meta VALUES (?)",(snapshot.generation,))
            self._db.executemany("INSERT INTO documents VALUES (?,?,?,?,?)",[(i,row.key,row.name,row.text,snapshot.generation) for i,row in enumerate(snapshot.documents)])
            self._db.executemany("INSERT INTO terms VALUES (?,?,?,?)",[(i,term,pack_vector((snapshot.idf[i],)),snapshot.generation) for i,term in enumerate(snapshot.vocab)])
            self._db.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?)",[(chunk.flat_id,chunk.source_id,chunk.ordinal,chunk.start,chunk.end,chunk.text,pack_vector(snapshot.vectors[chunk.flat_id]),snapshot.generation) for chunk in snapshot.chunks])
    def load(self):
        """Return saved Snapshot or None for an empty store; never refit text."""
        header = self._db.execute("SELECT generation FROM meta").fetchone()
        if header is None:return None
        generation = header[0]
        docs = self._db.execute("SELECT id,name,text,generation FROM documents ORDER BY pos").fetchall()
        terms = self._db.execute("SELECT term,idf,generation FROM terms ORDER BY pos").fetchall()
        chunks = self._db.execute("SELECT id,source,ordinal,start,end,text,vector,generation FROM chunks ORDER BY id").fetchall()
        for rows in (docs,terms,chunks):generation_rows(rows,generation)
        snapshot = Snapshot(generation,tuple(Document(*row[:3]) for row in docs),tuple(Chunk(*row[:6]) for row in chunks),tuple(row[0] for row in terms),tuple(unpack_vector(row[1],1)[0] for row in terms),tuple(unpack_vector(row[6],len(terms)) for row in chunks))
        return validate_snapshot(snapshot)
