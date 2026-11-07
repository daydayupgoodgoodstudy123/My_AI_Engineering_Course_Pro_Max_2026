"""Candidate nested ant-path continuity, exact visited-edge credit and shared once-per-epoch trail updates."""
from .models import Trail,TrailState,PathAudit,ExpeditionAudit,TrailReport
def audit_expeditions(roots,catalog,state,rho,floor=0.):
    """Build every layer's path audit; deposit actual sealed amounts on valid visited trails with per-traversal multiplicity and shared epoch state."""
    raise NotImplementedError
