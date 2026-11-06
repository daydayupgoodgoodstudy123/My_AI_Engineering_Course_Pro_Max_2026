"""Original interview practice for 17-infrastructure-and-production/03-gpu-autoscaling-kubernetes.

Local source: phases/17-infrastructure-and-production/03-gpu-autoscaling-kubernetes/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def replicas(arrival_rate, capacity_per_replica, target_utilization, minimum, maximum):
    if arrival_rate < 0 or capacity_per_replica <= 0 or (not 0 < target_utilization <= 1) or (type(minimum) is not int) or (type(maximum) is not int) or (not 0 <= minimum <= maximum):
        raise ValueError('capacity')
    return min(maximum, max(minimum, math.ceil(arrival_rate / (capacity_per_replica * target_utilization))))

def schedule_jobs(jobs, capacity):
    if type(capacity) is not int or capacity < 0 or len({j['id'] for j in jobs}) != len(jobs):
        raise ValueError('queue')
    return [j['id'] for j in sorted((j for j in jobs if j['status'] == 'queued'), key=lambda j: (-j['priority'], j['created'], j['id']))[:capacity]]
