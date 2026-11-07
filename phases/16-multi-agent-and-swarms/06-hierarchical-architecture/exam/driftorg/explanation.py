"""Nested synthesis explanation over prior semantic audit and shared leaf citations."""
from .models import Status
from .graph_support import postorder

def merge_child_states(states):
    """Empty evidence is UNKNOWN; any UNKNOWN survives through all managers.

    Missing and conflicting evidence retain their declared states; a mixture
    of known positive and negative answers is CONFLICT, not a majority vote.
    """
    raise NotImplementedError

def explain_synthesis(dossier,audit):
    """Build nested summary states and occurrence paths without rerunning workers.

    Every citation occurrence retains its path, including a shared leaf under
    two different summaries. unique_leaf_ids counts actual leaf identities.
    Semantic first-divergence and original obligation attribution come from P3;
    this function does not reinterpret summary prose or recompose mappings.
    """
    raise NotImplementedError
