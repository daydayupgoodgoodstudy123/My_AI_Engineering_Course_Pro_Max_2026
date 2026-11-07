"""Broad-then-narrow task dossier; no scheduler or worker execution."""
from .tree_support import validate_shape

def audit_work_tree(root):
    """Return ordered leaf provenance and findings for the finite task tree.

    Every child scope is a proper subset of its parent's scope. Each node's
    budget covers ALL descendant task nodes, not only its immediate children or
    longest path. A leaf artifact must keep that leaf's question id and scope.
    Internal unresolved claim ids remain explicit. The input is not modified.
    """
    validate_shape(root);leaves=[];findings=[];unresolved=[]
    def visit(node,path):
        here=path+(node['question_id'],);descendants=0
        for child in node['children']:
            if not set(child['scope'])<set(node['scope']):findings.append(('scope-not-narrower',here+(child['question_id'],)))
            descendants+=1+visit(child,here)
        if descendants>node['budget']:findings.append(('branch-budget',here))
        if node['children']:
            unresolved.append((here,tuple(node['unresolved'])))
        else:
            artifact=node['artifact']
            if artifact is None or artifact.question_id!=node['question_id'] or artifact.scope!=tuple(node['scope']):findings.append(('leaf-provenance',here))
            leaves.append({'path':here,'scope':tuple(node['scope']),'artifact':artifact})
        return descendants
    count=visit(root,())
    return {'leaves':leaves,'unresolved':unresolved,'findings':findings,'descendants':count}
