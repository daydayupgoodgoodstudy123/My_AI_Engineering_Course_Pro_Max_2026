"""Complete ordered joint/local rollout snapshot; scalar binary mechanics are supplied."""
from .models import World,Observation,ActionValue,JointTransition,GridReport
from .binary_support import BinaryFile

def world_record(w):return w.size,w.positions,w.pellets

def transition_record(t):
    """Preserve central training state separately from both already-bound local execution records."""
    observations=tuple((o.agent_uid,o.size,o.cell,o.target)for o in t.observations)
    values=tuple(tuple((q.action,q.value)for q in row)for row in t.local_values)
    return t.uid,t.episode,t.step,world_record(t.before),observations,values,t.actions,t.collected,t.rewards,world_record(t.after),t.done,t.policy

def restore_transition(r):
    uid,episode,step,before,observations,values,actions,collected,rewards,after,done,policy=r
    return JointTransition(uid,episode,step,World(*before),tuple(Observation(*o)for o in observations),tuple(tuple(ActionValue(*q)for q in row)for row in values),actions,collected,rewards,World(*after),done,policy)

class RolloutArchive:
    def __init__(self,path):self.file=BinaryFile(path)
    def save(self,report):self.file.write(tuple(transition_record(t)for t in report.transitions))
    def reopen(self):return GridReport(tuple(restore_transition(r)for r in self.file.read()))
    def close(self):self.file.close()
