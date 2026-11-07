"""Complete UID resolution, shared occurrence expansion, path cycles and leaf-decision lookup."""
from .models import ExpandedClaim
class ClaimCatalog:
    """Claim IDs are globally unique. Exactly one of entry_id or nonempty children is declared."""
    def __init__(self,claims):
        self._claims={claim.claim_id:claim for claim in claims}
        if len(self._claims)!=len(claims):raise ValueError('unique claim IDs required')
        for claim in claims:
            if (claim.entry_id is not None)==bool(claim.children):raise ValueError('leaf or nonempty derived claim required')
    def expand(self,root):
        def walk(uid,path,ancestors):
            here=path+(uid,);claim=self._claims.get(uid)
            if claim is None:return ExpandedClaim(None,here,obstacle='missing:'+ '/'.join(here))
            if uid in ancestors:return ExpandedClaim(claim,here,obstacle='cycle:'+ '/'.join(here))
            return ExpandedClaim(claim,here,tuple(walk(child,here,ancestors+(uid,))for child in claim.children))
        return walk(root,(),())
def decision_index(decisions):
    """Use already-correct P3 decisions; the certificate does not repeat the finding join."""
    result={decision.entry.entry_id:decision for decision in decisions}
    if len(result)!=len(decisions):raise ValueError('one decision per immutable entry required')
    return result
def leaf_support(occurrence,decisions):
    entry_id=occurrence.claim.entry_id;decision=decisions.get(entry_id)
    if decision is None or decision.status!='VERIFIED' or decision.entry.source is None:
        return frozenset((entry_id,)),frozenset(),frozenset(),frozenset(('unsupported:'+ '/'.join(occurrence.path),))
    return frozenset((entry_id,)),frozenset((entry_id,)),frozenset((decision.entry.source,)),frozenset()
