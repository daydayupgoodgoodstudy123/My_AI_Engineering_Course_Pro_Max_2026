"""Original interview practice for 16-multi-agent-and-swarms/22-production-scaling-queues-checkpoints.

Local source: phases/16-multi-agent-and-swarms/22-production-scaling-queues-checkpoints/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json

def schedule_jobs(jobs, capacity):
    """Jobs have unique id(str), priority(number), created(number), status. Select only queued jobs, sorted priority descending, created ascending, id ascending. Return at most capacity ids. capacity exact nonnegative int; duplicate ids or invalid capacity raises ValueError."""
    raise NotImplementedError('TODO 1: schedule_jobs; see PROMPT.md')

def replay_requests(requests):
    """Requests have id and payload (JSON values). First use of id is executed and recorded; exact canonical-JSON payload replay is not executed again. Conflicting reuse raises ValueError. Return {'executed':[first-use ids], 'replayed':[duplicate ids in encounter order]}. Do not treat bool and int payloads as equal."""
    raise NotImplementedError('TODO 2: replay_requests; see PROMPT.md')
