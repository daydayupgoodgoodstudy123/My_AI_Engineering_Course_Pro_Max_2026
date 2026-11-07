"""Structure an already observed decision path through the finite course tree."""
from .contracts import RULE_TREE,validate_decision
def structure_trace(decision):
    """Return nested observed guard nodes and the decisive true-leaf evidence.

    A guard node has rule_id/path/matched/evidence and one true or false child.
    Its path appends the rule ID; an edge appends 'true' or 'false'. The true leaf
    has path/framework/decisive_rule/reason/requirements. Retain false evaluations
    and complete operand evidence. Refuse gaps, extra evaluations, no true match,
    or a decisive rule/framework inconsistent with the supplied observed path.
    No Problem input, predicate evaluation or counterfactual search is available.
    """
    validate_decision(decision)
    def visit(node,index,path):
        if node is None or index>=len(decision.trace):raise ValueError('incomplete observed path')
        step=decision.trace[index]
        if step.rule_id!=node.rule_id:raise ValueError('observed path gap')
        here=path+(node.rule_id,)
        out={'rule_id':node.rule_id,'path':here,'matched':step.matched,'evidence':step.evidence}
        if step.matched:
            if index!=len(decision.trace)-1 or decision.decisive_rule!=node.rule_id or decision.framework!=node.framework:raise ValueError('decisive path mismatch')
            out['true']={'path':here+('true',),'framework':decision.framework,'decisive_rule':decision.decisive_rule,'reason':decision.reason,'requirements':decision.requirements}
        else:out['false']=visit(node.otherwise,index+1,here+('false',))
        return out
    return visit(RULE_TREE,0,())
