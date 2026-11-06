"""Packed Hamming shortlist followed by dense re-score on that shortlist only."""
from .formats import packed_pair, pack_sign_bits
from .records import count_value, records_value, vector_value, dense_metric
from . import metrics

def packed_hamming(a, b, dimension):
    """Count differing VALID bits in MSB-first packed codes via XOR/popcount.

    Both codes have exactly ceil(dimension/8) bytes. Unused low tail bits may
    contain arbitrary padding and never contribute, including dirty inputs.
    Byte-aligned dimensions retain all eight bits of the final byte.
    """
    a, b = packed_pair(a, b, dimension)
    total = 0
    for index, (left, right) in enumerate(zip(a, b)):
        difference = left ^ right
        if index == len(a) - 1 and dimension % 8:
            difference &= (255 << (8 - dimension % 8)) & 255
        total += difference.bit_count()
    return total

def binary_first_search(query, records, shortlist_m, final_k, metric="cosine"):
    """Return final hits from a stable binary-first/dense-second pipeline.

    Validate via supplied helpers; m/k are independent nonnegative exact ints.
    m=0/k=0/empty bank -> []; m>N clamps to N; m<k returns at most m.
    Stage1: every code's Hamming distance, ascending then original bank index.
    Stage2: call repaired metrics.metric_value ONLY for the first m candidates;
    use repaired metrics.order_hits for dense metric direction and bank ties.
    No candidate outside the shortlist can re-enter. Do not project vectors.
    Hits have key/index/score/hamming/binary_rank/rank. index is zero-based
    original position; both ranks are one-based and binary_rank is retained
    from stage1 even when dense reranking changes final order.
    """
    query = vector_value(query)
    rows = records_value(records, len(query))
    count_value(shortlist_m)
    count_value(final_k)
    dense_metric(metric)
    if shortlist_m == 0 or final_k == 0 or not rows:
        return []
    query_code = pack_sign_bits(query)
    coarse = [(packed_hamming(query_code, pack_sign_bits(row.vector), len(query)), index) for index, row in enumerate(rows)]
    coarse.sort(key=lambda value: (value[0], value[1]))
    hits = []
    for binary_rank, (distance, index) in enumerate(coarse[:shortlist_m], 1):
        row = rows[index]
        hits.append({"key": row.key, "index": index, "score": metrics.metric_value(query, row.vector, metric), "hamming": distance, "binary_rank": binary_rank})
    selected = metrics.order_hits(hits, metric)[:final_k]
    return [dict(hit, rank=rank) for rank, hit in enumerate(selected, 1)]
