"""Complete global issue/party/group bindings, finite tree expansion and public blocker projection, not private evaluation."""
from .models import OfferOccurrence
class OfferCatalog:
    def __init__(self,issues,parties,groups):
        self.issues=tuple(issues);self.parties=tuple(parties);self._groups={g.uid:g for g in groups};self._rules={p.uid:{r.issue_id:r for r in p.rules}for p in self.parties}
        if len(set(self.issues))!=len(self.issues)or len(self._rules)!=len(self.parties)or len(self._groups)!=len(groups):raise ValueError('globally unique declarations required')
        if any(len(self._rules[p.uid])!=len(p.rules)or set(self._rules[p.uid])!=set(self.issues)for p in self.parties):raise ValueError('complete private utility coefficient vectors required')
        if any(not r.unit_value.is_finite()or not r.cash_weight.is_finite()for p in self.parties for r in p.rules):raise ValueError('finite private utility coefficient vectors required')
    def rule(self,party,issue):return self._rules[party][issue]
    def expand(self,root):
        seen=set();terms=set()
        def visit(uid,path):
            if uid in seen:raise ValueError('finite unique ordered group tree required')
            seen.add(uid);group=self._groups[uid];here=path+(uid,)
            if len(set(group.required_issues))!=len(group.required_issues)or not set(group.required_issues)<=set(self.issues):raise ValueError('declared issue coverage required')
            if len({p for p,_ in group.minimum_utilities})!=len(group.minimum_utilities)or {p for p,_ in group.minimum_utilities}!=set(self._rules)or any(not m.is_finite()for _,m in group.minimum_utilities):raise ValueError('complete private group minimum vector required')
            for t in group.terms:
                if t.uid in terms or t.issue_id not in self.issues:raise ValueError('unique term and declared issue binding required')
                terms.add(t.uid)
                if any(not x.is_finite()for x in(t.quantity,t.price,t.minimum_quantity,t.maximum_quantity))or min(t.quantity,t.price,t.minimum_quantity)<0 or t.maximum_quantity<t.minimum_quantity:raise ValueError('finite declared nonnegative quantity intervals and prices required')
            return OfferOccurrence(group,here,tuple(visit(child,here)for child in group.children))
        return visit(root,())
def public_blocker(audit):
    b=audit.first_blocker
    return None if b is None else{'path':list(b.path),'term_uid':b.term_uid,'category':b.category}
