"""Complete original-core evidence binding and sealed P3 decisions; no Edge carries independent voting mass."""
from .models import SealedCore
from .scalar_support import positions_from_inspection
from . import center
def seal_core(core_uid,epoch,inspection,tie_policy,radius,threshold,truth=None):
    """Actually consume corrected P1/P2 inspection and all three candidate P3 operations."""
    positions=positions_from_inspection(inspection)
    interval=center.weighted_median_interval(positions)
    chosen=center.choose_interval_center(interval,tie_policy)
    decision=center.audit_center_support(positions,chosen,radius,threshold,truth)
    return SealedCore(core_uid,epoch,tuple(p.uid for p in positions),decision)
class CoreCatalog:
    """Complete globally unique core lookup, original proposal admission and ack-reference validation."""
    def __init__(self,sealed):
        self._cores={item.core_uid:item for item in sealed}
        if len(self._cores)!=len(sealed):raise ValueError('unique core IDs required')
        for item in sealed:
            if len(set(item.proposal_uids))!=len(item.proposal_uids):raise ValueError('unique original core evidence required')
    def core(self,uid):return self._cores[uid]
    def references_valid(self,ack):
        core=self._cores.get(ack.core_uid)
        return core is not None and bool(ack.references)and set(ack.references)<=set(core.proposal_uids)
    def validate_tree(self,node):
        cores=set();edges=set()
        def walk(current):
            if current.core_uid in cores or current.core_uid not in self._cores:raise ValueError('finite unique declared core tree required')
            cores.add(current.core_uid)
            for edge in current.edges:
                if edge.edge_uid in edges:raise ValueError('unique edge IDs required')
                edges.add(edge.edge_uid)
            for child in current.children:walk(child)
        walk(node)
