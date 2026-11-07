"""Nested primitive ownership adapter; explicit stores are shared object references."""

def flatten_composition(root,stores,default_store,default_scheduler):
    """Bind leaves to scoped names and inherited store/scheduler; report path-local cycles.

    group nodes contain kind/name/children and optional store/scheduler overrides.
    agent nodes contain kind/name/agent. Store values name entries in the supplied
    registry; each leaf retains that exact SharedState object. A reused acyclic
    subtree is allowed under distinct scoped paths. The composition is not run.
    """
    leaves=[];active=set()
    def visit(node,path,store_id,scheduler):
        scope=path+(node['name'],)
        if id(node) in active:raise ValueError('composition cycle at '+repr(scope))
        active.add(id(node))
        try:
            selected_store=node.get('store',store_id);selected_scheduler=node.get('scheduler',scheduler)
            if selected_store not in stores:raise ValueError('unknown composition store at '+repr(scope))
            if selected_scheduler not in ('static','handoff','selector'):raise ValueError('unknown composition scheduler at '+repr(scope))
            if node['kind']=='agent':
                leaves.append({'scope':scope,'agent':node['agent'],'store_id':selected_store,'store':stores[selected_store],'scheduler':selected_scheduler})
            elif node['kind']=='group':
                names=[child['name'] for child in node['children']]
                if len(set(names))!=len(names):raise ValueError('duplicate composition child at '+repr(scope))
                for child in node['children']:visit(child,scope,selected_store,selected_scheduler)
            else:raise ValueError('composition kind at '+repr(scope))
        finally:active.remove(id(node))
    visit(root,(),default_store,default_scheduler)
    return leaves
