"""Fixed-design context peaks and declared summary-fact conservation."""
from .models import boundary_value
from .service import prepare_design
from .usage import sum_branch_usage

def role_peak_context(receipts):
    """Return per-role max(input+output) across its measured calls, not a sum."""
    peaks={}
    for receipt in receipts:
        usage=receipt.usage
        peaks[usage.role]=max(peaks.get(usage.role,0),usage.input_tokens+usage.output_tokens)
    return peaks

def boundary_fact_losses(boundaries):
    """Return every boundary's missing required ids in declared required order.

    before/forwarded/required are explicit finite annotations. Only required
    facts omitted from that summary are lost; optional omissions do not block.
    This does not verify the semantic truth or completeness of model text.
    """
    rows=[]
    for boundary in boundaries:
        boundary_value(boundary);forwarded=set(boundary.forwarded)
        lost=tuple(dict.fromkeys(key for key in boundary.required if key not in forwarded))
        rows.append({"boundary":boundary.key,"role":boundary.role,"lost":lost})
    return rows

def compare_fixed_design(single,multi):
    """Compare two supplied designs; never choose an agent count or re-plan.

    Each context ceiling includes input and fixture output. Multi is preferred
    only when it fits all its roles, loses no required boundary facts, and
    either the single design is infeasible/lossy or multi uses fewer tokens.
    Otherwise retain the single design. Report costs even when multi is blocked;
    token preference is a declared local rule, not evidence of answer quality.
    """
    def report(design):
        receipts=prepare_design(design)
        peaks=role_peak_context(receipts)
        over=tuple(role.name for role in design.roles if peaks.get(role.name,0)>role.context_limit)
        losses=boundary_fact_losses(design.boundaries)
        return {**sum_branch_usage([receipt.usage for receipt in receipts]),"peak_by_role":peaks,"over_limit":over,"losses":losses}
    left=report(single);right=report(multi)
    bad_left=bool(left["over_limit"]) or any(row["lost"] for row in left["losses"])
    bad_right=bool(right["over_limit"]) or any(row["lost"] for row in right["losses"])
    preferred=not bad_right and (bad_left or right["total_tokens"]<left["total_tokens"])
    return {"single":left,"multi":right,"delta_tokens":right["total_tokens"]-left["total_tokens"],"prefer_multi":bool(preferred)}
