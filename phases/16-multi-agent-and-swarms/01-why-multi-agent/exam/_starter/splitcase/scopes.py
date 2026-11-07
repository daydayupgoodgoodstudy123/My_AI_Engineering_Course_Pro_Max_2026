"""Nested shared and branch-local private inputs for a fixed specialist design."""
from .models import Leaf,fact_map
from .scope_support import validate_scopes,leaf_facts

def context_scope_report(root,roles):
    """Return leaves in child order with full paths, visible ids and required losses.

    Shared facts descend; private notes descend only within their branch and
    are projected by the supplied role helper at each leaf. Siblings cannot
    inherit one another's local facts or notes. Inputs remain unchanged.
    """
    raise NotImplementedError
