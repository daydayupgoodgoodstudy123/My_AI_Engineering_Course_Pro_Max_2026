"""Compress oldest whole exchanges; retain the latest two complete pairs."""
from collections import deque
from .history_support import history_buffer, RollingSummary, exchange_words, complete_tokens, finalize_history

def compress_history(exchanges, budget):
    """Return complete bounded history, with every summary update included.

    Use supplied deque/rollup/render/accounting helpers. While over budget,
    summarize and remove the oldest complete exchange, stopping at two pairs.
    The given finalizer rejects if these compulsory recent pairs plus summary
    still cannot fit. Include role/header/summary words and apply the estimator
    once to the rendered total. Do not skip any rollup or provenance update.
    """
    buffer = history_buffer(exchanges, budget)
    summary = RollingSummary()
    counts = deque(exchange_words(row) for row in buffer)
    live_words = sum(counts)
    while complete_tokens(live_words, len(buffer), summary) > budget and len(buffer) > 2:
        removed = buffer.popleft()
        live_words -= counts.popleft()
        summary.add(removed)
    return finalize_history(buffer, summary, budget)
