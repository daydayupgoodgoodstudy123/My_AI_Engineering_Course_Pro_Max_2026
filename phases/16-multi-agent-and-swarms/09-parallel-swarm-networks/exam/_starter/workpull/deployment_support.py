"""Complete full-path resolver and immutable deployment subtree catalog."""
import json
class GroupCatalog:
    def __init__(self,root):
        self.groups={};self.worker_rows={};self.pool_rows=[];self.subtree={}
        def visit(group,path):
            if path in self.groups:raise ValueError('duplicate group path')
            self.groups[path]=group;uids=[]
            if len({w.uid for w in group.workers})!=len(group.workers)or len({p.pool_id for p in group.pools})!=len(group.pools):raise ValueError('duplicate group-local declaration')
            for worker in group.workers:
                uid=json.dumps(path+(worker.uid,),ensure_ascii=False,separators=(',',':'))
                self.worker_rows[(path,worker.uid)]=(uid,worker);uids.append(uid)
            for pool in group.pools:
                uid=json.dumps(path+(pool.pool_id,),ensure_ascii=False,separators=(',',':'))
                self.pool_rows.append((path,uid,pool))
            for child in group.children:uids.extend(visit(child,path+(child.name,)))
            self.subtree[path]=tuple(uids);return uids
        visit(root,(root.name,))
    def full_worker_uid(self,path,local):return self.worker_rows[(path,local)][0]
    def subtree_worker_uids(self,path):return self.subtree[path]
    def all_pools(self):return tuple(self.pool_rows)
    def is_ancestor(self,ancestor,path):return len(ancestor)<=len(path)and path[:len(ancestor)]==ancestor
