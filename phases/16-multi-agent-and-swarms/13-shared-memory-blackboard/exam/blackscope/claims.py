"""Build hierarchical certificates from supplied occurrences and verified leaf decisions."""
from .models import SupportCertificate
from .claims_support import leaf_support
def build_support(occurrence,decisions):
    """Compose required coverage and distinct external snapshots at every derived layer.

    A wrapper's announced source is a label, never another independent external source.
    Missing and cycle locations are already marked by the complete supplied catalog.
    """
    raise NotImplementedError
