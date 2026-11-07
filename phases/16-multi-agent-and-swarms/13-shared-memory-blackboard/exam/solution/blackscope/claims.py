"""Build hierarchical certificates from supplied occurrences and verified leaf decisions."""
from .models import SupportCertificate
from .claims_support import leaf_support
def build_support(occurrence,decisions):
    """Compose required coverage and distinct external snapshots at every derived layer.

    A wrapper's announced source is a label, never another independent external source.
    Missing and cycle locations are already marked by the complete supplied catalog.
    """
    if occurrence.obstacle is not None:
        return SupportCertificate(occurrence.path,frozenset(),frozenset(),frozenset(),frozenset((occurrence.obstacle,)))
    if occurrence.claim.entry_id is not None:
        return SupportCertificate(occurrence.path,*leaf_support(occurrence,decisions))
    children=tuple(build_support(child,decisions)for child in occurrence.children)
    required=frozenset().union(*(child.required for child in children))
    covered=frozenset().union(*(child.covered for child in children))
    sources=frozenset().union(*(child.sources for child in children))
    obstacles=frozenset().union(*(child.obstacles for child in children))
    return SupportCertificate(occurrence.path,required,covered,sources,obstacles,children)
