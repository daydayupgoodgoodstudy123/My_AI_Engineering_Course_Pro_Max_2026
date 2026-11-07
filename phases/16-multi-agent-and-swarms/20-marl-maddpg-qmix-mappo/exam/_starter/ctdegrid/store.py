"""Complete ordered joint/local rollout snapshot; scalar binary mechanics are supplied."""
from .models import World,Observation,ActionValue,JointTransition,GridReport
from .binary_support import BinaryFile

def world_record(w):return w.size,w.positions,w.pellets

def transition_record(t):
    """Preserve central training state separately from both already-bound local execution records."""
    raise NotImplementedError("Complete the declared domain contract")

def restore_transition(r):
    raise NotImplementedError("Complete the declared domain contract")

class RolloutArchive:
    def __init__(self,path):self.file=BinaryFile(path)
    def save(self,report):self.file.write(tuple(transition_record(t)for t in report.transitions))
    def reopen(self):return GridReport(tuple(restore_transition(r)for r in self.file.read()))
    def close(self):self.file.close()
