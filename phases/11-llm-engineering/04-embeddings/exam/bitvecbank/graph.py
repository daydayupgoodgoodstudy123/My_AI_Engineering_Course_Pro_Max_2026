"""Greedy inspection of a supplied multilayer neighbor graph, no ANN build."""
from .records import vector_value, records_value, dense_metric
from .layers import validated_layers
from .metrics import metric_value, score_key

def descend_layers(query, records, layers, entry, metric="euclidean"):
    """Report one greedy path per layer, carrying its best node downward.

    Validate with supplied helpers. At a step inspect the current node and
    all its neighbors; choose the lowest repaired score_key (metric order,
    then original bank position). Move only when this full key improves.
    Equal metric values may move toward an earlier bank index. Repetition
    across layers is legal; do not apply a global visited-node exclusion.
    Output {best,score,layers:[{layer,path,best}]}, layer indices top-first
    from zero. Empty neighbor lists stop a layer; no search beam, insertion,
    efSearch/recall guarantee or real HNSW construction is implemented.
    """
    raise NotImplementedError
