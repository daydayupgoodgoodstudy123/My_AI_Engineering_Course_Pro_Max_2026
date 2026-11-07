"""Nested file/span validation and hierarchical reports over resolved review memberships."""
from .models import Finding,GroupAudit,ReviewAudit
from .review_support import review_leaf,all_group_findings
def audit_review(artifact):
    """Build a nested domain report over the supplied global catalog.

    Declared file line counts and issue/group coordinates are non-bool integers.
    A child group stays in its parent's file and declared span. Each issue stays
    within its own group's file/span and the declared file's physical line range.
    Shared issue identities and all membership paths are fully resolved Given.
    """
    raise NotImplementedError
