"""Nested shared and branch-local private inputs for a fixed specialist design."""
from .models import Leaf,fact_map
from .scope_support import validate_scopes,leaf_facts

def context_scope_report(root,roles):
    """Return leaves in child order with full paths, visible ids and required losses.

    Shared facts descend; private notes descend only within their branch and
    are projected by the supplied role helper at each leaf. Siblings cannot
    inherit one another's local facts or notes. Inputs remain unchanged.
    """
    by_name={role.name:role for role in roles};validate_scopes(root,by_name);rows=[]
    def walk(node,path,shared,notes):
        path=path+(node.key,)
        if isinstance(node,Leaf):
            visible=fact_map(leaf_facts(by_name[node.role],shared,notes))
            rows.append({"path":path,"role":node.role,"visible":tuple(sorted(visible)),"missing":tuple(dict.fromkeys(key for key in node.required if key not in visible))})
            return
        shared=shared+node.shared_facts;notes=notes+node.private_notes
        for child in node.children:walk(child,path,shared,notes)
    walk(root,(),(),())
    return rows
