"""Given complete Usage persistence on its caller's SQLite connection.

The journal owns its schema, every Usage field codec, insertion order and raw
cost spelling. It never opens a connection or starts, commits or rolls back a
transaction; its caller controls the transaction shared with bucket state.
"""
from .contracts import Usage,validate_usage

USAGE_SCHEMA="""CREATE TABLE IF NOT EXISTS usage(seq INTEGER PRIMARY KEY,request_id TEXT UNIQUE NOT NULL,user TEXT NOT NULL,model TEXT NOT NULL,admitted INTEGER NOT NULL,input_tokens INTEGER NOT NULL,cached_input_tokens INTEGER NOT NULL,output_tokens INTEGER NOT NULL,cost_text TEXT NOT NULL)"""

def encode_usage(usage):
    """Given complete validated SQL values, preserving the original cost text."""
    validate_usage(usage)
    return (usage.request_id,usage.user,usage.model,int(usage.admitted),usage.input_tokens,usage.cached_input_tokens,usage.output_tokens,usage.cost_text)

def decode_usage(row):
    """Given restoration of every Usage field, including unnormalized cost text."""
    a,b,c,d,e,f,g,h=row
    return Usage(a,b,c,bool(d),e,f,g,h)

class UsageJournal:
    def __init__(self,connection):
        self.db=connection
        self.db.execute(USAGE_SCHEMA)
    def append(self,usage):
        """Append one unique request in the caller's current transaction."""
        self.db.execute("INSERT INTO usage(request_id,user,model,admitted,input_tokens,cached_input_tokens,output_tokens,cost_text) VALUES(?,?,?,?,?,?,?,?)",encode_usage(usage))
    def read(self):
        """Return complete Usage records in insertion order, with raw cost text."""
        rows=self.db.execute("SELECT request_id,user,model,admitted,input_tokens,cached_input_tokens,output_tokens,cost_text FROM usage ORDER BY seq").fetchall()
        return [decode_usage(row) for row in rows]
