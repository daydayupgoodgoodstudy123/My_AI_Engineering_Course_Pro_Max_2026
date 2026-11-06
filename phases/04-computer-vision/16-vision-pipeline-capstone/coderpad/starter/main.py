"""Original interview practice for 04-computer-vision/16-vision-pipeline-capstone.

Local source: phases/04-computer-vision/16-vision-pipeline-capstone/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def topological_order(dependencies):
    """dependencies maps node string to prerequisite-name list. Include names appearing only as prerequisites. Return lexicographically smallest available node at each step. Cycles raise ValueError. Duplicate dependencies count once; empty graph returns []."""
    raise NotImplementedError('TODO 1: topological_order; see PROMPT.md')

def latency_report(latencies, deadline):
    """Use nonempty nonnegative numeric latencies and deadline>=0. Return {'p50':nearest-rank median,'p95':nearest-rank 95th percentile,'goodput_fraction':fraction <=deadline}. Nearest-rank index=ceil(p*n)-1. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 2: latency_report; see PROMPT.md')
