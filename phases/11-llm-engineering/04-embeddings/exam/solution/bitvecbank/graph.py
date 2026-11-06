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
    query = vector_value(query)
    rows = records_value(records, len(query))
    dense_metric(metric)
    validated_layers(rows, layers, entry)
    by_key = {row.key: (index, row) for index, row in enumerate(rows)}
    def order(key):
        index, row = by_key[key]
        return score_key(metric_value(query, row.vector, metric), index, metric)
    current = entry
    report = []
    for level, layer in enumerate(layers):
        path = [current]
        while True:
            candidate = min([current] + list(layer[current]), key=order)
            if order(candidate) >= order(current):
                break
            current = candidate
            path.append(current)
        report.append({"layer": level, "path": path, "best": current})
    return {"best": current, "score": metric_value(query, by_key[current][1].vector, metric), "layers": report}
