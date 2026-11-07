"""GIVEN transaction and schema infrastructure; transaction mechanics are not a TODO."""
import sqlite3
from contextlib import contextmanager

class AuditDatabase:
    def __init__(self,path):
        self.connection=sqlite3.connect(path)
        self.connection.execute('PRAGMA foreign_keys=ON')
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY, agent TEXT NOT NULL, session_id TEXT,
                body BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS observations (
                run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                slot INTEGER NOT NULL, body BLOB NOT NULL,
                PRIMARY KEY(run_id,slot));
        """)
        self.connection.commit()

    @contextmanager
    def transaction(self):
        with self.connection:yield self.connection

    def close(self):self.connection.close()
