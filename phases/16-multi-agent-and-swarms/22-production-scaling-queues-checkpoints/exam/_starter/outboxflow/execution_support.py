"""Explicit independent atomic idempotent receiver and one-shot crash cuts. Given."""
from .db_support import Rows, encode
from .models import Receipt

class SimulatedCrash(RuntimeError):pass

class CrashCut:
    def __init__(self,cut=None):
        self.cut=cut
        self.fired=False
    def hit(self,name):
        if self.cut==name and not self.fired:
            self.fired=True
            raise SimulatedCrash(name)

class AtomicReceiver:
    """Stable key, actual effect and receipt commit together in this separate SQLite resource."""
    def __init__(self,path,uid='receiver'):
        self.rows=Rows(path)
        self.uid=uid
        self.calls=[]
    def deliver(self,intent):
        self.calls.append(intent.key)
        old={r[0]:r for r in self.rows.all('effect')}
        if intent.key in old:
            key,uid,amount,result=old[intent.key]
            if encode((amount,result))!=encode((intent.amount,{'destination':intent.destination,'payload':intent.payload})):
                raise ValueError('receiver key conflict')
            return Receipt(key,uid,amount,result)
        result={'destination':intent.destination,'payload':intent.payload}
        with self.rows.atomic():
            self.rows.put('effect',intent.key,(intent.key,self.uid,intent.amount,result))
        return Receipt(intent.key,self.uid,intent.amount,result)
    def effects(self):
        return tuple(Receipt(*v) for v in self.rows.all('effect'))
    def close(self):self.rows.close()

def bind_plans(run,plans):
    plans=tuple(plans)
    assert all(p.checkpoint.run==run and p.intent.run==run and p.checkpoint.step==p.intent.step for p in plans)
    assert all(type(p.checkpoint.step)is int and p.checkpoint.step>=0 for p in plans)
    assert len({p.checkpoint.step for p in plans})==len(plans)
    assert all(p.intent.amount.is_finite() and p.intent.amount>=0 for p in plans)
    return tuple(sorted(plans,key=lambda p:p.checkpoint.step))
