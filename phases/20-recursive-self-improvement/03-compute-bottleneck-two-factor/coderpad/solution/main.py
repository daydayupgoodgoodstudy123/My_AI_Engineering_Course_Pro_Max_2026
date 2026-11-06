"""Original interview practice for 20-recursive-self-improvement/03-compute-bottleneck-two-factor.

Local source: phases/20-recursive-self-improvement/03-compute-bottleneck-two-factor/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def amdahl(serial_fraction, speedup):
    if not 0 <= serial_fraction <= 1 or speedup < 1:
        raise ValueError('parameters')
    return 1 / (serial_fraction + (1 - serial_fraction) / speedup)

def schedule_jobs(jobs, capacity):
    if type(capacity) is not int or capacity < 0 or len({j['id'] for j in jobs}) != len(jobs):
        raise ValueError('queue')
    return [j['id'] for j in sorted((j for j in jobs if j['status'] == 'queued'), key=lambda j: (-j['priority'], j['created'], j['id']))[:capacity]]
