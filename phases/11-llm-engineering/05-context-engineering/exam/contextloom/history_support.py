"""Given complete history accounting, deque operations and bounded rollup.

The source appends unbounded uncounted summaries. Here one deterministic
rolling summary is bounded to twelve words and all original exchange ids
are retained separately. This is bookkeeping, not semantic summarization.
"""
from collections import deque
from .models import Exchange
from .primitives import estimate_words, count_tokens

def render_exchange(exchange):
    return f"user: {exchange.user}\nassistant: {exchange.assistant}"

def exchange_words(exchange):
    return len(render_exchange(exchange).split())

class RollingSummary:
    def __init__(self):
        self.text = ""
        self.source_ids = []
    def add(self, exchange):
        self.source_ids.append(exchange.key)
        words = (self.text + " " + render_exchange(exchange)).split()
        self.text = "Summary: " + " ".join(words[-11:])

def history_buffer(exchanges, budget):
    if type(budget) is not int or budget < 0:
        raise ValueError("history budget must be nonnegative")
    rows = list(exchanges)
    seen = set()
    for row in rows:
        if not isinstance(row, Exchange) or not isinstance(row.key, str) or not row.key or row.key in seen:
            raise ValueError("history requires unique complete exchange ids")
        seen.add(row.key)
        if not isinstance(row.user, str) or not isinstance(row.assistant, str):
            raise ValueError("history content must be text")
    return deque(rows)

def complete_tokens(live_words, retained_count, summary):
    """Apply source estimator once to complete rendered word total.

    Each section header has two words; every retained role label is already
    included in exchange_words. No sum of individually rounded token counts.
    """
    words = live_words + (2 if retained_count else 0)
    if summary.text:
        words += 2 + len(summary.text.split())
    return estimate_words(words)

def finalize_history(buffer, summary, budget):
    """Given final render and infeasible-budget rejection; min2pairs retained."""
    parts = []
    if summary.text:
        parts.extend(["[Conversation Summary]", summary.text])
    if buffer:
        parts.append("[Recent Conversation]")
        parts.extend(render_exchange(row) for row in buffer)
    text = "\n".join(parts)
    tokens = count_tokens(text)
    if tokens > budget:
        raise ValueError("retained exchanges and summary cannot fit history budget")
    return {"text": text, "tokens": tokens, "retained": tuple(buffer),
            "summary": summary.text, "summary_sources": tuple(summary.source_ids)}
