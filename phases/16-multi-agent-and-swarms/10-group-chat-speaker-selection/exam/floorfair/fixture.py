"""Real selector calls over an archived conversation; expected full report is assembled separately."""
import hashlib
from .models import Speaker,Utterance,Decision,Proposal,ChatReport
from .support import render_message
class ContextDigestSelector:
    def __init__(self,roster,rounds):self.roster=roster;self.rounds=rounds;self.calls=0
    def __call__(self,context,counts):
        if self.calls==self.rounds:return None
        i=self.calls;self.calls+=1
        reason=hashlib.sha256('\n'.join(context).encode('utf-8')).hexdigest()
        return Proposal(self.roster[i%len(self.roster)].name,'reply-'+str(i),True,reason)
def conversation_fixture(history_count=8000,rounds=80):
    roster=(Speaker('coder'),Speaker('reviewer'),Speaker('manager'))
    history=tuple(Utterance('timed','archived-'+str(i),'user','prior question '+str(i)+' 有限上下文',0)for i in range(history_count))
    pool=list(history);records=[];counts={s.name:0 for s in roster}
    for i in range(rounds):
        context=tuple(render_message(m)for m in pool[-3:]);speaker=roster[i%len(roster)].name
        reason=hashlib.sha256('\n'.join(context).encode('utf-8')).hexdigest();decision=Decision('timed','timed:d'+str(i),speaker,reason,context,i,True)
        message=Utterance('timed','timed:m'+str(i),speaker,'reply-'+str(i),i+1,decision.decision_id)
        records.extend((decision,message));pool.append(message);counts[speaker]+=1
    expected=ChatReport('timed',roster,tuple(pool),tuple(records),tuple(counts.items()),'max_rounds')
    return(roster,history,ContextDigestSelector(roster,rounds)),expected
