"""Candidate complete binary numeric checkpoint and independent deferred routing records."""
from .models import *
from .codec import dumps,loads,pack_vectors,unpack_vectors
from .checkpoint_support import CheckpointMembers
class OptimizerArchive:
    def __init__(self,path):self.driver=CheckpointMembers(path)
    def save(self,checkpoint):
        """Persist complete numeric vectors and domain metadata, full RNG, independent routes, allocations and ordered pending outcomes."""
        s=checkpoint.state;vectors=[s.best.coordinates,(s.best.fitness,)]
        for p in s.particles:vectors.extend((p.x,p.v,p.p_best,(p.p_best_fit,)))
        metadata=(checkpoint.uid,s.iteration,s.bounds,s.rng_state,s.evaluator_version,tuple(p.uid for p in s.particles),tuple((r.task_type,r.weights)for r in checkpoint.table.rows),checkpoint.table.applied_epochs,tuple((a.uid,a.task_uid,a.task_type,a.agent_uid)for a in checkpoint.allocations),tuple((o.uid,o.allocation_uid,o.quality,o.verified,o.success,o.arrival,o.epoch)for o in checkpoint.pending))
        self.driver.replace(dumps(metadata),pack_vectors(vectors))
    def load(self):
        """Reconstruct the complete state and explicit delayed arrival records without restarting a seed or deriving one field from another."""
        text,data=self.driver.read();uid,iteration,bounds,rng,version,ids,rows,epochs,allocations,outcomes=loads(text);vectors=unpack_vectors(data)
        if len(vectors)!=2+4*len(ids):raise ValueError('particle vector layout mismatch')
        particles=tuple(ParticleState(name,vectors[2+4*i],vectors[3+4*i],vectors[4+4*i],vectors[5+4*i][0])for i,name in enumerate(ids));state=SwarmState(iteration,particles,Best(vectors[0],vectors[1][0]),bounds,rng,version)
        return ExperimentCheckpoint(uid,state,RouteTable(tuple(RouteRow(*r)for r in rows),epochs),tuple(Allocation(*a)for a in allocations),tuple(Outcome(*o)for o in outcomes))
    def close(self):self.driver.close()
