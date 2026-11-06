"""dbm source/parent/child catalog with exact original typed metadata."""
import dbm
from .models import Catalog,Source,Parent,Child
from .codec import dbkey,encode,decode,record

class CatalogStore:
    def __init__(self,path):self.path=str(path)
    def save(self,catalog):
        """Replace a complete catalog; no transaction/crash guarantee requested."""
        with dbm.open(self.path,"c") as database:
            for key in database.keys():del database[key]
            database[b"source-order"]=encode([row.key for row in catalog.sources])
            for row in catalog.sources:database[dbkey("source",row.key)]=encode(record(row))
            for row in catalog.parents:database[dbkey("parent",row.source_key,row.ordinal)]=encode(record(row))
            for row in catalog.children:database[dbkey("child",row.source_key,row.parent,row.ordinal)]=encode(record(row))
    def load(self):
        """Return canonical source/parent/child order with integer indices/times.

        Source insertion order, then numeric parent/child ordinal defines
        catalog order; raw UTF8 spans/text and exact microseconds survive.
        No content-based deduplication or second-based timestamp rounding.
        An absent dbm file is not treated as an empty committed catalog.
        """
        with dbm.open(self.path,"r") as database:
            order=decode(database[b"source-order"])
            sources=tuple(Source(**decode(database[dbkey("source",key)])) for key in order)
            parents=[];children=[]
            for key in database.keys():
                if key==b"source-order":continue
                kind=decode(key)[0]
                if kind=="parent":parents.append(Parent(**decode(database[key])))
                if kind=="child":children.append(Child(**decode(database[key])))
            source_rank={key:i for i,key in enumerate(order)}
            parents.sort(key=lambda row:(source_rank[row.source_key],row.ordinal))
            children.sort(key=lambda row:(source_rank[row.source_key],row.parent,row.ordinal))
            return Catalog(sources,parents,children)
