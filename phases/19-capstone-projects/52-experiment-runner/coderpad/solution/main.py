"""Original interview practice for 19-capstone-projects/52-experiment-runner.

Local source: phases/19-capstone-projects/52-experiment-runner/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def schedule_jobs(jobs, capacity):
    if type(capacity) is not int or capacity < 0 or len({j['id'] for j in jobs}) != len(jobs):
        raise ValueError('queue')
    return [j['id'] for j in sorted((j for j in jobs if j['status'] == 'queued'), key=lambda j: (-j['priority'], j['created'], j['id']))[:capacity]]

def budget_decisions(costs, limit):
    if limit < 0 or any((c < 0 for c in costs)):
        raise ValueError('budget')
    spent = 0
    accepted = []
    for cost in costs:
        allow = spent + cost <= limit
        accepted.append(allow)
        if allow:
            spent += cost
    return {'accepted': accepted, 'spent': spent}
