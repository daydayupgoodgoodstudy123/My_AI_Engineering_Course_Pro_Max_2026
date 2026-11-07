"""Broad-then-narrow task dossier; no scheduler or worker execution."""
from .tree_support import validate_shape

def audit_work_tree(root):
    """Return ordered leaf provenance and findings for the finite task tree.

    Every child scope is a proper subset of its parent's scope. Each node's
    budget covers ALL descendant task nodes, not only its immediate children or
    longest path. A leaf artifact must keep that leaf's question id and scope.
    Internal unresolved claim ids remain explicit. The input is not modified.
    """
    raise NotImplementedError
