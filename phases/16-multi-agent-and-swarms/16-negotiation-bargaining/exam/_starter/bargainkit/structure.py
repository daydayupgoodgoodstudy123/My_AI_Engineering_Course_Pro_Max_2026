"""Private nested all-issue and all-party joint feasibility with explicit first blocking attribution."""
from decimal import Decimal
from .models import Blocker,PrivateGroupAudit
from .exact import add,multiply
def audit_offer_tree(occurrence,catalog):
    """Evaluate each own/child term, all required issues and every private joint minimum, preserving ordered layer reports."""
    raise NotImplementedError
