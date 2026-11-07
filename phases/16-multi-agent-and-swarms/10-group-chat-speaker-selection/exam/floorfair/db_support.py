"""Complete transaction and exact scalar codec; candidate owns the domain snapshot layout."""
import json,sqlite3
from contextlib import contextmanager
from fractions import Fraction
from .models import Utterance,Decision
def atom(value):
    if value is None:return['none']
    if type(value)is bool:return['bool',value]
    if type(value)is int:return['int',str(value)]
    if type(value)is str:return['str',value]
    if isinstance(value,Fraction):return['fraction',str(value.numerator),str(value.denominator)]
    if type(value)is tuple:return['tuple',[atom(x)for x in value]]
    raise ValueError('declared scalar domain')
def unatom(row):
    kind=row[0]
    if kind=='none':return None
    if kind=='bool':return row[1]
    if kind=='int':return int(row[1])
    if kind=='str':return row[1]
    if kind=='fraction':return Fraction(int(row[1]),int(row[2]))
    if kind=='tuple':return tuple(unatom(x)for x in row[1])
    raise ValueError('typed scalar tag')
def encode(value):return json.dumps(atom(value),ensure_ascii=False,separators=(',',':')).encode('utf-8')
def decode(value):return unatom(json.loads(value))
def restore_event(kind,fields):
    if kind=='message':return Utterance(*fields)
    if kind=='decision':return Decision(*fields)
    raise ValueError('typed observation kind')
@contextmanager
def transaction(path):
    db=sqlite3.connect(path)
    try:
        db.execute('BEGIN IMMEDIATE');yield db;db.commit()
    except BaseException:db.rollback();raise
    finally:db.close()

def ensure_schema(db):
    """Complete schema dependency, including record identity independent of committed turn number."""
    db.execute('CREATE TABLE IF NOT EXISTS chats(thread TEXT PRIMARY KEY,roster BLOB,baseline BLOB)')
    db.execute('CREATE TABLE IF NOT EXISTS observations(thread TEXT,position INTEGER,kind TEXT,payload BLOB,PRIMARY KEY(thread,position))')
