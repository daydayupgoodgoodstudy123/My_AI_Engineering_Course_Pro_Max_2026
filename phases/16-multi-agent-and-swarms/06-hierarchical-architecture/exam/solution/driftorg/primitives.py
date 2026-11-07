"""Branch/leaf producers, original-question canary and structural provenance only."""
from .models import Branch,Leaf,Status
from .graph_support import postorder

def pack_branch(label,branch_members):
    """A missing manager is MISSING; a present empty manager is UNKNOWN.

    VERIFIED means the available branch has sealed leaf evidence, not that
    the evidence proves a positive factual conclusion.
    """
    if label not in branch_members:return Branch(label,Status.MISSING,())
    members=tuple(branch_members[label])
    return Branch(label,Status.VERIFIED if members else Status.UNKNOWN,members)

def pack_leaf(observation):
    """Keep the worker's declared epistemic status and original evidence fields."""
    state=Status(observation['status'])
    return Leaf(observation['leaf_id'],observation['worker'],observation['obligation'],observation['department'],observation['question'],observation['answer'],state,tuple(observation['citation_ids']))

def canary_input(original_question,branch_label):
    """A canary always receives the unchanged original user question."""
    return original_question

def fold_descendant_ids(nodes,leaves,root_id):
    """Return each reachable manager's unique structural leaf and citation ids.

    Leaf references are evidence links, not extra worker executions. The result
    contains no original-obligation mappings or semantic drift decisions.
    """
    result={}
    for ident in postorder(nodes,root_id):
        node=nodes[ident];leaf_ids=set(node.leaf_ids);citations=set()
        for leaf_id in node.leaf_ids:citations.update(leaves[leaf_id].citation_ids)
        for child in node.children:
            leaf_ids.update(result[child][0]);citations.update(result[child][1])
        result[ident]=(tuple(sorted(leaf_ids)),tuple(sorted(citations)))
    return result
