"""Original interview practice for 14-agent-engineering/18-agno-and-mastra-runtimes.

Local source: phases/14-agent-engineering/18-agno-and-mastra-runtimes/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def transition(state, target):
    """Allowed edges: queued->running/canceled; running->waiting/completed/failed/canceled; waiting->running/canceled. Return target if allowed, otherwise ValueError. Terminal states cannot transition, including to themselves."""
    raise NotImplementedError('TODO 1: transition; see PROMPT.md')

def profile(events):
    """Events have name,start,end numeric milliseconds. Reject end<start with ValueError. Return name->{'count','total','max'} aggregated over individual durations. Empty input -> {}; overlapping durations are summed, not wall-clock latency."""
    raise NotImplementedError('TODO 2: profile; see PROMPT.md')
