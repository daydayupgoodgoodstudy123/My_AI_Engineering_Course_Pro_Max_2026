"""Construct every local Core/Edge audit layer from already-sealed independent core decisions."""
from .models import CoreAudit,EdgeAudit
def audit_core_tree(node,catalog):
    """Check each core snapshot and each own edge's parent/epoch/value, retaining ordered nested reports.

    Original evidence IDs, reference binding and admission are complete supplied dependencies.
    Edges follow an accepted core; their echoes never create another vote or truth verdict.
    """
    catalog.validate_tree(node)
    def visit(current,path):
        sealed=catalog.core(current.core_uid);decision=sealed.decision;findings=[];edge_reports=[]
        if current.epoch!=sealed.epoch:findings.append('core-epoch')
        if current.claimed_center!=decision.center or current.unit!=decision.unit:findings.append('core-value')
        if not decision.accepted:findings.append('core-not-accepted')
        for edge in current.edges:
            own=[]
            if edge.core_uid!=current.core_uid:own.append('edge-parent')
            if edge.epoch!=sealed.epoch:own.append('edge-epoch')
            if edge.center!=decision.center or edge.unit!=decision.unit:own.append('edge-value')
            if not catalog.references_valid(edge):own.append('edge-reference')
            if not decision.accepted:own.append('edge-before-core')
            edge_reports.append(EdgeAudit(edge.edge_uid,tuple(own)))
        here=path+(current.core_uid,)
        children=tuple(visit(child,here)for child in current.children)
        return CoreAudit(here,sealed,tuple(findings),tuple(edge_reports),children)
    return visit(node,())
