"""Original interview practice for 06-speech-and-audio/12-voice-assistant-pipeline.

Local source: phases/06-speech-and-audio/12-voice-assistant-pipeline/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def transition(state, target):
    """Allowed edges: queued->running/canceled; running->waiting/completed/failed/canceled; waiting->running/canceled. Return target if allowed, otherwise ValueError. Terminal states cannot transition, including to themselves."""
    raise NotImplementedError('TODO 1: transition; see PROMPT.md')

def budget_decisions(costs, limit):
    """Sequentially accept each nonnegative numeric cost if spent+cost<=limit, otherwise reject and keep spent unchanged. Return {'accepted':[bool per request],'spent':total}. Negative limit/cost raises ValueError. No rounding, billing API, or actual charge."""
    raise NotImplementedError('TODO 2: budget_decisions; see PROMPT.md')
