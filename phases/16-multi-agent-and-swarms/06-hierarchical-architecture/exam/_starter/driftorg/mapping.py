"""Finite explicit obligation mappings, not inferred meaning from summary prose."""
from .models import Status
from .primitives import fold_descendant_ids

def compose_obligation_mappings(dossier):
    """Trace every original obligation through declared parent/child bindings.

    Record routes and leaf evidence. Missing managers, department mismatches,
    undeclared local obligation ids and unmapped obligations are separate issues.
    No structural leaf id alone can satisfy an original semantic obligation.
    """
    raise NotImplementedError

def first_divergence_path(composed):
    """Choose each obligation's earliest issue by path length, then encounter order."""
    raise NotImplementedError

def audit_decomposition(dossier,canary):
    """Audit explicit obligations and compare separately attributed canary evidence.

    Canary must name the unchanged original question; unsupported obligation ids
    are errors. Unknown leaf evidence remains unknown, not a negative answer.
    A known canary/hierarchy disagreement is labelled canary-mismatch while both
    states remain explicit. Structural provenance comes from repaired P1 only.
    """
    raise NotImplementedError
