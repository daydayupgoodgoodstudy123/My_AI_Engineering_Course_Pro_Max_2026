"""Private nested all-issue and all-party joint feasibility with explicit first blocking attribution."""
from decimal import Decimal
from .models import Blocker,PrivateGroupAudit
from .exact import add,multiply
def audit_offer_tree(occurrence,catalog):
    """Evaluate each own/child term, all required issues and every private joint minimum, preserving ordered layer reports."""
    children=tuple(audit_offer_tree(child,catalog)for child in occurrence.children)
    terms=occurrence.group.terms+tuple(term for child in children for term in child.terms)
    blocker=None
    for term in occurrence.group.terms:
        if not term.minimum_quantity<=term.quantity<=term.maximum_quantity:
            blocker=Blocker(occurrence.path,term.uid,'quantity');break
    if blocker is None:blocker=next((child.first_blocker for child in children if not child.feasible),None)
    covered={term.issue_id for term in terms}
    if blocker is None:
        missing=next((issue for issue in occurrence.group.required_issues if issue not in covered),None)
        if missing is not None:blocker=Blocker(occurrence.path,missing,'missing-issue')
    utilities=[]
    for party in catalog.parties:
        total=Decimal(0)
        for term in terms:
            rule=catalog.rule(party.uid,term.issue_id);total=add(total,add(multiply(rule.unit_value,term.quantity),multiply(rule.cash_weight,term.price)))
        utilities.append((party.uid,total))
    by_party=dict(utilities)
    if blocker is None:
        for party,minimum in occurrence.group.minimum_utilities:
            if by_party[party]<minimum:blocker=Blocker(occurrence.path,None,'joint-utility',party);break
    return PrivateGroupAudit(occurrence.path,terms,tuple(utilities),blocker is None,blocker,children,occurrence.group.minimum_utilities)
