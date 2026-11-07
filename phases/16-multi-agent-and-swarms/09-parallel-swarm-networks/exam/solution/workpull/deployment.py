"""Inherited topic scope, pool visibility and actual per-group completed work."""
from .deployment_support import GroupCatalog

def inspect_deployment(root,completions):
    """Apply ancestor topic intersections, keep sibling private pools out, and total actual completions.

    GroupCatalog supplies full worker/pool identity, ancestor tests and complete
    subtree membership. A worker's effective topics are its own subscriptions
    intersected with every declared group restriction. Own pools are visible;
    only shared ancestor pools may be inherited. Running/queued work is not done.
    """
    catalog=GroupCatalog(root);counts={uid:0 for path,g in catalog.groups.items()for uid in catalog.subtree_worker_uids(path)}
    for c in completions:
        if c.worker_uid not in counts:raise ValueError('completion worker outside deployment')
        counts[c.worker_uid]+=1
    def visit(group,path,inherited):
        scope=inherited
        if group.topics is not None:scope=set(group.topics)if scope is None else scope&set(group.topics)
        pools=tuple(uid for owner,uid,pool in catalog.all_pools()if owner==path or(pool.shared and catalog.is_ancestor(owner,path)))
        workers=[]
        for worker in group.workers:
            uid=catalog.full_worker_uid(path,worker.uid);topics=set(worker.topics)
            if scope is not None:topics&=scope
            workers.append((uid,tuple(t for t in worker.topics if t in topics),pools,counts[uid]))
        children=tuple(visit(child,path+(child.name,),scope)for child in group.children)
        total=sum(counts[uid]for uid in catalog.subtree_worker_uids(path))
        return{'path':path,'workers':tuple(workers),'completed':total,'children':children}
    return visit(root,(root.name,),None)
