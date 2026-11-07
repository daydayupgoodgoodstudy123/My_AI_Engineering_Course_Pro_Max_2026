"""Durable complete domain snapshots: own criterion, observation, permutation, quality and credit records."""
from .models import Game,Criterion,UtilityReceipt,ReplayReport,QualityReceipt,Efficiency,AccountingSnapshot
from .db_support import RowDriver
class AccountingArchive:
    def __init__(self,path):self.driver=RowDriver(path)
    def save(self,snapshot):
        """Replace the complete snapshot, preserving declared orders and separate surplus/total fields."""
        g=snapshot.game;s=snapshot.statement
        rows=[('header',0,(g.uid,g.players,g.baseline,snapshot.unit,snapshot.quantum)),('statement',0,(s.game_uid,s.empty,s.grand,s.allocated,s.surplus,s.residual)),('replay',0,(snapshot.replay.game_uid,snapshot.replay.total))]
        rows.extend(('criterion',i,(x.uid,x.required,x.weight))for i,x in enumerate(g.criteria))
        rows.extend(('observation',i,(x.game_uid,x.coalition,x.value,x.contributions))for i,x in enumerate(snapshot.replay.observations))
        rows.extend(('permutation',i,x)for i,x in enumerate(snapshot.permutations))
        rows.extend(('quality',i,(x.uid,x.agent,x.reported,x.confirmed,x.quality))for i,x in enumerate(snapshot.receipts))
        rows.extend(('credit',i,x)for i,x in enumerate(snapshot.allocations))
        self.driver.replace(tuple(rows))
    def load(self):
        """Reopen every saved domain field, including repeated equal observations and unconfirmed receipts."""
        grouped={}
        for kind,ordinal,value in self.driver.rows():grouped.setdefault(kind,[]).append(value)
        uid,players,baseline,unit,quantum=grouped['header'][0]
        game=Game(uid,players,baseline,tuple(Criterion(*x)for x in grouped.get('criterion',())))
        replay_uid,total=grouped['replay'][0]
        replay=ReplayReport(replay_uid,tuple(UtilityReceipt(*x)for x in grouped.get('observation',())),total)
        return AccountingSnapshot(game,replay,tuple(grouped.get('permutation',())),tuple(QualityReceipt(*x)for x in grouped.get('quality',())),tuple(grouped.get('credit',())),Efficiency(*grouped['statement'][0]),unit,quantum)
    def close(self):self.driver.close()
