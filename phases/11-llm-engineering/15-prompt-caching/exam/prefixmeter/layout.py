"""Single legal exact-prefix breakpoint over an explicit nested prompt section layout."""
from .contracts import PrefixPlan,validate_layout
def plan_prefix(root,variants):
    """Preserve leaf order/information and pick the deepest common legal section boundary.

    Section tokens are supplied literal token fixtures, not real model tokenization.
    Parent volatile status propagates to descendants. No cache breakpoint may
    follow the first volatile leaf. Variants map every full leaf path to a supplied
    token tuple; compare exact ordered token spellings without Unicode normalization
    or tool reordering. Among leaf ends before volatility and within the actual
    shared exact token prefix, choose the deepest/latest positive complete leaf boundary.
    Return all original variants, preorder leaf paths, selected prefix/breakpoint,
    first volatile path and true common-token count. Empty variants use root token
    fixtures as the single observation. Tree shape/cycle/variant validation is given.
    This explicit local Section hierarchy is an Exercise3 teaching adaptation.
    """
    raise NotImplementedError
