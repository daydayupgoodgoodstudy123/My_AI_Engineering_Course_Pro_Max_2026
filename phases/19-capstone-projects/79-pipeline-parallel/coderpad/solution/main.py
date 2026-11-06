"""Original interview practice for 19-capstone-projects/79-pipeline-parallel.

Local source: phases/19-capstone-projects/79-pipeline-parallel/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def pipeline_bubble(stages, microbatches):
    if any((type(x) is not int or x <= 0 for x in (stages, microbatches))):
        raise ValueError('pipeline')
    return (stages - 1) / (microbatches + stages - 1)

def schedule_jobs(jobs, capacity):
    if type(capacity) is not int or capacity < 0 or len({j['id'] for j in jobs}) != len(jobs):
        raise ValueError('queue')
    return [j['id'] for j in sorted((j for j in jobs if j['status'] == 'queued'), key=lambda j: (-j['priority'], j['created'], j['id']))[:capacity]]
