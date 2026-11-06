"""A finite assumption tree, not a natural-language inference engine."""
from __future__ import annotations
from .model import Assumption, risk_score
from .ranking import evidence_status

def validate_tree(node, known: set[str]) -> None:
    """Supplied schema: known leaf id or exactly one nonempty all/any child list."""
    if isinstance(node,str):
        if node not in known: raise ValueError('unknown assumption: '+node)
        return
    if not isinstance(node,dict) or len(node)!=1 or next(iter(node)) not in ('all','any'):
        raise ValueError('invalid assumption tree')
    children=next(iter(node.values()))
    if not isinstance(children,list) or not children: raise ValueError('empty assumption group')
    for child in children: validate_tree(child,known)

def assess_tree(node, items: list[Assumption]) -> dict:
    """Return status and next experiment for an explicit three-valued tree.
    ALL: any rejected => rejected; all supported => supported; otherwise open.
    ANY: any supported => supported; all rejected => rejected; otherwise open.
    Decided subtrees offer no experiments. When the root is open, select only open
    leaves in still-open subtrees, highest risk then smallest id. Duplicate leaves
    count once, no sibling state leaks, no mutation. Validate via supplied helper.
    Return {'status': ..., 'next': id-or-None}.
    """
    by_id={item.id:item for item in items}
    validate_tree(node,set(by_id))
    def walk(current):
        if isinstance(current,str):
            status=evidence_status(by_id[current])
            return status, {current} if status=='open' else set()
        op,children=next(iter(current.items()))
        results=[walk(child) for child in children]
        states=[s for s,_ in results]
        if op=='all':
            state='rejected' if 'rejected' in states else ('supported' if all(s=='supported' for s in states) else 'open')
        else:
            state='supported' if 'supported' in states else ('rejected' if all(s=='rejected' for s in states) else 'open')
        active=set().union(*(leaves for _,leaves in results)) if state=='open' else set()
        return state,active
    status,active=walk(node)
    chosen=min(active,key=lambda key:(-risk_score(by_id[key]),key)) if active else None
    return {'status':status,'next':chosen}
