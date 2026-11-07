"""Complete exact typed codecs and logically separate private/public append logs; no raw-private public path."""
from pathlib import Path
from decimal import Decimal
from fractions import Fraction
import json
from .models import Strategy,Quote,Narration,PublicOffer,Settlement
from .exact import price_field,price_value
def strategy_fields(s):return [s.party,s.side,str(s.reservation),str(s.opening),[str(Fraction(s.concession).numerator),str(Fraction(s.concession).denominator)]]
def strategy_value(v):return Strategy(v[0],v[1],Decimal(v[2]),Decimal(v[3]),Fraction(int(v[4][0]),int(v[4][1])))
def quote_fields(q):return None if q is None else[q.uid,q.negotiation_id,q.issue_id,q.revision,q.round,q.side,str(q.price),str(q.tick),q.currency]
def quote_value(v):return None if v is None else Quote(v[0],v[1],v[2],v[3],v[4],v[5],Decimal(v[6]),Decimal(v[7]),v[8])
def settlement_fields(s):return None if s is None else[s.negotiation_id,s.issue_id,s.standing_uid,str(s.price)]
def settlement_value(v):return None if v is None else Settlement(v[0],v[1],v[2],Decimal(v[3]))
def public_fields(p):
    if type(p)is not PublicOffer or type(p.narration)is not Narration:raise TypeError('sealed public offer required')
    return {'quote':quote_fields(p.quote),'narration':[p.narration.quote_uid,p.narration.revision,p.narration.text],'price_ticks':p.price_ticks}
def public_value(d):return PublicOffer(quote_value(d['quote']),Narration(*d['narration']),d['price_ticks'])
class DualJournal:
    """Normal-process append/close/reopen, with complete typed public routing; no crash/permission security claim."""
    def __init__(self,directory):self.directory=Path(directory);self.closed=False;self.directory.mkdir(parents=True,exist_ok=True)
    def save(self,uid,private_document,offers):
        if self.closed:raise ValueError('closed journal')
        public=[public_fields(p)for p in offers]
        for name,document in(('private.jsonl',private_document),('public.jsonl',public)):
            with(self.directory/name).open('a',encoding='utf-8')as f:f.write(json.dumps({'uid':uid,'value':document},ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
    def _load(self,name,uid):
        if self.closed:raise ValueError('closed journal')
        found=None
        with(self.directory/name).open(encoding='utf-8')as f:
            for line in f:
                row=json.loads(line)
                if row['uid']==uid:found=row['value']
        if found is None:raise KeyError(uid)
        return found
    def load_private(self,uid):return self._load('private.jsonl',uid)
    def load_public(self,uid):return tuple(public_value(v)for v in self._load('public.jsonl',uid))
    def close(self):self.closed=True
