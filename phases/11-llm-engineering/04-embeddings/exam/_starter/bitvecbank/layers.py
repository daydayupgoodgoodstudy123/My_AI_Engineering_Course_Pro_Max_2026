"""Given shape validation for a finite supplied HNSW-style graph.

layers are ordered top -> bottom. Each is key -> ordered neighbor keys.
Every upper node exists on the following layer; each edge stays in its layer.
The supplied graph is not built or maintained here.
"""
def validated_layers(records, layers, entry):
    keys = {row.key for row in records}
    if not layers or not isinstance(entry, str) or entry not in layers[0]:
        raise ValueError("entry must exist at the top layer")
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict) or not set(layer).issubset(keys):
            raise ValueError("layer references unknown nodes")
        for neighbors in layer.values():
            if not isinstance(neighbors, (tuple, list)) or any(key not in layer for key in neighbors):
                raise ValueError("edge leaves its layer")
        if index and not set(layers[index - 1]).issubset(layer):
            raise ValueError("upper nodes must persist in lower layers")
    return layers
