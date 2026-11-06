"""Finite Prometheus text snapshots after completed local usage batches."""
from decimal import Decimal
from .contracts import validate_usage,decimal_cost,add_cost
PRELUDE=("# HELP quota_requests_total Observed admission decisions.\n# TYPE quota_requests_total counter\n"
         "# HELP quota_model_calls_total Admitted completed model calls.\n# TYPE quota_model_calls_total counter\n"
         "# HELP quota_tokens_total Billed tokens by category.\n# TYPE quota_tokens_total counter\n"
         "# HELP quota_cost_dollars_total Exact local fixture cost.\n# TYPE quota_cost_dollars_total counter\n")
def escape_label(value):
    """Escape backslash, double quote and LF for a Prometheus quoted label value."""
    raise NotImplementedError
def accumulate_batch(totals,batch):
    """Update cumulative per-user/model series from a completed batch, including empty.

    Each record increments its admission outcome. Only admitted completions add
    model calls, disjoint billed token categories and exact cost. The existing
    totals mapping retains previous batches and identities.
    """
    raise NotImplementedError

def render_snapshot(totals):
    """Render every cumulative series as one complete finite Prometheus text snapshot.

    Use the supplied HELP/TYPE prelude. Retain user/model identity with escaped
    labels, outcome/category names, zero values and exact decimal costs.
    """
    raise NotImplementedError

async def export_batches(batches):
    """Given pull-through driver: one completed batch updates then publishes one snapshot.

    This supplied driver owns async source consumption. Candidate functions own
    domain accumulation and complete Prometheus series rendering; there is no
    endpoint, live provider or additional stream lifecycle to implement.
    """
    totals={}
    async for batch in batches:
        accumulate_batch(totals,batch)
        yield render_snapshot(totals)
