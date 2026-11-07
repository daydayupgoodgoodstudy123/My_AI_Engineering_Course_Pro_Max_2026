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
    raise NotImplementedError('Part 5: structure only the observed nested decision path')
