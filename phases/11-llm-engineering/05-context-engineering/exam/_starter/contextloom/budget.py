"""Budget allocation by priority; final rendering order is a separate concern."""
from .primitives import count_tokens, fit_text, window_values

class ContextBudget:
    def __init__(self, max_tokens, generation_reserve):
        self.max_tokens = max_tokens
        self.generation_reserve = generation_reserve
        self.available = window_values(max_tokens, generation_reserve)
        self.contents = {}
        self.allocations = {}

    def allocate(self, key, text, cap=None):
        """Replace one live slot while respecting the final live-state budget.

        Preserve slot insertion order. Trim only to the explicit cap and
        currently free capacity. Token counts are component estimates.
        """
        used = sum(self.allocations.values())
        available = self.available - used
        limit = available if cap is None else min(available, cap)
        content = fit_text(text, limit)
        self.contents[key] = content
        self.allocations[key] = count_tokens(content)
        return content

    def report(self):
        used = sum(self.allocations.values())
        return {"contents": dict(self.contents), "allocations": dict(self.allocations), "used": used,
                "reserve": self.generation_reserve, "remaining": self.available - used,
                "selected": [key for key, text in self.contents.items() if text]}

def assemble_priority(system, query, optional, max_tokens, reserve):
    """Preserve full compulsory system/query before optional slots compete.

    Fixed output layout is system, optional slots in supplied order, query.
    Reject an infeasible compulsory allocation, using the supplied estimator.
    This entry point never implements lost-in-the-middle reordering.
    """
    budget = ContextBudget(max_tokens, reserve)
    if count_tokens(system) + count_tokens(query) > budget.available:
        raise ValueError("compulsory context exceeds available window")
    budget.allocate("system", system)
    for key, text in optional:
        if key in ("system", "query"):
            raise ValueError("optional slot uses compulsory key")
        budget.allocate(key, text)
    budget.allocate("query", query)
    report = budget.report()
    order = ["system"] + [key for key in budget.contents if key not in ("system", "query")] + ["query"]
    report["contents"] = {key: budget.contents[key] for key in order}
    report["selected"] = [key for key in order if budget.contents[key]]
    return report
