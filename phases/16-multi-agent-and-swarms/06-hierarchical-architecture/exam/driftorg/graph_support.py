"""GIVEN iterative finite DAG shape, shared citation and ancestor-cycle handling."""
def postorder(nodes,root_id):
    done=set();active=set();order=[];stack=[(root_id,False)]
    while stack:
        ident,exit=stack.pop()
        if exit:active.remove(ident);done.add(ident);order.append(ident);continue
        if ident in active:raise ValueError('structural cycle')
        if ident in done:continue
        if ident not in nodes:raise ValueError('unknown structural node')
        active.add(ident);stack.append((ident,True))
        for child in reversed(nodes[ident].children):stack.append((child,False))
    return order
