"""Fixed-design context peaks and declared summary-fact conservation."""
from .models import boundary_value
from .service import prepare_design
from .usage import sum_branch_usage

def role_peak_context(receipts):
    """Return per-role max(input+output) across its measured calls, not a sum."""
    raise NotImplementedError

def boundary_fact_losses(boundaries):
    """Return every boundary's missing required ids in declared required order.

    before/forwarded/required are explicit finite annotations. Only required
    facts omitted from that summary are lost; optional omissions do not block.
    This does not verify the semantic truth or completeness of model text.
    """
    raise NotImplementedError

def compare_fixed_design(single,multi):
    """Compare two supplied designs; never choose an agent count or re-plan.

    Each context ceiling includes input and fixture output. Multi is preferred
    only when it fits all its roles, loses no required boundary facts, and
    either the single design is infeasible/lossy or multi uses fewer tokens.
    Otherwise retain the single design. Report costs even when multi is blocked;
    token preference is a declared local rule, not evidence of answer quality.
    """
    raise NotImplementedError
