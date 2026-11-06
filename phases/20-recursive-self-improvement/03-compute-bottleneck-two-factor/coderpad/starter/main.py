"""Original interview practice for 20-recursive-self-improvement/03-compute-bottleneck-two-factor.

Local source: phases/20-recursive-self-improvement/03-compute-bottleneck-two-factor/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def amdahl(serial_fraction, speedup):
    """Return 1/(serial_fraction+(1-serial_fraction)/speedup). Require serial_fraction in [0,1] and speedup>=1; otherwise ValueError. This models latency, not queueing throughput."""
    raise NotImplementedError('TODO 1: amdahl; see PROMPT.md')

def schedule_jobs(jobs, capacity):
    """Jobs have unique id(str), priority(number), created(number), status. Select only queued jobs, sorted priority descending, created ascending, id ascending. Return at most capacity ids. capacity exact nonnegative int; duplicate ids or invalid capacity raises ValueError."""
    raise NotImplementedError('TODO 2: schedule_jobs; see PROMPT.md')
