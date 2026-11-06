"""Finite Prometheus text snapshots after completed local usage batches."""
from decimal import Decimal
from .contracts import validate_usage,decimal_cost,add_cost
PRELUDE=("# HELP quota_requests_total Observed admission decisions.\n# TYPE quota_requests_total counter\n"
         "# HELP quota_model_calls_total Admitted completed model calls.\n# TYPE quota_model_calls_total counter\n"
         "# HELP quota_tokens_total Billed tokens by category.\n# TYPE quota_tokens_total counter\n"
         "# HELP quota_cost_dollars_total Exact local fixture cost.\n# TYPE quota_cost_dollars_total counter\n")
def escape_label(value):
    """Escape backslash, double quote and LF for a Prometheus quoted label value."""
    return value.replace("\\","\\\\").replace("\n","\\n").replace('"','\\"')
def accumulate_batch(totals,batch):
    """Update cumulative per-user/model series from a completed batch, including empty.

    Each record increments its admission outcome. Only admitted completions add
    model calls, disjoint billed token categories and exact cost. The existing
    totals mapping retains previous batches and identities.
    """
    for row in batch:
        validate_usage(row)
        key=(row.user,row.model)
        values=totals.setdefault(key,[0,0,0,0,0,0,Decimal(0)])
        values[0 if row.admitted else 1]+=1
        if row.admitted:
            values[2]+=1;values[3]+=row.input_tokens-row.cached_input_tokens
            values[4]+=row.cached_input_tokens;values[5]+=row.output_tokens
            values[6]=add_cost(values[6],decimal_cost(row.cost_text))

def render_snapshot(totals):
    """Render every cumulative series as one complete finite Prometheus text snapshot.

    Use the supplied HELP/TYPE prelude. Retain user/model identity with escaped
    labels, outcome/category names, zero values and exact decimal costs.
    """
    lines=[PRELUDE]
    for (user,model),values in sorted(totals.items()):
        labels='user="'+escape_label(user)+'",model="'+escape_label(model)+'"'
        for outcome,count in (("allowed",values[0]),("denied",values[1])):
            lines.append('quota_requests_total{'+labels+',outcome="'+outcome+'"} '+str(count)+'\n')
        lines.append('quota_model_calls_total{'+labels+'} '+str(values[2])+'\n')
        for kind,count in zip(("uncached_input","cached_input","output"),values[3:6]):
            lines.append('quota_tokens_total{'+labels+',kind="'+kind+'"} '+str(count)+'\n')
        lines.append('quota_cost_dollars_total{'+labels+'} '+format(values[6],'f')+'\n')
    return ''.join(lines)

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
