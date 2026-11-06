"""Original interview practice for 17-infrastructure-and-production/03-gpu-autoscaling-kubernetes.

Local source: phases/17-infrastructure-and-production/03-gpu-autoscaling-kubernetes/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def replicas(arrival_rate, capacity_per_replica, target_utilization, minimum, maximum):
    """Compute ceil(arrival_rate/(capacity_per_replica*target_utilization)), clamped to exact integer minimum..maximum. Require arrival_rate>=0,capacity>0,0<utilization<=1,0<=minimum<=maximum. Invalid input raises ValueError. No Kubernetes call."""
    raise NotImplementedError('TODO 1: replicas; see PROMPT.md')

def schedule_jobs(jobs, capacity):
    """Jobs have unique id(str), priority(number), created(number), status. Select only queued jobs, sorted priority descending, created ascending, id ascending. Return at most capacity ids. capacity exact nonnegative int; duplicate ids or invalid capacity raises ValueError."""
    raise NotImplementedError('TODO 2: schedule_jobs; see PROMPT.md')
