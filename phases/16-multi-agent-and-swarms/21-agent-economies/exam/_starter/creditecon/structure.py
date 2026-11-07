"""Nested direct-child team games over deduplicated primitive membership unions."""
from fractions import Fraction
from .models import Primitive,TeamAudit,TeamSupport,UtilityReceipt
from .team_support import TeamCatalog,TeamValueOracle,local_game
from .allocation import shapley_exact,allocation_report

def audit_teams(catalog,primitive_oracle):
    """Build each nested team game, allocate direct children and explain each actual marginal's primitive support."""
    raise NotImplementedError('Complete the declared domain contract')
