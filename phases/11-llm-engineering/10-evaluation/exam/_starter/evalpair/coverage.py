"""Baseline/variant paired coverage through the declared evaluation hierarchy."""
from .contracts import validate_suite
def coverage_tree(suite,baseline,variant,comparison):
    """Report every declared category/case/criterion in supplied order.

    A pair requires judged baseline AND variant for the SAME case_id/criterion.
    States are paired/baseline_only/variant_only/neither. Paths use typed category,
    case and criterion indexes from the declared input. Category evidence is the
    original supplied comparison.categories value at ('categories', category_name),
    including negative evidence and absent evidence None. No resampling, decision
    gate, score averaging or hierarchy weights are performed here.
    """
    raise NotImplementedError
