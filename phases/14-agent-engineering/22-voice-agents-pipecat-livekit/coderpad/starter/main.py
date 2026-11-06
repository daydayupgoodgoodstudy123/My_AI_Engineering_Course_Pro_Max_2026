"""Original interview practice for 14-agent-engineering/22-voice-agents-pipecat-livekit.

Local source: phases/14-agent-engineering/22-voice-agents-pipecat-livekit/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def energy_vad(chunks, threshold):
    """For each numeric audio chunk, return RMS>=threshold; an empty chunk has RMS 0. threshold must be >=0 or raise ValueError. No model or microphone access."""
    raise NotImplementedError('TODO 1: energy_vad; see PROMPT.md')

def transition(state, target):
    """Allowed edges: queued->running/canceled; running->waiting/completed/failed/canceled; waiting->running/canceled. Return target if allowed, otherwise ValueError. Terminal states cannot transition, including to themselves."""
    raise NotImplementedError('TODO 2: transition; see PROMPT.md')
