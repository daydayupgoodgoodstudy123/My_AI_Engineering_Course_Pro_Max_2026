"""Nested SOP role I/O ownership and declared-output audit, not a role/tool selector."""
from .sop_support import SOPCatalog,ROLE_INPUTS,ROLE_OUTPUT

def audit_sop(root,records):
    """Audit typed producer/consumer ports at every stage and expose only declared output.

    Complete catalog resolution and bundle revision/link validation are supplied.
    Candidate work is required role inputs, real output producers/kinds and
    export boundaries at every nested stage. Full record handles are explicit.
    """
    raise NotImplementedError
