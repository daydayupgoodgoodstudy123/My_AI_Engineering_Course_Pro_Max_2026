"""Original interview practice for 19-capstone-projects/79-pipeline-parallel.

Local source: phases/19-capstone-projects/79-pipeline-parallel/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def pipeline_bubble(stages, microbatches):
    """Both arguments are exact positive ints. Return idle fraction (stages-1)/(microbatches+stages-1) for a simplified flush schedule; invalid input raises ValueError. No actual distributed execution."""
    raise NotImplementedError('TODO 1: pipeline_bubble; see PROMPT.md')

def schedule_jobs(jobs, capacity):
    """Jobs have unique id(str), priority(number), created(number), status. Select only queued jobs, sorted priority descending, created ascending, id ascending. Return at most capacity ids. capacity exact nonnegative int; duplicate ids or invalid capacity raises ValueError."""
    raise NotImplementedError('TODO 2: schedule_jobs; see PROMPT.md')
