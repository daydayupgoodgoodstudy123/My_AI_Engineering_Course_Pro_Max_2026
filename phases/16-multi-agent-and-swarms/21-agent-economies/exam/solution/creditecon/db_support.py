"""Given: exact scalar/container codec and atomic SQLite row resource, no accounting object mapping."""
import json,sqlite3
from fractions import Fraction
from decimal import Decimal

def pack(value):
    if type(value)is Fraction:return ['fraction',str(value.numerator),str(value.denominator)]
    if type(value)is Decimal:return ['decimal',str(value)]
    if type(value)is tuple:return ['tuple',[pack(x)for x in value]]
    if type(value)is frozenset:return ['set',[pack(x)for x in sorted(value)]]
    if value is None or type(value)in(str,int,bool):return ['scalar',value]
    raise TypeError('declared exact scalar/container required')
def unpack(value):
    tag,*data=value
    if tag=='fraction':return Fraction(int(data[0]),int(data[1]))
    if tag=='decimal':return Decimal(data[0])
    if tag=='tuple':return tuple(unpack(x)for x in data[0])
    if tag=='set':return frozenset(unpack(x)for x in data[0])
    if tag=='scalar':return data[0]
    raise ValueError('unknown scalar discriminator')
class RowDriver:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS accounting(kind TEXT,ordinal INTEGER,payload TEXT,PRIMARY KEY(kind,ordinal))')
    def replace(self,rows):
        with self.db:
            self.db.execute('DELETE FROM accounting')
            self.db.executemany('INSERT INTO accounting VALUES(?,?,?)',[(k,i,json.dumps(pack(v),ensure_ascii=False))for k,i,v in rows])
    def rows(self):return tuple((k,i,unpack(json.loads(v)))for k,i,v in self.db.execute('SELECT kind,ordinal,payload FROM accounting ORDER BY kind,ordinal'))
    def close(self):self.db.close()
