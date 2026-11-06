"""Lost-in-the-middle placement only inside the retrieved-context block."""
def zigzag_documents(items):
    """Stably rank selected ScoredDocument items by descending score.

    Output sorted ranks1,3,5,... followed by reversed ranks2,4,6,... .
    Best/second-best occupy opposite ends for N>=2. Preserve every item once,
    including duplicate text and equal scores in original input rank order.
    Do not mutate input, compare component text/metadata, allocate budgets,
    reorder system/query, or claim measured model-attention improvement.
    """
    raise NotImplementedError
