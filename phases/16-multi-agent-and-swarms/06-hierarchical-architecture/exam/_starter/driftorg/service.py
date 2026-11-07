"""GIVEN correct branch evidence consumer and complete local inspection desk."""
from .models import Status
from .primitives import pack_branch,pack_leaf,canary_input,fold_descendant_ids

def typed_leaf_consumer(branch,leaves):
    """VERIFIED branch availability requires actual sealed leaf references.

    MISSING/UNKNOWN availability are valid typed outcomes, not positive or
    negative factual answers. This invariant applies to every branch input.
    """
    if branch.status==Status.VERIFIED and not branch.leaf_ids:raise ValueError('verified branch requires leaf evidence')
    return {'branch_id':branch.branch_id,'availability':branch.status.value,'leaves':tuple(leaves[i] for i in branch.leaf_ids)}

def inspect_branch(label,branch_members,leaves):
    return typed_leaf_consumer(pack_branch(label,branch_members),leaves)

class HierarchyDesk:
    def inspect(self,original_question,labels,branch_members,observations,nodes,root_id,canary):
        """Return complete branch, leaf, canary and structural observations.

        All inputs are finite local fixtures. No worker, LLM or network is run.
        There is no semantic original-obligation coverage solver in this desk.
        """
        leaves={row['leaf_id']:pack_leaf(row) for row in observations}
        branches=tuple(inspect_branch(label,branch_members,leaves) for label in labels)
        question=canary_input(original_question,labels[-1] if labels else '')
        canary_record=canary(question)
        folded=fold_descendant_ids(nodes,leaves,root_id)
        rows=tuple({'node_id':ident,'leaf_ids':pair[0],'citation_ids':pair[1],'leaf_count':len(pair[0]),'citation_count':len(pair[1])} for ident,pair in folded.items())
        return {'question':original_question,'branches':branches,'leaves':tuple(leaves.values()),'canary_question':question,'canary':canary_record,'structure':rows}
