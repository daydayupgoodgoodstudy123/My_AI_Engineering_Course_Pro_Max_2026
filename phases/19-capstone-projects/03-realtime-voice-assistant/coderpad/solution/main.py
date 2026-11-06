"""Original interview practice for 19-capstone-projects/03-realtime-voice-assistant.

Local source: phases/19-capstone-projects/03-realtime-voice-assistant/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def energy_vad(chunks, threshold):
    if threshold < 0:
        raise ValueError('threshold')
    return [math.sqrt(sum((x * x for x in c)) / len(c)) >= threshold if c else 0 >= threshold for c in chunks]

def transition(state, target):
    edges = {'queued': {'running', 'canceled'}, 'running': {'waiting', 'completed', 'failed', 'canceled'}, 'waiting': {'running', 'canceled'}}
    if target not in edges.get(state, set()):
        raise ValueError('transition')
    return target
