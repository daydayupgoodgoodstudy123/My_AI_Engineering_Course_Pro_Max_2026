"""Compact shared-vector derivation over sealed numeric round records."""
from .derivation_support import RoundCatalog

def build_round_derivation(records):
    """Build one shared vector node per round with prior-confidence input edges.

    RoundCatalog supplies complete (round,agent) identity and previous-record
    resolution. Each noninitial node references one previous vector, never N
    recursively copied agent subtrees. Edge weights belong to that previous
    sealed round, not the updated confidences. Truth is evaluation metadata,
    never a numeric input to this scripted weighted update.
    """
    raise NotImplementedError

def trace_initial_inputs(graph,index,name):
    """Trace nonzero causal inputs to round0 without recursively copying shared nodes.

    A round0 target depends only on its own initial answer. Later all-to-all
    revisions read the previous vector; zero-confidence terms add no causal
    root. Return stable original-agent order, the requested value and shared
    node references. Do not perform the weighted solver again.
    """
    raise NotImplementedError
