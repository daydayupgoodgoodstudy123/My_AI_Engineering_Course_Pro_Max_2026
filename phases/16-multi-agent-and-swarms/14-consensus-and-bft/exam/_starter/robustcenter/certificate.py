"""Construct every local Core/Edge audit layer from already-sealed independent core decisions."""
from .models import CoreAudit,EdgeAudit
def audit_core_tree(node,catalog):
    """Check each core snapshot and each own edge's parent/epoch/value, retaining ordered nested reports.

    Original evidence IDs, reference binding and admission are complete supplied dependencies.
    Edges follow an accepted core; their echoes never create another vote or truth verdict.
    """
    raise NotImplementedError
